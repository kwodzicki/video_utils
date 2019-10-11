import logging;
import os, re, time;
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL
from video_utils.videotagger.metadata.getIMDb_ID import getIMDb_ID;

_plex_server  = 'Plex Media Server';                                            # Name of the Plex server command
_plex_scanner = 'Plex Media Scanner';                                           # Name of the Plex scanner command

_pgrep          = ['pgrep', '-fa', _plex_server];                               # Command for getting information about runnin Plex Server, if any
_LD_pattern     = re.compile( r'(?:LD_LIBRARY_PATH=([\w\d\S]+))' );             # Pattern for finding LD_LIBRARY_PATH in command
_splt_pattern   = re.compile( r'(?:([^"\s]\S*)|"(.+?)")' );                     # Pattern for spliting output of the pgrep command
_se_pattern     = re.compile( r'([sS]\d{2,}[eE]\d{2,})' );                      # Pattern for locating season/episode numbering
_season_pattern = re.compile( r'(?:[sS](\d+)[eE]\d+)' );                        # Pattern for extracting season number from season/episode numbering      

################################################################################
def plexDVR_Cleanup( in_file, file_info, wait = 60 ):
  '''
  Name:
    plexDVR_Cleanup
  Purpose:
    A python function that will try to find the new locaiton of the 
    in_file in the Plex library and remove it in a smart mannor. If 
    the smart way does NOT work, a brute force search will be
    performed.
  Inputs:
    in_file   : Full path to the file to rename
    file_info : Information parsed from file name; 
                 likely from the plexDVR_Rename function
  Outputs:
    None
  Keywords:
    wait       : Time to wait, in seconds, for the function
                  to start scanning. Default is 60 seconds
  Note:
    This function is intened to be run as a child process, i.e., 
    after call to os.fork()
  '''
  log = logging.getLogger(__name__);
  log.debug( 'Running as user: {}'.format( os.environ['USER'] ) )
  log.debug( 'Input file: {}'.format( in_file ) )
  log.debug( 'Sleeping {} seconds'.format( wait ) )
  time.sleep( wait );

  in_base    = os.path.basename( in_file );                                     # Base name of input file
  lib_dir    = in_file.split('.grab')[0];                                       # Top level directory of the Plex Library
  show_dir   = os.path.join( lib_dir, file_info[0] );                           # Path to show directory based on information from file name
  scan_dir   = None;
  moved_file = None;

  log.debug( 'Library directory: {}'.format( lib_dir ) )
  log.debug( 'Show    directory: {}'.format( show_dir ) )

  if os.path.isdir( show_dir ):                                                 # If the show directory exists
    scan_dir = show_dir                                                         # Set scan directory to show directory; should cut down find time
    season   = _season_pattern.findall( file_info[1] );                          # Attempt to find season number from information
    if len(season) == 1:                                                        # If season number was extracted from information
      season     = int( season[0] );                                            # Convert season number to integer
      season_dir = os.path.join( show_dir, 'Season {:02d}'.format( season ) );  # Path to Season directory of show
      if os.path.isdir( season_dir ):                                           # If the season directory does NOT exist
        scan_dir = season_dir                                                   # Set scan directory to season directory; should cut down on find time
        tmp_path = os.path.join( season_dir, in_base );                         # Path to the 'original' recoding file
        if os.path.isfile( tmp_path ):                                          # If the file does exist
          log.debug( 'Found moved file: {}'.format( tmp_path ) );
          moved_file = tmp_path;                                                # Set moved_file to tmp_path 
  
  if (moved_file is None) and (scan_dir is not None):                           # If the moved_file varaible is None and scan_dir is NOT None
    log.info( 'Looking for file in: {}'.format(scan_dir) );                     # Log some info
    moved_file = findFile( scan_dir, in_base );                                 # Try brute force scan on scan_dir

  if moved_file is None:                                                        # If moved_file is still None
    log.info( 
      'Moved file NOT found using smart method, searching library: {}'.format(
        lib_dir
      ) 
    );                                                                          # Log some info
    moved_file = findFile( lib_dir, in_base );                                  # Try brute force scan on entire library

  if moved_file is None:                                                        # If moved_file IS STILL NONE
    log.error( 'Failed to find new location of input file!' );                  # Log error
    return False;                                                               # Return False

  log.info( 'Removing file: {}'.format( moved_file ) )
  os.remove( moved_file );                                                      # If made here, we found the file so remove it

  log.debug('Finished')
  return True;                                                                  #

################################################################################
def plexDVR_Scan( recorded, converted, no_remove = False ):
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
  Note:
    This function is intened to be run as a child process, i.e., 
    after call to os.fork()
  '''
  log = logging.getLogger(__name__);
  log.debug( 'Running as user: {}'.format( os.environ['USER'] ) )
  log.debug( 'Sleeping {} seconds'.format( wait ) )
  time.sleep( wait );
  log.debug('Finished sleeping')

  try:
    cmd, myenv = getPlexScannerCMD();                                             # Attempt to get Plex Media Scanner command
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
    if 'TV' in tmp:                                                             # If TV is in the string
      section = tmp.split(':')[0].strip();                                      # Get the section number for the Plex section
  if section is None:                                                           # If section is still None
    log.critical( "Failed to find 'TV' section! Exiting" )
    return 1;                                                                   # Return 

  scan_dir  = os.path.basename( recorded );                                     # Base name of input file
  cmd      += [ '--scan', '--section', section, '--directory', scan_dir ];      # Append scan and section options to command

  log.debug( 'Plex Media Scanner command: {}'.format( ' '.join(cmd) ) )

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
  proc.communicate();

  if not no_remove:                                                             # If no_remove is False, i.e., want to remove file
    log.debug('Removing original recoding' );                                   # Debug info
    os.remove( recorded );                                                     # Remove the original recording file

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
    os.link( in_file, new );                                                    # Create hard link to file with new file name
  else:
    log.debug( 'Renaming input file' )
    os.rename( in_file, new );                                                  # Rename the file
  return new, (series, se, title);

################################################################################
def getPlexScannerCMD( ):
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
  log.debug( 'Environment: {}'.format( myenv ) )
  return cmd, myenv 

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
  
  # If made here, means nothing found in above method
  cmds = parseCommands( lines );                                                # Parse out all argumens from the commands
  for cmd in cmds:                                                              # Iterate over all command argument lists in the cmds list
    if _plex_server in cmd[-1]:                                                 # If the 'Plex Media Server' string is in the last argument of the command
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
