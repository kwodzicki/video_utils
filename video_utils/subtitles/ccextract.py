import logging;
import os;
from subprocess import call, Popen, STDOUT, DEVNULL

if call(['which', 'ccextractor'], stdout = DEVNULL, stderr = STDOUT ) != 0:     # If cannot find the ccextractor CLI
  msg = "ccextractor is NOT installed or not in your PATH!";
  logging.getLogger(__name__).warning(msg);
  raise Exception( msg );                 # Raise an exception

def ccextract( in_file, out_file, text_info ):
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
