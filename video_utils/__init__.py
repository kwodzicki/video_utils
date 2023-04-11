import logging
import os, json
import signal
from threading import Event

from .version import __version__
from .utils.check_cli import check_cli
from .config import screenFMT, DATADIR

    
__doc__     = "Collection of utilities to manipulate video files; " + \
  "namely transcoding, subtitle extraction, audio aligning/downmixing, "+\
  "and metadata editing."

# Set up the logger for the module
log = logging.getLogger( __name__ )                                          # Get root logger based on package name
log.setLevel(logging.DEBUG)                                                  # Set root logger level to debug
stream = logging.StreamHandler()
stream.setFormatter( screenFMT['formatter'] )
stream.setLevel( screenFMT['level'] )            # Set the format tot the screen format
stream.set_name( screenFMT['name'] )

log.addHandler( stream )

# Check for required CLIs
for cli in ['ffmpeg', 'mediainfo']:
  try:
    check_cli( cli )
  except Exception as err:
    log.critical( err )

# Set up event and link event set to SIGINT and SIGTERM
_sigintEvent  = Event()
_sigtermEvent = Event()

def _handle_sigint(*args, **kwargs):
  _sigintEvent.set()
  log.error('Caught interrupt...')

def _handle_sigterm(*args, **kwargs):
  _sigtermEvent.set()
  log.error('Caught terminate...')

def isRunning():
  """Check for SIGINT or SIGTERM encountered"""

  return (not _sigintEvent.is_set()) and (not _sigtermEvent.is_set())

signal.signal(signal.SIGINT,  _handle_sigint)
signal.signal(signal.SIGTERM, _handle_sigterm)

from .utils.subproc_pool import PopenPool
POPENPOOL = PopenPool()

del cli, screenFMT
