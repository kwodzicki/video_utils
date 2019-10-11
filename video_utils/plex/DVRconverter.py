import logging;
import os, time;

from video_utils.comremove import comremove;
from video_utils.videoconverter import videoconverter;
from video_utils._logging import plexFMT;

from video_utils.plex.utils import plexDVR_Rename;

log = logging.getLogger('video_utils');                                         # Get the video_utils logger
for handler in log.handlers:                                                    # Iterate over all the handlers
  if handler.get_name() == 'main':                                              # If found the main handler
    handler.setLevel(logging.INFO);                                             # Set log level to info
    break;                                                                      # Break for loop to save some iterations

def DVRconverter(in_file, 
     logdir      = None, 
     threads     = None, 
     cpulimit    = None,
     language    = None,
     verbose     = False,
     destructive = False,
     no_remove   = False,
     no_srt      = False):
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
    logdir      : Directory for any extra log files
    threads     : Number of threads to use for comskip and transcode
    cpulimit    : Percentage to limit cpu usage to
    language    : Language for audio/subtitles
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
  
  in_file = os.path.realpath( in_file )                                         # Get real input file path 
  log.info('Input file: {}'.format( in_file ) );
  file, info = plexDVR_Rename( in_file );                                       # Try to rename the input file using standard convention and get parsed file info; creates hard link to source file
  if not file:                                                                  # if the rename fails
    log.critical('Error renaming file');                                        # Log error
    return 1, info;                                                             # Return from function
  
  com_inst = comremove(threads=threads, cpulimit=cpulimit, verbose=verbose);    # Set up comremove instance
  status   = com_inst.process( file, chapters = not destructive )               # Try to remove commercials from video
  if not status:                                                                # If comremove failed
    log.cirtical('Error cutting commercials');                                  # Log error
    return 1, info;                                                             # Exit script
  
  inst = videoconverter( 
    log_dir       = logdir,
    in_place      = True,
    no_ffmpeg_log = True,
    threads       = threads,
    cpulimit      = cpulimit,
    language      = language,
    remove        = True,
    subfolder     = False,
    srt           = not no_srt);                                                # Set up video converter instance; we want to delete the hardlink
  
  out_file = inst.transcode( file );                                            # Run the transcode

  if os.path.isfile( file ):                                                    # If the renamed; i.e., hardlink to original file, exists
    os.remove( file );                                                          # Delete it

  if (out_file is not False) and (not no_remove):                               # If a file name was returned AND no_remove is False
    if os.path.isfile( in_file ) or os.path.islink( in_file ):                  # If the input file exists OR is an symlink
      os.remove( in_file );                                                     # Remove the input file
    # relpath = os.path.relpath( out_file, start = os.path.dirname( in_file ) );  # Get relative path to output file using directory of the input file as the start path
    # os.symlink( relpath, in_file );                                             # Create a symbolic link from the relative output file path to the input file path; relative link wont break after move
    os.link( out_file, in_file );                                               # Create hard link to the transcoded file using input file name
  return inst.transcode_status, out_file, info;                                 # Return transcode status, new file path, and info
