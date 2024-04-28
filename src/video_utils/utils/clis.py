#!/usr/bin/env python3

"""
This script is ment to renamin media files ina given directory to match
the new Plex naming format that allows for TVDb, TMDb, or IMDb tags
within the Movie/TV Series forlder name and file names.

"""

import argparse

from .. import log
from . import rename_media_plex_tag_format as rename_media_plex_tag_format_
from . import update_file_names as update_file_names_
from . import ffmpeg_utils as ffmpeg_utils_


def rename_media_plex_tag_format():
    parser = argparse.ArgumentParser(
        description=(
            'Rename Movies/TV Shows to match the new Plex file formatting '
            'that supports TMDb, TVDb, and IMDb tags in the directory/file '
            'names. Previous of file naming contained the tags, but not in '
            'the new format that Plex expects. Simply point this script to '
            'the Movie and/or TV Show directory and let it rename all your '
            'files. Note that this will NOT make duplicates of files and '
            'run the Plex Media Scanner to ensure that files are not '
            're-added to the library like the updateFileNames script does. '
            'This utility simply renames the files.'
        ),
    )
    parser.add_argument(
        'dir',
        nargs='+',
        type=str,
        help='Directories to iterate over',
    )
    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        help="Set to do a dry run; don't actually rename files/directories",
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help="Set for testing purposes",
    )

    args = parser.parse_args()

    for arg in args.dir:
        rename_media_plex_tag_format_.main(
            arg,
            dry_run=args.dry_run,
            test=args.test,
        )


def update_file_names():
    """
    CLI to update file names to a newer convention

    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'indir',
        nargs='+',
        help='Directories to rename files in',
    )
    parser.add_argument(
        '--root',
        type=str,
        help='Directories to rename files in',
    )
    parser.add_argument(
        '--dbID',
        type=str,
        help='Directories to rename files in',
    )
    parser.add_argument(
        '--dvdOrder',
        action='store_true',
        help='Match episodes based on DVD order',
    )
    parser.add_argument(
        '--log-level',
        type=int,
        default=20,
        help='Set logging leve',
    )
    args = parser.parse_args()

    log.handlers[0].setLevel(args.log_level)
    update_file_names_.update_file_names(
        *args.indir,
        rootdir=args.root,
        dbID=args.dbID,
        dvdOrder=args.dvdOrder,
    )


def split_on_chapter():
    """
    CLI Entry for splitting on chapter

    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'file',
        type=str,
        help="Full path of file to split",
    )
    parser.add_argument(
        'chapters',
        type=int,
        nargs='*',
        help=(
            'Number of chapters in each output segment. Can be single integer '
            'for fixed number of chapters in each segment, or multiple '
            'numbers of variable number of chapters in each segment'
        ),
    )

    args = parser.parse_args()
    if len(args.chapters) == 1:
        args.chapters = args.chapters[0]

    ffmpeg_utils_.split_on_chapter(args.file, args.chapters)
