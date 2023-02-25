import logging
import os
from subprocess import Popen, STDOUT, DEVNULL

from ..utils.checkCLI import checkCLI

CLIName = 'ccextractor'
try:
  CLI = checkCLI( CLIName )
except:
  logging.getLogger(__name__).warning( "{} is NOT installed or not in your PATH!".format(CLIName) )
  CLI = None

def ccextract( in_file, out_base, text_info ):
  """
  Wrapper for the ccextrator CLI, simply calls ccextractor using subprocess.Popen

  Arguments:
    in_file (str): File to extract closed captions from
    out_base (str): Base name for output file(s)
    text_info (dict): Text information from call to mediainfo

  Keyword arguments:
    None.

  Returns:
    None: ccextract creates some files

  """

  log  = logging.getLogger(__name__)                                           # Set up logger
  if CLI is None:
    log.warning( f"{CLIName} CLI not found; cannot extract!" )
    return None

  fname = out_base + text_info[0]['ext'] + '.srt'                               # Build file path based on text_info
  cmd   = [CLI, '-autoprogram', in_file, '-o', fname]                 # Command to run for extraction
  log.debug( f"{CLIName} command: {' '.join(cmd)}" )
  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT )                       # Run command
  proc.communicate()                                                           # Wait to finish
  if proc.returncode != 0:                                                      # If non-zero return code
    log.error('Something went wrong extracting subtitles')                     # Log error
    return False                                                               # Return false
  return True                                                                  # Return true
