import logging;
import os, re, time;
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL
from video_utils.videotagger.metadata.getIMDb_ID import getIMDb_ID;

plex_server  = 'Plex Media Server'
plex_scanner = 'Plex Media Scanner'

pgrep          = ['pgrep', '-fa', plex_server];
LD_pattern     = re.compile( r'(?:LD_LIBRARY_PATH=([\w\d\S]+))' );         # Pattern for finding LD_LIBRARY_PATH in command
splt_pattern   = re.compile( r'(?:([^"\s]\S*)|"(.+?)")' )
se_pattern     = re.compile( r'([sS]\d{1,2}[eE]\d{1,2})' )
season_pattern = re.compile( r'(?:[sS](\d+)[eE]\d+)' )

################################################################################
def plexDVR_Scan( in_file, file_info, no_remove = False, wait = 60 ):
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
    in_file   : Full path to the file to rename
    file_info : Information parsed from file name; 
                 likely from the plexDVR_Rename function
  Outputs:
    None
  Keywords:
    no_remove  : Set to True to keep the original file
    wait       : Time to wait, in seconds, for the function
                  to start scanning. Default is 60 seconds
  Note:
    This function is intened to be run as a child process, i.e., 
    after call to os.fork()
  '''
  log = logging.getLogger(__name__);
  log.debug( 'Running as use: {}'.format( os.environ['USER'] ) )
  log.debug( 'Sleeping {} seconds'.format( wait ) )
  time.sleep( wait );

  cmd, myenv = getPlexScannerCMD();                                             # Attempt to get Plex Media Scanner command
  if cmd is None:
    log.critical( "Did NOT find the 'Plex Media Scanner' command! Returnning!")
    return 1
  
  log.debug( 'Getting list of Plex Libraries' )
  try:
    plexList = check_output( cmd + ['--list'], 
                      universal_newlines = True, env = myenv );                 # Try to get help information from the scanner
  except:
    log.critical( 'Failed to get listing of sections! Returnning' )
    return 1
  else:
    if plexList == '':                                                          # If an empty string was returned
      cmd = ['stdbuf', '-oL', '-eL'] + cmd;                                     # Change the output and error buffering to line buffered or the cmd
      try:
        plexList = check_output( cmd + ['--list'], 
                          universal_newlines = True, env = myenv );             # Get the list again
      except:
        log.critical( 'Failed to get listing of sections! Returnning' )
        return 1
      else:
        if plexList == '':                                                          # If an empty string was returned
          log.critical( 'Failed to get listing of sections! Returnning')
          return 1

  log.debug( "Attemting to find 'TV' section...")

  plexList = plexList.splitlines();                                             # Split the string of Plex sections on new line
  section  = None;                                                              # Set section to None
  while (len(plexList) > 0) and (section is None):                              # While there are values left in the plexList AND section is None
    tmp = plexList.pop();                                                       # Pop off a string from the plexList
    if 'TV' in tmp:                                                             # If TV is in the string
      section = tmp.split(':')[0].strip();                                      # Get the section number for the Plex section
  if section is None:                                                           # If section is still None
    log.critical( "Failed to find 'TV' section! Exiting" )
    return 1;                                                                   # Return 

  cmd      += [ '--scan', '--section', section ];                               # Append scan and section options to command

  in_base    = os.path.basename( in_file );                                       # Base name of input file
  lib_dir    = in_file.split('.grab')[0];                                         # Top level directory of the Plex Library
  show_dir   = os.path.join( lib_dir, info[0] );                                  # Path to show directory based on information from file name
  season_dir = None
  orig_file  = None;
  scan_dir   = None;                                                              # Scan directory of Plex Media Scanner initialized to None

  log.debug( 'Library directory: {}'.format( lib_dir ) )
  log.debug( 'Show    directory: {}'.format( show_dir ) )
  if not os.path.isdir( show_dir ):                                             # If the show directory exists
    log.info('No show directory, will scan entire library')
  else:
    scan_dir = show_dir;                                                        # Set the directory to scan to the show directory
    season   = season_pattern.findall( info[1] );                               # Attempt to find season number from information
    if len(season) == 1:                                                        # If a season number was extracted from information
      season     = int( season[0] );                                            # Convert season number to integer
      season_dir = os.path.join( show_dir, 'Season {:02d}'.format( season ) );  # Path to Season directory of show
      if os.path.isdir( season_dir ):                                           # If the season directory exists
        orig_file = os.path.join( season_dir, in_base );                        # Path to the 'original' recoding file
        if os.path.isfile( orig_file ):                                         # If the file exists, then we are at the lowest level directory for scanning
          scan_dir = season_dir;                                                # Set the scan directory to the season directory
  
  if scan_dir is not None:                                                      # If scan_dir is NOT still None
    cmd += [ '--directory', scan_dir ];                                         # Append directory to scan to command

  log.debug( 'Plex Media Scanner command: {}'.format( ' '.join(cmd) ) )

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
  proc.communicate();

  if not no_remove:                                                             # If no_remove is False, i.e., want to remove file
    if orig_file is None:                                                       # If orig_file is not yet set
      orig_file = findFile( lib_dir, in_base );                                 # Try to find the file

    if orig_file is not None:                                                   # If the file was found
      if os.path.isfile( orig_file ):                                           # Check that it exists; redundant, but good habit
        log.debug('Removing original recoding' );                               # Debug info
        os.remove( in_file );                                                   # Remove the file

        log.debug( 'Rescanning library' );                                      # Debug info
        proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );    # Rescan the library; note this is only done IF the file is removed
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
  series, se, title = fname.split(' - ');                                       # Split the file name on ' - '; not header information of function
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
               creates hard link to file. Default is hard link
  '''
  log                    = logging.getLogger(__name__);
  fileDir                = os.path.dirname(  in_file );
  series, se, title, ext = plexFile_Info( in_file );

  if len( se_pattern.findall(se) ) == 1:
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
    os.link( in_file, new );                                                    # Create hard link to file with new file name
  else:
    log.debug( 'Renaming input file' )
    os.rename( in_file, new );                                                  # Rename the file
  return new, (series, se, title);

################################################################################
def getPlexScannerCMD( ):
  log = logging.getLogger(__name__);
  log.debug( "Trying to locate '{}'".format( plex_scanner ) );

  try:
    lines = check_output( pgrep, universal_newlines=True ).splitlines();
  except:
    log.critical( "Failed to find '{}' process".format(plex_server) )
    return None, None

  myenv            = os.environ.copy()
  cmd_dir, lib_dir = parse_cmd_lib_dirs( lines )

  if cmd_dir is None:
    log.error( "'Plex Media Scanner' NOT found!!!" );
  else: 
    cmd_dir = [os.path.join( cmd_dir, plex_scanner )]
    if lib_dir is not None:
      log.debug( 'Setting LD_LIBRARY_PATH in environment' )
      if lib_dir[-1] == os.path.sep: lib_dir = lib_dir[:-1]
      ld_path = myenv.pop( 'LD_LIBRARY_PATH', False)
      if ld_path:
        lib_dir = '{}:{}'.format( ld_path, lib_dir );
      log.debug( 'New LD_LIBRARY_PATH: {}'.format( lib_dir) )
      myenv['LD_LIBRARY_PATH'] = lib_dir
  
  log.debug( 'Plex directory: {}'.format( cmd_dir ) )
  log.debug( 'Environment: {}'.format( myenv ) )
  return cmd_dir, myenv 

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
    args = splt_pattern.findall( cmd );                                         # Split arguments; should return list of tuples
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
    lib_path = LD_pattern.findall( line );                                      # Attempt to find the LD_LIBRARY_PATH value in the string
    if len(lib_path) == 1:                                                      # If it is found
      return lib_path[0], lib_path[0];                                          # Return this value for both the command parent directory AND the LD_LIBRARY_PATH
  
  # If made here, means nothing found in above method
  cmds = parseCommands( lines );                                                # Parse out all argumens from the commands
  for cmd in cmds:                                                              # Iterate over all command argument lists in the cmds list
    if plex_server in cmd[-1]:                                                  # If the 'Plex Media Server' string is in the last argument of the command
      return os.path.dirname( cmd[-1] ), None;                                  # Return the parent directory of the command AND None for LD_LIBRARY_PATH
  
  # If made here, means nothing found
  return None, None;                                                            # Return None for both

################################################################################
def findFile( rootDir, filename ):
  log = logging.getLogger(__name__);
  for root, dirs, files in os.walk( rootDir ):
    for file in files:
      if file == filename:
        return os.path.join( root, file );
  log.warning( 
    'Failed to find file in: {} with name: {}'.format(rootDir, filename)
  )
  return None;