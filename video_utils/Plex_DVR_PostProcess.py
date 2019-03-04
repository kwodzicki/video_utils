import logging;
from logging.handlers import RotatingFileHandler;
import os, time;

from video_utils.utils.file_rename import file_rename;
from video_utils.comremove import comremove;
from video_utils.videoconverter import videoconverter;

lock_file = '/tmp/Plex_DVR_PostProcess.lock';                                   # Path to a lock file to stop multiple instances from running at same time
log_file  = '/tmp/Plex_DVR_PostProcess.log';
log_size  = 10 * 1024**2;
log_count = 4;
log = logging.getLogger('video_utils');                                         # Get the video_utils logger
for handler in log.handlers:                                                    # Iterate over all the handlers
  if handler.get_name() == 'main':                                              # If found the main handler
    handler.setLevel(logging.INFO);                                             # Set log level to info
    break;                                                                      # Break for loop to save some iterations
rfh = RotatingFileHandler(log_file, maxBytes=log_size, backupCount=log_count);  # Create a rotatin file handler
log.addHandler( rfh );                                                          # Add hander to the main logger

def rmLock():
  if os.path.isfile( lock_file ): 
    os.remove(lock_file)

def Plex_DVR_PostProcess(in_file, 
     logdir    = None, 
     verbose   = False,
     threads   = None, 
     cpulimit  = None,
     language  = None,
     verbose   = None,
     no_remove = False,
     not_srt   = False):
  if verbose:                                                                   # If verbose, then set file handler to DEBUG
    rfh.setLevel(logging.DEBUG);
  else:                                                                         # Else, set to INFO
    rfh.setLevel(logging.INFO);

  while os.path.isfile( lock_file ): time.sleep(1.0);                           # While the lock file exists, sleep for 1 second
  open(lock_file, 'w').close();                                                 # Create the new lock file so other processes have to wait

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