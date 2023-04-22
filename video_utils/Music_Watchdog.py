"""
Watchdog for new music

"""

import logging

import os
import time
from threading import Thread, Timer
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .plex.plex_media_scanner import plex_media_scanner
from .utils import isRunning
from .utils.handlers import send_email

TIMEOUT = 1.0
SLEEP   = 5.0
SLEEP   = 1.0

#scanMusic = lambda : plex_media_scanner('Music')

class Music_Watchdog( FileSystemEventHandler ):
    """
    Watchdog of new music files

    """

    def __init__(self, outdir, *args, **kwargs):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.log.info('Starting up...')

        # Try to get file_ext keyword from keyword dictionary
        file_ext = kwargs.get('fileExt', None)
        if file_ext is None:
            self.file_ext = ('.wav', '.flac', '.mp3')
        elif isinstance(file_ext, str):
            self.file_ext = (file_ext,)
        elif isinstance(file_ext, list):
            self.file_ext = tuple(file_ext)
        else:
            self.file_ext = file_ext

        self.outdir     = outdir
        self.scan_delay = kwargs.get('scanDelay', 600.0)
        self.scan_timer = None

        # Ensure trailing path separator
        self.src_dirs  = [os.path.join(arg, '') for arg in args]
        self.queue     = Queue()
        self.observer  = Observer()
        for src_dir in self.src_dirs:
            self.observer.schedule( self, src_dir, recursive=True )
            for root, _, items in os.walk( src_dir ):
                for item in items:
                    if item.endswith( self.file_ext ):
                        self.queue.put( os.path.join( root, item ) )

        self.observer.start()

        self.__runthread = Thread( target = self._run )
        self.__runthread.start()

    def on_created(self, event):
        """Method to handle events when file is created."""

        if event.is_directory:
            return
        if event.src_path.endswith( self.file_ext ):
            self.queue.put( event.src_path )
            self.log.debug( 'New file added to queue : %s', event.src_path )

    def on_moved(self, event):
        """Method to handle events when file is created."""

        if event.is_directory:
            return
        if event.dest_path.endswith( self.file_ext ):
            self.queue.put( event.dest_path )
            self.log.debug( 'New file added to queue : %s', event.dest_path )

    def join(self):
        """Method to wait for the watchdog observer to finish."""

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

        self.log.debug('Waiting for file to finish being created')
        if not os.path.isfile( fpath ):
            return False

        prev = -1
        curr = os.path.getsize(fpath)
        while prev != curr:
            time.sleep(SLEEP)
            prev = curr
            curr = os.path.getsize(fpath)
        return True

    def _remove_dir( self, root, fpath ):
        """To remove Artist/Album directories given audio file path"""

        fdir = os.path.dirname( fpath )
        while os.path.commonpath( [root, fdir] ) != fdir:
            print( root, fdir )
            print( os.path.commonpath( [root, fdir] ) )
            try:
                os.rmdir( fdir )
            except:
                return
            fdir = os.path.dirname( fdir )

#    @send_email
    def _process(self, fpath):

        # Wait to make sure file finishes copying/moving
        if not self._check_size( fpath ):
            return

        for src_dir in self.src_dirs:
            if src_dir in fpath:
                newpath = fpath.replace( src_dir, '' )
                newpath = os.path.join( self.outdir, newpath )
                print( src_dir )
                print(newpath)
                os.makedirs( os.path.dirname( newpath ), exist_ok=True )
                os.rename( fpath, newpath )
                self._remove_dir( src_dir, fpath )

        # If still running and the queue is empty
        if isRunning() and self.queue.empty():
            print( 'Queue is empty, scheduling library scan' )
            if self.scan_timer is not None:
                self.scan_timer.cancel()
          #self.scan_timer = Timer( self.scan_delay, scanMusic )

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

        self.log.info('Music watchdog stopped!')
        self.observer.stop()
