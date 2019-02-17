import os;
from subprocess import call, Popen, STDOUT, DEVNULL;

if call(['which', 'cpulimit'], stdout = DEVNULL, stderr = STDOUT) != 0:
  raise Exception( 'cpulimit is NOT installed' );

def limitCPUusage( pid, cpulimit, threads = 1, single = False ):
	'''
	Function for limiting cpu usage.
	The single keyword should be set to true when a
	command runs only on a single thread.
	'''
	limit = cpulimit if single else cpulimit * threads;                           # Set the cpu limit to threads times 75 per cent
	limit = '200' if limit > 200 else str( limit );                               # Make sure not more than 200
	limit = [ 'cpulimit', '-p', str( pid ), '-l', limit ];                        # Set up the cpulimit command
	cpuID = Popen(limit, stdout = DEVNULL, stderr = STDOUT);                      # Run cpu limit command
	return cpuID;