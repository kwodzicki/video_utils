import logging

import os, time, re
from threading import Thread
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from . import isRunning
from .videoconverter import VideoConverter
from .videotagger.metadata.getTMDb_Info import getTMDb_Info
from .videotagger.metadata.getTVDb_Info import getTVDb_Info
from .plex.plexMediaScanner import plexMediaScanner


class MakeMKV_Watchdog( FileSystemEventHandler ):
  seasonEp = re.compile( r'[sS](\d{2,4})[eE](\d{2,4})' )
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.log         = logging.getLogger(__name__)
    self.log.info('Starting up...')

    fileExt       = kwargs.pop('fileExt', None)                                     # Try to get fileExt keyword from keyword dictionary 
    if (fileExt is None):                                                           # If fileExt is None
      self.fileExt = ('.mkv',)                                                      # Set to fileExt attribute to default of '.mkv'
    elif isinstance(fileExt, str):                                                  # Else, if it is string
      self.fileExt = (fileExt,)                                                     # Set fileExt attribute to tuple of fileExt
    elif isinstance(fileExt, list):                                                 # Else, if it is list
      self.fileExt = tuple(fileExt)                                                 # Set fileExt attribute to tuple of fileExt
    else:                                                                           # Else
      self.fileExt = fileExt                                                        # Set fileExt attribute using fileExt keyword value

    self.converter = VideoConverter( **kwargs ) 
    self.Queue     = Queue()                                                         # Initialize queue for sending files to converting thread
    self.Observer  = Observer()                                                      # Initialize a watchdog Observer
    for arg in args:                                                                # Iterate over input arguments
      self.Observer.schedule( self, arg, recursive = True )                         # Add each input argument to observer as directory to watch; recursively
      for file in self._getDirListing( arg ):                                       # Iterate over all files (if any) in the input directory
        self.Queue.put( file )                                                      # Enqueue the file
 
    self.Observer.start()                                                           # Start the observer

    self.__runThread = Thread( target = self.__run )                                # Thread for dequeuing files and converting
    self.__runThread.start()                                                        # Start the thread

  def on_created(self, event):
    '''
    Purpose:
      Method to handle events when file is created.
    '''
    if event.is_directory: return                                                   # If directory; just return
    if event.src_path.endswith( self.fileExt ):
      self.Queue.put( event.src_path )                                              # Add split file path (dirname, basename,) tuple to to_convert list
      self.log.debug( 'New file added to queue : {}'.format( event.src_path) )      # Log info

  def join(self):
    '''
    Method to wait for the watchdog Observer to finish.
    The Observer will be stopped when _sigintEvent or _sigtermEvent is set
    '''
    self.Observer.join()                                                            # Join the observer thread

  def fileRename(self, file):
    '''
    Method to rename file to Plex compatible naming based
    on TVDb ID or TMDb ID in file name.
    Assume using input file convention outlined in docs.
    See following for Plex conventions:
      https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/
      https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/
    Inputs:
      file  : Full path to file
    '''
    fileDir, fileBase = os.path.split(file)
    fileBase, fileExt = os.path.splitext( fileBase )

    seasonEp = self.seasonEp.findall( fileBase )
    if (len(seasonEp) == 1): 
      self.log.info( 'File is episode: {}'.format(file) )
      TVDbID = fileBase.split('.')[0]
      info = getTVDb_Info( TVDbID = TVDbID, seasonEp = tuple( map(int, seasonEp[0]) ) )
      if info:
        fName = 'S{:02d}E{:02d} - {}.{}{}'.format(
          info['airedSeason'], info['airedEpisodeNumber'], info['episodeName'], 
          TVDbID, fileExt
        )
   
    else:
      self.log.info( 'File is movie: {}'.format(file) )
      TMDbID, extra = fileBase.split('.')
      info = getTMDb_Info( TMDbID = TMDbID )
      if info:
        fName = '{} ({}).{}.{}{}'.format(
            info['title'], info['year'], extra, TMDbID, fileExt
        )
    if info: 
      newFile = os.path.join( fileDir, fName )    
      self.log.info( 'Renaming file: {} ---> {}'.format(file, newFile) )
      os.rename( file, newFile )
      return newFile, info

    return file, None

  def _getDirListing(self, dir):
    '''
    Purpose:
      Method to get list of files in a directory (non-recursive), that
      ends with given extension
    Inputs:
      dir  : Path of directory to search
    Keywords:
      ext  : Tuple of extensions to check, default = ('.mkv',)
    Outputs:
      Returns list of files
    '''
    files = []
    for file in os.listdir(dir):
      if file.endswith( self.fileExt ):
        path = os.path.join( dir, file )
        if os.path.isfile( path ):
          files.append( path )
    return files

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
 
  def __run(self, **kwargs):
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
    while isRunning():                                                          # While the kill event is NOT set
      try:                                                                      # Try
        file = self.Queue.get( timeout = 0.5 )                                  # Get a file from the queue; block for 0.5 seconds then raise exception
      except:                                                                   # Catch exception
        continue                                                                # Do nothing

      self._checkSize( file )                                                   # Wait to make sure file finishes copying/moving

      file, metaData = self.fileRename( file )
    
      try:        
        out_file = self.converter.transcode( file, metaData = metData )         # Convert file 
      except:
        self.log.exception('Failed to convert file')
      else:
        plexMediaScanner('scan', directory = os.path.dirname(out_file),
          section = 'TV Shows' if self.converter.is_episode else 'Movies')

      self.Queue.task_done() 

    self.log.info('MakeMKV watchdog stopped!')
    self.Observer.stop()
