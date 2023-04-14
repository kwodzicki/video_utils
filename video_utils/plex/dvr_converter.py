"""
Converter for Plex DVR recordings

Defines a class for re-encoding Plex DVR recordings so that
they are not as large as MPEG-TS files are not very efficient.

"""

import logging
import os

from .. import isRunning#_sigintEvent, _sigtermEvent
from ..videoconverter import VideoConverter

from .plex_media_scanner import plex_media_scanner
from .utils import plex_dvr_rename


class DVRconverter(VideoConverter):
    """Combines the VideoConverter and ComRemove classes for post-processing Plex DVR recordings"""

    def __init__(self,
            logdir      = None,
            lang        = None,
            destructive = False,
            no_remove   = False,
            no_srt      = False,
            **kwargs,
    ):
        """
        Method to initialize class and superclasses along with a few attributes
        
        Arguments:
            None

        Keyword arguments:
            logdir      (str) : Directory for any extra log files
            threads     (int) : Number of threads to use for comskip and transcode
            cpulimit    (int) : Percentage to limit cpu usage to
            lang        (list): Language for audio/subtitles
            destructive (bool): If set, will cut commercials out of file. Note that
                commercial identification is NOT perfect, so this could
                lead to missing pieces of content. 
                By default, will add chapters to output file marking
                commercial breaks. This enables easy skipping, and does
                not delete content if commercials misidentified
            no_remove (bool): If set, input file will NOT be deleted
            no_srt    (bool): If set, no SRT subtitle files created
            Any other keyword argument is ignored

        Returns:
            None

        """

        super().__init__(
            log_dir       = logdir,
            in_place      = True,
            lang          = lang,
            remove        = not no_remove,
            subfolder     = False,
            srt           = not no_srt,
            **kwargs,
        )

        self.destructive = destructive
        self.log         = logging.getLogger(__name__)

    def convert(self, infile):
        """
        Method to actually post process Plex DVR files.

        This method does a few things:
            - Renames file to match convenction set by video_utils package
            - Attempts to remove commercials using comskip
            - Transcodes to h264

        Arguments:
            infile (str) : Path to file to process

        Keyword Arguments:
            None

        Returns:
            int: Returns success of transocde

        """

        # Set some variable defaults
        infile       = os.path.realpath( infile )
        out_file     = None
        success      = False
        # Set to opposite of the remove attribute
        no_remove    = not self.remove
        # Set infile class attribute; this will trigger mediainfo parsing
        self.infile  = infile

        self.log.info('Input file: %s', infile )

        self.log.debug('Checking file integrity')
        # If is NOT a valid file; i.e., video stream size is larger than
        # file size OR found 'overread' errors in file
        if not self.isValidFile():
            self.log.warning('File determined to be invalid, deleting: %s', infile )
            # Set local no_remove variable to True; done so that directory is not
            # scanned twice when the Plex Media Scanner command is run
            no_remove = True
            self._clean_up( infile )
        else:
            # Try to rename the input file using standard convention and get
            # parsed file info; creates hard link to source file
            fname, metadata = plex_dvr_rename( infile )
            # if the rename fails
            if not fname:
                self.log.critical('Error renaming file: %s', infile)
                return success, out_file

            if not isRunning():
                return success, out_file

            out_file = self.transcode(
                fname,
                metadata = metadata,
                chapters = not self.destructive,
            )

            self._clean_up( fname )

            if self.transcode_status == 0:
                success = True
            elif not isRunning():
                return success, out_file
            elif self.transcode_status == 5:
                self.log.error('Assuming bad file, deleting: %s', infile)
                # Set local no_remove variable to True; done so that directory is
                # not scanned twice when the Plex Media Scanner command is run
                no_remove = True
                self._clean_up( infile )
            else:
                self.log.error('Failed to transcode file. Will delete input')
                # Set local no_remove variable to True; done so that directory is
                # not scanned twice when the Plex Media Scanner command is run
                no_remove = True
                self._clean_up( infile, out_file )

        if isRunning():
            # Set arguments for PlexMediaScanner
            args   = ('TV Shows',)
            kwargs = {'path' : os.path.dirname( infile )}
            plex_media_scanner( *args, **kwargs )
            # If no_remove is NOT set, then we want to delete infile and rescan
            # the directory so original file is removed from Plex
            if not no_remove:
                self._clean_up( infile )
                # If file no longer exists; if it exists, don't want to run
                # Plex Media Scanner for no reason
                if not os.path.isfile( infile ):
                    self.log.debug('Original file removed, rescanning: %s', infile)
                    plex_media_scanner( *args, **kwargs )

        return success, out_file
