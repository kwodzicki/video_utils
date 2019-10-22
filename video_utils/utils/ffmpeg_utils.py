import logging;
import os, time, re;
import numpy as np;
from datetime import datetime, timedelta;
from subprocess import Popen, PIPE, STDOUT;

from video_utils import _sigintEvent, _sigtermEvent

_progPat = re.compile( r'time=(\d{2}:\d{2}:\d{2}.\d{2})' );                     # Regex pattern for locating file duration in ffmpeg ouput 
_durPat  = re.compile( r'Duration: (\d{2}:\d{2}:\d{2}.\d{2})' );                # Regex pattern for locating file processing location
_cropPat = re.compile( r'(?:crop=(\d+:\d+:\d+:\d+))' );                         # Regex pattern for extracting crop information
_resPat  = re.compile( r'(\d{3,5}x\d{3,5})' );                                  # Regex pattern for video resolution

_info    = 'Estimated Completion Time: {}';                                     # String formatter for conversion progress

_toSec   = np.array( [3600, 60, 1], dtype = np.float32 );                       # Array for conversion of hour/minutes/seconds to total seconds
_chunk   = np.full( (128, 4), np.nan );                                         # Base numpy chunk

###############################################################################
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
  crop = _chunk.copy();                                                         # List of crop regions

  log.debug( 'Detecting crop using chunks of length {}'.format( dt ) );

  detect = True;                                                                    # Set detect to True; flag for crop detected
  while detect and (not _sigintEvent.is_set()) and (not _sigtermEvent.is_set()):    # While detect is True, keep iterating
    detect = False;                                                                 # Set detect to False; i.e., at beginning of iteration, assume no crop found
    log.debug( 'Checking crop starting at {}'.format( ss ) );
    cmd[3] = str(ss);                                                               # Set the start offset in the video
    proc   = Popen( cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True );     # Start the command, piping stdout and stderr to a pipe
    line   = proc.stdout.readline();                                                # Read line from pipe
    while line != '':                                                               # While line is not empty
      if res is None:                                                               # If resolution not yet found
        res = _resPat.findall( line );                                              # Try to find resolution information
        res = [int(i) for i in res[0].split('x')] if len(res) == 1 else None;       # Set res to resolution if len of res is 1, else set back to None
      whxy = _cropPat.findall( line );                                              # Try to find pattern in line
    
      if len(whxy) == 1:                                                        # If found the pattern
        if not detect: detect = True;                                           # If detect is False, set to True
        if (nn == crop.shape[0]):                                               # If the current row is outside of the number of rows
          crop = np.concatenate( [crop, _chunk], axis = 0 );                    # Concat a new chunk onto the array
        crop[nn,:] = np.array( [int(i) for i in whxy[0].split(':')] );          # Split the string on colon
        nn += 1;                                                                # Increment nn counter
      line = proc.stdout.readline();                                            # Read another line form pipe
    proc.communicate();                                                         # Wait for FFmpeg to finish cleanly
    ss += timedelta( seconds = 60 * 5 );                                        # Increment ss by 5 minutes

  crop = np.nanmedian( crop, axis = 0 )                                         # Medain of crop values down column as integers
  if not np.isnan( crop[0] ):                                                   # If there is a non NaN value in the medain values, then at least one of the values was finite
    crop = crop.astype( np.uint16 )
    if res is not None:                                                         # If input resolution was found
      if (crop[0] == res[0]) and (crop[1] == res[1]):                           # If the crop size is the same as the input size
        log.debug( 'Crop size same as input size, NOT cropping' );              # Debug info
        return None;                                                            # Return None
    log.debug( 'Values for crop: {}'.format(crop) );                            # Debug info
    return 'crop={}:{}:{}:{}'.format( *crop );                                  # Return formatted string with crop option
  log.debug( 'No cropping region detected' );
  return None;                                                                  # Return None b/c if made here, no crop detected

###############################################################################
def totalSeconds( *args ):
    '''
    Name:
      totalSeconds
    Purpose:
      A function to convert an arbitrary number of time strings to the total
      number of 
      seconds represented by the time
    Inputs:
      One or more time strings of format HH:MM:SS
    Outputs:
      Returns a numpy array of total number of seconds in time
    Keywords:
      None.
    '''
    times = [np.array(arg.split(':'), dtype=np.float32)*_toSec for arg in args];# Iterate over all arugments, splitting on colon (:), converting to numpy array, and converting each time element to seconds
    return np.array( times ).sum( axis=1 );                                     # Conver list of numpy arrays to 2D numpy array, then compute sum of seconds across second dimension

###############################################################################
def prettyTime( *args, timeFMT = '%H:%M:%S' ):
    '''
    Name:
      prettyTime
    Purpose:
      A function to convert an arbitrary number of integers or floats
      from time in seconds to a string of format 'HH:MM:SS'
    Inputs:
      One or more integers or floats representing time in seconds
    Outputs:
      Returns a list of strings
    Keywords:
      timeFMT  : Format string of time. Default is '%H:%M:%S'
    '''
    return [time.strftime( timeFMT, time.gmtime( i ) ) for i in args];          # Interate over each argument and convert to string time, returning the list

###############################################################################
def progress( proc, interval = 60.0, nintervals = None ):
    '''
    Name:
      progess
    Purpose:
      A function to loop over the output from ffmpeg to determine how much
      time remains in the conversion.
    Inputs:
      proc  : A subprocess.Popen instance. The stdout of Popen must be set
               to subprocess.PIPE and the stderr must be set to 
               subprocess.STDOUT so that all information runs through 
               stdout. The universal_newlines keyword must be set to True
               as well
    Outputs:
      Returns nothing. Does NOT wait for the process to finish so MUST handle
      that in calling function
    Keywords:
      interval   : The update interval, in seconds, to log time remaining info.
                    Default is sixty (60) seconds, or 1 minute.
      nintervals : Set to number of updates you would like to be logged about
                    progress. Default is to log as many updates as it takes
                    at the interval requested. Setting this keyword will 
                    override the value set in the interval keyword.
                    Note that the value of interval will be used until the
                    first log, after which point the interval will be updated
                    based on the remaing conversion time and the requested
                    number of updates
    '''
    log = logging.getLogger(__name__);                                          # Initialize logger for the function
    if proc.stdout is None:                                                     # If the stdout of the process is None
        log.error( 'Subprocess stdout is None type! No progess to print!' );    # Log an error
        return;                                                                 # Return
    if not proc.universal_newlines:                                             # If universal_newlines was NOT set on Popen initialization
        log.error( 'Must set universal_newlines to True in call to Popen! No progress to print!' ); # Log an error
        return;                                                                 # Return

    t0 = t1 = time.time();                                                      # Initialize t0 and t1 to the same time; i.e., now
    dur     = None;                                                             # Initialize dur to None; this is the file duration
    line    = proc.stdout.readline();                                           # Read a line from stdout for while loop start
    while (line != ''):                                                         # While the line is NOT empty
        if dur is None:                                                         # If the file duration has NOT been set yet
            tmp = _durPat.findall( line );                                      # Try to find the file duration pattern in the line
            if len(tmp) == 1:                                                   # If the pattern is found
                dur     = totalSeconds( tmp[0] )[0];                            # Compute the total number of seconds in the file, take element zero as returns list
        elif (time.time()-t1) >= interval:                                      # Else, if the amount of time between the last logging and now is greater or equal to the interval
            t1  = time.time();                                                  # Update the time at which we are logging
            tmp = _progPat.findall( line );                                     # Look for progress time in the line
            if len(tmp) == 1:                                                   # If progress time found
                elapsed = t1 - t0;                                              # Compute the elapsed time
                prog    = totalSeconds( tmp[0] )[0]                             # Compute total number of seconds comverted so far, take element zero as returns list
                ratio   = elapsed / prog;                                       # Ratio of real-time seconds per seconds of video processed
                remain  = ratio * (dur - prog);                                 # Multiply ratio by the number of seconds of video left to convert
                endTime = datetime.now() + timedelta( seconds=remain );         # Compute estimated completion time
                log.info( _info.format( endTime ) );                            # Log information
                if (nintervals is not None) and (nintervals > 1):               # If the adaptive interval keyword is set AND nn is greater than zero
                    nintervals -= 1;                                            # Decrement nintervals
                    interval    = remain / float(nintervals);                   # Set interval to remaining time divided by nn
        line = proc.stdout.readline();                                          # Read the next line
    return

###############################################################################
def _testFile():                                                                 
    '''
    This is a grabage function used only for testing during development.
    '''
    infile   = '/mnt/ExtraHDD/Movies/short.mp4'                                 
    outfile  = os.path.join(os.path.dirname(infile), 'tmp1.mp4')                 

    cmd      = ['ffmpeg', '-nostdin', '-y', '-i', infile]                       
    cmd     += ['-c:v', 'libx264']                                              
    cmd     += ['-c:a', 'copy']                                                 
    cmd     += ['-threads', '1']                                                
    cmd     += [outfile]              
    print( ' '.join(cmd) )
    proc = Popen( cmd, stdout = PIPE, stderr = STDOUT, universal_newlines=True) 
    progress( proc, interval = 10.0, nintervals = None); 
    proc.communicate()                                                          

###############################################################################
if __name__ == "__main__":
    logging.getLogger().setLevel(0);
    stream = logging.StreamHandler()
    stream.setLevel(0)
    logging.getLogger().addHandler( stream )
    _testFile()
