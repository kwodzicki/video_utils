#!/usr/bin/env python3

"""
This script is ment to renamin media files ina given directory to match
the new Plex naming format that allows for TVDb, TMDb, or IMDb tags
within the Movie/TV Series forlder name and file names.

"""

import os
import argparse

MATCH = ('tmdb', 'tvdb')

def strip_empty_dir( topdir ):
    """Strip off any trailing path separaters"""

    while os.path.split( topdir )[1] == '':
        topdir = os.path.dirname( topdir )
    return topdir

def rename_files( topdir, dry_run = False, **kwargs ):
    """
    Actually rename files

    Recursively search directly for files containg 'tmdb' or 'tvdb' tags.
    Rename files, and the top-level directory where theres files reside,
    with the Plex approved ID format

    Arguments:
        topdir (str) : Top-level directory of a Movie or TV Show

    Keywords:
        dry_run (bool) : If set, do NOT rename files, only print how files will
            be renamed
        **kwargs : Any other arguments silently ignored

    """

    topdir = strip_empty_dir( topdir )
    mid    = None

    for root, _, items in os.walk( topdir ):
        for item in items:
            src = os.path.join( root, item )
            if not os.path.isfile( src ):
                continue

            parts = item.split('.')
            for i, part in enumerate(parts):
                if part.startswith( MATCH ):
                    parts[i] = '{' + part[:4] + '-' + part[4:] + '}'
                    if mid is None:
                        mid = parts[i]
                    break
            dst = os.path.join( root, '.'.join( parts ) )

            print( f'{src} -- > {dst}' )
            if not dry_run:
                os.rename( src, dst )

    if mid is not None:
        src = topdir
        if mid not in src:
            dst = f'{src} {mid}'
            print( f'{src} --> {dst}' )
            if not dry_run:
                os.rename( src, dst )

def main( topdir, **kwargs ):
    """
    Main function to iterate over directories at within topdir

    Arguments:
        topdir (str) : Directory to search non-recursively

    """

    for item in os.listdir( topdir ):
        path = os.path.join( topdir, item )
        if os.path.isdir( path ):
            rename_files( path, **kwargs )
        if kwargs.get('test', False):
            return


def cli():
    parser = argparse.ArgumentParser(
        description = (
            'Rename Movies/TV Shows to match the new Plex file formatting that '
            'supports TMDb, TVDb, and IMDb tags in the directory/file names. '
            'Previous of file naming contained the tags, but not in the new '
            'format that Plex expects. Simply point this script to the Movie '
            'and/or TV Show directory and let it rename all your files. '
            'Note that this will NOT make duplicates of files and run the '
            'Plex Media Scanner to ensure that files are not re-added to the '
            'library like the updateFileNames script does. This utility '
            'simply renames the files.'
        ),
    )
    parser.add_argument(
        'dir',
        nargs = '+',
        type = str,
        help = 'Directories to iterate over',
    )
    parser.add_argument(
        '-n', '--dry-run',
        action = 'store_true',
        help   = "Set to do a dry run; don't actually rename files/directories",
    )
    parser.add_argument(
        '--test',
        action = 'store_true',
        help   = "Set for testing purposes",
    )

    args = parser.parse_args()

    for arg in args.dir:
        main( arg, dry_run = args.dry_run, test = args.test)
