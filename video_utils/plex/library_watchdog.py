import logging

import os, time
from subprocess import Popen, STDOUT, DEVNULL
from threading import Thread, Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from video_utils import _sigintEvent, _sigtermEvent
from video_utils.config import plex_dvr

from video_utils.plex.DVRconverter import DVRconverter
from video_utils.plex.utils import DVRqueue

class library_watchdog( FileSystemEventHandler ):
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.log         = logging.getLogger(__name__)
    self.log.info('Starting up...')

    self.recordings  = []                                                           # Initialize list to store paths of newly started DVR recordings
    self.converting  = DVRqueue( plex_dvr['queueFile'] )                                     # Initialize DVRqueue, this is a subclass of list that, when items modified, will save pickled list to file as backup
      
    self.converter = None
    self.script    = kwargs.get('script', None)
    if not self.script:
      self.converter = DVRconverter( **kwargs )

    self.Lock        = Lock()                                                       # Lock for ensuring threads are safe
 
    self.Observer    = Observer()                                                   # Initialize a watchdog Observer
    for arg in args:                                                                # Iterate over input arguments
      self.Observer.schedule( self, arg, recursive = True )                         # Add each input argument to observer as directory to watch; recursively
    self.Observer.start()                                                           # Start the observer

    self.__runThread = Thread( target = self.__run )                                # Thread for dequeuing files and converting
    self.__runThread.start()                                                        # Start the thread
 
  def on_created(self, event):
    '''
    Purpose:
      Method to handle events when file is created.
    '''
    if event.is_directory: return                                                   # If directory; just return
    if ('.grab' in event.src_path):                                                 # If '.grab' is in the file path, then it is a new recording! 
      with self.Lock:                                                               # Acquire Lock so other events cannot change to_convert list at same time
        self.recordings.append( os.path.split(event.src_path) )                     # Add split file path (dirname, basename,) tuple to to_convert list
      self.log.debug( 'A recording started : {}'.format( event.src_path) )          # Log info
    else:
      self.checkRecording( event.src_path )                                     # Check if new file is a DVR file (i.e., file has been moved)

  def on_moved(self, event):
    '''
    Purpose:
      Method to handle events when file is moved.
    '''
    if (not event.is_directory):
      self.checkRecording( event.dest_path )         # If not a directory and the destination file was a recording (i.e.; checkRecordings)

  def checkRecording(self, file):
    '''
    Purpose:
      A method to check that newly created file is 
      a DVR recording
    Input:
      file : Path to newly created file from event
              in on_created() method
    Outputs:
      Boolean : True if file is a recording (i.e., it's just been moved) or
                 False if it is not
    Keywords:
      None.
    '''
    with self.Lock:                                                                 # Acquire Lock so other events cannot change to_convert list at same time
      fDir, fName = os.path.split( file )                                           # Split file source path
      i           = 0                                                               # Initialize counter to zero (0)                                       
      while (i < len(self.recordings)):                                             # Iterate over all tuples in to_convert list
        if (self.recordings[i][1] == fName):                                        # If the name of the input file matches the name of the recording file
          self.log.debug( 'Recoding moved from {} --> {}'.format(
                os.path.join( *self.recordings[i] ), file ) )                       # Log some information
          self.converting.append( file )                                            # Append to converting list; this will trigger update of queue file
          self.recordings.pop( i )                                                  # Pop off the tuple from to_convert attribute
          return True                                                               # Return True
        i += 1                                                                      # Increment i
      return False                                                                  # If made it here, then file is NOT DVR recording, return False

  def join(self):
    '''
    Method to wait for the watchdog Observer to finish.
    The Observer will be stopped when _sigintEvent or _sigtermEvent is set
    '''
    self.Observer.join()                                                            # Join the observer thread

  def _checkSize(self, file):
    '''
    Purpose:
      Method to check that file size has stopped changing
    Inputs:
      file   : Full path to a file
    Outputs:
      None.
    Keywords:
      None.
    '''
    self.log.debug('Waiting for file to finish being created')
    prev = -1                                                                       # Set previous file size to -1
    curr = os.path.getsize(file)                                                    # Get current file size
    while (prev != curr):                                                           # While sizes differ
      time.sleep(0.5)                                                               # Sleep 0.5 seconds
      prev = curr                                                                   # Set previous size to current size
      curr = os.path.getsize(file)                                                  # Update current size
 
  def __run(self):
    '''
    Purpose:
      A thread to dequeue video file paths and convert them
    Inputs:
      None.
    Outputs:
      None.
    Keywords:
      None.
    '''
    while (not _sigintEvent.is_set()) and (not _sigtermEvent.is_set()):         # While the kill event is NOT set
      try:                                                                      # Try
        file = self.converting[0]                                    # Get a file from the queue; block for 0.5 seconds then raise exception
      except:                                                                   # Catch exception
        time.sleep(0.5)
        continue                                                                # Do nothing

      self._checkSize( file )                                     # Wait to make sure file finishes copying/moving
      if self.script:
        self.log.info('Running script : {}'.format(self.script) )
        proc = Popen( [self.script, file], stdout=DEVNULL, stderr=STDOUT )
        proc.communicate()
        status = proc.returncode
        if (status != 0):
          self.log.error( 'Script failed with exit code : {}'.format(status) )
      else:
        try:        
          status, out_file, info = self.converter.convert( file )  # Convert file 
        except:
          self.log.exception('Failed to convert file')

      self.converting.remove( file )                              # Remove from converting list; this will tirgger update of queue file
 
    self.log.info('Plex watchdog stopped!')
    self.Observer.stop()
