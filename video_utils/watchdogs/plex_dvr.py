"""
Watchdog for Plex DVR recordings

The watchdog class defined here will monitor for new
Plex DVR recordings and re-encode the file AFTER it
is moved to its final location

"""

import logging

import os
import time
from subprocess import run, STDOUT, DEVNULL
from threading import Thread, Timer, Event, Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..config import plex_dvr
from ..utils import isRunning#_sigintEvent, _sigtermEvent
from ..utils.handlers import send_email
from ..plex.dvr_converter import DVRconverter
from ..plex.utils import DVRqueue

RECORDTIMEOUT = 86400.0
TIMEOUT       =     1.0
SLEEP         =     1.0

class PlexDVRWatchdog( FileSystemEventHandler ):
    """Class to watch for, and convert, new DVR recordings"""

    PURGE_INTERVAL = 10800.0

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log         = logging.getLogger(__name__)
        self.log.info('Starting up...')

        self.record_timeout = kwargs.get('recordTimeout', RECORDTIMEOUT)
        # Initialize list to store paths of newly started DVR recordings
        self.recordings    = []
        # Initialize DVRqueue, this is a subclass of list that, when items
        # modified, will save pickled list to file as backup
        self.converting    = DVRqueue( plex_dvr['queueFile'] )

        self.converter = None
        self.script    = kwargs.get('script', None)
        if not self.script:
            self.converter = DVRconverter( **kwargs )

        self.__lock = Lock()
        self.__stop = Event()

        # Initialize a watchdog Observer
        self.__observer  = Observer()
        # Iterate over input arguments
        for arg in args:
            # Add each input argument to observer as directory to watch; recursively
            self.__observer.schedule( self, arg, recursive = True )
        self.__observer.start()# Start the observer

        # Thread for dequeuing files and converting
        self.__run_thread = Thread( target = self.__run )
        self.__run_thread.start()
        # Initialize thread to clean up self.recordings list; thread sleeps
        # for 3 hours inbetween runs
        self.__purge_timer = Timer(
            self.PURGE_INTERVAL,
            self.__purge_recordings,
        )
        self.__purge_timer.start()

    def on_created(self, event):
        """Method to handle events when file is created."""

        # Skip directories
        if event.is_directory:
            return

        # If '.grab' is in the file path, then it is a new recording!
        if '.grab' in event.src_path:
            # Acquire Lock so other events cannot change to_convert list at same time
            with self.__lock:
                # Add split file path (dirname, basename,) AND time
                # (secondsSinceEpoch,) tuples as one tuple to recordings list
                self.recordings.append(
                    os.path.split(event.src_path) + (time.time(),),
                )
            self.log.debug( 'A recording started : %s', event.src_path )
        else:
            # Check if new file is a DVR file (i.e., file has been moved)
            self.check_recording( event.src_path )

    def on_moved(self, event):
        """Method to handle events when file is moved."""

        # If not a directory and the destination file was a recording
        # (i.e.; check_recordings)
        if not event.is_directory:
            self.check_recording( event.dest_path )

    def check_recording(self, fpath):
        """
        A method to check that newly created file is a DVR recording

        Arguments:
            fpath (str): Path to newly created file from event in on_created() method

        Keyword arguments:
            None

        Returns:
            bool: True if file is a recording (i.e., it's just been moved), False otherwise

        """

        # Acquire Lock so other events cannot change to_convert list at same time
        with self.__lock:
            t_start  = time.time()
            _, fname = os.path.split( fpath )
            i        = 0

            # Iterate over all tuples in to_convert list
            while i < len(self.recordings):
                # If the name of the input file matches the name of the
                # recording file
                if self.recordings[i][1] == fname:
                    self.log.debug(
                        'Recording moved from %s --> %s',
                        os.path.join( *self.recordings[i][:2] ),
                        fpath,
                    )
                    # Append to converting list; this will trigger update of queue file
                    self.converting.append( fpath )
                    self.recordings.pop( i )
                    return True
                time_delta = t_start - self.recordings[i][2]
                if time_delta > self.record_timeout:
                    self.log.info(
                        'File is more than %0.0f s old, assuming record failed: %s',
                        time_delta,
                        os.path.join( *self.recordings[i][:2] ),
                    )
                    self.recordings.pop( i )
                else:
                    i += 1
            return False

    def join(self):
        """
        Method to wait for the watchdog Observer to finish.

        The Observer will be stopped when _sigintEvent or _sigtermEvent is set

        """

        self.__observer.join()

    def _check_size(self, fpath, timeout = None):
        """
        Method to check that file size has stopped changing

        Arguments:
            fpath (str): Full path to a file

        Keywords:
            timeout (float): Specify how long to wait for file to transfer.
                Default is forever (None)

        Returns:
            bool: True if file size is NOT changing, False if timeout

        """

        self.log.debug('Waiting for file to finish being created')
        prev  = -1
        curr  = os.path.getsize(fpath)
        t_ref = time.time()
        while (prev != curr) and isRunning():
            if timeout and ((time.time() - t_ref) > timeout):
                return False
            time.sleep( SLEEP )
            prev = curr
            curr = os.path.getsize(fpath)
        return True

    def __pretty_time(self, sec):
        days   = sec  // 86400
        sec   -= days  * 86400
        hours  = sec  //  3600
        sec   -= hours *  3600
        mins   = sec  //    60
        sec   -= mins  *    60
        text   = []
        if days:
            text.append( '%0.0f day%s', days, ('s' if days > 1 else '') )
        if hours or mins or sec:
            text.append( '%02d:%02d:%04.1f', hours, mins, sec )
        return ' '.join( text )

    def __purge_recordings(self):
        """
        Pruge old files

        Remove files from the recordings list that are more than
        self.record_timeout seconds old. 

        Arguments:
            None

        Keyword arguments:
            None

        Returns:
            None

        """

        with self.__lock:
            t_start = time.time()
            i       = 0
            # Iterate over all tuples in to_convert list
            while i < len(self.recordings):
                time_delta = t_start - self.recordings[i][2]
                if time_delta < self.record_timeout:
                    i += 1
                    continue

                fpath = os.path.join( *self.recordings[i][:2] )
                # If file size is NOT chaning
                if self._check_size( fpath, timeout = 5.0 ):
                    self.log.info(
                        'File is more than %s old, assuming record failed: %s',
                        self.__pretty_time( self.record_timeout ),
                        fpath,
                    )
                    self.recordings.pop( i )
                    continue

                self.log.warning(
                    'File is %s old and size is still changing: %s',
                    self.__pretty_time(time_delta),
                    fpath,
                )
                i += 1

        self.__purge_timer = Timer(
            self.PURGE_INTERVAL,
            self.__purge_recordings,
        )
        self.__purge_timer.start()

    def _run_script(self, file):
        """Method to apply custom script to file"""

        self.log.info('Running script : %s', self.script )
        proc = run(
            [self.script, file],
            stdout =DEVNULL,
            stderr =STDOUT,
            check  = False,
        )
        status = proc.returncode
        if status != 0:
            self.log.error( 'Script failed with exit code : %s', status )

    @send_email
    def _process(self, fpath):
        """Actually process a file"""

        try:
            self._check_size( fpath )
        except Exception as err:
            self.log.warning(
                'Error checking file, assuming not exist: Error - %s',
                err,
            )
            return

        if self.script:
            self._run_script( fpath )
        else:
            try:
                _ = self.converter.convert( fpath )
            except:
                self.log.exception('Failed to convert file')

    def __run(self):
        """
        A thread to dequeue video file paths and convert them

        Arguments:
            None

        Keyword arguments:
            None

        Returns:
            None

        """

        while isRunning():
            try:
                fpath = self.converting[0]
            except:
                time.sleep(TIMEOUT)
            else:
                self._process(fpath)
                if isRunning():
                    self.converting.remove( fpath )

        with self.__lock:
            self.__stop.set()

        self.__purge_timer.cancel()
        self.__observer.stop()
        self.log.info('Plex watchdog stopped!')
