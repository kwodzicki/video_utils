import logging;
from logging.handlers import RotatingFileHandler;
import os, stat, time;

from video_utils.utils.plex_utils import plexDVR_Rename;
from video_utils.comremove import comremove;
from video_utils.videoconverter import videoconverter;
from video_utils._logging import plexFMT;

log = logging.getLogger('video_utils');                                         # Get the video_utils logger
for handler in log.handlers:                                                    # Iterate over all the handlers
  if handler.get_name() == 'main':                                              # If found the main handler
    handler.setLevel(logging.INFO);                                             # Set log level to info
    break;                                                                      # Break for loop to save some iterations

def Plex_DVR_PostProcess(in_file, 
     logdir    = None, 
     threads   = None, 
     cpulimit  = None,
     language  = None,
     verbose   = False,
     no_srt    = False):
  '''
  Name:
    Plex_DVR_PostProcess
  Purpose:
    A python function to post process Plex DVR files.
    This function does a few things:
      - Renames file to match convenction set by video_utils package
      - Attempts to remove commercials using comskip
      - Transcodes to h264
  Inputs:
    in_file  : Path to file to process
  Outputs:
    Returns status of transocde
  Keywords:
    logdir    : Directory for any extra log files
    threads   : Number of threads to use for comskip and transcode
    cpulimit  : Percentage to limit cpu usage to
    language  : Language for audio/subtitles
    verbose   : Increase verbosity
    no_srt    : If set, no SRT subtitle files created
  '''
  noHandler = True;                                                             # Initialize noHandler to True
  for handler in log.handlers:                                                  # Iterate over all handlers
    if handler.get_name() == plexFMT['name']:                                   # If handler name matches plexFMT['name']
      noHandler = False;                                                        # Set no handler false
      break;                                                                    # Break for loop

  if noHandler:    
    rfh = RotatingFileHandler(plexFMT['file'], 
            backupCount = plexFMT['backupCount'],
            maxBytes    = plexFMT['maxBytes']);                                 # Set up rotating file handler
    rfh.setFormatter( plexFMT['formatter'] );
    rfh.setLevel(     plexFMT['level']     );                                   # Set the logging level
    rfh.set_name(     plexFMT['name']      );                                   # Set the log name
    log.addHandler( rfh );                                                      # Add hander to the main logger
    
    info = os.stat( plexFMT['file'] );                                          # Get information about the log file
    if (info.st_mode & plexFMT['permissions']) != plexFMT['permissions']:       # If the permissions of the file are not those requested
      try:                                                                      # Try to 
        os.chmod( plexFMT['file'], plexFMT['permissions'] );                    # Set the permissions of the log file
      except:
        log.info('Failed to change log permissions; this may cause issues')
  
  log.info('Input file: {}'.format( in_file ) );
  file, info = plexDVR_Rename( in_file );                                       # Try to rename the input file using standard convention and get parsed file info; creates hard link to source file
  if not file:                                                                  # if the rename fails
    log.critical('Error renaming file');                                        # Log error
    return 1, info;                                                             # Return from function
  
  com_inst = comremove(threads=threads, cpulimit=cpulimit, verbose=verbose);    # Set up comremove instance
  status   = com_inst.process( file );                                          # Try to remove commercials from video
  if not status:                                                                # If comremove failed
    log.cirtical('Error cutting commercials');                                  # Log error
    return 1, info;                                                             # Exit script
  
  inst = videoconverter( 
    log_dir       = logdir,
    in_place      = True,
    no_hb_log     = True,
    threads       = threads,
    cpulimit      = cpulimit,
    language      = language,
    remove        = True,
    srt           = not no_srt);                                               # Set up video converter instance; we want to delete the hardlink
  
  inst.transcode( file );                                                       # Run the transcode
  return inst.transcode_status, info;                                           # Return transcode status