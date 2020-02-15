import logging
import os

from .. import isRunning#_sigintEvent, _sigtermEvent
from ..videoconverter import VideoConverter
from ..utils.ffmpeg_utils import checkIntegrity

from .plexMediaScanner import plexMediaScanner
from .utils import plexDVR_Rename


class DVRconverter(VideoConverter): 
  '''
  DVRconverter

  Purpose:
    A class to combine the VideoConverter and ComRemove classes for
    post-processing Plex DVR recordings
  '''
  def __init__(self,
     logdir      = None, 
     lang        = None,
     verbose     = False,
     destructive = False,
     no_remove   = False,
     no_srt      = False,
     **kwargs):
    '''
    Name:
      __init__ 
    Purpose:
      Method to initialize class and superclasses along with
      a few attributes
    Inputs:
      None.
    Keywords:
      logdir      : Directory for any extra log files
      threads     : Number of threads to use for comskip and transcode
      cpulimit    : Percentage to limit cpu usage to
      lang        : Language for audio/subtitles
      verbose     : Increase verbosity
      destructive : If set, will cut commercials out of file. Note that
                     commercial identification is NOT perfect, so this could
                     lead to missing pieces of content. 
                     By default, will add chapters to output file marking
                     commercial breaks. This enables easy skipping, and does
                     not delete content if commercials misidentified
      no_remove   : If set, input file will NOT be deleted
      no_srt      : If set, no SRT subtitle files created
      Any other keyword argument is ignored

   Keywords:
      logdir      : Directory for any extra log files
      threads     : Number of threads to use for comskip and transcode
      cpulimit    : Percentage to limit cpu usage to
      lang        : Language for audio/subtitles
      verbose     : Increase verbosity
      destructive : If set, will cut commercials out of file. Note that
                     commercial identification is NOT perfect, so this could
                     lead to missing pieces of content. 
                     By default, will add chapters to output file marking
                     commercial breaks. This enables easy skipping, and does
                     not delete content if commercials misidentified
      no_remove   : If set, input file will NOT be deleted
      no_srt      : If set, no SRT subtitle files created
    '''
    super().__init__(
      log_dir       = logdir,
      in_place      = True,
      no_ffmpeg_log = True,
      lang          = lang,
      remove        = not no_remove,
      subfolder     = False,
      srt           = not no_srt,
      **kwargs)

    self.destructive = destructive

  ######################################################################################
  def convert(self, in_file):
    '''
    Name:
      convert
    Purpose:
      Method to actually post process Plex DVR files.
      This method does a few things:
        - Renames file to match convenction set by video_utils package
        - Attempts to remove commercials using comskip
        - Transcodes to h264
    Inputs:
      in_file  : Path to file to process
    Outputs:
      Returns success of transocde
    Keywords:
      None.
    '''
    in_file      = os.path.realpath( in_file )                                      # Get real input file path 
    out_file     = None                                                             # Set out_file to None
    info         = None
    no_remove    = not self.remove                                                  # Set local no_remove value as opposite of remove flag 
    success      = False                                                            # Default success to bad
    self.in_file = in_file                                                          # Set in_file class attribute; this will trigger mediainfo parsing

    self.log.info('Input file: {}'.format( in_file ) )

    self.log.debug('Checking file integrity')
#    if (not self.isValidFile()) or (not checkIntegrity(in_file)):                  # If is NOT a valid file; i.e., video stream size is larger than file size OR found 'overread' errors in file
    if (not self.isValidFile()):                                                    # If is NOT a valid file; i.e., video stream size is larger than file size OR found 'overread' errors in file
      self.log.warning('File determined to be invalid, deleting: {}'.format(in_file) )
      no_remove = True                                                              # Set local no_remove variable to True; done so that directory is not scanned twice when the Plex Media Scanner command is run
      self._cleanUp( in_file )                                                      # If infile exists, delete it
    else:                                                                           # Is, is a valid file
      file, info = plexDVR_Rename( in_file );                                       # Try to rename the input file using standard convention and get parsed file info; creates hard link to source file
      if not file:                                                                  # if the rename fails
        self.log.critical('Error renaming file: {}'.foramt(in_file))                # Log error
        return success, out_file                                                    # Return from function
 
      if not isRunning(): return success, out_file
      out_file = self.transcode( file,
                metaData          = info, 
                chapters          = not self.destructive,
                removeCommercials = True )                                          # Run the transcode

      self._cleanUp( file )                                                         # If the renamed; i.e., hardlink to original file, exists

      if (self.transcode_status == 0):
        success = True
      elif (self.transcode_status == 5):
        self.log.critical('Assuming bad file deleting: {}'.format(in_file) )        # Log error
        no_remove = True                                                            # Set local no_remove variable to True; done so that directory is not scanned twice when the Plex Media Scanner command is run
        self._cleanUp( in_file )                                                    # If infile or file exists, delete it
      elif not isRunning():                                                         # Else, if not runnint 
        return success, out_file                                                    # Return status and out_file
      else:                                                                         # Else
        self.log.critical('Failed to transcode file. Will delete input')            # Only
        no_remove = True                                                            # Set local no_remove variable to True; done so that directory is not scanned twice when the Plex Media Scanner command is run
        self._cleanUp( in_file, out_file )                                          # If infile exists, delete it

    if isRunning():                                                                 # If a file name was returned AND no_remove is False
      args   = ('scan',)                                                            # Set arguements for plexMediaScanner function
      kwargs = {'section'   : 'TV Shows',
                'directory' : os.path.dirname( in_file )}                           # Set keyword arguments for plexMediaScanner function
      plexMediaScanner( *args, **kwargs )
      if not no_remove:                                                             # If no_remove is NOT set, then we want to delete in_file and rescan the directory so original file is removed from Plex
        self._cleanUp( in_file )                                                    # Delete the file
        if not os.path.isfile( in_file ):                                           # If file no longer exists; if it exists, don't want to run Plex Media Scanner for no reason
          self.log.debug('Original file removed, rescanning: {}'.format(in_file))   # Debug information
          plexMediaScanner( *args, **kwargs )                                       # Run Ple Media Scanner to remove deleted file from library

    return success, out_file                                                        # Return transcode success, new file path, and info
