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
from difflib import SequenceMatcher
from threading import Lock
from getpass import getpass

from plexapi.myplex import MyPlexAccount

from ..config import PLEXTOKEN
from ..videotagger import (
    TMDb,
    TVDb,
    movie as _movie,
    episode as _episode,
)

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
        searcher = _tmdb.search
    else:
        # Will search the TVDb
        searcher = _tvdb.search

    # Search for aired order
    metadata_aired = searcher(
        title    = title,
        year     = year,
        episode  = episode,
        seasonEp = season_ep,
        dvdOrder = False,
    )
    # Search for DVD order
    metadata_dvd = searcher(
        title    = title,
        year     = year,
        episode  = episode,
        seasonEp = season_ep,
        dvdOrder = True,
    )

    new, metadata = compare_aired_dvd(
        title,
        year,
        season_ep,
        episode,
        metadata_aired,
        metadata_dvd,
    )

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

def compare_aired_dvd(title, year, season_ep, episode, aired, dvd):
    """
    Compare aired and dvd order

    Arguments:
        title (str) : Title of the series/movie
        year (int) : Release year of the series/movie
        season_ep (list) : The [season #, episode #] for the series/movie.
            Will be None is determined to be movie.
        episode (str) : Name of the episode of the series.
            Will be None is determined to be movie.
        aired (list) : List of aired-order results returned from search
        dvd (list) : List of dvd-order results fretruend from search

    """

    log = logging.getLogger(__name__)
    # If zero (0) or >1 result for both search, have a problem
    if len(aired) != 1 and len(dvd) != 1:
        log.error(
            'Zero OR >1 movie/TV show found for aired & DVD order, skipping'
        )
        new = (
            _episode.get_basename( *season_ep, episode )
            if season_ep else
            _movie.get_basename( title, year )
        )
        return new, None

    # If zero (0) or >1 for aired, we assume DVD
    if len(aired) != 1:
        log.info(
            'More than one movie/TV show found for aired order, assuming DVD'
        )
        metadata = dvd[0]
        return metadata.get_basename(), metadata

    # If zero (0) or >1 for dvd, we assume aired
    if len(dvd) != 1:
        log.info(
            'More than one movie/TV show found for DVD order, assuming aired'
        )
        metadata = aired[0]
        return metadata.get_basename(), metadata

    # If made here, we have one (1) result for both aired and dvd, so
    # check if season_ep si defined. If not, then assume movie and return
    if season_ep is None or episode is None: 
        return _movie.get_basename( title, year ), None

    # If made here, the matches for both aired and dvd order of episode
    # so we get episode title match for aired order title dvd order tile
    # versus the file name episode tiltle
    aired_ratio = SequenceMatcher(None, episode, aired[0].title).ratio()
    dvd_ratio   = SequenceMatcher(None, episode,   dvd[0].title).ratio()

    # If the similarity ratio for aired is >= DVD, assume aired order, else dvd
    if aired_ratio >= dvd_ratio:
        log.info('Assuming aired order based on episode file name')
        metadata = aired[0]
    else:    
        log.info('Assuming dvd order based on episode file name')
        metadata = dvd[0]

    return metadata.get_basename(), metadata

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
