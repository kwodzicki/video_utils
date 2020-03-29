import logging
import os, re 
from subprocess import check_output, Popen, PIPE, STDOUT, DEVNULL

from .utils import getPlexMediaScanner, getPlexLibraries

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
    A python function that will try to run the Plex Media Scanner CLI.
  Inputs:
    Any flags from the Plex Media Scanner Actions list; note that
    you do NOT include hyphens (-). Note that if you are adding a section,
    the --type, --agent, etc. flags should be input as keywords.
    Can also input Modifies to actions here
  Keywords:
    Any flag/value pair from the Plex Media Scanner Items list   
  Outputs:
    Returns status code; 0 is successful scan
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

  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT, env = _env );
  proc.communicate();

  return 0
