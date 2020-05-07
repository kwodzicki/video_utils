import logging
import os, time, re, json
import numpy as np
from datetime import datetime, timedelta
from subprocess import Popen, check_output, PIPE, STDOUT, DEVNULL

from .. import _sigintEvent, _sigtermEvent
from .. import POPENPOOL

_progPat = re.compile( r'time=(\d{2}:\d{2}:\d{2}.\d{2})' )                              # Regex pattern for locating file duration in ffmpeg ouput 
_durPat  = re.compile( r'Duration: (\d{2}:\d{2}:\d{2}.\d{2})' )                         # Regex pattern for locating file processing location
_cropPat = re.compile( r'(?:crop=(\d+:\d+:\d+:\d+))' )                                  # Regex pattern for extracting crop information
_resPat  = re.compile( r'(\d{3,5}x\d{3,5})' )                                           # Regex pattern for video resolution
_durPat  = re.compile( r'Duration: ([^,]*)' )
_info    = 'Estimated Completion Time: {}'                                              # String formatter for conversion progress

_toSec   = np.array( [3600, 60, 1], dtype = np.float32 )                                # Array for conversion of hour/minutes/seconds to total seconds
_chunk   = np.full( (128, 4), np.nan )                                                  # Base numpy chunk

TIME_BASE   = '1/1000000000'                                                            # Default time_base for chapters
PREROLL     = -1.0                                                                      # Padding before beginning of chapter
POSTROLL    =  1.0                                                                      # Padding after end of chapter

HEADERFMT   = ';FFMETADATA{}' + os.linesep                                              # Format for FFMETADATA file header
METADATAFMT = '{}={}' + os.linesep                                                      # Format string for a FFMETADATA metadata tag
CHAPTERFMT  = ['[CHAPTER]', 'TIMEBASE={}', 'START={}', 'END={}', 'title={}', '']        # Format of CHAPTER block in FFMETADATA file
CHAPTERFMT  = os.linesep.join( CHAPTERFMT )                                             # Join CHAPTER block format list on operating system line separator

class FFMetaData( object ):
  def __init__(self, version = 1):
    self.__log     = logging.getLogger(__name__)
    self._version  = version
    self._metadata = {}
    self._chapters = []
    self._chapter  = 1
 
  def addMetadata(self, **kwargs):
    '''
    Purpose:
      Method to add new metadata tags to FFMetaData file
    Inputs:
      None.
    Keywords:
      Any key/value pair where key is a valid metadata tag and value is
      the value for the tag. 
    Returns:
      None.
    '''
    self._metadata.update( kwargs )

  def addChapter(self, *args, **kwargs):
    '''
    Purpose:
      Method to add chapter marker to FFMetaData file
    Inputs:
      If one (1) input:
        Must be Chapter instance
      If three (3) inputs:
        start  : Start time of chapter (float or datetime.timedelta)
        end    : End time of chapter (float or datetime.timedelta)
        title  : Chapter title (str)
    Keywords:
      time_base : String of form 'num/den’, where num and den are integers. 
                  If the time_base is missing then start/end times are assumed
                 to be in nanosecond. Ignored if NOT three (3) inputs.
    Returns:
      None.
    '''
    if len(args) == 1:
      chapter = args[0]
    elif len(args) == 3:
      if isinstance(args[0], timedelta):
        start = arg[0].total_seconds()
      if isinstance(args[1], timedelta):
        end   = args[1].total_seconds()

      chapter   = Chapter()
      time_base = kwargs.get('time_base', TIME_BASE)
      if isinstance(time_base, str):                                                    # If is string
        num, den = map(int, time_base.split('/'))                                       # Get the numberator and denominator as integers
        factor   = den / num                                                            # Do den/num to get factor to go from seconds to time_base
      else:
        raise Exception( "time_base must be a string of format 'num/den'!" )
      chapter.time_base = time_base 
      chapter.start     = round( args[0] * factor )                                     # Get total seconds from timedelta, apply factor, then convert to integer
      chapter.end       = round( args[1] * factor )                                     # Do same for end time
      chapter.title     = args[2]
    else:
      raise Exception( "Incorrect number of arguments!" )

    if re.match('Chapter\s\d?', chapter.title):                                         # If chapter title matches generic title
      chapter.title = 'Chapter {:02d}'.format(self._chapter)                            # Reset chapter number title

    self._chapters.append( chapter.toFFMetaData() )                                     # Append tuple of information to _chapters attribute
    self._chapter += 1

  def save(self, filePath):
    '''
    Purpose:
      Method to write ffmetadata to file
    Inputs:
      filePath  : Full path of file to write to
    Keywords:
      None.
    Returns:
      Returns the filePath input
    '''
    with open(filePath, 'w') as fid:                                            # Open file for writing
      fid.write( HEADERFMT.format( self._version ) )                       # Write header to file

      for key, val in self._metadata.items():                                   # Iterate over all key/value pairs in metadata dictionary
        fid.write( METADATAFMT.format(key, val) )                          # Write metadata

      fid.write( os.linesep )                                                   # Add space between header/metadata and chapter(s)
      for info in self._chapters:                                               # Iterate over all chapters
        fid.write( info )                                                       # Write the chapter info
        fid.write( os.linesep )                                                 # Write extra space between chapters

    self._chapters = []
    self._chapter = 1
    return filePath                                                             # Return file path

###############################################################################
class Chapter( object ):
  def __init__(self, chapter={}):
    self._data     = chapter
    time_base      = self.time_base
    start          = self.start
    end            = self.end
    self.time_base = time_base
    self.start     = start
    self.end       = end

  def __repr__(self):
    return '<{} : {}s --> {}s>'.format(self.title, self.start_time, self.end_time)    

  @property
  def time_base(self):
    return self._data.get('time_base', TIME_BASE)
  @time_base.setter
  def time_base(self, val):
    self._data['time_base'] = val                                                       # Set time_base to new value
    self._num, self._den = map(int, val.split('/'))                                     # Get new numerator and denominator
    start_time = self.start_time
    if isinstance(start_time, float):
      self.start_time = start_time                                                   # Set start_time to current start_time; will trigger conversion of start
    end_time   = self.end_time                                                     # Set end_time to current end_time; will trigger conversion of end
    if isinstance(end_time, float):
      self.end_time   = end_time                                                     # Set end_time to current end_time; will trigger conversion of end

  @property
  def start(self):
    return self._data.get('start', 0)
  @start.setter
  def start(self, val):
    self._data['start']      = val
    self._data['start_time'] = self.base2seconds( val )

  @property
  def end(self):
    return self._data.get('end', 0)
  @end.setter
  def end(self, val):
    self._data['end']      = val
    self._data['end_time'] = self.base2seconds( val )

  @property
  def start_time(self):
    return self._data.get('start_time', 0)
  @start_time.setter
  def start_time(self, val):
    self._data['start_time'] = val
    self._data['start']      = self.seconds2base( val )

  @property
  def end_time(self):
    return self._data.get('end_time', 0)
  @end_time.setter
  def end_time(self, val):
    self._data['end_time'] = val
    self._data['end']      = self.seconds2base( val )

  @property
  def title(self):
    key = 'tags'
    if key in self._data:
      return self._data[key].get('title', '')
  @title.setter
  def title(self, val):
    key  = 'tags'
    tags = self._data.get(key, None)
    if not isinstance(tags, dict):
      self._data[key] = {}
    self._data[key]['title'] = val

  def _convertTimebase(self, inInt, inFloat, time_base):
    '''
    Purpoe:
      Method to convert to new time_base
    Inputs:
      inInt     : Value of time in time_base units
      inFloat   : Value of time in seconds
      time_base : str contianing new time_base
    Keywords:
      None.
    Returns:
      (inInt, inFloat) where inInt is in requested time_base
    '''
    if time_base != self.time_base:                                                     # If requested time_base NOT match time_base
      num, den = map(int, time_base.split('/'))                                         # Get numerator and denominator of new time_base
      factor   = (self._num * den) / (self._den * num)                                  # Cross multiply original time_base with new time_base
      return  round(inInt * factor), inFloat                                            # Convert integer time to new base, return float
    return inInt, inFloat

  def toFFMetaData(self):
    '''Method that returns information in format for FFMETADATA file'''
    return CHAPTERFMT.format(self.time_base, self.start, self.end, self.title)

  def base2seconds(self, val):
    '''Method that converts value in time_base units to seconds'''
    return val * self._num / self._den

  def seconds2base(self, val):
    '''Method that converts value in seconds to time_base units'''
    return round( val * self._den / self._num )

  def getStart(self, time_base = None):
    '''Method to return chapter start time in time_base and seconds units'''
    if time_base:
      return self._convertTimebase( *self.getStart(), time_base )
    return self.start, self.start_time

  def getEnd(self, time_base = None):
    '''Method to return chapter end time in time_base and seconds units'''
    if time_base:
      return self._convertTimebase( *self.getEnd(), time_base )
    return self.end, self.end_time

  def addOffset(self, offset, flag = 2):
    '''
    Purpose:
      To adjust the start, end, or both times
    Inputs:
      offset  : float specifying offset time in seconds
    Keywords:
      flag    : Set to: 0 - to add offset to start time,
                        1 - to add offset to end time,
                        2 - (default) add offset to start and end
    Returns:
      None, updates internal attributes
    '''
    if isinstance(offset, timedelta):
      offset = offset.total_seconds()
    if flag == 2:                                                                       # If flag is 2
      self.start_time += offset                                                         # offset start time
      self.end_time   += offset                                                         # Offset end time
    elif flag == 1:                                                                     # If flag is 1
      self.end_time   += offset                                                         # Offset end_time
    elif flag == 0:                                                                     # If flag is 0
      self.start_time += offset                                                         # Offset start time

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
    times = [np.array(arg.split(':'), dtype=np.float32)*_toSec for arg in args]         # Iterate over all arugments, splitting on colon (:), converting to numpy array, and converting each time element to seconds
    return np.array( times ).sum( axis=1 )                                              # Conver list of numpy arrays to 2D numpy array, then compute sum of seconds across second dimension

###############################################################################
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
  return dur

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
def getChapters(inFile):
  '''
  Purpose:
    Function for extract chapter information from video
  Inputs:
    inFile      : Path of file to extract chapter information from
  Keywords:
    None.
  Returns:
    List of Chapter objects if chapters exist, None otherwise
  '''
  cmd = ['ffprobe', '-i', inFile, '-print_format', 'json', 
         '-show_chapters', '-loglevel', 'error']                                        # Command to get chapter information
  try:                                                                                  # Try to...
    chaps = str(check_output( cmd ), 'utf-8')                                           # Get chapter information from ffprobe
  except:                                                                               # On exception
    print('Failed to get chapter information')                                          # Print a message
    return None                                                                         # Return
  return [ Chapter(chap) for chap in json.loads( chaps )['chapters'] ]               # Parse the chapter information

###############################################################################
def partialExtract( inFile, outFile, startOffset, duration, chapterFile = None ):
  '''
  Purpose:
    Function for extracting video segement
  Inputs:
    inFile      : Path of file to extract segment from
    outFile     : Path of file to extract segment to
    startOffset : float or timedelta object specifying segment start time in input file.
                   If float, units must be seconds.
    duration    : float or timedelta object specifying segment duration
                   If float, units must be seconds.
  Keywords:
    chapterFile : Path to ffmetadata file specifying chapters for new segment
  Returns:
    True on successful extraction, False otherwise
  '''
  if not isinstance(startOffset, timedelta):                                            # Ensure startOffset is timedelta
    startOffset = timedelta(seconds = startOffset)
  if not isinstance(duration, timedelta):                                               # Ensure duration is timedelta
    duration    = timedelta(seconds = duration)
  cmd  = ['ffmpeg', '-y', '-v', 'quiet', '-stats']                                      # Base command
  cmd += ['-ss', str( startOffset ), '-t',  str( duration )]                            # Set starting read position and read for durtation for input file
  cmd += ['-i', inFile]                                                                 # Set input file
  if chapterFile:                                                                       # If chapter file specified
    cmd += ['-i', chapterFile, '-map_chapters', '1']                                    # Add chapter file to command
  cmd += ['-codec', 'copy']                                                             # Set codec to copy and map stream to all
  cmd += ['-ss', '0', '-t',  str( duration ) ]                                          # Set start time and duration for output  file
  cmd += [outFile]                                                                      # Set up list for command to split file
  proc = Popen(cmd, stderr=DEVNULL)                                                     # Write errors to /dev/null
  proc.communicate();                                                                   # Wait for command to complete
  if proc.returncode != 0:                                                              # If return code is NOT zero
    return False                                                                        # Return
  return True

###############################################################################
def splitOnChapter(inFile, nChapters):
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
    inFile    : Full path to the file that is to be split.
    nChapters : The number of chapters in each episode.
  Outputs:
    Outputs n files, where n is equal to the total number
    of chapters in the input file divided by nChaps.
  Keywords:
    None.
  Author and History:
    Kyle R. Wodzicki     Created 01 Feb. 2018
  '''
  chapters = getChapters( inFile )                                                      # Get all chapters from file
  if not chapters: return                                                               # If no chapters, return

  if isinstance(nChapters, (tuple,list)):                                               # If nChapters is eterable
    nChapters = [int(n) for n in nChapters]                                             # Ensure all values are integers
  elif type(nChapters) is not int:                                                      # Else
    nChapters = int(nChapters);                                                         # Ensure that nChap is type int
  
  fileDir, fileBase = os.path.split(inFile)                                             # Get input file directory and base name
  fileBase, fileExt = os.path.splitext(fileBase)                                        # Get input file name and extension

  ffmeta   = FFMetaData()                                                               # Initialize FFMetaData instance
  splitFMT = 'split_{:03d}'+fileExt                                                     # Set file name format for split files
  chapName = 'split.chap'                                                               # Set file name for chapter metadata file
  num      = 0                                                                          # Set split file number
  sID      = 0                                                                          # Set chater starting number
  while sID < len(chapters):                                                            # While chapters left
    width    = nChapters[num] if isinstance(nChapters, (tuple,list)) else nChapters     # Get number of chapters to process; i.e., width of video segment
    eID      = sID + width                                                              # Set chapter ending index
    preroll  = PREROLL  if sID > 0 else 0.0                                             # Set local preroll
    postroll = POSTROLL if eID < len(chapters) else 0.0                                 # Set local postroll
    chaps    = chapters[sID:eID]                                                        # Subset chapters
    start    = chaps[ 0].start_time                                                     # Get chapter start time
    end      = chaps[-1].end_time                                                       # Get chapter end time
    startD   = timedelta(seconds = start + preroll)                                     # Set start time for segement with preroll adjustment
    dur      = timedelta(seconds = end   + postroll) - startD                           # Set segment duration with postroll adjustment
    nn       = len(chaps)                                                               # Determine number of chapers; may be less than width if use fixed width
    for i in range(nn):                                                                 # Iterate over chapter subset
      if i == 0:                                                                        # If first chapter
        chaps[i].addOffset(-start, 0)                                                   # Set chapter start offset to zero
        chaps[i].addOffset(-start-preroll,1)                                            # Set chapter end offset to PREROLL greater than start to compensate for pre-roll
      elif i == (nn-1):                                                                 # If on last chapter
        chaps[i].addOffset(-start-preroll, 0)                                           # Adjust starting
        chaps[i].end_time = dur.total_seconds()                                         # Set end_time to segment duration
      else:                                                                             # Else
        chaps[i].addOffset( -start-preroll )                                            # Adjust start and end times compenstating for pre-roll
      ffmeta.addChapter( chaps[i] )

    splitName = splitFMT.format(num)                                                    # Set file name
    splitFile = os.path.join( fileDir, splitName )                                      # Set output segement file path
    chapFile  = os.path.join( fileDir, chapName)                                        # Set segment chapter file
    ffmeta.save(chapFile)                                                               # Create the FFMetaData file
    if not partialExtract( inFile, splitFile, startD, dur, chapterFile=chapFile ):      # Try to extract segment
      break                                                                             # Return on error
    num += 1                                                                            # Increment split number
    sID  = eID                                                                          # Set sID to eID
  os.remove( chapFile )                                                                 # Remove the chapter file

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

