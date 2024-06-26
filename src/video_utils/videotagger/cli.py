#!/usr/bin/env python3
"""
CLI for videotagging

"""

import logging
import os
import sys
import argparse

try:
    from PyQt5.QtWidgets import QApplication
except:
    QApplication = None

from .. import log, __version__, __name__ as pkg_name

from ..mediainfo import MediaInfo
from . import getMetaData

if QApplication is not None:
    from . import gui


def tag_file(args):
    """
    Tag video file with metadata

    """

    if not args.path.endswith(('.mkv', '.mp4')):
        log.critical('File must be MP4 or MKV!')
        return False
    metadata = getMetaData(
        args.path,
        dbID=args.dbID,
        seasonEp=args.season_episode,
        dvdOrder=args.dvdOrder,
    )
    metadata.addComment(
        f'Metadata written with {pkg_name} version {__version__}.'
    )
    try:
        metadata.write_tags(args.path)
    except:
        log.critical('Failed to write tags')
        return False
    if args.rename:
        mediainfo = MediaInfo(args.path)
        video = mediainfo.get_video_info()
        audio = mediainfo.get_audio_info()
        _, ext = os.path.splitext(args.path)
        new_dir = metadata.get_dirname(root=args.rename)
        os.makedirs(new_dir, exist_ok=True)
        new_file = (
            [metadata.get_basename()]
            + video['file_info']
            + audio['file_info']
        )
        new_path = os.path.join(new_dir, '.'.join(new_file) + ext)
        log.info('Renaming file: %s ---> %s', args.path, new_path)
        os.rename(args.path, new_path)
    return True


def cli():
    """Entry point for CLI"""

    parser = argparse.ArgumentParser(
        description="Write metadata to MP4 and MKV files",
    )
    parser.add_argument(
        "path",
        type=str,
        nargs='?',
        help="Path to file to write tags to.",
    )
    parser.add_argument(
        "--dbID",
        type=str,
        help=(
            "TVDb or TMDb ID, should start with 'tvdb' or "
            "'tmdb', respectively"
        ),
    )
    parser.add_argument(
        '--season-episode',
        type=int,
        nargs=2,
        help='Season and episode number for tv show',
    )
    parser.add_argument(
        '-v', '--verbose',
        nargs='?',
        default='info',
        help='Increase verbosity. Levels are info (default) and debug.',
    )
    parser.add_argument(
        "--rename",
        type=str,
        help=(
            "Top-level path for rename; note that 'Movies' or 'TV Shows' "
            "will be placed below this directory, with files below that."
        ),
    )
    parser.add_argument(
        "--dvdOrder",
        action='store_true',
        help=(
            'Set if the season/episode number corresponds to dvd ordering '
            'on TVDb. Default is to use aired ordering'
        ),
    )
    parser.add_argument(
        "--gui",
        action='store_true',
        help="Start GUI",
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s ' + __version__,
    )

    args = parser.parse_args()
    log.setLevel(
        logging.DEBUG if args.verbose == 'debug' else logging.INFO
    )

    SCREEN_FMT = '%(levelname)-5.5s - %(funcName)-10.10s - %(message)s'
    SCREEN_FMT = logging.Formatter(SCREEN_FMT)
    SCREEN_LVL = logging.DEBUG
    screen_log = logging.StreamHandler()
    screen_log.setFormatter(SCREEN_FMT)
    screen_log.setLevel(SCREEN_LVL)
    log.addHandler(screen_log)

    if args.gui:
        if QApplication is None:
            raise Exception(
                'PyQt5 NOT installed. Must install before running GUI!',
            )
        app = QApplication(sys.argv)
        w = gui.VideoTaggerGUI()
        w.show()
        sys.exit(app.exec_())

    if os.path.isdir(args.path):
        files = []
        for item in os.listdir(args.path):
            path = os.path.join(args.path, item)
            if os.path.isfile(path):
                files.append(path)
    elif os.path.isfile(args.path):
        files = [args.path]
    else:
        log.critical("'path' argument must be a file or directory")
        sys.exit(1)

    for fpath in files:
        args.path = fpath
        tag_file(args)

    sys.exit(0)
