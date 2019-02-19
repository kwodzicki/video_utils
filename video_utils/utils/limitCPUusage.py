import logging;
import os;
from subprocess import call, Popen, STDOUT, DEVNULL;

if call(['which', 'cpulimit'], stdout = DEVNULL, stderr = STDOUT) != 0:
  msg = 'cpulimit is NOT installed';
  logging.getLogger(__name__).error( msg );
  raise Exception( msg );

def limitCPUusage( pid, cpulimit, threads = 1, single = False ):
  '''
  Function for limiting cpu usage.
  The single keyword should be set to true when a
  command runs only on a single thread.
  '''
  log = logging.getLogger(__name__);
  limit = cpulimit if single else cpulimit * threads;                           # Set the cpu limit to threads times 75 per cent
  limit = '200' if limit > 200 else str( limit );                               # Make sure not more than 200
  log.debug('Limiting CPU usage to {}%'.format(limit))

  limit = [ 'cpulimit', '-p', str( pid ), '-l', limit ];                        # Set up the cpulimit command
  cpuID = Popen(limit, stdout = DEVNULL, stderr = STDOUT);                      # Run cpu limit command
  return cpuID;