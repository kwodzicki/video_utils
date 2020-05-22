import logging
import os, re, time, pickle
from threading import Lock
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL

from ..videotagger import TMDb, TVDb, Movie, Episode

_tmdb = TMDb()
_tvdb = TVDb()

_plex_server  = 'Plex Media Server';                                            # Name of the Plex server command
_plex_scanner = 'Plex Media Scanner';                                           # Name of the Plex scanner command

_pgrep          = ['pgrep', '-fa', _plex_server];                               # Command for getting information about runnin Plex Server, if any
_LD_pattern     = re.compile( r'(?:LD_LIBRARY_PATH=([\w\d\S]+))' );             # Pattern for finding LD_LIBRARY_PATH in command
_splt_pattern   = re.compile( r'(?:([^"\s]\S*)|"(.+?)")' );                     # Pattern for spliting output of the pgrep command
_se_pattern     = re.compile( r'[sS](\d{2,})[eE](\d{2,})' );                    # Pattern for locating season/episode numbering
_season_pattern = re.compile( r'(?:[sS](\d+)[eE]\d+)' );                        # Pattern for extracting season number from season/episode numbering      
_year_pattern   = re.compile( r'\(([0-9]{4})\)' );                                      # Pattern for finding yea

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

################################################################################
def getPlexMediaScanner( ):
  """ 
  Function to get full path to the Plex Media Scanner command

  Arguments:
    None.

  Keyword arguments:
    None.

  Returns:
    Returns list containing full path to Plex Media Scanner command

  """

  log = logging.getLogger(__name__);
  log.debug( "Trying to locate '{}'".format( _plex_scanner ) );

  cmd = myenv = None;
  try:
    lines = check_output( _pgrep, universal_newlines=True ).splitlines();
  except:
    log.critical( "Failed to find '{}' process".format(_plex_server) )
    return cmd, myenv

  myenv            = os.environ.copy()
  cmd_dir, lib_dir = parse_cmd_lib_dirs( lines )

  if cmd_dir is None:
    log.error( "'Plex Media Scanner' NOT found!!!" );
  else: 
    cmd = os.path.join( cmd_dir, _plex_scanner )
    while (not os.path.isfile(cmd)) and (cmd_dir != os.path.dirname(cmd_dir)):  # While the command has NOT been found and we are NOT at the top level directory
      cmd_dir = os.path.dirname( cmd_dir );                                     # Reset cmd_dir to directory name of command dir; i.e., go up one (1) directory
      cmd     = os.path.join( cmd_dir, _plex_scanner );                         # Set Plex Scanner path to new cmd_dir plus scanner name

    if not os.path.isfile( cmd ):                                               # If command is not found after while loop break
      cmd = None;                                                               # Set cmd to None
    else:                                                                       # Else, we found the command
      cmd = [cmd];                                                              # Set command to list containing only the command
      if lib_dir is not None:                                                   # Check if the lib_dir is NOT None
        log.debug( 'Setting LD_LIBRARY_PATH in environment' )
        if lib_dir[-1] == os.path.sep:                                          # If the last character of the library directory is a path separator
          lib_dir = lib_dir[:-1];                                               # Trim off the last value
        
        ld_path = myenv.pop( 'LD_LIBRARY_PATH', False)
        if ld_path:                                                             # If LD_LIBRARY_PATH already in environment
          if (lib_dir not in ld_path):                                          # If the library directory is NOT in the LD_LIBRARY_PATH variable
            lib_dir = '{}:{}'.format( ld_path, lib_dir );                       # Update the lib_dir to be the old LD_LIBRARY_PATH with the new path appended
          else:                                                                 # Else
            lib_dir = ld_path;                                                  # Set lib_dir to the current LD_LIBRARY_PATH
        myenv['LD_LIBRARY_PATH'] = lib_dir;                                     # Add/update environment variable
  
  log.debug( 'Plex command: {}'.format( cmd ) )
  return cmd, myenv 

################################################################################
def getPlexLibraries( cmd, env = None ):
  """ 
  Function to get list of plex libraries from the Plex Media Scanner CLI.

  Arguments:
    cmd (list): Full path to the Plex Media Scanner CLI (list, 1-element)

  Keyword arguments:
    env (dict): Environment for running Plex Media Scanner CLI. Default is os.environ.

  Returns:
    dict: Plex Libraries where key is library name and value is library number.

  """

  log      = logging.getLogger(__name__)                                        # Get logger
  plexLibs = {}                                                                 # Initialize plexLibs to empty dictionary
  if (os.environ.get('USER', '').upper() != 'PLEX'):
    log.error("Not running as user 'plex'; current user : {}. Could NOT get Plex Libraries".format(os.environ.get('USER', '')))
    return plexLibs

  if env is None: env = os.environ
  cmd      = cmd + ['--list']                                                   # Set cmd
  kwargs   = {'universal_newlines' : True, 'env' : env}                         # Set keyword arguments for call to check_output() function
  output   = None
  try:                                                                          # Try to
    output = check_output( ['stdbuf', '-oL', '-eL'] + cmd, **kwargs )           # Get the list
  except:                                                                       # On exception
    log.debug("Failed to get library listing with 'stdbuf', trying without")    # Log debug info

  if not output:                                                                # If plexLibs is None, or empty string
    try:                                                                        # Try to 
      output = check_output( cmd, **kwargs )                                    # Try to get list from the scanner
    except:                                                                     # On exception
      log.debug( 'Exception while running command' )                            # Log debug info

  if not output:                                                                # If none or empty string was returned
    log.debug( 'Failed to get listing of sections!' )                           # Log debug information
  else:                                                                         # Else; parse string into dictionary
    plexLibs = dict( [map(str.strip, lib.split(':')[::-1]) for lib in output.splitlines()] )

  return plexLibs                                                               # Return dictionary

################################################################################
def parse_cmd_lib_dirs( lines ):
  """ 
  Function to parse :code:`Plex Media Server` command directory and LD_LIBRARY_PATH path.

  Arguments:
    lines (list): List of strings containing output from a call to 
      :code:`pgrep -fa Plex Media Server`

  Keyword arguments:
    None.

  Returns:
    Returns the command parent directory and LD_LIBRARY_PATH.
    in that order. If either/both NOT found, None is returned.

  """ 

  for line in lines:                                                            # Iterate over all the lines in the list
    lib_path = _LD_pattern.findall( line );                                     # Attempt to find the LD_LIBRARY_PATH value in the string
    if len(lib_path) == 1:                                                      # If it is found
      return lib_path[0], lib_path[0];                                          # Return this value for both the command parent directory AND the LD_LIBRARY_PATH
 
  for line in lines:
    cmd = ' '.join( line.split()[1:] ) 
    if (_plex_server in cmd):
      try:
        path = os.path.dirname(cmd)
      except:
        continue
      else:
        if os.path.isdir( path ):
          return path, None

  return None, None;                                                            # Return None for both
