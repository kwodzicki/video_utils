"""
To manage multiple/concurrent subprocess

"""

import logging
import os
import time
from subprocess import Popen, STDOUT, DEVNULL
from threading import Thread, Event
from multiprocessing import cpu_count

from .. import _sigintEvent, _sigtermEvent
from ..utils.check_cli import check_cli

nthreads = cpu_count() // 2

try:
    CPULIMITINSTALLED = check_cli( 'cpulimit' )
except:
    logging.getLogger(__name__).warning(
        'cpulimit NOT found! Cannot limit CPU usage!'
    )
    CPULIMITINSTALLED = False
else:
    CPULIMITINSTALLED = True

class SubprocManager( ):
    """
    Manage multiple/conncurent subprocess

    """

    def __init__(self, cpulimit = None, threads = None, interval = None, **kwargs):
        """ 
        Keyword arguments:
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

        """

        super().__init__(**kwargs)
        self.__log         = logging.getLogger(__name__)
        self.cpulimit      = cpulimit
        self.threads       = threads
        self.interval      = interval
        self._log_fmt       = 'Process %3d of %3d - %s'# Format for logging message
        self.__n           =  0# Counter for the process number being run
        self.__n_popen     =  0# Total number of process added
        self.__queue       = []# Empty list to queue process information
        self.__procs       = []# Empty list for Popen handles for process
        self.__returncodes = []
        self.__cpu_procs   = []# Empty list for Popen handles from cpulimit instances
        self.__exit_id     = None
        self.__thread_id   = None# Set __thread_id attribute to None
        self.__run_event   = Event()

    ##############################################################################
    def add_proc(self, args, **kwargs):
        """
        Method for adding a command to the queue

        Arguments:
            args  : same as input to subprocess.Popen

        Keyword arguments:
            single  : Set to True if the process you are controlling is single
                threaded; i.e., it can only ever use one CPU core.
            stdout  : Same as stdout for Popen, however, if you set this to a
                string, it is assumed that this is a file path and
                will pipe all output to file.
            stderr  : Same as for stdout but for all stderr values
            **kwargs: Accepts all subprocess.Popen arguments. Only difference is that
                by default stdout and stderr are piped to DEVNULL

        """

        # Append the Popen info to the queue as a tuple and increment # of process
        self.__queue.append( (args, kwargs,) )
        self.__n_popen += 1

    def run(self, block = True):
        """
        Method to start running the commands in the queue

        Keyword arguments:
            block (bool): Wait for all commands to finish before returning. 
                Default is to wait. Set to False to return right away.
                Returning right away may be useful if you want to add 
                more processes the to process queue. You can then use
                the .wait() method to wait for processes to finish.

        """

        self.__run_event.set()
        self.__returncodes = []# Reset __return codes to empty list
        self.__exit_id     = Thread( target = self.__exit )
        self.__thread_id   = Thread( target = self.__thread )# Initialize Thread class
        self.__exit_id.start()
        self.__thread_id.start()# Start the thread
        # If block (default), wait for processes to complete
        if block:
            self.wait()

    def wait(self, timeout = None):
        """
        Similar to Popen.wait(), however, returns False if timed out

        Keyword arguments:
            timeout : Time, in seconds, to wait for process to finish.

        """

        # If the __thread_id attribute valid; i.e., not None
        if self.__thread_id:
            # Try to join the thread
            self.__thread_id.join(timeout = timeout)
            # If the thread is still alive, then return
            if self.__thread_id.is_alive():
                return False
            # If made here, then thread is dead, remove reference
            self.__thread_id = None
        self.__n_popen = 0
        return True

    def kill(self):
        """Method to kill all running processes"""

        for proc in self.__procs:
            proc[0].terminate()

    def apply_func(self, func, args=None, kwargs=None):
        """
        Apply function to Popen instance

        This method is only applicable when one (1) process running

        Arguments:
            func  : Function to apply

        Keyword arguments:
            args (tuple) : List of arguments, besides Popen instance, to
                apply to function
            kwargs (dict) : keyword arguments to apply to input function

        """

        self.__log.debug('Attempting to apply function to process')
        if args   is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        # If no processes running, sleep for 500 ms to see if one will start
        if len(self.__procs) != 1:
            time.sleep(0.5)

        # If there is NOT one process running
        if len(self.__procs) != 1:
            # Check if no processes running
            if len(self.__procs) == 0:
                self.__log.error('No processes running!')
            else:
                self.__log.error('More than one (1) process running!')
            return False

        # Apply the function to the only running process
        func( self.__procs[0][0], *args, **kwargs )
        return True

    def __thread(self):
        """ 
        Private method for actually running all the process.

        This is done in a thread so that blocking can be disabled; i.e.,
        user can keep adding processes to the queue if they want

        """

        # Ensure the counter is at zero
        self.__n = 0
        # While there are commands in the queue
        while (
                not _sigintEvent.is_set() and
                not _sigtermEvent.is_set() and
                len(self.__queue) > 0
            ):
            # If the number of allowable subprocess are running
            if len(self.__procs) == self.threads:
                self.__proc_check()# Wait for a process to finish
            # Pop off first element of the _queue
            args, kwargs = self.__queue.pop(0)
            # Call method to start a new subprocess
            self.__popen( args, **kwargs )

        # While there are processes running
        while (
                not _sigintEvent.is_set() and
                not _sigtermEvent.is_set() and
                len(self.__procs) > 0
            ):
            self.__proc_check()# Wait for a process to finish

        # Clear the run event so the __exit thread quits
        self.__run_event.clear()
        self.__procs = []

    def __popen( self, args, **kwargs ):
        """
        Method for starting subprocess and applying cpu limiting

        Arguments:
            args  : Same as Popen args

        Keyword arguments:
            **kwargs: All kwargs from Popen

        """

        if _sigintEvent.is_set() or _sigtermEvent.is_set():
            return

        # Increment n by one
        self.__n += 1
        # Pop off the 'single' keyword argument, or get False if not keyword
        single = kwargs.pop('single', False)
        stdout = kwargs.pop('stdout', DEVNULL)
        stderr = kwargs.pop('stderr', STDOUT)

        log_type = 0
        if isinstance(stdout, str):
            if self.__makedirs( stdout, True ):
                log_type += 1
            else:
                stdout = DEVNULL

        if isinstance(stderr, str):
            if self.__makedirs( stderr ):
                log_type += 2
            else:
                stderr = STDOUT

        self.__log.debug( 'Running command : %s', args )
        if log_type == 0:
            proc = Popen( args, stdout=stdout, stderr=stderr, **kwargs )
        elif log_type == 1:
            with open( stdout, 'w' ) as stdout:
                proc = Popen( args, stdout=stdout, stderr=stderr, **kwargs )
        elif log_type == 2:
            with open( stderr, 'w' ) as stderr:
                proc = Popen( args, stdout=stdout, stderr=stderr, **kwargs )
        else:
            with open(stdout, 'w') as stdout, open(stderr, 'w') as stderr:
                proc = Popen( args, stdout=stdout, stderr=stderr, **kwargs )

        self.__log.info( self._log_fmt, self.__n, self.__n_popen, 'Started!' )

        # Append handle and process number tuple to the _procs attribute
        self.__procs.append( (proc, self.__n) )
        if CPULIMITINSTALLED and (self.cpulimit > 0) and (self.cpulimit < 100):
            limit = self.cpulimit if single else self.cpulimit * self.threads
            # limit = '200' if limit > 200 else str( limit )
            # limit = [ 'cpulimit', '-p', str( proc.pid ), '-l', limit ]
            limit = [ 'cpulimit', '-p', str( proc.pid ), '-l', str(limit) ]
            self.__cpu_procs.append(
                Popen(limit, stdout=DEVNULL, stderr=STDOUT)
            )

    ##############################################################################
    def __proc_check(self):
        """Private method to check for finished processes"""

        # While all of the processes are working (remember _procs contains tuples)
        while all( proc[0].poll() is None for proc in self.__procs ):
            time.sleep(self.interval)

        # Iterate over all the process
        for i, info in enumerate(self.__procs):
            # If the process has not finished (remember _procs contains tuples)
            if info[0].returncode is None:
                continue

            # Pop off the (process, #) tuple
            proc, proc_num = self.__procs.pop( i )
            proc.communicate()
            self.__log.info(self._log_fmt, proc_num, self.__n_popen, 'Finished!')
            try:
                cpu_proc = self.__cpu_procs.pop( i )
            except:
                pass
            else:
                cpu_proc.communicate()

            self.__returncodes.append( proc.returncode )
            if proc.returncode != 0:
                self.__log.warning(
                    self._log_fmt, proc_num, self.__n_popen, 'Non-zero returncode!!!',
                )
            return

    def __makedirs( self, fpath, stdout = False ):
        """A private method to try to make parent directory for log files"""

        err_fmt = 'stdout' if stdout else 'stderr'
        err_fmt = f'Error making path to {err_fmt} file: {fpath}. Using default logging'

        fdir = os.path.dirname( fpath )
        if os.path.isdir( fdir ):
            return True

        try:
            os.makedirs( fdir )
        except:
            self.__log.warning(self._log_fmt, self.__n, self.__n_popen, err_fmt)
            return False

        return True

    def __exit(self, *args, **kwargs):
        """ 
        Private method for killing everything (cleanly). 

        Intended to be called when SIGINT or something else occurs

        """
        while self.__run_event.is_set():
            if _sigintEvent.wait(timeout=0.5) or _sigtermEvent.wait(timeout=0.5):
                self.__run_event.clear()
                self.kill()

    @property
    def log_fmt(self):
        """Get log_fmt attribute"""
        return self._log_fmt
    @log_fmt.setter
    def log_fmt(self, value):
        """Update the log_fmt attribute"""
        if isinstance(value, str):
            self._log_fmt = value

    @property
    def cpulimit(self):
        """Get current CPU limit percentage"""
        return self.__cpulimit
    @cpulimit.setter
    def cpulimit(self, value):
        """Set the CPUlimit percentage"""
        self.__cpulimit = 75 if (value is None) else int(value)

    @property
    def threads(self):
        """Get number of threads"""
        return self.__threads
    @threads.setter
    def threads(self, value):
        """Set number of threads"""
        self.__threads = min(
            nthreads if (value is None) else int(value),
            1,
        )

    @property
    def interval(self):
        """Get polling intervale"""
        return self.__interval
    @interval.setter
    def interval(self, value):
        """Set polling interval"""
        interval = 0.5 if (value is None) else float(value)
        interval = min( interval, 0.50 )
        interval = max( interval, 0.01 )
        self.__interval = interval

    @property
    def returncodes(self):
        """Get process returncodes"""
        return self.__returncodes
