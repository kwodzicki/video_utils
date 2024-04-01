"""
Watchdog for MakeMKV output

A watchdog is defined that monitors direcory(ies) for files 
output by MakeMKV so that these files can be transcoded and add
to Plex.

"""

import logging

import os

from threading import Thread

from .. import __version__
from ..videoconverter import VideoConverter
from ..plex.plex_media_scanner import plex_media_scanner
from ..utils import isRunning
from ..utils.handlers import send_email
from .base import BaseWatchdog

class MakeMKV_Watchdog( BaseWatchdog ):
    """
    Watchdog for conversion of MakeMKV output

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log         = logging.getLogger(__name__)
        self.log.info('Starting up (v%s)...', __version__)

        # Sets watchdog to recursive
        recursive = kwargs.pop('recursive', False)

        self.set_file_exts(
            kwargs.pop('fileExt', None),
            ('.mkv',),
        )

        self.converter = VideoConverter( **kwargs )

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

    @send_email
    def _process(self, fpath):
        """
        Actual process a file

        Arguments:
            fpath (str) : Full path of file to transcode

        Returns:
            None.

        """

        if not self._check_size( fpath ):
            return

        try:
            out_file = self.converter.transcode( fpath )
        except:
            self.log.exception('Failed to convert file')
            return

        if isinstance(out_file, str) and isRunning():
            plex_media_scanner(
                'TV Shows' if self.converter.metadata.isEpisode else 'Movies',
                path = os.path.dirname( out_file )
            )
