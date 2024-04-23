"""
Watchdog for MakeMKV output

A watchdog is defined that monitors direcory(ies) for files 
output by MakeMKV so that these files can be transcoded and add
to Plex.

"""

import logging
import os
import time
from queue import Queue

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..utils import isRunning

TIMEOUT =  1.0
SLEEP   = 30.0

class BaseWatchdog( FileSystemEventHandler ):
    """
    Base watchdog class for package

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log      = logging.getLogger(__name__)
        # Initialize queue for sending files to converting thread
        self.queue    = Queue()
        # Initialize a watchdog Observer
        self.observer = Observer()

        self.file_ext = None

    def set_file_exts( self, file_ext, default_ext ):
        """
        Get file extension(s) to use
    
        Arguments:
            file_ext (str) : File extenion to defined by user
            default_ext (tuple) : Default file extensions defined
                in code
    
        Returns:
            tuple : File extensions for valid files
    
        """

        if file_ext is None:
            self.file_ext = default_ext
        elif isinstance(file_ext, str):
            self.file_ext = (file_ext,)
        elif isinstance(file_ext, list):
            self.file_ext = tuple(file_ext)
        else:
            self.file_ext = file_ext

    def on_created(self, event):
        """
        Method to handle events when file is created.

        Arguments:
            event () : Watchdog event

        Returns:
            None.

        """

        if event.is_directory:
            return
        if event.src_path.endswith( self.file_ext ):
            self.queue.put( event.src_path )
            self.log.debug( 'New file added to queue : %s', event.src_path )

    def on_moved(self, event):
        """
        Method to handle events when file is created.

        Arguments:
            event () : Watchdog Event

        Returns:
            None.

        """

        if event.is_directory:
            return
        if event.dest_path.endswith( self.file_ext ):
            self.queue.put( event.dest_path )
            self.log.debug( 'New file added to queue : %s', event.dest_path )

    def join(self):
        """Method to wait for the watchdog Observer to finish."""

        self.observer.join()

    def _check_size(self, fpath):
        """
        Method to check that file size has stopped changing

        Arguments:
            fpath (str): Full path to a file

        Keyword arguments:
            None

        Returns:
            None

        """

        self.log.debug( 'Waiting for file to finish being created : %s', fpath )
        prev = -1

        try:
            curr = os.stat(fpath).st_size
        except Exception as err:
            self.log.debug( "Failed to get file size : %s", err )
            return False

        # While sizes differ and isRunning()
        while (prev != curr) and isRunning():
            time.sleep(SLEEP)
            prev = curr
            try:
                curr = os.stat(fpath).st_size
            except Exception as err:
                self.log.debug( "Failed to get file size : %s", err )
                return False

        if not isRunning():
            return False

        return prev == curr

    def _run(self):
        """
        A thread to dequeue video file paths and convert them

        Arguments:
            None

        Keywords:
            **kwargs

        Returns:
            None

        """

        while isRunning():
            try:
                fpath = self.queue.get( timeout = TIMEOUT )
            except:
                continue

            self._process( fpath )
            self.queue.task_done()

        self.log.info('MakeMKV watchdog stopped!')
        self.observer.stop()

    def _process(self, fpath):
        """
        Process a file

        This method should be overridden in subclasses to
        process a file.

        Arguments:
            fpath (str) : File to process

        Returns:
            None.

        """
