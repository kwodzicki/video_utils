import logging

import os, time, re
from threading import Thread, Timer
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from . import isRunning
from .plex.plexMediaScanner import plexMediaScanner
from .utils.handlers import sendEMail

TIMEOUT = 1.0
SLEEP   = 5.0
SLEEP   = 1.0

scanMusic = lambda : plexMediaScanner('scan', 'refresh',  section = 'Music')
 
class Music_Watchdog( FileSystemEventHandler ):
  def __init__(self, outdir, *args, **kwargs):
    super().__init__()
    self.log         = logging.getLogger(__name__)
    self.log.info('Starting up...')

    fileExt       = kwargs.get('fileExt', None)                                     # Try to get fileExt keyword from keyword dictionary 
    if (fileExt is None):                                                           # If fileExt is None
      self.fileExt = ('.wav', '.flac', '.mp3')                                      # Set to fileExt attribute to default
    elif isinstance(fileExt, str):                                                  # Else, if it is string
      self.fileExt = (fileExt,)                                                     # Set fileExt attribute to tuple of fileExt
    elif isinstance(fileExt, list):                                                 # Else, if it is list
      self.fileExt = tuple(fileExt)                                                 # Set fileExt attribute to tuple of fileExt
    else:                                                                           # Else
      self.fileExt = fileExt                                                        # Set fileExt attribute using fileExt keyword value

    self.outdir    = outdir                                                         # Output directory to move music files to; this should be top-level of Plex Media Server music library
    self.scanDelay = kwargs.get('scanDelay', 600.0)                                   # Set default scan delay to 10 minutes
    self.scanTimer = None                                                           # Initailize attribute for keeping track fo plexmediascan timer

    self.srcDirs   = [os.path.join(arg, '') for arg in args]                        # Ensure trailing path separator 
    self.Queue     = Queue()                                                        # Initialize queue for sending files to converting thread
    self.Observer  = Observer()                                                     # Initialize a watchdog Observer
    for srcDir in self.srcDirs:                                                     # Iterate over input arguments
      self.Observer.schedule( self, srcDir, recursive = True )                      # Add each input argument to observer as directory to watch; recursively
      for root, dirs, items in os.walk( srcDir ):                                   # Iterate over all files (if any) in the input directory
        for item in items:
          if item.endswith( self.fileExt ):
            self.Queue.put( os.path.join( root, item ) )                            # Enqueue the file
 
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

  def _checkSize(self, fpath):
    """
    Method to check that file size has stopped changing

    Arguments:
      file (str): Full path to a file

    Keyword arguments:
      None

    Returns:
      None

    """

    self.log.debug('Waiting for file to finish being created')
    if os.path.isfile( fpath ):
      prev = -1                                                                       # Set previous file size to -1
      curr = os.path.getsize(fpath)                                                   # Get current file size
      while (prev != curr):                                                           # While sizes differ
        time.sleep(SLEEP)                                                             # Sleep a few seconds seconds
        prev = curr                                                                   # Set previous size to current size
        curr = os.path.getsize(fpath)                                                 # Update current size
      return True
    return False

  def _removeDir( self, root, fPath ):
    """To remove Artist/Album directories given audio file path"""

    fdir = os.path.dirname( fPath )
    while os.path.commonpath( [root, fdir] ) != fdir:
      print( root, fdir )
      print( os.path.commonpath( [root, fdir] ) )
      try:
        os.rmdir( fdir )
      except:
        return
      else:
        fdir = os.path.dirname( fdir )

#  @sendEMail
  def _process(self, fPath):
    if self._checkSize( fPath ):                                                   # Wait to make sure file finishes copying/moving
      for srcDir in self.srcDirs:
        if srcDir in fPath:
          newPath = fPath.replace( srcDir, '' )
          newPath = os.path.join( self.outdir, newPath )
          print( srcDir )
          print(newPath)
          os.makedirs( os.path.dirname( newPath ), exist_ok=True )
          os.rename( fPath, newPath )
          self._removeDir( srcDir, fPath )

      if isRunning() and self.Queue.empty():                                          # If stillr unning and the queue is empty
        print( 'Queue is empty, scheduling library scan' )
        if self.scanTimer is not None:                                                # If scanTimer is defined
          self.scanTimer.cancel()                                                     # Cancel any previously scheduled scans
        #self.scanTimer = Timer( self.scanDelay, scanMusic )                           # Schedule a scan of the music library
 
  def _run(self):
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

    self.log.info('Music watchdog stopped!')
    self.Observer.stop()
