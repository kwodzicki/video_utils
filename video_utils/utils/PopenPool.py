import logging
import time
from subprocess import Popen, STDOUT, DEVNULL 
from queue import Queue
from threading import Thread, Lock, Event
from multiprocessing import cpu_count
from .checkCLI import checkCLI
from .. import isRunning

THREADS = cpu_count() // 2
TIMEOUT = 1.0

try:
  CPULIMIT = checkCLI( 'cpulimit' )
except:
  logging.getLogger(__name__).warning(
    'cpulimit NOT found! Cannot limit CPU usage!'
  )
  CPULIMIT = None


########################################################################################
class NLock( object ):                                                          
  __n       = 0                                                                    
  __threads = 0                                                                    
  def __init__(self, threads = THREADS):                                                 
    self.__lock1 = Lock()                                                       
    self.__lock2 = Lock()                                                       
    self.threads = threads                                                         
                                                                                
  @property                                                                     
  def n(self):                                                                  
    return self.__n                                                             
                                                                                
  @property                                                                     
  def threads(self):                                                               
    return self.__threads                                                          
  @threads.setter                                                                  
  def threads(self, val):                                                          
    if isinstance(val, int):                                                    
      with self.__lock1:                                                        
        self.__threads = 1 if (val < 1) else val                                   
                                                                                
  def __enter__(self, *args, **kwargs):                                         
    self.acquire( *args, **kwargs )                                             
                                                                                
  def __exit__(self, *args, **kwargs):                                          
    self.release(*args, **kwargs)                                               

  def locked(self):
    return self.__lock2.locked()
                                                                                
  def acquire(self, *args, **kwargs):                                           
    ''''
    Purpose:
      This method acts the same as a normal Lock.acquire(), however,
      it allows for n grabs to lock, and will block only when too many
      acquires called.
    Inputs:
      Accepts all inputs from Lock.aquire()
    Keywords:
      threads : Specifies the number of 'locks' to acquire; default 1.
                 When using this class to block number of processes,
                 this is used when a process will use more than one
                 thread.
      All other keywords for Lock.aquire()
    Returns:
      True if lock acquire, False if not
    ''' 
    threads = kwargs.pop('threads', 1)                                                  # Get threads keyword for number of processes to reserver, default is 1                                                             
 
    with self.__lock1:                                                          
      self.__n += threads                                                               # Increment number of locks to grab
      check     = self.__n >= self.__threads                                       
    if check and not self.__lock2.acquire(*args, **kwargs):                             # If check is true and fail to acqurie the lock 
      with self.__lock1:                                                                # Grab lock for n grabs
        self.__n -= threads                                                             # Decement n grabs
      return False                                                                      # Return false
    return True                                                                         # Return True; this happens when (check == False) or (check == True) and (grabbed lock)

  def release(self, threads = 1):
    ''''
    Purpose:
      This method acts the same as a normal Lock.release()
    Inputs:
      None.
    Keywords:
      threads : Specifies the number of 'locks' to release; default 1.
                 When using this class to block number of processes,
                 this is used when a process will use more than one
                 thread.
    Returns:
      None
    ''' 
    with self.__lock1:                                                          
      self.__n -= threads 
      if self.__lock2.locked():                                                 
        self.__lock2.release()                                                  
                                
########################################################################################
PROCLOCK = NLock()                                                                      # Initialize NLock for use in all classes

########################################################################################
class PopenThread( Thread ):
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.__log     = logging.getLogger(__name__)
    self._threads  = kwargs.pop('threads',     1)
    self._cpulimit = kwargs.pop('cpulimit', None)
    self._args     = args
    self._kwargs   = kwargs
    self._proc     = None

  @property
  def threads(self):
    return self._threads

  @property
  def returncode(self):
    if self._proc:
      return self._proc.returncode
    return None

  def poll(self):
    if self._proc:
      return self._proc.poll()
    return None

  def applyFunc(self, func, *args, **kwargs):
    '''
    Purpose:
      Method to apply function to Popen process
    Inputs:
      func  : Function to apply to process; Must accept subprocess.Popen
              instance as first argument
      Any other arguments to pass the func
    Keywords:
      Any keywords to pass to func
    Returns:
    '''
    if self._proc:
      func( self._proc, *args, **kwargs )
      return True
    return False

  def run(self):
    '''Overload run method'''
    try:
      self._proc = Popen( *self._args, **self._kwargs )                                 # Start the process
    except Exception as err:
      self.__log.error( 'Failed to start process: {}'.format(err) )
    else:
      self.__log.debug('Process started')
      limit = self.__cpulimit( )                                                        # Maybe cpulimit
      while isRunning():                                                                # While not interupts
        if self._proc.poll() is None:                                                   # If process not done
          time.sleep( TIMEOUT )                                                         # Sleep
        else:                                                                           # Else
          break                                                                         # Break while loop
      if self._proc.poll() is None:                                                     # If process still not done; then assume interupt encounterd
        self.__log.debug('Terminating process')                                         # Log debug info
        self._proc.terminate()                                                          # Terminate process
        if limit: limit.terminate()                                                     # Maybe termiate cpulimit
      elif self._proc.returncode != 0:
        self.__log.warning('Non-zero exit status from process!')
    PROCLOCK.release( threads = self._threads )                                         # Release lock

  def __cpulimit(self):
    '''
    Purpose:
      Method to apply cpulimit CLI to process
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      Popen instance for cpulimit if started, else None
   '''
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
  __threads  =    1
  __cpulimit = None
  def __init__(self, threads = THREADS, cpulimit = 75, queueDepth = 50, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__log        = logging.getLogger(__name__)
    self.__closed     = Event()
    self.__threadQueue = Queue( maxsize = queueDepth )
    self.threads      = threads
    self.cpulimit     = cpulimit
    self.start()

  @property
  def threads(self):
    return self.__threads
  @threads.setter
  def threads(self, val):
    if isinstance(val, int):
      val = val if val > 0 else 1
      self.__threads   = val
      PROCLOCK.threads = val

  @property
  def cpulimit(self):
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
    '''
    Sets the private 'closed' threading.Event()
    Running this method will disable adding processes
    to the queue
    '''
    self.__closed.set()

  def Popen_async(self, *args, **kwargs):
    '''
    Purpose:
      A method to asynconously run subprocess.Popen calls
    Inputs:
      All inputs for subprocess.Popen
    Keywords:
      threads : Specify the number of threads the process will use.
                Default is one (1)
      All keywords for subprocess.Popen
    Returns:
      A PopenPool.PopenThread instance; very similar to subprocess.Popen instance

    Note that if too many processes are already queued, this method will block
    until some finish.
    '''
    if self.__closed.is_set():                                                          # If closed is set
      raise Exception('Cannot add process to closed pool')                              # Raise exception
    kwargs['cpulimit'] = self.cpulimit                                                  # Set cpulimit in kwargs dictionary
    proc = PopenThread(*args, **kwargs)                                                 # Create PopenThread instance
    self.__threadQueue.put( proc )                                                      # Add instance to queue
    return proc                                                                         # Return instance

  def run(self):
    '''
    Method to run as thread that handles dequeuing and starting 
    Popen processes.
    '''
    self.__log.debug('PopenPool open')
    thread = None                                                                       # Initialize thread as None
    while isRunning():                                                                  # Loop forever
      if thread is None:                                                                # If PopenThread is None, we will try to get a thread object from the queue
        try:                                                                            # Try to get left most element from queue list
          thread = self.__threadQueue.get(timeout=TIMEOUT)                              # Get first element of threads list queue
        except:
          pass         
        else:
          thread = self._Popen( thread )                                                # Try to run the thread
      else:
        thread = self._Popen( thread )                                                  # Try to run the thread
      if self.__closed.is_set() and self.__threadQueue.empty() and not thread:          # If pool has been closed, no more proesses in list, and no process trying to start, break while loop
        break
    while not self.__threadQueue.empty():
      _ = self.__threadQueue.get()
      self.__threadQueue.task_done()

    self.__log.debug('PopenPool closed')

  def _Popen(self, thread):
    '''
    Purpose:
      Method for starting PopenThreads that allows for specifying
      number of threads to .acquire() method
    Inputs:
      thread  : A PopenThread object
    Keywords:
      None.
    Returns:
      None if the lock acquired and process started.
      thread if the lock not acqurie and process not started
    '''
    if PROCLOCK.acquire(timeout = TIMEOUT, threads = thread.threads):                   # Grab lock specifying theads and with timeout
      thread.start()                                                                    # If got lock, start the thread
      self.__threadQueue.task_done()                                                    # Signal that work on dequeued item finished
      return None                                                                       # Return None to signal thread started
    return thread                                                                       # Return thread to signal NOT started

