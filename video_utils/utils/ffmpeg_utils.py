import logging;
import re;
from datetime import timedelta;
from subprocess import Popen, PIPE, STDOUT;

cropPattern = re.compile( r'(?:crop=(\d+:\d+:\d+:\d+))' );                      # Pattern for extracting crop information
resPattern  = re.compile( r'(\d{3,5}x\d{3,5})' );                               # Pattern for video resolution

def cropdetect( infile, dt = 30 ):
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
          for crop detection, default is 30 seconds
  '''
  log  = logging.getLogger(__name__);                                           # Get a logger
  whxy = [ [] for i in range(4) ];                                              # Initialize list of 4 lists for crop parameters
  res  = None;                                                                  # Initialize video resolution to None
  dt   = str( timedelta(seconds = dt) );                                        # Get nicely formatted time
  cmd  = ['ffmpeg', '-nostats', '-i', infile];                                  # Base command for crop detection
  cmd  = cmd + ['-t', dt, '-vf', 'cropdetect', '-f', 'null', '-'];              # Add length, cropdetec filter and pipe to null muxer

  log.debug( 'Using first {} of video to detect crop'.format( dt ) );
  proc = Popen( cmd, stdout = PIPE, stderr = STDOUT, universal_newlines=True ); # Start the command, piping stdout and stderr to a pipe
  line = proc.stdout.readline();                                                # Read line from pipe
  while line != '':                                                             # While line is not empty
    if res is None:                                                             # If resolution not yet found
      res = resPattern.findall( line );                                         # Try to find resolution information
      res = [int(i) for i in res[0].split('x')] if len(res) == 1 else None;     # Set res to resolution if len of res is 1, else set back to None
    crop = cropPattern.findall( line );                                         # Try to find pattern in line
    if len(crop) == 1:                                                          # If found the pattern
      crop = crop[0].split(':');                                                # Split the string on colon
      for i in range( 4 ):                                                      # Iterate over 4 values
        whxy[i].append( int(crop[i]) );                                         # Convert crop value to integer and append the appropriate list in whxy
    line = proc.stdout.readline();                                              # Read another line form pipe
  proc.communicate();                                                           # Wait for FFmpeg to finish cleanly

  if len( whxy[0] ) > 0:                                                        # If lenth of first list is greater than zero
    whxy = [str( int( sum(i)/len(i) ) ) for i in whxy];                         # Compute mean of each list, convert to integer string
    if res is not None:                                                         # If input resolution was found
      if (whxy[0] == res[0]) and (whxy[1] == res[1]):                           # If the crop size is the same as the input size
        log.debug( 'Crop size same as input size, NOT cropping' );              # Debug info
        return None;                                                            # Return None
    log.debug( 'Values for crop: {}'.format(whxy) );                            # Debug info
    return 'crop={}:{}:{}:{}'.format( *whxy );                                  # Return formatted string with crop option
  log.debug( 'No cropping region detected' );
  return None;                                                                  # Return None b/c if made here, no crop detected
