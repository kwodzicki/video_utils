import logging
import os, time
import atexit
from subprocess import Popen, STDOUT, DEVNULL 
from queue import Queue
from threading import Thread, Lock, Event
from .checkCLI import checkCLI
from .threadCheck import threadCheck
from .. import isRunning, _sigtermEvent

TIMEOUT = 1.0

try:
  CPULIMIT = checkCLI( 'cpulimit' )
except:
  logging.getLogger(__name__).warning(
    'cpulimit NOT found! Cannot limit CPU usage!'
  )
  CPULIMIT = None

def makeDirs( path ):
  """
  Try to make all directories in input path

  Arguments:
    path (str): Path to file

  Keyword arguments:
    None

  Returns:
    bool: True if directory(ies) created, False otherwise

  """

  dirName = os.path.dirname(path)
  try:
    os.makedirs( dirName )
  except:
    pass
  return os.path.isdir( dirName )

########################################################################################
class NLock( object ):                                                          
  """
  Semaphore-like class that allows acquire to decrement by arbitrary number

  This class is designed to mimic a semaphore object, with the aquried and release
  methods decrementing and incrementing, respectively, an internal counter. The
  difference is that the acquire and release methods can be passed a 'threads'
  value to increment/decrement by a number larget than one (1). This allows
  locking for processes that require more than one thread to run.

  Note:
    This is not perfect and, because of how events are 'queue', more
    threads than specified could start. For example, say 2 threads are allowed
    in the NLock object:
    code-block::

       LOCK = NLock(2)

    Now, image two (2) processes, each requiring one (1) thread, acquire the lock
    code-block::

       if LOCK.acquire( threads = 1 ):
         ...process1...
       if LOCK.acquire( threads = 1 ):
         ...process2...

    While those are running, say a third (3rd) process that requries two (2) threads
    tries to get the lock
    code-block::

        if LOCK.acquire( threads = 2 ):
          ...process3...

    Now, this call to acquire() for process3 will block, but only until one (1)
    of the single threaded processes finish (process1 or process2). Say process1
    is very long running and process2 is fairly short. In this case, process2
    will finish, releasing the lock, allowing process3 to start.

    The issue in this case is that the NLock object has now allowed three (3) threads 
    to run instead of only allowing two (2).

    This issue will only be encountered if acquire is called with varying thread
    counts.

  """

  __n       = 0                                                                    
  __threads = 0                                                                    
  def __init__(self, threads = None):                                                 
    self.__lock1 = Lock()                                                       
    self.__lock2 = Lock()                                                       
    self.threads = threads 

  @property                                                                     
  def n(self):                                                                  
    """Count of threads trying to acquire lock"""

    return self.__n                                                             
                                                                                
  @property                                                                     
  def threads(self):                                                               
    """Number of thread acquires allowed"""

    return self.__threads
                                        
  @threads.setter                                                                  
  def threads(self, val):                                                          
    self.__threads = threadCheck( val ) 

  def __enter__(self, *args, **kwargs):                                         
    self.acquire( *args, **kwargs )                                             
                                                                                
  def __exit__(self, *args, **kwargs):                                          
    self.release(*args, **kwargs)                                               

  def locked(self):
    """Returns True if locked, False otherwise"""

    return self.__lock2.locked()
                                                                                
  def acquire(self, *args, **kwargs):                                           
    """
    Similar to threading.Lock.acquire(), however, allows for n grabs to lock

    Alows for n grabs to lock before it will block. For example, say n = 10, then
    the acquire() can be called 10 times before it will block. Just as with 
    threading.Lock.acquire(), it will block forever unless keywords are passed

    Arguments:
      *args: Accepts all inputs from threading.Lock.aquire()

    Keyword arguments:
      threads (int): Specifies the number of 'locks' to acquire; default 1.
                 When using this class to block number of processes,
                 this is used when a process will use more than one
                 thread.
      **kwargs: All other keywords for threading.Lock.aquire()

    Returns:
      bool: True if lock acquired, False otherwise

    """

    threads = kwargs.pop('threads', None)                                                  # Get threads keyword for number of processes to reserver, default is 1 
    if not isinstance(threads, int):
      threads = 1
    elif threads < 1:
      threads = 1

    with self.__lock1:                                                          
      self.__n += threads                                                               # Increment number of locks to grab
      check     = self.__n >= self.__threads                                       
    if check and not self.__lock2.acquire(*args, **kwargs):                             # If check is true and fail to acqurie the lock 
      with self.__lock1:                                                                # Grab lock for n grabs
        self.__n -= threads                                                             # Decement n grabs
      return False                                                                      # Return false
    return True                                                                         # Return True; this happens when (check == False) or (check == True) and (grabbed lock)

  def release(self, threads = None):
    """
    This method acts the same as a normal threading.Lock.release()

    Arguments:
      None

    Keyword arguments:
      threads (int): Specifies the number of 'locks' to release; default 1.
                 When using this class to block number of processes,
                 this is used when a process will use more than one
                 thread.
    Returns:
      None

    """

    with self.__lock1:                                                                  # Get lock1 to ensure no other process changes __n 
      if not isinstance(threads, int):                                                  # If threads is NOT an integer instance
        threads = 1                                                                     # Set threads to 1
      elif threads < 1:                                                                 # Else, if threads is less than 1
        threads = 1                                                                     # Set threads to 1
      self.__n -= threads                                                               # Decrement __n by threads
      if self.__lock2.locked():                                                         # If lock2 is locked 
        self.__lock2.release()                                                          # Then release it
                                
########################################################################################
PROCLOCK = NLock()                                                                      # Initialize NLock for use in all classes

########################################################################################
class PopenThread( Thread ):
  """
  Wrapper class for subprocess.Popen that allows starting process in future

  This class is designed to allow for starting a subprocess.Popen instance in
  the future by initializing the Popen instance within the Thread.run method.
  Thus, the subprocess does not start until the Thread.start method is called.

  Note:
    The thread will run until the subprocess finishes, fails, or is killed

  """

  def __init__(self, *args, **kwargs):
    """
    Initialize the PopenThread instance

    Arguments:
      *args: All arguments accepted by subprocess.Popen

    Keywords arguments:
      cpulimit (int): Percentage of CPU to all the subprocess to use
      threads (int): Specify number of threads the subprocess will use; default is one (1)
      **kwargs: All keyword arguments accepted by subprocess.Popen.

    Returns:
      A PopenThread instance

    """

    super().__init__()
    self.__log         = logging.getLogger(__name__)
    self._cpulimit     = kwargs.pop('cpulimit', None)
    threads            = kwargs.pop('threads',  None) 
    self._threads      = threadCheck( threads )
    self._args         = args
    self._kwargs       = kwargs
    self._returncode   = None
    self._proc         = None
    self._proc_started = Event()

  @property
  def threads(self):
    """Number of threads this process requries"""

    return self._threads

  @property
  def returncode(self):
    """Return code of subprocess; see subprocess.Popen()"""

    return self._returncode

  def poll(self):
    """Poll subprocess to see if finished; see subprocess.Popen()"""

    if self._proc:                                                                      # If process
      code = self._proc.poll()                                                          # Poll the process
      if code is not None:                                                              # If return value is not None
        self._returncode = code                                                         # Set return code
      return code                                                                       # Return return code
    return None                                                                         # Return None; only makes it here if not _proc

  def startWait(self, timeout = None):
    """Wait for subprocess to start; waits for global NLOCK to be acquried"""

    return self._proc_started.wait( timeout = timeout )

  def wait(self, timeout = None):
    """Wait for subprocess to finish; see subprocess.Popen()"""

    self.startWait()                                                                    # Make sure thread is started
    self.join( timeout = timeout )
    return not self.is_alive()

  def kill(self):
    """Kill the subprocess; see subprocess.Popen()"""

    if self._proc:
      self._proc.terminate()

  def applyFunc(self, func, *args, **kwargs):
    """
    Method to apply function to Popen process

    Arguments:
      func: Function to apply to process; Must accept subprocess.Popen instance as first argument
      *args: Any other arguments to pass the func

    Keyword arguments:
      **kwargs: Any keywords to pass to func

    Returns:
      bool: True if function applied, False otherwise.

    """

    if self._proc:
      func( self._proc, *args, **kwargs )
      return True
    return False

  def run(self):
    """Overload run method"""

    PROCLOCK.acquire( threads = self._threads )                                         # Acquire lock
    self._proc_started.set()                                                            # Set _proc_started event after lock is acquired
    kwargs = self._kwargs.copy()                                                        # Get copy of keyword arguments; don't want to change the originals
    stdout = kwargs.get('stdout', DEVNULL)                                              # Get the stdout keyword, use DEVNULL as default
    stderr = kwargs.get('stderr', STDOUT)                                               # Get the stderr keyword, use STDOUT as default

    if isinstance(stdout, str):                                                         # If stdout is str instance, assume is file path
      if makeDirs( stdout ):                                                            # If make directory for stdout file
        stdout = open(stdout, 'w')                                                      # Open file for writing
    if isinstance(stderr, str):                                                         # Same as above but for stderr
      if makeDirs( stderr ):
        stderr = open(stderr, 'w')

    kwargs.update( {'stdout' : stdout, 'stderr' : stderr} )                             # Update the stdout and stderr keywords
    try:                                                                                # Try to start the process
      self._proc = Popen( *self._args, **kwargs )                                       # Start the process
    except FileNotFoundError as err:                                                    # On command not exist error
      self.__log.error(f'Setting returncode to 127 (command not found): {err}')         # Log error
      self._returncode = 127                                                            # Set return code to 127; standard "command not found" value
    except Exception as err:                                                            # On exception
      self.__log.error(f'Failed to start process: {err}')                               # Log error
      self._returncode = 256                                                            # Set to out-of-range code on any other error
    else:                                                                               # On sucess
      self.__log.debug('Process started')                                               # Inform that process running
      limit = self.__cpulimit( )                                                        # Maybe cpulimit
      while isRunning():                                                                # While not interupts
        if self.poll() is None:                                                         # If process not done
          time.sleep( TIMEOUT )                                                         # Sleep
        else:                                                                           # Else
          break                                                                         # Break while loop
      if self.poll() is None:                                                           # If process still not done; then assume interupt encounterd
        self.__log.debug('Terminating process')                                         # Log debug info
        self.kill()                                                                     # Terminate process
        if limit: limit.terminate()                                                     # Maybe termiate cpulimit
      elif self.returncode != 0:
        self.__log.warning('Non-zero exit status from process!')
      self._proc.communicate()                                                          # Wait for process to finish
      self.poll()                                                                       # Poll one last time to ensure returncode is set

    try:
      kwargs['stdout'].close()
    except:
      pass
    try:
      kwargs['stderr'].close()
    except:
      pass

    PROCLOCK.release( threads = self._threads )                                         # Release lock

  def __cpulimit(self):
    """
    Method to apply cpulimit CLI to process

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      Popen instance for cpulimit if started, else None

    """

    if self._proc and CPULIMIT and self.cpulimit:                                       # If process and cpulimit CLI found and cpulimit set
      limit = self.threads * self.cpulimit                                              # Set the limit as theads*cpulimit
      cmd = [ CPULIMIT, '-p', str( self._proc.pid ), '-l', str(limit) ]                 # Build command
      try:                                                                              # Try to 
        proc = Popen(cmd, stdout = DEVNULL, stderr = STDOUT)                            # Start command; stdout/stderr piped to devnull
      except:
        self.__log.warning('Failed to start cpu limiting')                              # Log warning on exception
      else:
        return proc                                                                     # Return Popen instance if started
    return None                                                                         # Return None as nothing started

########################################################################################
class PopenPool(Thread):
  """Mimic the multiprocessing.Pool class, but for subprocess.Popen objects"""

  __threads  =    1
  __cpulimit = None

  def __init__(self, threads = None, cpulimit = None, queueDepth = None, *args, **kwargs):
    """
    Arguments:
      *args: All arguments accepted by threading.Thread

    Keyword arguments:
      threads (int): Number of threads to allow to run at one time
      cpulimit (int): Percentage of CPU to allow each subprocess to use
      queueDepth (int): Number of subprocesses that can be queued before the Popen_async method blocks
      **kwargs: All keyword arguments accepted by threading.Thread

    Returns:
      A PopenPool instance

    """

    kwargs['daemon'] = kwargs.pop('daemon', True)                                       # Default to deamon
    super().__init__(*args, **kwargs)
    self.__log         = logging.getLogger(__name__)
    self.__closed      = Event()
    if not isinstance(queueDepth, int): queueDepth = 50
    self.__threadQueue = Queue( maxsize = queueDepth )
    self.threads       = threads
    self.cpulimit      = cpulimit
    self.start()
    atexit.register( self.close )

  @property
  def threads(self):
    """Number of threads to all to run at one time"""

    return self.__threads

  @threads.setter
  def threads(self, val):
    self.__threads = threadCheck( val )
    PROCLOCK.threads = self.__threads

  @property
  def cpulimit(self):
    """Percentage of CPU allowed for each process"""

    return self.__cpulimit

  @cpulimit.setter
  def cpulimit(self, val):
    if CPULIMIT and isinstance(val, int):
      if (val > 0) and (val < 100):
        self.__cpulimit = val
      else:
        self.__log.warning('Invalid value for cpu limit, disabling cpu limiting')
        self.__cpulimit = None

  def close(self):
    """
    Closes the PopenPool, similar to multiprocessing.Pool.close()

    Running this method will disable adding processes to the queue.

    """

    self.__closed.set()

  def wait(self, timeout = None):
    """
    Method to wait for all processes in queue to finish
    
    Arguments:
      None

    Keyword arguments:
      timeout (float): Timeout in seconds

    Returns:
      bool:True if queue is empty, False otherwise; will be False on timeout

    """

    endtime = None                                                                      # Initialize endTime to None
    while PROCLOCK.n > 0 or self.__threadQueue.unfinished_tasks > 0:                    # While process(es) have the lock or there are unfinished tasks from the queue
      if timeout is not None:                                                           # If timeout is not None; i.e., it is set
        if endtime is None:                                                             # If endtime is None; i.e., first time through loop
          endtime = time.monotonic() + timeout                                          # set endtime to current time plus the timeout value; i.e., time in the future
        else:                                                                           # Else, endtime was set in previous loop
          timeout = endtime - time.monotonic()                                          # Compute timeout as endtime - current time
          if timout <= 0.0:                                                             # If timeout is <= 0.0
            break                                                                       # break the while loop
      time.sleep( TIMEOUT )                                                             # Sleep for TIMEOUT seconds
    return PROCLOCK.n == 0                                                              # Return values signifies whether all processes finished; i.e., no processes have the PROCLOCK

  def Popen_async(self, *args, **kwargs):
    """
    A method to asynconously run subprocess.Popen calls

    Arguments:
      *args: All inputs for subprocess.Popen

    Keyword arguments:
      threads (int): Specify the number of threads the process will use.
                Default is one (1)
      **kwargs All keywords for subprocess.Popen

    Returns:
      A PopenPool.PopenThread instance; very similar to subprocess.Popen instance

    Note:
      If too many processes are already queued, this method will block until some finish.

    """

    if self.__closed.is_set():                                                          # If closed is set
      raise Exception('Cannot add process to closed pool')                              # Raise exception
    kwargs['cpulimit'] = self.cpulimit                                                  # Set cpulimit in kwargs dictionary
    proc = PopenThread(*args, **kwargs)                                                 # Create PopenThread instance
    self.__threadQueue.put( proc )                                                      # Add instance to queue
    return proc                                                                         # Return instance

  def run(self):
    """Run as Thread that handles dequeuing and starting Popen processes."""

    self.__log.debug('PopenPool open')
    thread = None                                                                       # Initialize thread as None
    while not _sigtermEvent.is_set():                                                   # Loop while a terminate has NOT been called
      if thread is None:                                                                # If PopenThread is None, we will try to get a thread object from the queue
        try:                                                                            # Try to get left most element from queue list
          thread = self.__threadQueue.get(timeout=TIMEOUT)                              # Get first element of threads list queue
        except:                                                                         # On exception
          pass                                                                          # Pass
        else:                                                                           # Else, we got a thread from the Queue
          thread = self._Popen( thread )                                                # Try to run the thread; the _Popen method will return None if the process was started, otherwise return input
      else:                                                                             # Else, there is already a thread running
        thread = self._Popen( thread )                                                  # Try to run the thread; the _Popen method will return None if the process was started, otherwise return input

      if self.__closed.is_set() and self.__threadQueue.empty() and not thread:          # If pool has been closed, no more proesses in list, and no process trying to start, break while loop
        break

    while not self.__threadQueue.empty():                                               # While the Queue is not empty
      _ = self.__threadQueue.get()                                                      # Pop off a value
      self.__threadQueue.task_done()                                                    # Call task_done()

    self.__log.debug('PopenPool closed')

  def _Popen(self, thread):
    """
    Wrapper to tart PopenThreads

    This method allows for specifying number of threads to .acquire() method when
    trying to obtain the NLOCK

    Arguments:
      thread: A PopenThread object

    Keyword arguments:
      None

    Returns:
      None if the lock acquired and process started.
      thread (input object) if the lock not acqurie and process not started.

    """

    if PROCLOCK.acquire(timeout = TIMEOUT, threads = thread.threads):                   # Grab lock specifying theads and with timeout
      thread.start()                                                                    # If got lock, start the thread; note that the thread might get stuck as it tries to acquire the lock, but that is fine
      PROCLOCK.release(threads = thread.threads)                                        # Release lock
      thread.startWait()                                                                # Wait for thread to really start; an event in the object will be set after the lock is acquired
      self.__threadQueue.task_done()                                                    # Signal that work on dequeued item finished; this will decrement the Queue.unfinished_tasks value
      return None                                                                       # Return None to signal thread started
    return thread                                                                       # Return thread to signal NOT started
