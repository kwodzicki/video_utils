import logging;
from ._logging import screenFMT;
from .version import __version__;
from subprocess import call, DEVNULL, STDOUT;

# Check for required CLIs
for i in ['HandBrakeCLI', 'ffmpeg', 'mediainfo']:
  if call(['which', i], stdout = DEVNULL, stderr = STDOUT ) != 0: 
    raise Exception( 
      "The following required command line utility was NOT found." +
      " If it is installed, be sure it is in your PATH: " +
      i
    );

__doc__     = "Collection of utilities to manipulate video files; " + \
  "namely transcoding, subtitle extraction, audio aligning/downmixing, "+\
  "and metadata editing."


# Set up the logger for the module
log = logging.getLogger( __name__ );                                          # Get root logger based on package name
log.setLevel(logging.DEBUG);                                                  # Set root logger level to debug
log.addHandler( logging.StreamHandler() );
log.handlers[0].setFormatter( screenFMT['formatter'] )
log.handlers[0].setLevel( screenFMT['level'] );            # Set the format tot the screen format
log.handlers[0].set_name( screenFMT['name'] );

del i, DEVNULL, STDOUT, screenFMT;

#from .videoconverter import videoconverter;
