"""
Subtitle utilities

Various functions and class for extracting
subtitle files from video files, converting
image based subtitles to SRT, and download
subtitles from OpenSubtitles.com

"""

import logging

from .vobsub_to_srt import vobsub_to_srt
from .pgs_to_srt import pgs_to_srt


def sub_to_srt(out_file: str, text_info: list[dict], **kwargs) -> list[str]:
    """
    Convert image based subtitles to srt

    DVDs and BluRays make use of image based subtitles in the form
    of VobSubs and PGS files, respectively. This wrapper function
    is used to convert either format to SRT using the vobsub_to_srt
    and pgs_to_srt functions, respectively.

    Arguments:
        out_file (str) : Base path and name for the output video file.
        text_info (list) : List of dicts containing information about
            text streams in video file.

    Keyword arguments:
        **kwargs : Passed directory to the converter functions.

    Returns:
        list : Paths to SRT files created. Will be empty if no
            files to convert OR if all conversions failed.

    """

    log = logging.getLogger(__name__)
    files = []
    for info in text_info:
        fmt = info.get('format', '')
        if fmt == 'PGS':
            res, fname = pgs_to_srt(out_file, info, **kwargs)
        elif fmt == 'VobSub':
            res, fname = vobsub_to_srt(out_file, info, **kwargs)
        else:
            log.info("Format not supported : %s", fmt)
            continue

        if res <= 1:
            files.append(fname)

    return files
