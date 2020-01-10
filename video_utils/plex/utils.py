import logging
import os, re, time, pickle
from threading import Lock
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL

from ..videotagger.metadata.getIMDb_ID import getIMDb_ID

_plex_server  = 'Plex Media Server';                                            # Name of the Plex server command
_plex_scanner = 'Plex Media Scanner';                                           # Name of the Plex scanner command

_pgrep          = ['pgrep', '-fa', _plex_server];                               # Command for getting information about runnin Plex Server, if any
_LD_pattern     = re.compile( r'(?:LD_LIBRARY_PATH=([\w\d\S]+))' );             # Pattern for finding LD_LIBRARY_PATH in command
_splt_pattern   = re.compile( r'(?:([^"\s]\S*)|"(.+?)")' );                     # Pattern for spliting output of the pgrep command
_se_pattern     = re.compile( r'([sS]\d{2,}[eE]\d{2,})' );                      # Pattern for locating season/episode numbering
_season_pattern = re.compile( r'(?:[sS](\d+)[eE]\d+)' );                        # Pattern for extracting season number from season/episode numbering      

################################################################################
def plexDVR_Scan( recorded, no_remove = False, movie = False ):
  '''
  Name:
    plexDVR_Scan
  Purpose:
    A python function that will try to scan a specific directory
    so that newly DVRed/transcoded files will be added.

    When Plex records, it saves the file in a temporary folder. When
    recording finishes, that folder is then moved to the proper 
    location and the recording added to the library; however, the
    transoded file will NOT be added. 

    This function will attempt
    to scan just the specific season directory (or full TV library
    as last resort) to add transcoded file. 

    After the scan is complete, pending the no_remove keyword,
    the original recording file fill be removed. It is NOT removed
    first because then Plex will see the transcoded file as a new
    file and NOT a duplicate (I think)
  Inputs:
    recorded : Full path to the DVRd file; i.e., the file that 
                 Plex recoded data to, should be a .ts file.
                 This file MUST be in its final location, that
                 is in the directory AFTER Plex moves it when
                 recording is complete.
  Outputs:
    None
  Keywords:
    no_remove  : Set to True to keep the original file
    movie      : Set if scanning for movie
  Note:
    This function is intened to be run as a child process, i.e., 
    after call to os.fork()
  '''
  log = logging.getLogger(__name__);
  if (os.environ['USER'].upper() != 'PLEX'):
    log.error("Not running as user 'plex'; current user : {}. Skipping Plex Library Scan".format(os.environ['USER']) )
    return 2
 
  try:
    cmd, myenv = getPlexMediaScanner();                                             # Attempt to get Plex Media Scanner command
  except:
    log.exception('Something went wrong finding Plex commands')
    return 1


  if cmd is None:
    log.critical( "Did NOT find the 'Plex Media Scanner' command! Returning!")
    return 1
  
  log.debug( 'Getting list of Plex Libraries' )
  plexList = None
  try:
    plexList = check_output( ['stdbuf', '-oL', '-eL'] + cmd + ['--list'], 
                          universal_newlines = True, env = myenv );             # Get the list again
  except:
    log.debug("Failed to get library listing with 'stdbuf', trying without")        

  if (plexList is None) or (plexList == ''):   
    try:
      plexList = check_output( cmd + ['--list'], 
                      universal_newlines = True, env = myenv );                 # Try to get help information from the scanner
    except:
      log.debug( 'Exception while running command' )
      return 1

  if (plexList is None) or (plexList == ''):                                                      # If an empty string was returned
    log.critical( 'Failed to get listing of sections! Returning')
    return 1

  log.debug( "Attemting to find 'TV' section...")

  plexList = plexList.splitlines();                                             # Split the string of Plex sections on new line
  section  = None;                                                              # Set section to None
  while (len(plexList) > 0) and (section is None):                              # While there are values left in the plexList AND section is None
    tmp = plexList.pop();                                                       # Pop off a string from the plexList
    if movie:                                                                   # If movie is set
      if 'MOVIE' in tmp.upper():                                                # If MOVIE in tmp
        section = tmp.split(':')[0].strip();                                    # Get the section number for the Plex section
    elif 'TV' in tmp:                                                           # If TV is in the string
      section = tmp.split(':')[0].strip();                                      # Get the section number for the Plex section
  if section is None:                                                           # If section is still None
    if movie:
      log.critical( "Failed to find 'Movie' section! Exiting" )
    else:
      log.critical( "Failed to find 'TV' section! Exiting" )
    return 1;                                                                   # Return 

  scan_dir  = os.path.dirname( recorded );                                      # Directory name of input file
  cmd      += [ '--scan', '--section', section, '--directory', scan_dir ];      # Append scan and section options to command

  log.debug( 'Plex Media Scanner command: {}'.format( ' '.join(cmd) ) )

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
  proc.communicate();

  if not no_remove:                                                             # If no_remove is False, i.e., want to remove file
    log.debug('Removing original recoding' );                                   # Debug info
    try:
      os.remove( recorded );                                                     # Remove the original recording file
    except:
      pass

    log.debug( 'Rescanning library' );                                          # Debug info
    proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );        # Rescan the library; note this is only done IF the file is removed
    proc.communicate();

  return 0

################################################################################
def plexFile_Info( in_file ):
  '''
  Name:
    plexFile_Info
  Purpose:
    A python function to extract series, season/episode, and episode title
    information from a file path
  Inputs:
    in_file : Full path to the file to rename
  Outputs:
    Returns series name, season/episode or date, episode title, and file extension
  Keywords:
    None.
  '''
  log               = logging.getLogger(__name__);
  log.debug( 'Getting information from file name' );

  fileBase          = os.path.basename( in_file );                              # Get base name of input file
  fname, ext        = os.path.splitext( fileBase )
  try:
    series, se, title = fname.split(' - ');                                       # Split the file name on ' - '; not header information of function
  except:
    series = ''
    se     = ''
    title  = fname
  return series, se, title, ext

################################################################################
def plexDVR_Rename( in_file, hardlink = True ):
  '''
  Name:
    plexDVR_Rename
  Purpose:
    A python function to rename Plex DVR files to match 
    file nameing convetion for video_utils package
  Inputs:
    in_file : Full path to the file to rename
  Outputs:
    Returns path to renamed file and tuple with parsed file information
  Keywords:
    hardlink  : Boolean, if set to True, will rename input file, else
               creates hard link to file. Default is to hard link
  '''
  log                    = logging.getLogger(__name__);
  fileDir                = os.path.dirname(  in_file );
  series, se, title, ext = plexFile_Info( in_file );

  if len( _se_pattern.findall(se) ) != 1:
    log.warning( 'Season/episode info NOT found; may be date? Things may break' );

  log.debug('Attempting to get IMDb ID')
  imdbId = getIMDb_ID( series, title, season_ep = se );                         # Try to get IMDb id

  if not imdbId: 
    log.warning( 'No IMDb ID! Renaming file without it')
    imdbId = '';                                                                # If no IMDb id found, set imdbId to emtpy string

  new = '{} - {}.{}{}'.format(se.lower(), title, imdbId, ext);                  # Build new file name
  new = os.path.join( fileDir, new );                                           # Build new file path
  if hardlink:
    log.debug( 'Creating hard link to input file' )
    if os.path.exists( new ):                                                       # If new file exists
      try:                                                                          # Try to
        os.remove( new )                                                            # Delete it
      except:                                                                       # Fail silently
        pass                                                                        #
    try:                                                                            # Try to
      os.link( in_file, new )                                                       # Create hard link to file with new file name
    except Exception as err:                                                        # Catch exception
      log.warning( 'Error creating hard link : {}'.format(err) )                    # Log exception
  else:
    log.debug( 'Renaming input file' )
    os.replace( in_file, new );                                                  # Rename the file, overwiting destination if it exists
  return new, (series, se, title);

################################################################################
class DVRqueue( list ):
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
  '''
  Purpose:
    Function to get full path to the Plex Media Scanner command
  Inputs:
    None.
  Keywords:
    None.
  Outputs:
    Returns list containing full path to Plex Media Scanner command
  '''
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
def getPlexLibraries( cmd, env = os.environ ):
  '''
  Purpose:
    Function to get list of plex libraries from the Plex Media Scanner CLI.
  Inputs:
    cmd    : Full path to the Plex Media Scanner CLI (list, 1-element)
  Keywords:
    env    : Environment for running Plex Media Scanner CLI.
             Default os os.environ
  Ouputs:
    Returns dictionary of Plex Libraries where key is library name and
    value is library number.
  '''
  log      = logging.getLogger(__name__)                                        # Get logger
  plexLibs = {}                                                                 # Initialize plexLibs to empty dictionary
  if (os.environ['USER'].upper() != 'PLEX'):
    log.error("Not running as user 'plex'; current user : {}. Could NOT get Plex Libraries".format(os.environ['USER']))
    return plexLibs

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
def parseCommands( cmd_list ):
  '''
  Name:
    parseCommands
  Purpose:
    A python function to parse out the arguments from a string
  Inputs:
    cmd_list : List of strings contiaining output from a call to 
               'pgrep -fa Plex Media Server'
  Outputs:
    Returns list of lists, where sub-lists contain all arguments
    from pgrep output
  Keywords:
    None.
  '''
  cmds = [];                                                                    # Initialze list for all commands
  for cmd in cmd_list:                                                          # Iterate over all cmds in the command list
    args = _splt_pattern.findall( cmd );                                        # Split arguments; should return list of tuples
    for i in range(len(args)):                                                  # Iterate over each argument
      index   = ( args[i].index('') + 1 ) % 2;                                  # Each arg is a 2-element tuple where one is empty string, so, locate empty string, add value of 1 to index do modulus to find index of non-empty string
      args[i] = args[i][index]                                                  # Set argument at i to non-empty string
    cmds.append( args );                                                        # Append args list to the cmds list
  return cmds;                                                                  # Return commands list

################################################################################
def parse_cmd_lib_dirs( lines ):
  '''
  Name:
    parse_cmd_lib_dirs
  Purpose:
    A python function to parse out the Plex Media Server command
    parent directory and LD_LIBRARY_PATH (if exists) path
  Inputs:
    lines   : List of strings contiaining output from a call to 
               'pgrep -fa Plex Media Server'
  Outputs:
    Returns the command parent directory and LD_LIBRARY_PATH.
    in that order. If either/both NOT found, None is returned.
  Keywords:
    None.
  '''
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

  # If made here, means nothing found in above method
#  cmds = parseCommands( lines );                                                # Parse out all argumens from the commands
#  for cmd in cmds:                                                              # Iterate over all command argument lists in the cmds list
#    if _plex_server in cmd[-1]:                                                 # If the 'Plex Media Server' string is in the last argument of the command
#      return os.path.dirname( cmd[-1] ), None;                                  # Return the parent directory of the command AND None for LD_LIBRARY_PATH
  
  # If made here, means nothing found
  return None, None;                                                            # Return None for both
