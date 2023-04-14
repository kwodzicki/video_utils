"""
Watchdog for MakeMKV output

A watchdog is defined that monitors direcory(ies) for files 
output by MakeMKV so that these files can be transcoded and add
to Plex.

"""

import logging

import os
import time

from threading import Thread
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from . import isRunning
from .videoconverter import VideoConverter
from .plex.plex_media_scanner import plex_media_scanner
from .utils.handlers import send_email

TIMEOUT =  1.0
SLEEP   = 30.0

class MakeMKV_Watchdog( FileSystemEventHandler ):
    """
    Watchdog for conversion of MakeMKV output

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log         = logging.getLogger(__name__)
        self.log.info('Starting up...')

        # Try to get file_ext keyword from keyword dictionary
        file_ext   = kwargs.pop('fileExt', None)
        # Sets watchdog to recursive
        recursive = kwargs.pop('recursive', False)

        if file_ext is None:
            self.file_ext = ('.mkv',)
        elif isinstance(file_ext, str):
            self.file_ext = (file_ext,)
        elif isinstance(file_ext, list):
            self.file_ext = tuple(file_ext)
        else:
            self.file_ext = file_ext

        self.converter = VideoConverter( **kwargs )

        # Initialize queue for sending files to converting thread
        self.queue    = Queue()
        # Initialize a watchdog Observer
        self.observer = Observer()

        # Iterate over input arguments
        for arg in args:
            self.observer.schedule( self, arg, recursive=recursive )
            # Iterate over all files (if any) in the input directory
            # Enque to the list
            for fpath in self._get_dir_listing( arg ):
                self.queue.put( fpath )

        self.observer.start()

        self.__run_thread = Thread( target = self._run )
        self.__run_thread.start()

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

    def _get_dir_listing(self, root):
        """
        Get list of files in a directory (non-recursive), that ends with given extension

        Arguments:
            root (str): Path of directory to search

        Keyword arguments:
            None 

        Returns:
            list: Files

        """

        fpaths = []
        for item in os.listdir(root):
            if not item.endswith( self.file_ext ):
                continue
            fpath = os.path.join( root, item )
            if os.path.isfile( fpath ):
                fpaths.append( fpath )

        return fpaths

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

    @send_email
    def _process(self, fname):
        """
        Actual process a file

        Arguments:
            fname (str) : Full path of file to transcode

        Returns:
            None.

        """

        if not self._check_size( fname ):
            return

        try:
            out_file = self.converter.transcode( fname )
        except:
            self.log.exception('Failed to convert file')
            return

        if isinstance(out_file, str) and isRunning():
            plex_media_scanner(
                'TV Shows' if self.converter.metadata.isEpisode else 'Movies',
                path = os.path.dirname( out_file )
            )

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
