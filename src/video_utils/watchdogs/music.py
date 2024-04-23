"""
Watchdog for new music

"""

import logging

import os
from threading import Thread

#from .plex.plex_media_scanner import plex_media_scanner
from ..utils import isRunning
#from .utils.handlers import send_email
from .base import BaseWatchdog

#scanMusic = lambda : plex_media_scanner('Music')

class Music_Watchdog( BaseWatchdog ):
    """
    Watchdog of new music files

    """

    def __init__(self, outdir, *args, **kwargs):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.log.info('Starting up...')

        # Try to get file_ext keyword from keyword dictionary
        self.set_file_exts(
            kwargs.get('fileExt', None),
            ('.wav', '.flac', '.mp3'),
        )

        self.outdir     = outdir
        self.scan_delay = kwargs.get('scanDelay', 600.0)
        self.scan_timer = None

        # Ensure trailing path separator
        self.src_dirs  = [os.path.join(arg, '') for arg in args]

        for src_dir in self.src_dirs:
            self.observer.schedule( self, src_dir, recursive=True )
            for root, _, items in os.walk( src_dir ):
                for item in items:
                    if item.endswith( self.file_ext ):
                        self.queue.put( os.path.join( root, item ) )

        self.observer.start()

        self.__runthread = Thread( target = self._run )
        self.__runthread.start()

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
