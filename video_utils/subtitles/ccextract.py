import logging
import os
from subprocess import Popen, STDOUT, DEVNULL

from video_utils.utils.checkCLI import checkCLI

try:
  checkCLI( 'ccextractor' )
except:
  logging.getLogger(__name__).warning( "ccextractor is NOT installed or not in your PATH!" )
  raise 

def ccextract( in_file, out_file, text_info ):
  '''
  Name:
    ccextract
  Purpose:
    A wrapper for the ccextrator CLI, simply calls ccextractor using 
    subprocess.Popen
  Inputs:
    in_file   : File to extract closed captions from
    out_file  : Base name for output file(s)
    text_info : Dictionary of text information from call to mediainfo
  Keywords:
    None.
  Outputs:
    ccextract creates some files
  '''
  log  = logging.getLogger(__name__);                                           # Set up logger
  file = out_file + text_info[0]['ext'] + '.srt';                               # Build file path based on text_info
  cmd  = ['ccextractor', '-autoprogram', in_file, '-o', file];                  # Command to run for extraction
  log.debug( 'ccextractor command: {}'.format( ' '.join(cmd)) );
  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );                       # Run command
  proc.communicate();                                                           # Wait to finish
  if proc.returncode != 0:                                                      # If non-zero return code
    log.error('Something went wrong extracting subtitles');                     # Log error
    return False;                                                               # Return false
  return True;                                                                  # Return true
