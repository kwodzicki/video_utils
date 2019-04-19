import logging;
import re;
import numpy as np;
from datetime import timedelta;
from subprocess import Popen, PIPE, STDOUT;

cropPattern = re.compile( r'(?:crop=(\d+:\d+:\d+:\d+))' );                      # Pattern for extracting crop information
resPattern  = re.compile( r'(\d{3,5}x\d{3,5})' );                               # Pattern for video resolution
chunk       = np.full( (128, 4), np.nan );

def cropdetect( infile, dt = 20 ):
  '''
  Name:
    cropdetect
  Purpose:
    A python function that uses FFmpeg to to detect a cropping region for
    video files
  Inputs:
    infile  : Path to input file for crop detection
  Outputs:
    Returns string for FFmpeg video filter in the format crop=w:h:x:y
    or None if no cropping detected
  Keywords:
    dt  : Length of video, in seconds, starting from beginning to use
          for crop detection, default is 20 seconds
  '''
  log  = logging.getLogger(__name__);                                           # Get a logger
  whxy = [ [] for i in range(4) ];                                              # Initialize list of 4 lists for crop parameters
  res  = None;                                                                  # Initialize video resolution to None
  dt   = str( timedelta(seconds = dt) );                                        # Get nicely formatted time
  ss   = timedelta(seconds = 0)
  cmd  = ['ffmpeg', '-nostats', '-ss', '', '-i', infile];                       # Base command for crop detection
  cmd  = cmd + ['-t', dt, '-vf', 'cropdetect', '-f', 'null', '-'];              # Add length, cropdetec filter and pipe to null muxer
  nn   = 0;                                                                     # Counter for number of crop regions detected
  crop = chunk.copy();                                                          # List of crop regions

  log.debug( 'Detecting crop using chunks of length {}'.format( dt ) );

  detect = True;                                                                # Set detect to True; flag for crop detected
  while detect:                                                                 # While detect is True, keep iterating
    detect = False;                                                             # Set detect to False; i.e., at beginning of iteration, assume no crop found
    log.debug( 'Checking crop starting at {}'.format( ss ) );
    cmd[3] = str(ss);                                                           # Set the start offset in the video
    proc   = Popen( cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True ); # Start the command, piping stdout and stderr to a pipe
    line   = proc.stdout.readline();                                            # Read line from pipe
    while line != '':                                                           # While line is not empty
      if res is None:                                                           # If resolution not yet found
        res = resPattern.findall( line );                                       # Try to find resolution information
        res = [int(i) for i in res[0].split('x')] if len(res) == 1 else None;   # Set res to resolution if len of res is 1, else set back to None
      whxy = cropPattern.findall( line );                                       # Try to find pattern in line
    
      if len(whxy) == 1:                                                        # If found the pattern
        if not detect: detect = True;                                           # If detect is False, set to True
        if (nn == crop.shape[0]):                                                # If the current row is outside of the number of rows
          crop = np.concatenate( [crop, chunk], axis = 0 );                     # Concat a new chunk onto the array
        crop[nn,:] = np.array( [int(i) for i in whxy[0].split(':')] );          # Split the string on colon
        nn += 1;                                                                # Increment nn counter
      line = proc.stdout.readline();                                            # Read another line form pipe
    proc.communicate();                                                         # Wait for FFmpeg to finish cleanly
    ss += timedelta( seconds = 60 * 5 );                                        # Increment ss by 5 minutes

  crop = np.nanmedian( crop, axis = 0 ).astype(np.uint16);                      # Medain of crop values down column as integers
  if not np.isnan( crop[0] ):                                                   # If there is a non NaN value in the medain values, then at least one of the values was finite
    if res is not None:                                                         # If input resolution was found
      if (crop[0] == res[0]) and (crop[1] == res[1]):                           # If the crop size is the same as the input size
        log.debug( 'Crop size same as input size, NOT cropping' );              # Debug info
        return None;                                                            # Return None
    log.debug( 'Values for crop: {}'.format(crop) );                            # Debug info
    return 'crop={}:{}:{}:{}'.format( *crop );                                  # Return formatted string with crop option
  log.debug( 'No cropping region detected' );
  return None;                                                                  # Return None b/c if made here, no crop detected
