import logging
import os, re 
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL

from video_utils.plex.utils import getPlexMediaScanner, getPlexLibraries

try:
  _scanner, _env = getPlexMediaScanner();                                           # Attempt to get Plex Media Scanner command
except:                                                                             # If failed
  _scanner  = None                                                                  # Set _scanner to None
  _env      = None                                                                  # Set _env to none
  _plexLibs = {}                                                                    # Set _plexLibs to empty dictionary
else:                                                                               # Else
  _plexLibs = getPlexLibraries( _scanner, _env )                                    # Attempt to get Plex Libraries

################################################################################
def plexMediaScanner( *args, **kwargs ):
  '''
  Name:
    plexMediaScanner
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
  '''
  log = logging.getLogger(__name__);
  if (os.environ['USER'].upper() != 'PLEX'):
    log.error("Not running as user 'plex'; current user : {}. Skipping Plex Library Scan".format(os.environ['USER']) )
    return 2
  elif (_scanner is None):
    log.critical( "Did NOT find the 'Plex Media Scanner' command! Returning!")
    return 1
  elif not isinstance(_plexLibs, dict): 
    log.critical('No libraries found! Returning')
    return 1
  
  cmd  = _scanner + ['--{}'.format(arg) for arg in args]
  for key, val in kwargs.items():
    if (key == 'section'):
      val = _plexLibs.get(val, None)
      if not val:
        log.error('Failed to find library section in list of libraries! Returning')
        return 3
    cmd += ['--{}'.format(key), val]
# '--scan', '--section', section, '--directory', scan_dir ];      # Append scan and section options to command

  log.debug( 'Plex Media Scanner command: {}'.format( ' '.join(cmd) ) )

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = myenv );
  proc.communicate();

  return 0
