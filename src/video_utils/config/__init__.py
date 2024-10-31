"""
Configuration settings for package

"""

import logging
import os
import shutil
import stat
import argparse

import yaml

from .. import __version__
from ..utils import HALFTHREADS

PKGNAME = __name__.split('.', maxsplit=1)[0]
HOME = os.path.expanduser('~')
DATADIR = os.path.join(os.path.dirname(__file__))
APPDIR = os.path.join(HOME, 'Library', 'Application Support', PKGNAME)
CACHEDIR = os.path.join(APPDIR, 'cache')
LOGDIR = os.path.join(APPDIR, 'Logs')
PLEXTOKEN = os.path.join(APPDIR, '.plextoken')
CONFIG = os.path.join(HOME, f'.{PKGNAME}.yml')


def install_config():

    if os.path.isfile(CONFIG):
        if os.stat(CONFIG).st_size > 0:
            return

    shutil.copy(
        os.path.join(DATADIR, 'settings.yml'),
        CONFIG,
    )


_ = install_config()

try:
    with open(CONFIG, mode='r', encoding='utf8') as fid:
        CONFIG = yaml.load(fid, Loader=yaml.SafeLoader)
except:
    CONFIG = {}

COMSKIPINI = os.path.join(os.path.dirname(__file__), 'comskip.ini')

"""Settings for screen logger and file logger"""
screenFMT = {
    'name': 'main',
    'level': logging.CRITICAL,
    'formatter': logging.Formatter(
        '%(levelname)-8s - %(asctime)s - %(name)s - %(message)s',
        '%Y-%m-%d %H:%M:%S',
    ),
}

ROTATING_FORMAT = {
    'maxBytes': 5 * 1024**2,
    'backupCount': 4,
}

fileFMT = {
    'level': logging.INFO,
    'formatter': logging.Formatter(
        '%(levelname)-.4s - %(funcName)-15.15s - %(message)s',
        '%Y-%m-%d %H:%M:%S',
    ),
}

plexFMT = {
    'pidFile': os.path.join(APPDIR, 'Plex_DVR_Watchdog.pid'),
    'file': os.path.join(LOGDIR, 'Plex_DVR_Watchdog.log'),
    'transcode': os.path.join(LOGDIR, 'Plex_DVR_Watchdog_Transcode.log'),
    'name': 'plex_dvr',
    'level': logging.DEBUG,
    'formatter': logging.Formatter(
        '%(levelname)-.4s - %(asctime)s - '
        '%(name)s.%(funcName)-15.15s - %(message)s',
        '%Y-%m-%d %H:%M:%S',
    ),
    'permissions': (
        stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | stat.S_IRGRP
        | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    ),
}

MakeMKVFMT = {
    'pidFile': os.path.join(APPDIR, 'MakeMKV_Watchdog.pid'),
    'file': os.path.join(LOGDIR, 'MakeMKV_Watchdog.log'),
    'name': 'MakeMKV',
    'level': logging.DEBUG,
    'formatter': logging.Formatter(
        '%(levelname)-.4s - %(asctime)s - '
        '%(name)s.%(funcName)-15.15s - %(message)s',
        '%Y-%m-%d %H:%M:%S',
    ),
    'permissions': (
        stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | stat.S_IRGRP
        | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    ),
}

# do NOT use opensubtitles info in other programs, register for your own
opensubtitles = {
    'url': 'https://api.opensubtitles.org:443/xml-rpc',
    'user_agent': 'makemkv_to_mp4'
}

# Path to a lock file to stop multiple instances from running at same time
plex_dvr = {
    'queueFile': os.path.join(APPDIR, 'plex_dvr_convert_queue.pic'),
    'lock_file': '/tmp/Plex_DVR_PostProcess.lock',
    'lock_perm': (
        stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | stat.S_IRGRP
        | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    ),
}

BASEPARSER = argparse.ArgumentParser(
    add_help=False,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
BASEPARSER.add_argument(
    "-t", "--threads",
    type=int,
    default=None,
    help="Set number of CPUs to use.",
)
BASEPARSER.add_argument(
    "-c", "--cpulimit",
    type=int,
    default=75,
    help=(
        "Set to limit CPU usage. Set to 0 to disable CPU limiting. "
        "Has no effect if cpulimit CLI is not installed."
    ),
)
BASEPARSER.add_argument(
    "--lang",
    type=str,
    default='eng',
    nargs='+',
    help=(
        "Set audio and subtitle language(s) using three (3) character codes "
        "(ISO 639-2). For multiple langauges, seperate using spaces; e.g., "
        "'--lage eng fra' for English and French."
    ),
)
BASEPARSER.add_argument(
    "--no-remove",
    action="store_true",
    help=(
        "Set to disbale removing input file after transcode. "
        "Default is to delete soruce file."
    ),
)
BASEPARSER.add_argument(
    "--no-srt",
    action="store_true",
    help="Set to disbale conversion of VobSub(s) to SRT",
)
BASEPARSER.add_argument(
    "--loglevel",
    type=int,
    help="Set logging level",
)
BASEPARSER.add_argument(
    "--version",
    action='version',
    version='%(prog)s ' + __version__,
)


def get_comskip_log(prog_name: str, logdir: str | None = None) -> str:
    """
    Generate file path to comskip log file.

    Arguments:
        prog_name (str): Name of the running program. This will be prepended
            to :code:`_Comskip.log`

    Keyword arguments:
        logdir (str): Path to logging directory

    Returns:
        str: Path to log file

    """

    if logdir is None:
        logdir = LOGDIR
    return os.path.join(logdir, f'{prog_name}_Comskip.log')


def get_transcode_log(prog_name: str, logdir: str | None = None) -> str:
    """
    Generate file path to transcode log file.

    Arguments:
        prog_name (str): Name of the running program. This will be prepended
            to :code:`_Transcoder.log`

    Keyword arguments:
        logdir (str): Path to logging directory

    Returns:
        str: Path to log file

    """
    if logdir is None:
        logdir = LOGDIR
    return os.path.join(logdir, f'{prog_name}_Transcoder.log')
