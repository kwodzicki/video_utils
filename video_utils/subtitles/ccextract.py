import logging;
import os;
from subprocess import call, Popen, STDOUT, DEVNULL

if call(['which', 'ccextractor'], stdout = DEVNULL, stderr = STDOUT ) != 0:     # If cannot find the ccextractor CLI
  raise Exception( "ccextractor is NOT installed or not in your PATH!" );       # Raise an exception

def ccextract( in_file, out_file, text_info ):
  log  = logging.getLogger(__name__);
  cmd  = ['ccextractor', '-autoprogram', in_file, '-o', out_file];
  log.debug( 'ccextractor command: {}'.format( ' '.join(cmd)) );
  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );
  proc.communicate();
  if proc.returncode != 0:
    log.error('Something went wrong extracting subtitles');
    return False;
  return True;