import logging
import sys
from subprocess import check_output, STDOUT

def checkCLI( cli ):
  log = logging.getLogger(__name__)
  if sys.platform == 'win32':
    cmd = ['where', cli]
  else:
    cmd = ['which', cli]

  try:
    path = check_output( cmd, stderr = STDOUT )
  except:
    path = None

  if (path is None):
    raise Exception(
      "The following required command line utility was NOT found." +
      " If it is installed, be sure it is in your PATH: " +
      cli
    )
  
  return path.decode().rstrip()
