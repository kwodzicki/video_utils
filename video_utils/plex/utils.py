"""
Utilties for interfacing with Plex

While this package does very minimal direct interfacing with
Plex, these utilites support functionality in other parts of
this package.

"""

import logging
import os
import re
import pickle
from threading import Lock
from getpass import getpass

from plexapi.myplex import MyPlexAccount

from ..config import PLEXTOKEN
from ..videotagger import TMDb, TVDb, movie, episode

_tmdb = TMDb()
_tvdb = TVDb()

# Pattern for locating season/episode numbering
_se_pattern   = re.compile( r'[sS](\d{2,})[eE](\d{2,})' )
# Pattern for finding year
_year_pattern = re.compile( r'\(([0-9]{4})\)' )
# Pattern for finding date in DVR recording
_date_pattern = re.compile( r'\d{4}-\d{2}-\d{2} \d{2} \d{2} \d{2}')

def plex_file_info( in_file ):
    """ 
    Extract info from file path

    Extracts series, season/episode, and episode title information from
    a Plex DVR file path

    Arguments:
        in_file (str): Full path to the file to rename

    Keyword arguments:
        None.

    Returns:
        tuple: series name, season/episode or date, episode title, and file extension

    """

    log        = logging.getLogger(__name__)
    log.debug( 'Getting information from file name' )

    filebase   = os.path.basename( in_file )
    fname, ext = os.path.splitext( filebase )

    title     = None
    year      = None
    season_ep = None
    episode   = None

    # If the date pattern is found in the file name
    if _date_pattern.search( in_file ) is not None:
        log.warning( 'ISO date string found in file name; NO METADATA WILL BE DOWNLOADED!!!' )
        return title, year, season_ep, episode, ext

    # Split the file name on ' - '; not header information of function
    try:
        title, season_ep, episode = fname.split(' - ')
    except:
        title = fname
        log.warning('Error splitting file name, does it match Plex convention?')

    # Try to find year in series name
    year = _year_pattern.findall( title )
    if len(year) == 1:
        year  = int( year[0] )
        title = _year_pattern.sub('', title)# Remove year for series name
    else:
        year = None
    title = title.strip()

    try:
        season_ep = _se_pattern.findall( season_ep )[0]
    except:
        season_ep = None
    else:
        if len(season_ep) == 2:
            season_ep = [int(i) for i in season_ep]
        else:
            season_ep = None

    return title, year, season_ep, episode, ext

def plex_dvr_rename( in_file, hardlink = True ):
    """ 
    Function to rename Plex DVR files to match file nameing convetion.

    Arguments:
        in_file (str): Full path to the file to rename

    Keyword arguments:
        hardlink (bool): if set to True, will rename input file, else
            creates hard link to file. Default is to hard link

    Returns:
        Returns path to renamed file and tuple with parsed file information

    """

    log      = logging.getLogger(__name__)
    file_dir = os.path.dirname(  in_file )
    title, year, season_ep, episode, ext = plex_file_info( in_file )

    # If all the values are None, then date in file name
    if all( v is None for v in [title, year, season_ep, episode] ):
        return in_file, None

    if not season_ep:
        log.warning( 'Season/episode info NOT found; assuming movie...things may break' )
        # Search the movie database
        metadata = _tmdb.search(
            title    = title,
            year     = year,
            episode  = episode,
            seasonEp = season_ep
        )
    else:
        # Search the tv database
        metadata = _tvdb.search(
            title    = title,
            year     = year,
            episode  = episode,
            seasonEp = season_ep
        )

    # If NOT one (1) result from search
    if len(metadata) != 1:
        if len(metadata) > 1:
            log.error('More than one movie/Tv show found, skipping')
        elif len(metadata) == 0:
            log.error('No ID found!')
        metadata = None
        if season_ep:
            new = episode.get_basename( *season_ep, episode )
        else:
            new = movie.get_basename( title, year )
    else:
        metadata = metadata[0]
        new = metadata.get_basename()

    # Build new file path
    new = os.path.join( file_dir, new+ext )

    if hardlink:
        log.debug( 'Creating hard link to input file' )
        if os.path.exists( new ):
            try:
                os.remove( new )
            except:
                pass
        try:
            os.link( in_file, new )
        except Exception as err:
            log.warning( 'Error creating hard link : %s', err )
    else:
        log.debug( 'Renaming input file' )
        os.replace( in_file, new )
    return new, metadata

class DVRqueue( list ):
    """
    Sub-class of list that writes list to pickled file on changes

    This class acts to backup a list to file on disc so that DVR can
    remember where it was in the event of a restart/power off. Whenever
    the list is modified via the append, remove, etc methods, data are
    written to disc.

    """

    def __init__(self, file):
        super().__init__()
        self.__file = file
        self.__load_file()
        self.__lock = Lock()
        self.__log  = logging.getLogger(__name__)

    def append(self, val):
        with self.__lock:
            super().append(val)
            self.__save_file()

    def remove(self, val):
        with self.__lock:
            super().remove(val)
            self.__save_file()

    def pop(self, val):
        with self.__lock:
            pval = super().pop(val)
            self.__save_file()
        return pval

    def __save_file(self):
        if len(self) > 0:
            self.__log.debug( 'Storing list in : %s', self.__file )
            fdir = os.path.dirname(self.__file)
            if not os.path.isdir( fdir ):
                self.__log.debug( 'Making directory : %s', fdir )
                os.makedirs( fdir )
            with open(self.__file, 'wb') as fid:
                pickle.dump( list(self), fid )
        else:
            self.__log.debug( 'No data in list, removing file : %s', self.__file )
            os.remove( self.__file )

    def __load_file(self):
        if os.path.isfile(self.__file):
            try:
                with open(self.__file, 'rb') as fid:
                    self.extend( pickle.load(fid) )
            except:
                self.__log.error('Failed to load old queue. File corrupt?')
                os.remove( self.__file )

def get_token( login=False ):
    """
    Use plexapi to get token for server

    Keyword arguments:
        login (bool) : Authenticate to Plex and get token.
            If False (default), then just try to load existing
            token.

    Returns:
        If login/load success, then dict, else is None

    """


    if login:
        server  = input( "Enter Plex server name : " )
        user    = input( "Enter Plex user name : " )
        account = MyPlexAccount(
            user,
            getpass( "Enter Plex password : " ),
            code = input( "Enter Plex 2FA code : " )
        )
        plex = account.resource( server ).connect()

        info = {
            'baseurl' : plex._baseurl,
            'token'   : plex._token,
        }

        with open( PLEXTOKEN, 'wb' ) as oid:
            pickle.dump( info, oid )
        return info

    if os.path.isfile( PLEXTOKEN ):
        with open( PLEXTOKEN, 'rb' ) as iid:
            return pickle.load( iid )

    return None
