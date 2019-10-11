import logging
from logging.handlers import RotatingFileHandler

import os, time
from threading import Thread, Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from video_utils import _killEvent
from video_utils.plex.DVRconverter import DVRconverter

class library_watchdog( FileSystemEventHandler ):
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.log         = logging.getLogger(__name__)
    self.recordings  = []
    self.converting  = []
    self.nConversion = 0
    self.concurrency = kwargs.pop('concurrency', 1)
    self.kwargs      = kwargs

    self.Observer    = Observer()
    for arg in args:
      self.Observer.schedule( self, arg, recursive = True )
    self.Observer.start()

    self.Lock   = Lock()
    self.thread = Thread( target = self.__stop )
    self.thread.start()

  def on_created(self, event):
    if event.is_directory: return
    if ('.grab' in event.src_path):                                                 # If is directory 
      with self.Lock:                                                                 # Acquire Lock so other events cannot change to_convert list at same time
        self.recordings.append( os.path.split(event.src_path) )                      # Add split file path (dirname, basename,) tuple to to_convert list
    else:
      with self.Lock:                                                               # Acquire Lock so other events cannot change to_convert list at same time
        fDir, fName = os.path.split(event.src_path)                                 # Split file source path
        match       = False                                                         # Set to_convert local variable to None
        i           = 0                                                            # Initialize counter to zero (0)                                       
        while (i < len(self.recordings)):                                           # Iterate over all tuples in to_convert list
          match = (self.recordings[i][1] == fName)                                      # If the file base name from to_convert attribute matches newly crated file base name
          if match:
            self.log.debug( 'New recoding moved from {} --> {}'.format(
                  os.path.join( *self.recordings[i], event.src_path ) ) )           # Log some information
            self.recordings.pop( i )                                                # Pop off the tuple from to_convert attribute
            break
          i += 1

      if match:
        with self.lock: 
          self.nConversion += 1                                        # Increment number of conversions occuring
          self.converting.append( event.src_path )

        while (self.nConversion > self.concurrency) and (not _killEvent.is_set()): 
          time.sleep(0.5)
        DVRconverter(event.src_path, **self.kwargs)                         # Convert file 

        with self.lock:
          self.nConversion -= 1                                        # Decrement number of conversions occuring
          self.converting.remove( event.src_path )

  def wait(self):
    while self.Observer.is_alive():
      time.sleep(0.5)    

  def __stop(self):
    _killEvent.wait()
    self.log.info('Plex watchdog stopped!')
    self.Observer.stop()
