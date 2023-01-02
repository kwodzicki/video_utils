import logging
import os, re, time, pickle
from threading import Lock
from getpass import getpass

from plexapi.myplex import MyPlexAccount

from ..config import PLEXTOKEN 
from ..videotagger import TMDb, TVDb, Movie, Episode

_tmdb = TMDb()
_tvdb = TVDb()

_se_pattern     = re.compile( r'[sS](\d{2,})[eE](\d{2,})' );                    # Pattern for locating season/episode numbering
_year_pattern   = re.compile( r'\(([0-9]{4})\)' );                                      # Pattern for finding yea
_date_pattern   = re.compile( r'\d{4}-\d{2}-\d{2} \d{2} \d{2} \d{2}') 

################################################################################
def plexFile_Info( in_file ):
  """ 
  Function to extract series, season/episode, and episode title information from a file path

  Arguments:
    in_file (str): Full path to the file to rename

  Keyword arguments:
    None.

  Returns:
    tuple: series name, season/episode or date, episode title, and file extension

  """

  log               = logging.getLogger(__name__);
  log.debug( 'Getting information from file name' );

  fileBase          = os.path.basename( in_file );                              # Get base name of input file
  fname, ext        = os.path.splitext( fileBase )

  title    = None
  year     = None
  seasonEp = None
  episode  = None

  if _date_pattern.search( in_file ) is not None:                               # If the date pattern is found in the file name
    log.warning( 'ISO date string found in file name; NO METADATA WILL BE DOWNLOADED!!!' )
    return title, year, seasonEp, episode, ext
    
  try:
    title, seasonEp, episode = fname.split(' - ');                                       # Split the file name on ' - '; not header information of function
  except:
    title = fname
    log.warning('Error splitting file name, does it match Plex convention?')

  year = _year_pattern.findall( title )                                               # Try to find year in series name
  if (len(year) == 1):                                                                # If year found
    year  = int( year[0] )                                                            # Set year
    title = _year_pattern.sub('', title)                                              # Remove year for series name
  else:
    year = None
  title = title.strip()                                                               # Strip any leading/trailing spaces from series title

  try:
    seasonEp = _se_pattern.findall( seasonEp )[0]
  except:
    seasonEp = None
  else:
    if (len(seasonEp) == 2):
      seasonEp = [int(i) for i in seasonEp] 
    else:
      seasonEp = None

  return title, year, seasonEp, episode, ext

################################################################################
def plexDVR_Rename( in_file, hardlink = True ):
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

  log     = logging.getLogger(__name__)
  fileDir = os.path.dirname(  in_file )
  title, year, seasonEp, episode, ext = plexFile_Info( in_file )

  if all( v is None for v in [title, year, seasonEp, episode] ):                # If all the values are None, then date in file name
    return in_file, None                                                        # Return the input file name AND None for metadata
 
  if not seasonEp:
    log.warning( 'Season/episode info NOT found; assuming movie...things may break' )
    metaData = _tmdb.search( title=title, year=year, episode=episode, seasonEp=seasonEp )    # Try to get IMDb id
  else:
    metaData = _tvdb.search( title=title, year=year, episode=episode, seasonEp=seasonEp )    # Try to get IMDb id

  if len(metaData) != 1:                                                                # If NOT one (1) result from search
    if len(metaData) > 1:                                                               # More than one
      log.error('More than one movie/Tv show found, skipping')
    elif len(metaData) == 0:                                                            # None
      log.error('No ID found!')
    metaData = None
    if seasonEp:
      new = Episode.getBasename( *seasonEp, episode )
    else:
      new = Movie.getBasename( title, year )
  else:
    metaData = metaData[0]
    new = metaData.getBasename() 

  new = os.path.join( fileDir, new+ext )                                                # Build new file path

  if hardlink:                                                                          # If hardlink set
    log.debug( 'Creating hard link to input file' )
    if os.path.exists( new ):                                                           # If new file exists
      try:                                                                              # Try to
        os.remove( new )                                                                # Delete it
      except:                                                                           # Fail silently
        pass                                                                            #
    try:                                                                                # Try to
      os.link( in_file, new )                                                           # Create hard link to file with new file name
    except Exception as err:                                                            # Catch exception
      log.warning( 'Error creating hard link : {}'.format(err) )                        # Log exception
  else:
    log.debug( 'Renaming input file' )
    os.replace( in_file, new )                                                          # Rename the file, overwiting destination if it exists
  return new, metaData

################################################################################
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
    self.__loadFile()
    self.__lock = Lock()
    self.__log  = logging.getLogger(__name__)

  def append(self, val):
    with self.__lock:
      super().append(val)
      self.__saveFile()

  def remove(self, val):
    with self.__lock:
      super().remove(val)
      self.__saveFile()

  def pop(self, val):
    with self.__lock:
      pval = super().pop(val)
      self.__saveFile()
    return pval

  def __saveFile(self):
    if (len(self) > 0):
      self.__log.debug( 'Storing list in : {}'.format( self.__file ) )
      fdir = os.path.dirname(self.__file) 
      if not os.path.isdir( fdir ):
        self.__log.debug( 'Making directory : {}'.format( fdir ) )
        os.makedirs( fdir )
      with open(self.__file, 'wb') as fid:
        pickle.dump( list(self), fid )
    else:
      self.__log.debug( 'No data in list, removing file : {}'.format( self.__file ) )
      os.remove( self.__file )

  def __loadFile(self):
    if os.path.isfile(self.__file):
      try:
        with open(self.__file, 'rb') as fid:
          self.extend( pickle.load(fid) )
      except:
        self.__log.error('Failed to load old queue. File corrupt?')
        os.remove( self.__file )

def getToken( login=False ):
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
            'token'   : plex._token
        }

        with open( PLEXTOKEN, 'wb' ) as oid:
            pickle.dump( info, oid )
        return info
    elif os.path.isfile( PLEXTOKEN ):
        with open( PLEXTOKEN, 'rb' ) as iid:
            return pickle.load( iid )

    return None
