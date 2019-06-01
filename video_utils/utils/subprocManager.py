import logging;
import os, time;
from subprocess import call, Popen, STDOUT, DEVNULL;
from threading import Thread;
from multiprocessing import cpu_count;

nthreads = cpu_count() // 2;                                                    # Set global nthreads as half the number of cpus
cpulimitInstalled = True;                                                       # Set global cpulimitInstalled flag to True
if call(['which','cpulimit'], stdout=DEVNULL, stderr=STDOUT) != 0:              # If cannot find cpulimit command in path
  logging.getLogger(__name__).warning(
    'cpulimit NOT found! Cannot limit CPU usage!'
  );                                                                            # Log a warning
  cpulimitInstalled = False;                                                    # Set global cpulimitInstalled flag to False;

class subprocManager(object):
  def __init__(self, cpulimit = None, threads = None, interval = None):
    '''
    Keywords:
       cpulimit : Limit, in percent, for CPU usage. 
                   Values range from 1 - 100.
                   A value of 0 means no limiting.
                   Default is 75%
       threads  : Number of processes that can be run at one time.
                   Default is half the number of cores, or 1
       interval : Update interval for checking process completion.
                   Default is 0.5 seconds. 
                   Smallest interval is 0.01 seconds or 10 ms
                   Smaller values will catch process completions faster,
                   but will also use more resources while checking for
                   process completion.
    '''
    super().__init__();
    self.log           = logging.getLogger(__name__);                           # Get logger for the class
    self.cpulimit      = cpulimit;                                              # Set cpulimit attribute to user input cpulimit; see @properties at bottom for defaults
    self.threads       = threads;                                               # Set threads attribute to user input threads; see @properties at bottom for defaults
    self.interval      = interval;                                              # Set interval attribute to user input interval; see @properties at bottom for defaults
    self._logFMT       = 'Process {:3d} of {:3d} - {}';                         # Format for logging message
    self.__n           =  0;                                                    # Counter for the process number being run
    self.__nProcs      =  0;                                                    # Total number of process added
    self.__queue       = [];                                                    # Empty list to queue process information
    self.__procs       = [];                                                    # Empty list for Popen handles for process
    self.__returncodes = [];
    self.__cpuProcs    = [];                                                    # Empty list for Popen handles from cpulimit instances
    self.__threadID    = None;                                                  # Set _threadID attribute to None

  ##############################################################################
  def addProc(self, args, **kwargs):
    '''
    Purpose:
      Method for adding a command to the queue
    Inputs:
      args  : same as input to subprocess.Popen
    Keywords:
      single  : Set to True if the process you are controlling is single
                 threaded; i.e., it can only ever use one CPU core.
      stdout  : Same as stdout for Popen, however, if you set this to a
                 string, it is assumed that this is a file path and
                 will pipe all output to file.
      stderr  : Same as for stdout but for all stderr values
      Accepts all subprocess.Popen arguments. Only difference is that
      by default stdout and stderr are piped to DEVNULL
    '''
    self.__queue.append( (args, kwargs,) );                                     # Append the Popen info to the queue as a tuple
    self.__nProcs += 1;                                                         # Increment the number of processes to be run
  ##############################################################################
  def run(self, block = True):
    '''
    Purpose:
      Method to start running the commands in the queue
    Keywords:
      block   : Wait for all commands to finish before returning. 
                 Default is to wait. Set to False to return right away.
                 Returning right away may be useful if you want to add 
                 more processes the to process queue. You can then use
                 the .wait() method to wait for processes to finish.
    '''
    self.__returncodes = [];                                                    # Reset __return codes to empty list
    self.__threadID    = Thread( target = self.__thread );                      # Initialize Thread class
    self.__threadID.start();                                                    # Start the thread
    if block: self.wait();                                                      # If block (default), wait for processes to complete
  ##############################################################################
  def wait(self, timeout = None):
    '''
    Purpose:
      Similar to Popen.wait(), however, returns False if timed out
    Keywords:
      timeout : Time, in seconds, to wait for process to finish.
    '''
    if self.__threadID:                                                         # If the _threadID attribute valid; i.e., not None
      self.__threadID.join(timeout = timeout);                                  # Try to join the thread
      if self.__threadID.is_alive():                                            # If the thread is still alive
        return False;                                                           # Return False
      else:                                                                     # Else, thread is done
        self.__threadID = None;                                                 # Set _threadID attribute to None;
    self.__nProcs = 0;                                                          # Reste number of processes to zero (0)
    return True;                                                                # Return True by default
  ##############################################################################
  def applyFunc(self, func, args=(), kwargs={}):
    '''
    Purpose:
      Method to apply given function to Popen instance.
      Only applicable when one (1) process running
    Inputs:
      func  : Function to apply
    Keywords:
      args   : Tuple or list of arguments, besides Popen instance, to
               apply to function
      kwargs : Dictionary of keyword arguments to apply to input function
    '''
    self.log.debug('Attempting to apply function to process')
    if len(self.__procs) != 1: time.sleep(0.5);                                 # If no processes running, sleep for 500 ms to see if one will start
    if len(self.__procs) != 1:                                                  # If there is NOT one process running
      if len(self.__procs) == 0:                                                # Check if no processes running
        self.log.error('No processes running!');                                # Log error
      else:                                                                     # Else, more than one
        self.log.error('More than one (1) process running!');                   # Log error
      return False;                                                             # Return False
    func( self.__procs[0][0], *args, **kwargs );                                # Apply the function to the only running process
    return True;                                                                # Return True
  ##############################################################################
  def __thread(self):
    '''
    Private method for actually running all the process.
    This is done in a thread so that blocking can be disabled; i.e.,
    user can keep adding processes to the queue if they want
    '''
    self.__n = 0;                                                               # Ensure the counter is at zero
    while len(self.__queue) > 0:                                                # While there are commands in the queue
      if len(self.__procs) == self.threads:                                     # If the number of allowable subprocess are running
        self.__procCheck();                                                     # Wait for a process to finish
      args, kwargs = self.__queue.pop(0);                                       # Pop off first element of the _queue
      self.__Popen( args, **kwargs );                                           # Call method to start a new subprocess
    while len(self.__procs) > 0:                                                # While there are processes running
      self.__procCheck();                                                       # Wait for a process to finish
  ##############################################################################
  def __Popen( self, args, **kwargs ):    
    '''
    Method for starting subprocess and applying cpu limiting
    Inputs:
      args  : Same as Popen args
    Keywords:
      All kwargs from Popen
    '''      
    self.__n += 1;                                                              # Increment n by one
    single = kwargs.pop('single', False);                                       # Pop off the 'single' keyword argument, or get False if not keyword
    stdout = kwargs.pop('stdout', DEVNULL);                                     # Set default stdout to DEVNULL
    stderr = kwargs.pop('stderr', STDOUT);                                      # Set default stderr to STDOUT, which will be DEVNULL if default stdout is used
    
    logType = 0;                                                                # Variable that will determine what type of logging is required; (0) no files, (1) stdout file, (2), stderr file, (3), both (1) and (2)
    if type(stdout) is str:                                                     # If stdout is string type
      if self.__makedirs( stdout, True ):                                       # Try to make directory tree
        logType += 1;                                                           # Increment log type by 1
      else:                                                                     # Else, make failed
        stdout = DEVNULL;                                                       # Set stdout to DEVNULL

    if type(stderr) is str:                                                     # If stderr is string type
      if self.__makedirs( stderr ):                                             # Try to make directory tree
        logType += 2;                                                           # Increment log type by 2
      else:                                                                     # Else, make failed
        stderr = STDOUT;                                                        # Set stderr to STDOUT

    if logType == 0:                                                            # If no log files are needed
      proc = Popen( args, stdout = stdout, stderr = stderr, **kwargs );         # Start the process
    elif logType == 1:                                                          # Else, if stdout is a file
      with open( stdout, 'w' ) as stdout:                                       # Open file for writing
        proc = Popen( args, stdout = stdout, stderr = stderr, **kwargs );       # Start the process
    elif logType == 2:                                                          # Else, if stderr is a file
      with open( stderr, 'w' ) as stderr:                                       # Open file for writing
        proc = Popen( args, stdout = stdout, stderr = stderr, **kwargs );       # Start the process
    else:                                                                       # Else, both stdout and stderr must be files
      with open( stdout, 'w' ) as stdout:                                       # Open stdout file for writing
        with open( stderr, 'w' ) as stderr:                                     # Open stderr file for writing
          proc = Popen( args, stdout = stdout, stderr = stderr, **kwargs );     # Start the process

    self.log.info( self._logFMT.format(self.__n, self.__nProcs, 'Started!') ); # Logging information

    self.__procs.append( (proc, self.__n) );                                    # Append handle and process number tuple to the _procs attribute
    if cpulimitInstalled and (self.cpulimit > 0) and (self.cpulimit < 100):     # If the cpulimit CLI is installed AND the cpulimit is greater than zero (0) AND less than 100
      limit = self.cpulimit if single else self.cpulimit * self.threads;        # Set the cpu limit to threads times the current cpulimit percentage
      # limit = '200' if limit > 200 else str( limit );                           # Make sure not more than 200
      # limit = [ 'cpulimit', '-p', str( proc.pid ), '-l', limit ];               # Set up the cpulimit command
      limit = [ 'cpulimit', '-p', str( proc.pid ), '-l', str(limit) ];            # Set up the cpulimit command
      self.__cpuProcs.append( Popen(limit, stdout=DEVNULL, stderr=STDOUT) );    # Start new subprocess for CPU limit command and append handle to _cpuProcs
  ##############################################################################
  def __procCheck(self):
    '''
    Private method to check for finished processes
    '''
    while all( [proc[0].poll() is None for proc in self.__procs] ):             # While all of the processes are working (remember _procs contains tuples)
      time.sleep(self.interval);                                                # Sleep for the interval defined
    for i in range( len(self.__procs) ):                                        # Iterate over all the process
      if self.__procs[i][0].returncode is not None:                             # If the process has finished (remember _procs contains tuples)
        proc, n = self.__procs.pop( i );                                        # Pop off the (process, #) tuple
        proc.communicate();                                                     # Ensure processes finished, just good practice
        self.log.info( self._logFMT.format( n, self.__nProcs, 'Finished!' ) );  # Log some information
        try:                                                                    # Try to
          cpuProc = self.__cpuProcs.pop( i );                                   # Pop off the cpulimit Popen handle for the process
        except:                                                                 # If there is an exception
          pass;                                                                 # Do nothing, cpulimiting must be disabled
        else:                                                                   # Else, cpulimiting must be enabled
          cpuProc.communicate();                                                # Ensure processes finished, just good practice 
        self.__returncodes.append( proc.returncode );                           # Append the return code to the __returcodes attribute
        if proc.returncode != 0:                                                # If a non-zero returncode
          self.log.warning( 
            self._logFMT.format( n, self.__nProcs, 'Non-zero returncode!!!' ) 
          );                                                                    # Log some information
        break;                                                                  # Break out of the for loop  
  ##############################################################################
  def __makedirs( self, path, stdout = False ):
    '''A private method to try to make parent directory for log files'''
    errFMT = 'Error making path to {} file: {}. Using default logging';         # Format for logging error
    if stdout:                                                                  # If stdout True
      errFMT = errFMT.format('stdout','{}');                                    # Update errFMT with stdout in first entry
    else:                                                                       # Else, must be stderr
      errFMT = errFMT.format('stderr','{}');                                    # Update errFMT with stderr in first entry

    dir = os.path.dirname( path );                                              # Get the directory name
    if not os.path.isdir( dir ):                                                # If the directory does NOT exist
      try:                                                                      # Try to...
        os.makedirs( dir );                                                     # Make the directory tree
      except:                                                                   # On exception; likely no write permissions on dst
        self.log.warning( 
          self._logFMT.format( self.__n, self.__nProcs, errFMT.format(path) ) 
        );                                                                      # Log information
        return False;                                                           # Return False
    return True;                                                                # Return True
  ##############################################################################
  @property
  def cpulimit(self):
    return self.__cpulimit;                                                     # return _cpulimit
  @cpulimit.setter
  def cpulimit(self, value):
    self.__cpulimit = 75 if (value is None) else int(value);                    # Set _cpulimit to defulat if value if value is None, else set to integer of value
  ##############################################################################
  @property
  def threads(self):
    return self.__threads;                                                      # return _threads
  @threads.setter
  def threads(self, value):
    self.__threads = nthreads if (value is None) else int(value);               # Set _threads to default if value is None, else set to integer of value
    if self.__threads < 1: self.__threads = 1;                                  # If _threads is less than one (1), set to one (1)
  ##############################################################################
  @property
  def interval(self):
    return self.__interval;                                                     # return _cpulimit
  @interval.setter
  def interval(self, value):
    self.__interval = 0.5 if (value is None) else float(value);                 # Set _interval to default if value is None, else set to float of value
    if self.__interval < 0.01: self.__interval = 0.01;                          # If _interval is less than 0.01, set to 0.01
  ##############################################################################
  @property
  def returncodes(self):
    return self.__returncodes;                                                  # return _cpulimit
