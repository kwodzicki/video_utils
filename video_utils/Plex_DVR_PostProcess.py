import logging;
from logging.handlers import RotatingFileHandler;
import os, stat, time;

from video_utils.utils.file_rename import file_rename;
from video_utils.comremove import comremove;
from video_utils.videoconverter import videoconverter;
from video_utils._logging import plexFMT;
from video_utils.config import plex_dvr;

log = logging.getLogger('video_utils');                                         # Get the video_utils logger
for handler in log.handlers:                                                    # Iterate over all the handlers
  if handler.get_name() == 'main':                                              # If found the main handler
    handler.setLevel(logging.INFO);                                             # Set log level to info
    break;                                                                      # Break for loop to save some iterations

def rmLock():
  if os.path.isfile( plex_dvr['lock_file'] ): 
    os.remove( plex_dvr['lock_file'] )

def Plex_DVR_PostProcess(in_file, 
     logdir    = None, 
     threads   = None, 
     cpulimit  = None,
     language  = None,
     verbose   = False,
     no_remove = False,
     not_srt   = False):

  while os.path.isfile( plex_dvr['lock_file'] ): time.sleep(1.0);               # While the lock file exists, sleep for 1 second
  open(plex_dvr['lock_file'], 'w').close();                                     # Create the new lock file so other processes have to wait
  os.chmod( plex_dvr['lock_file'], plex_dvr['lock_perm'] );                     # Set permissions on file

  logName   = plexFMT.pop('name');                                              # Get logger name
  noHandler = True;                                                             # Initialize noHandler to True
  for handler in log.handers:                                                   # Iterate over all handlers
    if handler.get_name() == logName:                                           # If handler name matches logName
      noHandler = False;                                                        # Set no handler false
      break;                                                                    # Break for loop

  if noHandler:
    logFile = plexFMT.pop('file');                                              # Pop off file for logging
    logFMT  = plexFMT.pop('formatter');                                         # Pop off formatter
    logLvl  = plexFMT.pop('level');                                             # Pop off the logging level
    logPerm = plexFMT.pop('permissions');                                       # Pop off permissions for the logging file
    logLvl  = logging.DEBUG if verbose else plt
    if verbose: logLvl = logging.DEBUG;                                         # If verbose, then set file handler to DEBUG
    
    rfh = RotatingFileHandler(logFile, **plexFMT);                              # Set up rotating file handler
    rfh.setFormatter( logFMT  );                                                # Set formatter for the handler
    rfh.setLevel(     logLvl  );                                                # Set the logging level
    rfh.set_name(     logName );                                                # Set the log name
    log.addHandler( rfh );                                                      # Add hander to the main logger
    
    info = os.stat( logFile );                                                  # Get information about the log file
    if (info.st_mode & logPerm) != logPerm:                                     # If the permissions of the file are not those requested
      try:                                                                      # Try to 
        os.chmod( logFile, logPerm );                                           # Set the permissions of the log file
      except:
        log.info('Failed to change log permissions; this may cause issues')
  
  log.info('Input file: {}'.format( in_file ) );
  file = file_rename( in_file );                                                # Try to rename the input file using standard convention
  if not file:                                                                  # if the rename fails
    log.critical('Error renaming file');                                        # Log error
    rmLock();                                                                   # Function to remove the lock file
    return 1;                                                                   # Return from function
  
  com_inst = comremove(threads=threads, cpulimit=cpulimit, verbose=verbose);    # Set up comremove instance
  status   = com_inst.process( file );                                          # Try to remove commercials from video
  if not status:                                                                # If comremove failed
    log.cirtical('Error cutting commercials');                                  # Log error
    rmLock();                                                                   # Function to remove the lock file
    return 1;                                                                   # Exit script
  
  inst = videoconverter( 
    log_dir       = logdir,
    in_place      = True,
    no_hb_log     = True,
    threads       = threads,
    cpulimit      = cpulimit,
    language      = language,
    remove        = not no_remove,
    srt           = not not_srt);                                               # Set up video converter instance
  
  inst.transcode( file );                                                       # Run the transcode
  rmLock();                                                                     # Function to remove the lock file
  return inst.transcode_status;                                                 # Return transcode status