import logging
import signal
from importlib.metadata import version as get_version

__doc__ = (
    "Collection of utilities to manipulate video files; namely transcoding, "
    "subtitle extraction, audio aligning/downmixing, and metadata editing."
)

__version__ = get_version(__name__)
# Set up the logger for the module
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
stream = logging.StreamHandler()
stream.setFormatter(screenFMT['formatter'])
stream.setLevel(screenFMT['level'])
stream.set_name(screenFMT['name'])

log.addHandler(stream)

# Check for required CLIs
for cli in ['ffmpeg', 'mediainfo']:
    try:
        check_cli(cli)
    except Exception as err:
        log.critical(err)

signal.signal(signal.SIGINT, _handle_sigint)
signal.signal(signal.SIGTERM, _handle_sigterm)

POPENPOOL = PopenPool()

from .config import screenFMT, DATADIR  # DATADIR imported for use else where
from .utils import _handle_sigint, _handle_sigterm
from .utils.check_cli import check_cli
from .utils.subproc_pool import PopenPool

del cli, screenFMT
