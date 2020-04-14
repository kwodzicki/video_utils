import logging
import os, time, re, json
import numpy as np
from datetime import datetime, timedelta
from subprocess import Popen, check_output, PIPE, STDOUT, DEVNULL

from .. import _sigintEvent, _sigtermEvent
from .. import POPENPOOL

_progPat = re.compile( r'time=(\d{2}:\d{2}:\d{2}.\d{2})' )                      # Regex pattern for locating file duration in ffmpeg ouput 
_durPat  = re.compile( r'Duration: (\d{2}:\d{2}:\d{2}.\d{2})' )                 # Regex pattern for locating file processing location
_cropPat = re.compile( r'(?:crop=(\d+:\d+:\d+:\d+))' )                          # Regex pattern for extracting crop information
_resPat  = re.compile( r'(\d{3,5}x\d{3,5})' )                                   # Regex pattern for video resolution
_durPat  = re.compile( r'Duration: ([^,]*)' )
_info    = 'Estimated Completion Time: {}'                                     # String formatter for conversion progress

_toSec   = np.array( [3600, 60, 1], dtype = np.float32 );                       # Array for conversion of hour/minutes/seconds to total seconds
_chunk   = np.full( (128, 4), np.nan );                                         # Base numpy chunk

###############################################################################
def cropdetect( infile, dt = 20, threads = POPENPOOL.threads):
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
  log  = logging.getLogger(__name__);                                                   # Get a logger

  def buildCmd(infile, ss, dt, threads):                                                # Local function to build command for ffmpeg
    '''
    Purpose:
      Generate ffmpeg command list for cropping
    Inputs:
      infile   : str; File to read from
      ss       : timedelta; Start time for segment
      dt       : timedelta; Length of segment for crop detection
      threads  : int; number of threads to let ffmpeg use
    Keywords:
      None.
    Returns:
      List of strings containing ffmpeg command
    '''
    if not isinstance(ss,      str): ss = str(ss)
    if not isinstance(dt,      str): dt = str(dt)
    if not isinstance(threads, str): threads = str(threads)
    cmd = ['ffmpeg', '-nostats', '-threads', threads, '-ss', ss, '-i', infile]          # Base command for crop detection
    return cmd + ['-t', dt, '-vf', 'cropdetect', '-f', 'null', '-']                     # Add length, cropdetec filter and pipe to null muxer

  if not isinstance(threads, int): threads = 1
  whxy    = [ [] for i in range(4) ];                                                   # Initialize list of 4 lists for crop parameters
  res     = None;                                                                       # Initialize video resolution to None
  dt      = timedelta(seconds = dt)                                                     # Get nicely formatted time
  ss      = timedelta(seconds = 0)
  nn      = 0;                                                                          # Counter for number of crop regions detected
  crop    = _chunk.copy();                                                              # List of crop regions

  log.debug( 'Detecting crop using chunks of length {}'.format( dt ) );

  detect = True;                                                                    # Set detect to True; flag for crop detected
  while detect and (not _sigintEvent.is_set()) and (not _sigtermEvent.is_set()):    # While detect is True, keep iterating
    detect = False;                                                                 # Set detect to False; i.e., at beginning of iteration, assume no crop found
    log.debug( 'Checking crop starting at {}'.format( ss ) );
    cmd    = buildCmd( infile, ss, dt, threads )
    proc   = Popen( cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True )          # Start the command, piping stdout and stderr to a pipe
    line   = proc.stdout.readline()                                                     # Read line from pipe
    while line != '':                                                                   # While line is not empty
      if res is None:                                                                   # If resolution not yet found
        res = _resPat.findall( line )                                                   # Try to find resolution information
        res = [int(i) for i in res[0].split('x')] if len(res) == 1 else None            # Set res to resolution if len of res is 1, else set back to None
      whxy = _cropPat.findall( line )                                                   # Try to find pattern in line
    
      if len(whxy) == 1:                                                                # If found the pattern
        if not detect: detect = True                                                    # If detect is False, set to True
        if (nn == crop.shape[0]):                                                       # If the current row is outside of the number of rows
          crop = np.concatenate( [crop, _chunk], axis = 0 )                             # Concat a new chunk onto the array
        #log.debug( 'Crop : {}'.format(whxy) )
        crop[nn,:] = np.array( [int(i) for i in whxy[0].split(':')] )                   # Split the string on colon
        nn += 1                                                                         # Increment nn counter
      line = proc.stdout.readline()                                                     # Read another line form pipe
    proc.communicate()                                                                  # Wait for FFmpeg to finish cleanly
    ss += timedelta( seconds = 60 * 5 )                                                 # Increment ss by 5 minutes

  maxVals = np.nanmax(crop, axis = 0)                                                   # Compute maximum across all values
  xWidth  = maxVals[0]                                                                  # First value is maximum width
  yWidth  = maxVals[1]                                                                  # Second is maximum height

  if (xWidth/res[0] > 0.5) and (yWidth/res[1] > 0.5):                                   # If crop width and height are atleast 50% of video width and height
    xOffset = (res[0] - xWidth) // 2                                                    # Compute x-offset, this is half of the difference between video width and crop width because applies to both sizes of video
    yOffset = (res[1] - yWidth) // 2                                                    # Compute x-offset, this is half of the difference between video height and crop height because applies to both top and bottom of video
    crop    = np.asarray( (xWidth, yWidth, xOffset, yOffset), dtype = np.uint16 )       # Numpy array containing crop width/height of offsets as unsigned 16-bit integers

    if res is not None:                                                                 # If input resolution was found
      if (crop[0] == res[0]) and (crop[1] == res[1]):                                   # If the crop size is the same as the input size
        log.debug( 'Crop size same as input size, NOT cropping' )                       # Debug info
        return None                                                                     # Return None
    log.debug( 'Values for crop: {}'.format(crop) )                                     # Debug info
    return 'crop={}:{}:{}:{}'.format( *crop )                                           # Return formatted string with crop option
  log.debug( 'No cropping region detected' )
  return None                                                                           # Return None b/c if made here, no crop detected

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

class FFmpegProgress(object):
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
  def __init__(self, interval = 60.0, nintervals = None):
    self.log = logging.getLogger(__name__)                                          # Initialize logger for the function
    self.t0  = self.t1 = time.time()                                                      # Initialize t0 and t1 to the same time; i.e., now
    self.dur        = None                                                             # Initialize dur to None; this is the file duration
    self.interval   = interval
    self.nintervals = nintervals

  def progress(self, inVal):
    if isinstance( inVal, Popen ):
      self._subprocess( inVal )
    else:
      self._processLine( inVal )

  def _subprocess( self, proc ):
    if proc.stdout is None:                                                     # If the stdout of the process is None
      log.error( 'Subprocess stdout is None type! No progess to print!' );    # Log an error
      return                                                                 # Return
    if not proc.universal_newlines:                                             # If universal_newlines was NOT set on Popen initialization
      log.error( 'Must set universal_newlines to True in call to Popen! No progress to print!' ); # Log an error
      return                                                                 # Return

    line = proc.stdout.readline();                                           # Read a line from stdout for while loop start
    while (line != ''):                                                         # While the line is NOT empty
      self._processLine( line )
      line = proc.stdout.readline();                                          # Read the next line

  def _processLine( self, line ):
    if self.dur is None:                                                         # If the file duration has NOT been set yet
      tmp = _durPat.findall( line );                                      # Try to find the file duration pattern in the line
      if len(tmp) == 1:                                                   # If the pattern is found
        self.dur = totalSeconds( tmp[0] )[0];                            # Compute the total number of seconds in the file, take element zero as returns list
    elif (time.time()-self.t1) >= self.interval:                                      # Else, if the amount of time between the last logging and now is greater or equal to the interval
      self.t1  = time.time();                                                  # Update the time at which we are logging
      tmp      = _progPat.findall( line );                                     # Look for progress time in the line
      if len(tmp) == 1:                                                   # If progress time found
        elapsed = self.t1 - self.t0                                              # Compute the elapsed time
        prog    = totalSeconds( tmp[0] )[0]                             # Compute total number of seconds comverted so far, take element zero as returns list
        ratio   = elapsed / prog                                       # Ratio of real-time seconds per seconds of video processed
        remain  = ratio * (self.dur - prog)                                 # Multiply ratio by the number of seconds of video left to convert
        endTime = datetime.now() + timedelta( seconds=remain )         # Compute estimated completion time
        self.log.info( _info.format( endTime ) )                            # Log information
        if (self.nintervals is not None) and (self.nintervals > 1):               # If the adaptive interval keyword is set AND nn is greater than zero
          self.nintervals -= 1                                            # Decrement nintervals
          self.interval    = remain / float(self.nintervals)                   # Set interval to remaining time divided by nn


###############################################################################
def progress( proc, interval = 60.0, nintervals = None ):
  '''
  Name:
    procProgess
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

########################################################
def getVideoLength(in_file):
  proc = Popen( ['ffmpeg', '-i', in_file], stdout=PIPE, stderr=STDOUT)
  info = proc.stdout.read().decode()
  dur  = _durPat.findall( info )
  if (len(dur) == 1):
    hh, mm, ss = [float(i) for i in dur[0].split(':')]
    dur = hh*3600.0 + mm*60.0 + ss
  else:
    dur = 86400.0
  return timedelta( seconds = dur )

###############################################################################
def checkIntegrity(filePath):
  '''
  Name:
    checkIntegrity
  Purpose:
    A function to test the integrity of a video file.
    Runs ffmpeg with null output, checking errors for
    'overread'. If overread found, then return False,
    else True
  Inputs:
    filePath  : Full path of file to check
  Keywords:
    None.
  Outputs:
    Returns True if no overread errors, False if error
  '''
  cmd  = ['ffmpeg', '-nostdin', '-v', 'error', '-threads', '1', 
            '-i', filePath, '-f', 'null', '-']                                              # Command to run
  proc = Popen( cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)                   # Run ffmpeg command
  line = proc.stdout.readline()                                                             # Read line from stdout
  while (line != ''):                                                                       # While line is NOT empty
    if ('overread' in line):                                                                # If 'overread' in line
      proc.terminate()                                                                      # Terminate process
      proc.communicate()                                                                    # Wait for proc to finish
      return False                                                                          # Return False
    line = proc.stdout.readline()                                                           # Read another line

  proc.communicate()                                                                        # Make sure process done
  return True                                                                               # Return True

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
def splitOnChapter(inFile, nChap):
  '''
  Name:
    splitOnChapter
  Purpose:
    A python script to split a video file based on chapters.
    the idea is that if a TV show is ripped with multiple 
    episodes in one file, assuming all episodes have the 
    same number of chapters, one can split the file into
    individual episode files.
  Inputs:
    inFile  : Full path to the file that is to be split.
    nChaps  : The number of chapters in each episode.
  Outputs:
    Outputs n files, where n is equal to the total number
    of chapters in the input file divided by nChaps.
  Keywords:
    None.
  Author and History:
    Kyle R. Wodzicki     Created 01 Feb. 2018
  '''
  if type(nChap) is not int: nChap = int(nChap);                                # Ensure that nChap is type int
  cmd = ['ffprobe', '-i', inFile, '-print_format', 'json', 
         '-show_chapters', '-loglevel', 'error'];                               # Command to get chapter information
  try:                                                                          # Try to...
    chaps = str(check_output( cmd ), 'utf-8')                                   # Get chapter information from ffprobe
    chaps = json.loads( chaps )['chapters']                                     # Parse the chapter information
  except:                                                                       # On exception
    print('Failed to get chapter information');                                 # Print a message
    return;                                                                     # Return
  
  cmd = ['ffmpeg', '-v', 'quiet', '-stats', 
         '-ss', '', 
         '-i', inFile,
          '-codec', 'copy', '-map', '0',
         '-t', '', ''];                                                         # Set up list for command to split file
  fmt = 'split_{:03d}.' + inFile.split('.')[-1];                                # Set file name for split files
  num = 0;                                                                      # Set split file number
  for i in range(0, len(chaps), nChap):                                         # Iterate over chapter ranges
    fName   = fmt.format(num);                                                  # Set file name
    s, e    = i, i+nChap-1
    start   = timedelta( seconds = float(chaps[s]['start_time']) + 0.05 );      # Get chapter start time
    end     = timedelta( seconds = float(chaps[e]['end_time'])   - 0.05 );      # Get chapter end time
    dur     = end - start;                                                      # Get chapter duration
    cmd[ 5] = str(start);                                                       # Set start offset to string of start time
    cmd[-2] = str(dur);                                                         # Set duration to string of dur time
    cmd[-1] = os.path.join( os.path.dirname(inFile), fName );                   # Set output file

    proc = Popen(cmd, stderr=DEVNULL)                                           # Write errors to /dev/null
    proc.communicate();                                                         # Wait for command to complete
    if proc.returncode != 0:                                                    # If return code is NOT zero
      print('FFmpeg had an error!');                                            # Print message
      return;                                                                   # Return
    num += 1;                                                                   # Increment split number

#if __name__ == "__main__":
#  import argparse;                                                              # Import library for parsing
#  parser = argparse.ArgumentParser(description="Split on Chapter");             # Set the description of the script to be printed in the help doc, i.e., ./script -h
#  parser.add_argument("file",          type=str, help="Input file to split"); 
#  parser.add_argument("-n", "--nchap", type=int, help="Number of chapters per track"); 
#  args = parser.parse_args();                                                   # Parse the arguments
#
#  splitOnChapter( args.file, args.nchap );

###############################################################################
def combine_mp4_files(outFile, *args):
  '''
  Purpose:
    Function for combining multiple (2+) mp4 files into a single
    mp4 file. Needs the ffmpeg CLI
  Inputs
    inFiles : List of input file paths
    outFile : Output (combined) file path
  Outputs:
    Creates a new combined mp4 file
  Keywords:
    None.
  '''
  log = logging.getLogger( __name__ )
  if len(args) < 2:                                                          # If there are less than 2 ipputs
    log.critical('Need at least two (2) input files!')
    return;                                                                     # Return from function
  tmpFiles = [ '.'.join(f.split('.')[:-1])+'.ts' for f in args]                 # Iterate over inFiles list and create intermediate TS file paths

  cmdTS = ['ffmpeg', '-y', '-nostdin', 
    '-i',      '', 
    '-c',     'copy', 
    '-bsf:v', 'h264_mp4toannexb',
    '-f',     'mpegts', ''
  ];                                                                            # List with options for creating intermediate files
  cmdConcat = ['ffmpeg', '-nostdin', 
    '-i',     'concat:{}'.format( '|'.join(tmpFiles) ),
    '-c',     'copy', 
    '-bsf:a', 'aac_adtstoasc',
    outFile
  ];                                                                            # List with options for combining TS files back into MP4
  for i in range(len(args)):                                                 # Iterate over all the input files
    cmdTS[4], cmdTS[-1] = args[i], tmpFiles[i];                              # Set input/output files in the cmdTS list
    proc = POPENPOOL.Popen_async( cmdTS.copy() )
  proc.wait()
  POPENPOOL.wait()
  proc = POPENPOOL.Popen_async( cmdConcat )
  proc.wait()

  for f in tmpFiles:                                                            # Iterate over the temporary files
    if os.path.isfile(f):                                                       # If the file exists
      os.remove(f);                                                             # Delete it

#if __name__ == "__main__":
#  import argparse
#  parser = argparse.ArgumentParser(description="Simple python wrapper for FFmpeg to combine multiple mp4 files")
#  parser.add_argument('inputs', nargs='+', help='input file(s) to combine')
#  parser.add_argument('output', help='Name of the output file')
#  args = parser.parse_args()
#  combine_mp4_files( args.output, *args.inputs );
