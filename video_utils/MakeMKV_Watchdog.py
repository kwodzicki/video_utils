import logging

import os, time, re
from threading import Thread
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from . import isRunning
from .videoconverter import VideoConverter
from .plex.plexMediaScanner import plexMediaScanner
from .utils.handlers import sendEMail

TIMEOUT =  1.0
SLEEP   = 30.0

class MakeMKV_Watchdog( FileSystemEventHandler ):
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.log         = logging.getLogger(__name__)
    self.log.info('Starting up...')

    fileExt       = kwargs.pop('fileExt', None)                                     # Try to get fileExt keyword from keyword dictionary 
    recursive     = kwargs.pop('recursive', False)                                  # Sets watchdog to recursive
    if (fileExt is None):                                                           # If fileExt is None
      self.fileExt = ('.mkv',)                                                      # Set to fileExt attribute to default of '.mkv'
    elif isinstance(fileExt, str):                                                  # Else, if it is string
      self.fileExt = (fileExt,)                                                     # Set fileExt attribute to tuple of fileExt
    elif isinstance(fileExt, list):                                                 # Else, if it is list
      self.fileExt = tuple(fileExt)                                                 # Set fileExt attribute to tuple of fileExt
    else:                                                                           # Else
      self.fileExt = fileExt                                                        # Set fileExt attribute using fileExt keyword value

    self.converter = VideoConverter( **kwargs ) 
    self.Queue     = Queue()                                                        # Initialize queue for sending files to converting thread
    self.Observer  = Observer()                                                     # Initialize a watchdog Observer
    for arg in args:                                                                # Iterate over input arguments
      self.Observer.schedule( self, arg, recursive=recursive )                      # Add each input argument to observer as directory to watch; recursively
      for file in self._getDirListing( arg ):                                       # Iterate over all files (if any) in the input directory
        self.Queue.put( file )                                                      # Enqueue the file
 
    self.Observer.start()                                                           # Start the observer

    self.__runThread = Thread( target = self._run )                                 # Thread for dequeuing files and converting
    self.__runThread.start()                                                        # Start the thread

  def on_created(self, event):
    """Method to handle events when file is created."""

    if event.is_directory: return                                                   # If directory; just return
    if event.src_path.endswith( self.fileExt ):
      self.Queue.put( event.src_path )                                              # Add split file path (dirname, basename,) tuple to to_convert list
      self.log.debug( 'New file added to queue : {}'.format( event.src_path) )      # Log info

  def on_moved(self, event):
    """Method to handle events when file is created."""

    if event.is_directory: return                                                   # If directory; just return
    if event.dest_path.endswith( self.fileExt ):
      self.Queue.put( event.dest_path )                                             # Add split file path (dirname, basename,) tuple to to_convert list
      self.log.debug( 'New file added to queue : {}'.format( event.dest_path) )     # Log info

  def join(self):
    """Method to wait for the watchdog Observer to finish."""

    self.Observer.join()                                                            # Join the observer thread

  def _getDirListing(self, dir):
    """
    Get list of files in a directory (non-recursive), that ends with given extension

    Arguments:
      dir (str): Path of directory to search

    Keyword arguments:
      None 

    Returns:
      list: Files

    """

    files = []
    for file in os.listdir(dir):
      if file.endswith( self.fileExt ):
        path = os.path.join( dir, file )
        if os.path.isfile( path ):
          files.append( path )
    return files

  def _checkSize(self, file):
    """
    Method to check that file size has stopped changing

    Arguments:
      file (str): Full path to a file

    Keyword arguments:
      None

    Returns:
      None

    """

    self.log.debug( f'Waiting for file to finish being created : {file}' )
    prev = -1                                                                       # Set previous file size to -1

    try:
      curr = os.stat(file).st_size                                                  # Get current file size
    except Exception as err:
      self.log.debug( f"Failed to get file size : {err}" )
      return False

    while (prev != curr) and isRunning():                                           # While sizes differ and isRunning()
      time.sleep(SLEEP)                                                             # Sleep a few seconds seconds
      prev = curr                                                                   # Set previous size to current size
      try:
        curr = os.stat(file).st_size                                                  # Get current file size
      except Exception as err:
        self.log.debug( f"Failed to get file size : {err}" )
        return False

    if not isRunning():
      return False

    return prev == curr

  @sendEMail
  def _process(self, fname):

    if not self._checkSize( fname ):                                           # If file size check fails, just return; this will block for a while
      return

    try:        
      out_file = self.converter.transcode( fname )                             # Convert file 
    except:
      self.log.exception('Failed to convert file')
    else:
      if isinstance(out_file, str) and isRunning():
        plexMediaScanner( 
          'TV Shows' if self.converter.metaData.isEpisode else 'Movies',
          path = os.path.dirname( out_file )
        )
 
  def _run(self, **kwargs):
    """
    A thread to dequeue video file paths and convert them

    Arguments:
      None

    Keywords:
      **kwargs

    Returns:
      None

    """

    while isRunning():                                                          # While the kill event is NOT set
      try:                                                                      # Try
        file = self.Queue.get( timeout = TIMEOUT )                              # Get a file from the queue; block for 0.5 seconds then raise exception
      except:                                                                   # Catch exception
        continue                                                                # Do nothing

      self._process( file )
      self.Queue.task_done() 

    self.log.info('MakeMKV watchdog stopped!')
    self.Observer.stop()
