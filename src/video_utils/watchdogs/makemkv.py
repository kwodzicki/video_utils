"""
Watchdog for MakeMKV output

A watchdog is defined that monitors direcory(ies) for files
output by MakeMKV so that these files can be transcoded and add
to Plex.

"""

import logging

import os
import sys
import argparse

from threading import Thread

from .. import __version__, log
from ..videoconverter import VideoConverter
from ..plex.plex_media_scanner import plex_media_scanner
from ..config import BASEPARSER, MakeMKVFMT, get_transcode_log, get_comskip_log
from ..utils import isRunning
from ..utils.handlers import send_email, init_log_file, EMailHandler
from ..utils.pid_check import pid_running
from .base import BaseWatchdog

"""
The following code 'attempts' to add what should be the
site-packages location where video_utils is installed
"""
#
# binDir  = os.path.dirname(os.path.realpath(__file__))
# topDir  = os.path.dirname(binDir)
# pyVers  = f'python{sys.version_info.major}.{sys.version_info.minor}'
# siteDir = ['lib', pyVers, 'site-packages']
# siteDir = os.path.join(topDir, *siteDir)
#
# if os.path.isdir(siteDir):
#    if siteDir not in sys.path:
#        sys.path.append(siteDir)


class MakeMKV_Watchdog(BaseWatchdog):
    """
    Watchdog for conversion of MakeMKV output

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.log.info('Starting up (v%s)...', __version__)

        # Sets watchdog to recursive
        recursive = kwargs.pop('recursive', False)

        self.set_file_exts(
            kwargs.pop('fileExt', None),
            ('.mkv',),
        )

        self.converter = VideoConverter(**kwargs)

        # Iterate over input arguments
        for arg in args:
            self.observer.schedule(self, arg, recursive=recursive)
            # Iterate over all files (if any) in the input directory
            # Enque to the list
            for fpath in self._get_dir_listing(arg):
                self.queue.put(fpath)

        self.observer.start()

        self.__run_thread = Thread(target=self._run)
        self.__run_thread.start()

    def _get_dir_listing(self, root):
        """
        Get list of files in a directory (non-recursive)

        List of files in directory that ends with given extension

        Arguments:
            root (str): Path of directory to search

        Keyword arguments:
            None

        Returns:
            list: Files

        """

        fpaths = []
        for item in os.listdir(root):
            if not item.endswith(self.file_ext):
                continue
            fpath = os.path.join(root, item)
            if os.path.isfile(fpath):
                fpaths.append(fpath)

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

        if not self._check_size(fpath):
            return

        try:
            out_file = self.converter.transcode(fpath)
        except:
            self.log.exception('Failed to convert file')
            return

        if isinstance(out_file, str) and isRunning():
            plex_media_scanner(
                'TV Shows' if self.converter.metadata.isEpisode else 'Movies',
                path=os.path.dirname(out_file)
            )


def cli():
    """Entry point for CLI"""

    desc = (
        'A CLI for running a watchdog to monitor a directory (or directories)'
        'for new files to transcode and add Plex'
    )

    # Set the description of the script to be printed in the help doc;
    # i.e., ./script -h
    parser = argparse.ArgumentParser(
        description=desc,
        parents=[BASEPARSER],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.set_defaults(loglevel=MakeMKVFMT['level'])
    parser.add_argument(
        "indir",
        type=str,
        nargs='+',
        help="Directory(s) to watch for new MakeMKV output files",
    )
    parser.add_argument(
        "outdir",
        type=str,
        help=(
            "Top level directory for Plex library directories. E.g., "
            "'/mnt/plexLibs' if your library directories are "
            "'/mnt/plexLibs/Movies' and '/mnt/plexLibs/TV Shows'."
        ),
    )
    parser.add_argument(
        "--fileExt",
        type=str,
        nargs='+',
        help=(
            "Set file extensions to look for in watched directories; only "
            "files with given extension(s) will be processed. "
            "Default is just '.mkv'"
        ),
    )
    parser.add_argument(
        "--subtitles",
        action="store_true",
        help="Set to extract subtitle(s) from files.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="If set, will look recursively through directory for new files.",
    )
    args = parser.parse_args()

    if pid_running(MakeMKVFMT['pidFile']):
        log.critical('%s instance already running!', parser.prog)
        sys.exit(1)

    if args.fileExt is not None:
        args.fileExt = [item for sublist in args.fileExt for item in sublist]

    MakeMKVFMT['level'] = args.loglevel
    init_log_file(MakeMKVFMT)

    email = EMailHandler(subject=f'{parser.prog} Update')
    if email:
        log.addHandler(email)

    try:
        wd = MakeMKV_Watchdog(
            *args.indir,
            fileExt=args.fileExt,
            outdir=args.outdir,
            threads=args.threads,
            cpulimit=args.cpulimit,
            lang=args.lang,
            remove=not args.no_remove,
            srt=not args.no_srt,
            subtitles=args.subtitles,
            transcode_log=get_transcode_log(parser.prog),
            comskip_log=get_comskip_log(parser.prog),
            recursive=args.recursive,
        )
    except:
        log.exception('Something went wrong! Watchdog failed to start')
    else:
        wd.join()
