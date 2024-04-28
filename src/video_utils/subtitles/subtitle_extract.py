"""
Utilities for extracting subtitles

"""

import logging
import os
from subprocess import call, DEVNULL, STDOUT

from ..utils.check_cli import check_cli

CLINAME = 'mkvextract'
try:
    CLI = check_cli(CLINAME)
except:
    logging.getLogger(__name__).error("%s is NOT installed", CLINAME)
    CLI = None


def check_files_exist(files: list[str]) -> bool:
    """
    Check that all files exist

    If any of the files in the input list do NOT
    exist, than will return False

    Arguments:
        files (array-like) : List of files to check if exist

    Returns:
        bool : True if all of the files exists, False otherwise

    """

    for fname in files:
        if not os.path.isfile(fname):
            return False
    return True


def gen_sub_info(out_base: str, stream: dict) -> dict | None:
    """
    Generate information for subtitle streams

    Build a dict that contains subtitle type and list of
    output subtitle files after extraction

    Arguments:
        out_base (str) : Base output file name that information for
            subtitle files will be appended to
        stream (dict) : Information about given text stream for
            build/extrating text files

    Returns:
        dict

    """

    fmt, ext = stream['format'], stream['ext']
    base = f"{out_base}{ext}"

    if fmt == 'UTF-8':
        return {
            'subtype': 'srt',
            'files': [f"{base}.srt"],
        }
    if fmt == 'VobSub':
        return {
            'subtype': 'vobsub',
            'files': [f"{base}.sub", f"{base}.idx"],
        }
    if fmt == 'PGS':
        return {
            'subtype': 'pgs',
            'files': [f"{base}.sup"],
        }

    return None


def subtitle_extract(
    in_file: str,
    out_base: str,
    text_info: dict,
    **kwargs,
) -> tuple:
    """
    Extract subtitle(s) from a file and convert them to SRT file(s).

    If a file fails to convert, the VobSub files are removed and
    the program continues.

    Arguments:
        in_file (str): File to extract subtitles from
        out_file (str): Base name for output file(s)
        text_info (dict): Data returned by call to
            :meth:`video_utils.mediainfo.MediaInfo.get_text_info`

    Keyword arguments:
        srt (bool): Set to convert image based subtitles to srt format;
            Default does NOT convert file

    Returns:
        int: Updates subtitle_status and creates/updates list of subtitle
            files that failed extraction
            Return codes for success/failure of extraction.
            Codes are as follows:
                -  0 : Completed successfully
                -  1 : VobSub(s) already exist
                -  2 : No VobSub(s) to extract
                -  3 : Error extracting VobSub(s).
                - 10 : mkvextract not found/installed

    Dependencies:
        mkvextract - A CLI for extracting streams for an MKV file.

    """

    log = logging.getLogger(__name__)

    if CLI is None:
        log.warning("%s CLI not found; cannot extract!", CLINAME)
        return 10, None

    if text_info is None:
        log.warning('No text stream information; cannot extract anything')
        return 4, None

    # Initialize list to store command for extracting VobSubs from MKV files
    extract = [CLI, 'tracks', in_file]
    files = {}

    for i, stream in enumerate(text_info):
        sub_info = gen_sub_info(out_base, stream)
        if check_files_exist(sub_info['files']):
            stream[sub_info['subtype']] = True
            continue

        files[i] = sub_info
        extract.append(f"{stream['mkvID']}:{sub_info['files'][0]}")

    if len(extract) == 3:
        return 1, files

    log.info('Extracting Subtitles...')
    log.debug(extract)
    # Run command and dump all output and errors to /dev/null
    status = call(extract, stdout=DEVNULL, stderr=STDOUT)

    if status != 0:
        log.warning("Error extracting subtitles %d", status)
        return 3, files

    for index, info in files.items():
        text_info[index][info['subtype']] = (
            check_files_exist(info['files'])
        )

    return 0, files
