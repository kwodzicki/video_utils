import logging;
import os;
from subprocess import Popen, STDOUT, DEVNULL

def ccextract( in_file, out_file ):
  log  = logging.getLogger(__name__);
  cmd  = ['ccextractor', '-autoprogram', in_file, '-o', out_file];
  log.debug( 'ccextractor command: {}'.format( ' '.join(cmd)) );
  proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );
  proc.communicate();
  if proc.returncode != 0:
    log.error('Something went wrong extracting subtitles');
    return False;
  return True;
