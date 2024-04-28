"""
Wrapper utils for running ccextractor CLI

"""

import logging
import os
from subprocess import run, STDOUT, DEVNULL

from ..utils.check_cli import check_cli

CLINAME = 'ccextractor'
try:
    CLI = check_cli(CLINAME)
except:
    logging.getLogger(__name__).warning(
        "'%s' is NOT installed or not in your PATH!",
        CLINAME,
    )
    CLI = None


def dir_list(path: str):
    """
    Generate path to all files in a directory

    Arguments:
        path (str) : Path to directory, or file, for directory to
            search. If is file, will get dirname of path

    Returns:
        generator : File path generator

    """

    root = os.path.dirname(path) if not os.path.isdir(path) else path
    for item in os.listdir(root):
        path = os.path.join(root, item)
        if os.path.isfile(path):
            yield path


def ccextract(
    in_file: str,
    out_base: str,
    text_info: dict,
) -> list[str] | None:
    """
    Wrapper for the ccextrator CLI

    Simply calls ccextractor using subprocess.Popen

    Arguments:
        in_file (str): File to extract closed captions from
        out_base (str): Base name for output file(s)
        text_info (dict): Text information from call to mediainfo

    Keyword arguments:
        None.

    Returns:
        list : Paths to files that ccextractor created

    """

    log = logging.getLogger(__name__)  # Set up logger
    if CLI is None:
        log.warning("%s CLI not found; cannot extract!", CLINAME)
        return None

    # Get list of files that were originally in the directory
    orig = list(dir_list(out_base))

    fname = out_base + text_info[0]['ext'] + '.srt'
    cmd = [CLI, '-autoprogram', in_file, '-o', fname]
    log.debug("%s command: %s", CLINAME, ' '.join(cmd))
    proc = run(cmd, stdout=DEVNULL, stderr=STDOUT, check=False)
    new_files = [item for item in dir_list(out_base) if item not in orig]
    if proc.returncode != 0:
        log.error(
            'Something went wrong extracting subtitles, removing any files'
        )
        for path in new_files:
            os.remove(path)

    return new_files
