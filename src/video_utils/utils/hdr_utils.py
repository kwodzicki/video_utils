"""
Extra HDR metdata from files

Use the dovi_tool and/or hdr10plus_tool to extract HDR information.

"""

import logging
import os
from subprocess import Popen, STDOUT, DEVNULL

from .ffmpeg_utils import extract_hevc

RUST_CARGO = os.path.join(
    os.path.expanduser('~'),
    ".cargo",
    "bin",
)
DOVI_TOOL = os.path.join(
    RUST_CARGO,
    "dovi_tool",
)
HDR10PLUS_TOOL = os.path.join(
    RUST_CARGO,
    "hdr10plus_tool",
)


def ingect_hdr(hevc_file, dolby_vision_file, hdr10plus_file):
    """
    Ingect Dolby Vision/HDR10 data

    Given an HEVC encoded video file ingect Dolby Vision
    and or HDR10+ metadata into the file.

    Arguments:
        hevc_file (str) : Path to hevc_mp4toannexb formatted video stream.
        dolby_vision_file (str): Path to Dolby Vision .bin metadata file.
            If set to None, or file not exist, then no data injected.
        hdr10plus_file (str): Path to HDR10+ .json metadta file
            If set to None, or file not exist, then no data injected.

    Returns:
        str : Path to HEVC file with injected metadata

    """

    hevc_file = dovi_inject(hevc_file, dolby_vision_file)
    hevc_file = hdr10plus_inject(hevc_file, hdr10plus_file)

    return hevc_file


def dovi_inject(hevc_file, dolby_vision_file):
    """
    Inject Dolby Vision metadata into HEVC file

    Arguments:
        hevc_file (str) : Path to hevc_mp4toannexb formatted video stream.
        dolby_vision_file (str): Path to Dolby Vision .bin metadata file.
            If set to None, or file not exist, then no data injected.

    Returns:
        str : Path to HEVC file with injected metadata

    """

    log = logging.getLogger(__name__)

    if not os.path.isfile(DOVI_TOOL):
        log.error("dovi_tool NOT installed!")
        return hevc_file

    if not check_file(dolby_vision_file):
        return hevc_file

    log.info("Injecting Dolby Vision data : %s", hevc_file)
    fname, fext = os.path.splitext(hevc_file)
    out_file = f"{fname}-DV{fext}"
    cmd = [
        DOVI_TOOL,
        "inject-rpu",
        "-i", hevc_file,
        "--rpu-in", dolby_vision_file,
        "-o", out_file,
    ]

    proc = Popen(cmd, stdout=DEVNULL, stderr=STDOUT)
    if proc.wait() == 0:
        # command finished successfully!
        # Remove source file and update hevc_file to injected file
        os.rename(out_file, hevc_file)
    else:
        log.warning("Failed to inject Dolby Vision data : %s", hevc_file)
        if os.path.isfile(out_file):
            os.remove(out_file)

    return hevc_file


def dovi_extract(
    src_file: str,
    out_file: str | None = None,
    ext: str = ".bin",
) -> str | None:
    """
    Run 'dovi_tool' for Dolby Vision data

    Extract Dolby Vision HDR data from file

    Arguments:
        hevc_file (str) : Path to hevc_mp4toannexb formatted video stream.

    Returns:
        str : Path to .bin file with Dolby Vision info if command success,
            else None

    """

    log = logging.getLogger(__name__)
    if not os.path.isfile(DOVI_TOOL):
        log.error("dovi_tool NOT installed!")
        return None

    out_file, _ = os.path.splitext(out_file or src_file)
    if not out_file.endswith(ext):
        out_file += ext

    cmd = [
        DOVI_TOOL,
        '-c',
        '-m', '2',
        'extract-rpu',
        '-o', out_file,
        '-',
    ]

    log.info("Extracting Dolby Vision data: %s --> %s", src_file, out_file)
    extract = extract_hevc(src_file)
    proc = Popen(cmd, stdin=extract.stdout, stdout=DEVNULL, stderr=STDOUT)
    extract.stdout.close()

    if proc.wait() != 0:
        log.warning("Failed to extract Dolby Vision data!")
        return None
    _ = proc.communicate()

    if check_file(out_file):
        return out_file
    log.warning("Issue with Dolby Vision metadata file!")
    return None


def hdr10plus_inject(hevc_file, hdr10plus_file):
    """
    Inject Dolby Vision metadata into HEVC file

    Arguments:
        hevc_file (str) : Path to hevc_mp4toannexb formatted video stream.
        hdr10plus_file (str): Path to HDR10+ .json metadta file
            If set to None, or file not exist, then no data injected.

    Returns:
        str : Path to HEVC file with injected metadata

    """

    log = logging.getLogger(__name__)

    if not os.path.isfile(HDR10PLUS_TOOL):
        log.error("hdr10plus_tool NOT installed!")
        return hevc_file

    if not check_file(hdr10plus_file):
        return hevc_file

    log.info("Injecting HDR10+ data : %s", hevc_file)
    fname, fext = os.path.splitext(hevc_file)
    out_file = f"{fname}-HDR10Plus{fext}"
    cmd = [
        HDR10PLUS_TOOL,
        "inject",
        "-i", hevc_file,
        "-j", hdr10plus_file,
        "-o", out_file,
    ]

    proc = Popen(cmd, stdout=DEVNULL, stderr=STDOUT)
    if proc.wait() == 0:
        # command finished successfully!
        # Remove source file and update hevc_file to injected file
        os.rename(out_file, hevc_file)
    else:
        log.warning("Failed to inject HDR10+ data : %s", hevc_file)
        if os.path.isfile(out_file):
            os.remove(out_file)

    return hevc_file


def hdr10plus_extract(
    src_file: str,
    out_file: str | None = None,
    ext: str = ".json",
) -> str | None:
    """
    Run 'hdr10plus_tool' for Dolby Vision data

    Extract HDR10+ HDR data from file

    Arguments:
        hevc_file (str) : Path to hevc_mp4toannexb formatted video stream.

    Returns:
        str : Path to .json file with HDR10+ info if command success,
            else None

    """

    log = logging.getLogger(__name__)
    if not os.path.isfile(HDR10PLUS_TOOL):
        log.error("hdr10plus_tool NOT installed!")
        return None

    out_file, _ = os.path.splitext(out_file or src_file)
    if not out_file.endswith(ext):
        out_file += ext

    cmd = [
        HDR10PLUS_TOOL,
        "extract",
        "-o", out_file,
        "-",
    ]

    log.info("Extracting HDR10+ data: %s --> %s", src_file, out_file)
    extract = extract_hevc(src_file)

    proc = Popen(cmd, stdin=extract.stdout, stdout=DEVNULL, stderr=STDOUT)
    extract.stdout.close()

    if proc.wait() != 0:
        log.warning("Failed to extract HDR10+ data!")
        return None

    _ = proc.communicate()

    if check_file(out_file):
        return out_file
    log.warning("Issue with HDR10+ metadata file!")
    return None


def check_file(fpath):
    """
    Check fpath exists/not empty

    Checks if file exists and is not zero bytes

    Returns:
        bool : True if file exists and has data, False otherwise

    """

    if fpath is None:
        return False

    if not os.path.isfile(fpath):
        return False

    if os.stat(fpath).st_size == 0:
        os.remove(fpath)
        return False

    return True
