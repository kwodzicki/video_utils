import logging;
import os, re, time;
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL
from video_utils.videotagger.metadata.getIMDb_ID import getIMDb_ID;

plex_server  = 'Plex Media Server'
plex_scanner = 'Plex Media Scanner'

pgrep        = ['pgrep', '-fa', plex_server];
LD_pat       = re.compile( r'(?:LD_LIBRARY_PATH=([\w\d\S]+))' );         # Pattern for finding LD_LIBRARY_PATH in command
splt_pat     = re.compile( r'(?:([^"\s]\S*)|"(.+?)")' )

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
  log               = logging.getLogger(__name__);
  log.debug( 'Getting information from file name' );

  fileDir           = os.path.dirname(  in_file );
  fileBase          = os.path.basename( in_file );                              # Get base name of input file
  series, se, title = fileBase.split(' - ');                                    # Split the file name on ' - '; not header information of function
  title             = title.split('.');                                         # Split the title on period; this is to get file extension
  ext               = title[-1];                                                # Get the file extension; last element of list
  title             = '.'.join(title[:-1]);                                     # Join all but last element of title list using period; will rebuild title
  log.debug('Attempting to get IMDb ID')
  imdbId            = getIMDb_ID( in_file );                                    # Try to get IMDb id

  if not imdbId: 
    log.warning( 'No IMDb ID! Renaming file without it')
    imdbId = '';                                                                # If no IMDb id found, set imdbId to emtpy string

  new = '{} - {}.{}.{}'.format(se.lower(), title, imdbId, ext);                 # Build new file name
  new = os.path.join( fileDir, new );                                           # Build new file path
  if hardlink:
    os.link( in_file, new );                                                    # Create hard link to file with new file name
  else:
    os.rename( in_file, new );                                                  # Rename the file
  return new, (series, se, title);

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
  log.debug('Sleeping {} seconds'.format(wait) )
  time.sleep( wait );

  cmd, myenv = getPlexScannerCMD();                                             # Attempt to get Plex Media Scanner command
  if cmd is None:
    log.critical( "Did NOT find the 'Plex Media Scanner' command! Exiting!")
    return 1
  
  plexList = check_output( cmd+['--list'], universal_newlines=True, env=myenv );# Try to get help information from the scanner
  if plexList == '':                                                            # If an empty string was returned
    cmd      = ['stdbuf', '-oL', '-eL'] + cmd;                                  # Change the output and error buffering to line buffered or the cmd
    try:
      plexList = check_output( cmd+['--list'], universal_newlines=True, env=myenv );# Get the list again
    except:
      log.critical( 'Failed to get listing of sections! Exiting' )
      return 1
  
  plexList = plexList.splitlines();
  section  = None;
  while (len(plexList) > 0) and (section is None):
    tmp = plexList.pop();
    if 'TV' in tmp:
      section = tmp.split(':')[0].strip();
  if section is None:
    log.critical( "Failed to find 'TV' section! Exiting" )
    return 1

  cmd      += [ '--scan', '--section', section ];                               # Append scan and section options to command
  in_base  = os.path.basename( in_file );

  scan_dir = None;
  lib_dir  = in_file.split('.grab')[0];                                         # Top level directory of the Plex Library
  show_dir = os.path.join( lib_dir, info[0] )

  if os.path.isdir( show_dir ):                                                 # If the show directory exists
    season = re.findall( r'(?:[sS](\d+)[eE]\d+)', info[1] );                    # Attempt to find season number from information
    if len(season) == 1:
      season     = int( season[0] )
      season_dir = os.path.join( show_dir, 'Season {:02d}'.format( season ) );
      if os.path.isdir( season_dir ):
        src_file = os.path.join( season_dir, in_base );
        if os.path.isfile( src_file ):                                          # If the file exists, then we are at the lowest level directory for scanning
          scan_dir = season_dir;                                                # Set the scan directory to the season directory
  
  if scan_dir is not None:
    cmd += [ '--directory', scan_dir ];                                         # Append directory to scan to command
  log.debug( 'Plex Media Scanner command: {}'.format( ' '.join(cmd) ) )

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
  proc.communicate();

  if not no_remove:                                                             # If no_remove is False, i.e., want to remove file
    os.remove( in_file );
    proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
    proc.communicate();
  return 0

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
      ld_path = myenv.pop( 'LD_LIBRARY_PATH', False)
      if ld_path:
        lib_dir = '{}:{}'.format( ld_path, lib_dir );
      myenv['LD_LIBRARY_PATH'] = lib_dir

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
    args = splt_pat.findall( cmd );                                             # Split arguments; should return list of tuples
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
    lib_path = LD_pat.findall( line );                                          # Attempt to find the LD_LIBRARY_PATH value in the string
    if len(lib_path) == 1:                                                      # If it is found
      return lib_path[0], lib_path[0];                                          # Return this value for both the command parent directory AND the LD_LIBRARY_PATH
  
  # If made here, means nothing found in above method
  cmds = parseCommands( lines );                                                # Parse out all argumens from the commands
  for cmd in cmds:                                                              # Iterate over all command argument lists in the cmds list
    if plex in cmcd[-1]:                                                        # If the 'Plex Media Server' string is in the last argument of the command
      return os.path.dirname( c[-1] ), None;                                    # Return the parent directory of the command AND None for LD_LIBRARY_PATH
  
  # If made here, means nothing found
  return None, None;                                                            # Return None for both
