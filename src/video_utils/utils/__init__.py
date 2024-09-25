"""
Various utilities to aid in processing

Tons of different utilities to aid in the conversion/manipulation of video
files.

"""
import logging

from threading import Lock, Event
from multiprocessing import cpu_count

MAXTHREADS = cpu_count()
MINTHREADS = 1

HALFTHREADS = max(MAXTHREADS // 2, 1)

_sigintEvent = Event()
_sigtermEvent = Event()


def _handle_sigint(*args, **kwargs):
    log = logging.getLogger(__name__)
    _sigintEvent.set()
    log.error('Caught interrupt...')


def _handle_sigterm(*args, **kwargs):
    log = logging.getLogger(__name__)
    _sigtermEvent.set()
    log.error('Caught terminate...')


def isRunning(**kwargs):
    """Check for SIGINT or SIGTERM encountered"""

    key = 'timeout'
    if key in kwargs:
        return not (
            _sigintEvent.wait(timeout=kwargs[key])
            or _sigtermEvent.wait(timeout=kwargs[key])
        )

    return (not _sigintEvent.is_set()) and (not _sigtermEvent.is_set())


def thread_check(val: int | None) -> int | None:
    """
    Check requested number of threads

    Check that requested number of threads is integer type and is
    within allowable range

    """

    if not isinstance(val, int):
        return MAXTHREADS

    if val < MINTHREADS:
        return MINTHREADS

    if val > MAXTHREADS:
        return MAXTHREADS

    return val


class NLock:
    """
    Semaphore-like class that allows acquire to decrement by arbitrary number

    This class is designed to mimic a semaphore object, with the aquried
    and release methods decrementing and incrementing, respectively, an
    internal counter. The difference is that the acquire and release methods
    can be passed a 'threads' value to increment/decrement by a number larget
    than one (1). This allows locking for processes that require more than one
    thread to run.

    Note:
        This is not perfect and, because of how events are 'queued', more
        threads than specified could start. For example, say 2 threads are
        allowed in the NLock object:
        code-block::

           LOCK = NLock(2)

        Now, image two (2) processes, each requiring one (1) thread, acquire
        the lock
        code-block::

           if LOCK.acquire( threads = 1 ):
             ...process1...
           if LOCK.acquire( threads = 1 ):
             ...process2...

        While those are running, say a third (3rd) process that requries
        two (2) threads tries to get the lock
        code-block::

            if LOCK.acquire( threads = 2 ):
              ...process3...

        Now, this call to acquire() for process3 will block, but only until
        one (1) of the single threaded processes finish (process1 or process2).
        Say process1 is very long running and process2 is fairly short.
        In this case, process2 will finish, releasing the lock, allowing
        process3 to start.

        The issue in this case is that the NLock object has now allowed
        three (3) threads to run instead of only allowing two (2).

        This issue will only be encountered if acquire is called with varying
        thread counts.

    """

    __n = 0
    __threads = 0

    def __init__(self, threads=None):
        self.log = logging.getLogger(__name__)
        self.__lock1 = Lock()
        self.__lock2 = Lock()
        self.threads = threads

    @property
    def n(self):
        """Count of threads trying to acquire lock"""

        return self.__n

    @n.setter
    def n(self, val):

        self.__set_n(val)

    @property
    def threads(self):
        """Number of thread acquires allowed"""

        return self.__threads

    @threads.setter
    def threads(self, val):

        self.__set_threads(val)

    @classmethod
    def __set_threads(cls, val):

        cls.__threads = thread_check(val)

    @classmethod
    def __set_n(cls, val):

        cls.__n = val

    def __enter__(self, *args, **kwargs):
        self.acquire(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        self.release(*args, **kwargs)

    def locked(self):
        """Returns True if locked, False otherwise"""

        return self.__lock2.locked()

    def acquire(self, *args, **kwargs):
        """
        Allows for n grabs to lock

        Alows for n grabs to lock before it will block. For example,
        say n = 10, then the acquire() can be called 10 times before it
        will block. Just as with threading.Lock.acquire(), it will block
        forever unless keywords are passed

        Arguments:
            *args: Accepts all inputs from threading.Lock.aquire()

        Keyword arguments:
            threads (int): Specifies the number of 'locks' to acquire.
                default 1.
                When using this class to block number of processes,
                this is used when a process will use more than one
                thread.
            **kwargs: All other keywords for threading.Lock.aquire()

        Returns:
            bool: True if lock acquired, False otherwise

        """

        threads = kwargs.pop('threads', None)
        if not isinstance(threads, int):
            threads = 1
        threads = max(threads, 1)

        self.log.debug(
            "Acquiring '%d' threads from lock; %d of %d already acquired",
            threads,
            self.n,
            self.threads,
        )

        # Increment number of locks to grab
        with self.__lock1:
            self.n += threads
            check = self.n >= self.threads

        self.log.debug("Check value is '%s', attempting to grab lock2", check)
        # If check is true and fail to acqurie the lock
        if check and not self.__lock2.acquire(*args, **kwargs):
            with self.__lock1:
                self.n -= threads  # Decement n grabs
            self.log.debug("Failed to acquire lock2")
            return False

        self.log.debug("Acquired lock2")
        return True

    def release(self, threads=None):
        """
        This method acts the same as a normal threading.Lock.release()

        Arguments:
            None

        Keyword arguments:
            threads (int): Specifies the number of 'locks' to release.
                default 1.
                When using this class to block number of processes,
                this is used when a process will use more than one
                thread.
        Returns:
            None

        """

        # Get lock1 to ensure no other process changes __n
        with self.__lock1:
            if not isinstance(threads, int):
                threads = 1
            threads = max(threads, 1)

            self.log.debug(
                "Releasing %d threads from lock; %d of %d already acquired",
                threads,
                self.n,
                self.threads,
            )

            # Decrement __n by threads
            self.n -= threads
            # If lock2 is locked
            if self.__lock2.locked():
                self.log.debug("Releasing lock 2")
                self.__lock2.release()
