"""
Scheduler for multiple subprocesses

Classes to support scheduling of multiple subprocesses so that not
too many threads/processes are consumed on machine.

"""

import logging
import os
import time
import atexit
from subprocess import Popen, STDOUT, DEVNULL
from queue import Queue
from threading import Thread, Event

from .check_cli import check_cli
from .import NLock, thread_check
from . import isRunning, _sigtermEvent

TIMEOUT = 1.0
PROCLOCK = NLock()

try:
    CPULIMIT = check_cli('cpulimit')
except:
    logging.getLogger(__name__).warning(
        'cpulimit NOT found! Cannot limit CPU usage!'
    )
    CPULIMIT = None


def make_dirs(path):
    """
    Try to make all directories in input path

    Arguments:
        path (str): Path to file

    Keyword arguments:
        None

    Returns:
        bool: True if directory(ies) created, False otherwise

    """

    dirname = os.path.dirname(path)
    if os.path.isdir(dirname):
        return True

    try:
        os.makedirs(dirname)
    except:
        return False
    return True


class PopenThread(Thread):
    """
    Wrapper class for subprocess.Popen that allows starting process in future

    This class is designed to allow for starting a subprocess.Popen instance
    in the future by initializing the Popen instance within the Thread.run
    method. Thus, the subprocess does not start until the Thread.start method
    is called.

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
            threads (int): Specify number of threads the subprocess will use;
                default is one (1)
            **kwargs: All keyword arguments accepted by subprocess.Popen.

        Returns:
            A PopenThread instance

        """

        super().__init__()
        self.__log = logging.getLogger(__name__)
        self._cpulimit = kwargs.pop('cpulimit', None)
        threads = kwargs.pop('threads', None)
        self._threads = thread_check(threads)
        self._args = args
        self._kwargs = kwargs
        self._returncode = None
        self._proc = None
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

        if not self._proc:
            return None

        code = self._proc.poll()
        if code is not None:
            self._returncode = code
        return code

    def start_wait(self, timeout=None):
        """
        Wait for subprocess to start

        Waits for global NLOCK to be acquried

        Keyword arguments:
            timeout (float) : Time (in seconds) to wait for process to
                start. If None, will block forever.

        Returns:
            bool : True if process started, False if failed or timed out

        """

        return self._proc_started.wait(timeout=timeout)

    def wait(self, timeout=None):
        """Wait for subprocess to finish; see subprocess.Popen()"""

        # Make sure thread is started
        self.start_wait()
        self.join(timeout=timeout)
        return not self.is_alive()

    def kill(self):
        """Kill the subprocess; see subprocess.Popen()"""

        if self._proc:
            self._proc.terminate()

    def apply_func(self, func, *args, **kwargs):
        """
        Method to apply function to Popen process

        Arguments:
            func: Function to apply to process; Must accept subprocess.Popen
                instance as first argument
            *args: Any other arguments to pass the func

        Keyword arguments:
            **kwargs: Any keywords to pass to func

        Returns:
            bool: True if function applied, False otherwise.

        """

        if self._proc:
            func(self._proc, *args, **kwargs)
            return True
        return False

    def run(self):
        """Overload run method"""

        PROCLOCK.acquire(threads=self._threads)
        # Set _proc_started event after lock is acquired
        self._proc_started.set()
        kwargs = self._kwargs.copy()
        stdout = kwargs.get('stdout', DEVNULL)
        stderr = kwargs.get('stderr', STDOUT)
        encode = kwargs.get('encoding', 'utf8')
        if isinstance(stdout, str) and make_dirs(stdout):
            stdout = open(stdout, mode='w', encoding=encode)
        if isinstance(stderr, str) and make_dirs(stderr):
            stderr = open(stderr, mode='w', encoding=encode)

        kwargs.update(
            {
                'stdout': stdout,
                'stderr': stderr,
                'encoding': encode,
            }
        )
        self.__log.debug('Running command : %s', self._args)
        try:
            self._proc = Popen(*self._args, **kwargs)
        except FileNotFoundError as error:
            self.__log.error(
                'Setting returncode to 127 (command not found): %s',
                error,
            )
            self._returncode = 127
        except Exception as error:
            self.__log.error('Failed to start process: %s', error)
            self._returncode = 256
        else:
            self.__log.debug('Process started')
            limit = self.__cpulimit()
            while isRunning():
                if self.poll() is not None:
                    break
                time.sleep(TIMEOUT)

            # If process still not done; then assume interupt encounterd
            if self.poll() is None:
                self.__log.debug('Terminating process')
                self.kill()
                if limit:
                    limit.terminate()
            elif self.returncode != 0:
                self.__log.warning('Non-zero exit status from process!')
            self._proc.communicate()
            self.poll()

        try:
            kwargs['stdout'].close()
        except:
            pass
        try:
            kwargs['stderr'].close()
        except:
            pass

        PROCLOCK.release(threads=self._threads)

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

        if not (self._proc and CPULIMIT and self._cpulimit):
            return None

        limit = self.threads * self._cpulimit
        cmd = [CPULIMIT, '-p', str(self._proc.pid), '-l', str(limit)]
        try:
            proc = Popen(cmd, stdout=DEVNULL, stderr=STDOUT)
        except:
            self.__log.warning('Failed to start cpu limiting')
        else:
            return proc

        return None


class PopenPool(Thread):
    """Mimic multiprocessing.Pool class, but for subprocess.Popen objects"""

    __threads = 1
    __cpulimit = None

    def __init__(
        self,
        *args,
        threads=None,
        cpulimit=None,
        queueDepth=None,
        **kwargs,
    ):
        """
        Arguments:
            *args: All arguments accepted by threading.Thread

        Keyword arguments:
            threads (int): Number of threads to allow to run at one time
            cpulimit (int): Percentage of CPU to allow each subprocess to use
            queueDepth (int): Number of subprocesses that can be queued before
                the popen_async method blocks
            **kwargs: All keyword arguments accepted by threading.Thread

        Returns:
            A PopenPool instance

        """

        kwargs['daemon'] = kwargs.pop('daemon', True)
        super().__init__(*args, **kwargs)

        self.__log = logging.getLogger(__name__)
        self.__closed = Event()
        if not isinstance(queueDepth, int):
            queueDepth = 50

        self.__thread_queue = Queue(maxsize=queueDepth)
        self.threads = threads
        self.cpulimit = cpulimit

        self.start()

        atexit.register(self.close)

    @property
    def threads(self):
        """Number of threads to all to run at one time"""

        return self.__threads

    @threads.setter
    def threads(self, val):
        self.__set_threads(val)

    @classmethod
    def __set_threads(cls, val):

        cls.__threads = thread_check(val)
        PROCLOCK.threads = cls.__threads

    @property
    def cpulimit(self):
        """Percentage of CPU allowed for each process"""

        return self.__cpulimit

    @cpulimit.setter
    def cpulimit(self, val):
        if CPULIMIT and isinstance(val, int):
            if 0 < val < 100:
                self.__cpulimit = val
            else:
                self.__log.warning(
                    'Invalid value for cpu limit, disabling cpu limiting'
                )
                self.__cpulimit = None

    def close(self):
        """
        Closes the PopenPool, similar to multiprocessing.Pool.close()

        Running this method will disable adding processes to the queue.

        """

        self.__closed.set()

    def wait(self, timeout: int | float | None = None) -> bool:
        """
        Method to wait for all processes in queue to finish

        Arguments:
            None

        Keyword arguments:
            timeout (float): Timeout in seconds

        Returns:
            bool : True if queue is empty, False otherwise;
                will be False on timeout

        """

        endtime = None
        while PROCLOCK.n > 0 or self.__thread_queue.unfinished_tasks > 0:
            # If timeout is not None; i.e., it is set
            if timeout is not None:
                # If endtime is None; i.e., first time through loop
                if endtime is None:
                    endtime = time.monotonic() + timeout
                else:
                    timeout = endtime - time.monotonic()
                    if timeout <= 0.0:
                        break
            # Sleep a default amount of time every loop
            time.sleep(TIMEOUT)
        return PROCLOCK.n == 0

    def popen_async(self, *args, **kwargs):
        """
        A method to asynconously run subprocess.Popen calls

        Arguments:
            *args: All inputs for subprocess.Popen

        Keyword arguments:
            threads (int): Specify the number of threads the process will use.
                Default is one (1)
            **kwargs All keywords for subprocess.Popen

        Returns:
            A PopenPool.PopenThread instance; very similar to subprocess.Popen
                instance

        Note:
            If too many processes are already queued, this method will
                block until some finish.

        """

        if self.__closed.is_set():
            raise Exception('Cannot add process to closed pool')

        kwargs['cpulimit'] = self.cpulimit
        proc = PopenThread(*args, **kwargs)
        self.__thread_queue.put(proc)
        return proc

    def run(self):
        """Handles dequeuing and starting Popen processes."""

        self.__log.debug('PopenPool open')
        thread = None

        # Loop while a terminate has NOT been called
        while not _sigtermEvent.is_set():
            # If PopenThread is None, we will try to get a thread
            # object from the queue
            if thread is None:
                try:
                    # Get first element of threads list queue
                    thread = self.__thread_queue.get(timeout=TIMEOUT)
                except:
                    pass
                else:
                    # Try to run the thread; the _popen method will return
                    # None if the process was started, otherwise return input
                    thread = self._popen(thread)
            else:
                # Try to run the thread; the _popen method will return None
                # if the process was started, otherwise return input
                thread = self._popen(thread)

            # If pool has been closed, no more proesses in list, and no
            # process trying to start, break while loop
            if all((
                self.__closed.is_set(),
                self.__thread_queue.empty(),
                not thread,
            )):
                break

        # While the Queue is not empty
        while not self.__thread_queue.empty():
            _ = self.__thread_queue.get()
            self.__thread_queue.task_done()

        self.__log.debug('PopenPool closed')

    def _popen(self, thread):
        """
        Wrapper to tart PopenThreads

        This method allows for specifying number of threads to .acquire()
        method when trying to obtain the NLOCK

        Arguments:
            thread: A PopenThread object

        Keyword arguments:
            None

        Returns:
            None if the lock acquired and process started.
                thread (input object) if the lock not acqurie and process
                not started.

        """

        # Grab lock specifying theads and with timeout
        if PROCLOCK.acquire(timeout=TIMEOUT, threads=thread.threads):
            # If got lock, start the thread; note that the thread might get
            # stuck as it tries to acquire the lock, but that is fine
            thread.start()
            PROCLOCK.release(threads=thread.threads)

            # Wait for thread to really start; an event in the object will
            # be set after the lock is acquired
            thread.start_wait()
            # Signal that work on dequeued item finished; this will decrement
            # the Queue.unfinished_tasks value
            self.__thread_queue.task_done()

            # Return None to signal thread started
            return None

        # Return thread to signal NOT started
        return thread
