import logging;
from ._logging import screenFMT;

log = logging.getLogger( __name__ );                                          # Get root logger based on package name
log.setLevel(logging.DEBUG);                                                  # Set root logger level to debug
log.addHandler( logging.StreamHandler() );
log.handlers[0].setFormatter( screenFMT['formatter'] )
log.handlers[0].setLevel( screenFMT['level'] );            # Set the format tot the screen format

#from .videoconverter import videoconverter;
