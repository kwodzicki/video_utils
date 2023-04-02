import logging
import os, re, time
from datetime import datetime

from . import __name__ as __pkg_name__
from . import __version__ as __pkg_version__
from . import _sigintEvent, _sigtermEvent, isRunning
from . import POPENPOOL

from .mediainfo import MediaInfo
from .comremove import ComRemove
from .utils.handlers import RotatingFile
from .utils.ffmpeg_utils   import cropdetect, FFmpegProgress, progress
from .utils.threadCheck import threadCheck 

from .subtitles import opensubtitles
from .subtitles import ccextract
from .subtitles import subtitle_extract
from .subtitles import sub_to_srt

from .videotagger import getMetaData

from .config import getComskipLog, getTranscodeLog, fileFMT


_sePat = re.compile( r'[sS](\d{2,})[eE](\d{2,})' )                              # Matching pattern for season/episode files; lower/upper case 's' followed by 2 or more digits followed by upper/lower 'e' followed by 2 or more digits followed by ' - ' string

class VideoConverter( ComRemove, MediaInfo, opensubtitles.OpenSubtitles ):
  """
  For converting video files h264 encoded files in either the MKV or MP4 container.

  Video files must be decodeable by the ffmpeg video software.
  All audio tracks will be passed through to the output file
  The x264 video code will be used for all files with resolutions of 1080P and lower,
  while x265 will be used for all videos with resolution greater than 1080P. 
  The x265 codec can be enabled for lower resolution videos.

  Dependencies:
     ffmpeg, mediainfo

  """

  def __init__(self, 
               in_place          = False, 
               transcode_log     = None,
               comskip_log       = None,
               lang              = None, 
               threads           = None, 
               container         = 'mp4',
               cpulimit          = None, 
               x265              = False,
               remove            = False,
               comdetect         = False,
               subtitles         = False, 
               srt               = False,
               sub_delete_source = False,
               **kwargs):
    """
    Keyword arguments:
       outDir   (str): Path to output directory. Optional input. 
                        DEFAULT: Place output file(s) in source directory.
       logDir  (str): Path to log file directory. Optional input.
                        DEFAULT: Place log file(s) in source directory.
       in_place (bool): Set to transcode file in place; i.e., do NOT create a 
                         new path to file such as with TV, where
                         ./Series/Season XX/ directories are created
       lang          : String or list of strings of ISO 639-2 codes for 
                        subtitle and audio languages to use. 
                        Default is english (eng).
       threads  (int): Set number of threads to use. Default is to use half
                        of total available.
       cpulimit (int): Set to percentage to limit cpu usage to. This value
                        is multiplied by number of threads to use.
                        DEFAULT: 75 per cent.
                        TO DISABLE LIMITING - set to 0.
       remove (bool): Set to True to remove mkv file after transcode
       comdetect (bool): Set to remove/mark commercial segments in file
       subtitles (bool): Set to extract VobSub file(s). If SRT is set, then
                        this keyword is also set. Setting this will NOT
                        enable downloading from opensubtitles.org as the
                        subtitles for opensubtitles.org are SRT files.
       srt  (bool): Set to convert the extracted VobSub file(s) to SRT
                        format. Also enables opensubtitles.org downloading 
                        if no subtitles are found in the input file.
       sub_delete_source (bool): Set to delete VobSub file(s) after they have been 
                        converted to SRT format. Used in conjunction with
                        srt keyword.
      username (str): User name for opensubtitles.org
      userpass (str): Password for opensubtitles.org. Recommend that
                        this be the md5 hash of the password and not
                        the plain text of the password for slightly
                        better security

    """

    super().__init__(**kwargs)
    self.__log = logging.getLogger( __name__ )                                   # Set log to root logger for all instances
    self.container = container
    if subtitle_extract.CLI is None:
      self.__log.warning("Subtitlte extraction is DISABLED! Check that mkvextract is installed and in your PATH")
      self.subtitles = False
    else:
      self.subtitles = subtitles
    self.srt = srt
    #if self.srt and (not vobsub_to_srt.CLI):
    #  self.__log.warning("VobSub2SRT conversion is DISABLED! Check that vobsub2srt is installed and in your PATH")

    if not isinstance(cpulimit, int): cpulimit = 75
    self.cpulimit = cpulimit
    self.threads  = threadCheck( threads )

    # Set up all the easy parameters first
    self.outDir        = kwargs.get('outDir', None)
    self.logDir        = kwargs.get('logDir', None)
    self.in_place      = in_place                                                       # Set the in_place attribute based on input value
    self.comdetect     = comdetect                                                      # Flag for commerical detection enabled

    self.miss_lang     = []
    self.x265          = x265
    self.remove        = remove
    self.sub_delete_source = sub_delete_source
    self.inFile       = None

    if transcode_log is None:
      self.transcode_log = getTranscodeLog(self.__class__.__name__, logdir=self.logDir)
    else:
      self.transcode_log = transcode_log

    if comskip_log is None:
      self.comskip_log = getComskipLog(self.__class__.__name__, logdir=self.logDir)
    else:
      self.comskip_log = comskip_log

    if lang:                                                                    # If lang is set
      self.lang = lang if isinstance(lang, (tuple,list,)) else [lang]           # Set lang attribute to lang if it is a tuple or list instance, else make lang a list
    if (len(self.lang) == 0):							# If lang is empty list
      self.lang = ["eng"]                                                       # Set default language to english 
    
    self.chapterFile      = None

    self.video_info       = None                                                # Set video_info to None by default
    self.audio_info       = None                                                # Set audio_info to None by default
    self.text_info        = None                                                # Set text_info to None by default
    self.subtitle_ltf     = None                                                # Array to store subtitle language, track, forced (ltf) tuples
    self.sub_status       = None                                                # Set sub_status to None by default
    self.srt_status       = None                                                # Set srt_status to None by default
    self.transcode_status = None                                                # Set transcode_status to None by default
    self.tagging_status   = None                                                # Set mp4tags_status to None by default
    
    self.IMDb             = None
    self.metaData         = None
    self.metaKeys         = None

    self.is_episode       = False
    self.tagging          = False

    self.v_preset         = 'slow'                                              # Set x264/5 preset to slow

    self._createdFiles    = None                                                        # List to store paths to all files created by transcode method
    self.__fileHandler    = None                                                        # logging fileHandler 
  
  @property
  def outDir(self):
    """Output directory for transcoded and extra files"""

    return self.__outDir

  @outDir.setter
  def outDir(self, val):
    if isinstance(val, str):
      if not os.path.isdir( val ):
        os.makedirs( val, exist_ok=True )
      self.__outDir = val
    else:
      self.__outDir = os.path.expanduser('~')

  @property
  def container(self):
    """Video container; e.g., mp4 or mkv"""

    return self.__container

  @container.setter
  def container(self, val):
    self.__container = val.lower()


  ################################################################################
  def transcode( self, inFile,
        log_file  = None,
        metaData  = None,
        chapters  = False,
        **kwargs):
    """
    Actually transcode a file

    Designed mainly with MKV file produced by MakeMKV in mind, this method
    acts to setup options to be fed into the ffmpeg CLI to transcode
    the file. A non-exhaustive list of options chosen are

      - Set quality rate factor for x264/x265 based on video resolution and the recommended settings found here: https://handbrake.fr/docs/en/latest/workflow/adjust-quality.html
      - Used variable frame rate, which 'preserves the source timing
      - Uses x264 codec for all video 1080P or lower, uses x265 for video greater than 1080P, i.e., 4K content.
      - Copy any audio streams with more than two (2) channels 
      - Extract VobSub subtitle file(s) from the mkv file.
      - Convert VobSub subtitles to SRT files.

    This program will accept both movies and TV episodes, however,
    movies and TV episodes must follow specific naming conventions 
    as specified under in the 'File Naming' section below.

    Arguments:
      inFile (str): Full path to MKV file to covert. Make sure that the file names
        follow the following formats for movies and TV shows:

    Keyword arguments:
      log_file (str): File to write logging information to
      metaData (dict): Pass in result from previous call to getMetaData
      chapters (bool): Set if commericals are to be marked with chapters.
        Default is to cut commericals out of video file
      comdetect (bool): Set to remove/mark commercial segments in file

    Returns:
      Outputs a transcoded video file in the MP4 container and 
      subtitle files, based on keywords used. Also returns codes 
      to signal any errors. 

    Transcode Status
      -  0 : Everything finished cleanly
      -  1 : Output file exists
      -  5 : comskip failed
      - 10 : No video OR no audio streams

    """
 
    if _sigtermEvent.is_set(): return False                                     # If _sigterm has been called, just quit

    _sigintEvent.clear()                                                        # Clear the 'global' kill event that may have been set by SIGINT

    if not self.file_info( inFile, metaData = metaData ): return False          # If there was an issue with the file_info function, just return
    self._init_logger( log_file )                                               # Run method to initialize logging to file
    if self.video_info is None or self.audio_info is None:                      # If there is not video stream found OR no audio stream(s) found
      self.__log.critical("No video or no audio, transcode cancelled!")         # Print log message
      self.transcode_status = 10                                                # Set transcode status
      return False                                                              # Return

    start_time            = datetime.now()                                      # Set start date
    self.chapterFile      = None                                                # Reset chapterFile to None
    self.transcode_status = None                                                # Reset transcode status to None
    self._createdFiles    = []                                                  # Reset created files list

    outFile   = f"{self.outFile}.{self.container}"                              # Set the output file path
    prog_file = self._inprogress_file( outFile )                                # Get file name for inprogress conversion; maybe a previous conversion was cancelled

    self.__log.info( f"Output file: {outFile}" )                              # Print the output file location
    if os.path.exists( outFile ):                                                       # IF the output file already exists
      if not os.path.exists( prog_file ):                                               # If the inprogress file does NOT exists, then conversion completed in previous attempt
        self.__log.info("Output file Exists...Skipping!")                               # Print a message
        self.transcode_status = 1
        if self.remove:
          self._cleanUp( self.inFile )                                                  # If remove is set, remove the source file
        self.chapterFile = self._cleanUp( self.chapterFile )
        return False                                                                   # Return to halt the function
      elif self._being_converted( outFile ):                                            # Inprogress file exists, check if output file size is changing
        self.__log.info("It seems another process is creating the output file")         # The output file size is changing, so assume another process is interacting with it
        return False
      else:
        msg  = "It looks like there was a previous attempt to transcode " + \
               "the file. Re-attempting transcode..." 
        self.__log.info( msg )                                                          # The output file size is changing, so assume another process is interacting with it
        self._cleanUp( outFile )

    open(prog_file, 'a').close()                                                        # Touch inprogress file, acts as a kind of lock

    if kwargs.get('comdetect', self.comdetect):                                         # If the comdetect keywords is set; if key not given use class-wide setting
      name = ''                                                                         # Default value for name keyword for remove_commercials method
      if self.metaData is not None:                                                     # If metaData attribute is not None
        if self.metaData.isEpisode:                                                     # If metaData for episode
          name = str(self.metaData.Series)                                              # Get series information
        else:                                                                           # Else
          name = str(self.metaData)                                                     # Get movie information
      status = self.remove_commercials( self.inFile, chapters = chapters, name = name )  # Try to remove commercials 
      if isinstance(status, str):                                                       # If string instance, then is path to chapter file
        self.chapterFile = status                                                       # Set chatper file attribute to status; i.e., path to chapter file
      elif not status:                                                                  # Else, will be boolean
        self.transcode_status = 5
        if isRunning():
          self.__log.error( "Error cutting commercials, assuming bad file..." )
          self._cleanUp( prog_file )
        return None

    self.ffmpeg_cmd = self._ffmpeg_command( outFile )                                   # Generate ffmpeg command list
    self._createdFiles.append( outFile )                                                # Append outFile to list of created files

    self.__log.info( "Transcoding file..." )

    progress = FFmpegProgress( nintervals = 10 )                                        # Initialize ffmpeg progress class
    stderr   = RotatingFile( self.transcode_log, callback=progress.progress )
    kwargs   = {'threads'            : self.threads,
                'stderr'             : stderr,
                'universal_newlines' : True}                                            # Initialzie keyword arguments from Popen_async method

    self.__log.debug( f"ffmpeg cmd: {' '.join(self.ffmpeg_cmd)}" )
    try:
      proc = POPENPOOL.Popen_async( self.ffmpeg_cmd, **kwargs )                         # Submit command to subprocess pool
    except:
      proc = None
    else:
      proc.wait()

    self.chapterFile = self._cleanUp( self.chapterFile )                                # Clean up chapter file

    try: 
      self.transcode_status = proc.returncode                                           # Set transcode_status      
    except:
      self.transcode_status = -1

    if self.transcode_status == 0:                                                      # If the transcode_status IS zero (0)
      self.__log.info( "Transcode SUCCESSFUL!" )                                        # Print information
      if self.metaData:
        self.metaData.writeTags( outFile )
      self.get_subtitles( )                                                             # Extract subtitles

      inSize  = os.stat(self.inFile).st_size                                           # Size of inFile
      outSize = os.stat(outFile).st_size                                               # Size of out_file
      difSize = inSize - outSize                                                       # Difference in file size
      change  = 'larger' if outSize > inSize else 'smaller'                            # Is out_file smaller or larger than in file
      self.__log.info(
        f"The new file is {abs(difSize)/inSize*100:4.1f}% {change} than the original"
      )

      if self.remove:                                                                   # If remove is set
        self.__log.info( "Removing the input file..." )                                # Log some information
        self._cleanUp( self.inFile )

      self.__log.info( f"Duration: {datetime.now()-start_time}" )                 # Print compute time
    elif isRunning():                                                                   # Else, there was an issue with the transcode
      self.__log.critical( 
        f"All transcode attempts failed : {self.inFile}. Removing all created files."           # Message for log
      )
      outFile = None                                                                    # Set out_file to None, this is returned at end of method
      self._createdFiles = self._cleanUp( *self._createdFiles ) 
    
    if isRunning(): self._cleanUp( prog_file )                                          # Only cleanup progress file if still running

    return outFile                                                              # Return output file from function, i.e., transcode was success

  ##############################################################################
  def file_info( self, inFile, metaData = None):
    """
    Extract some information from the input file name and set up some output file variables.
    
    Arguments:
      inFile (str): Full path of file

    Keyword arguments:
      metaData (dict): Metadata for file; if none entered, will attempt to get
        metadata from TMDb or TVDb

    Returns:
      None

    """

    if not isRunning(): return False
    self.__log.info("Setting up some file information...")

    # Set up file/directory information
    self.inFile  = inFile if os.path.exists( inFile ) else None                         # Set the inFile attribute for the class to the file input IF it exists, else, set the inFile to None
    if self.inFile is None:                                                             # IF the input file does NOT exist
      self.__log.info(  "File requested does NOT exist. Exitting..." )
      self.__log.info( f"   {inFile}" )
      return False                                                                      # Return, which stops the program

    self.__log.info( f"Input file: {self.inFile}" )                           # Print out the path to the input file
    self.__log.info(  "Getting video, audio, information...")                             # If verbose is set, print some output

    self.video_info = self.get_video_info( x265 = self.x265 )                           # Get and parse video information from the file
    if self.video_info is None:
      return 
    self.audio_info = self.get_audio_info( self.lang )                                  # Get and parse audio information from the file
    if self.audio_info is None:
      return

    if self.in_place:                                                                   # If file is to be converted in place then
      outDir = os.path.dirname( self.inFile )                                           # Set outDir to dirname of inFile
    else:                                                                               # Else, set outDir to self.outDir
      outDir = self.outDir                                                              # Set outDir to self.outDir

    if metaData is None:                                                                # If metaData is None
      self.metaData = getMetaData( self.inFile )                                        # Try to get metaData
    else:
      self.metaData = metaData

    if self.metaData:                                                                   # If metaData is valid
      self.metaData.addComment( 
        f"File converted and tagged using {__pkg_name__} version {__pkg_version__}"
      )
      outFile = self.metaData.getBasename()                                             # Get basename
      if not self.in_place:                                                             # If NOT converting file in place
        outDir  = self.metaData.getDirname( root = self.outDir )                             # Set outDir based on self.outDir and getDirname() method
    else:                                                                               # Else, metaData NOT valid
      outFile = os.path.splitext( os.path.basename( self.inFile ) )[0]                  # Set outFile to inFile basename without extension

    if not os.path.isdir( outDir ):
      os.makedirs( outDir )

    outFile      = os.path.join( outDir, outFile )                                      # Create full path to output file; no extension
    extraInfo    = self.video_info["file_info"] + self.audio_info["file_info"]
    self.outFile = '.'.join( [outFile] + extraInfo ) 
    return True 

  ##############################################################################    
  def get_subtitles( self ):
    """
    Try to get subtitles through various means

    Get subtitles for a movie/tv show via extracting VobSub(s) from the input
    file and converting them to SRT file(s).
    If a file fails to convert, the VobSub files are removed.

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      Updates sub_status and creates/updates list of VobSubs that failed vobsub2srt conversion.

    Return codes:
      - 0 : Completed successfully.
      - 1 : VobSub(s) and SRT(s) already exist
      - 2 : Error extracting VobSub(s).
      - 3 : VobSub(s) are still being extracted.

    Dependencies:
      - mkvextract : A CLI for extracting streams for an MKV file.
      - vobsub2srt : A CLI for converting VobSub images to SRT

    """ 

    if not isRunning(): return

    ######
    if (not self.subtitles) and (not self.srt):                                    # If both subtitles AND srt are False
      return                                                                    # Return from the method

    self.text_info = self.get_text_info( self.lang )                            # Get and parse text information from the file
    if self.text_info is None:                                                  # If there is not text information, then we cannot extract anything
      return

    srt_files = []
    if self.format == "MPEG-TS":                                                # If the input file format is MPEG-TS, then must use CCExtractor
      if ccextract.CLI:                                                         # If the ccextract function import successfully
        srt_files = ccextract.ccextract( self.inFile, self.outFile, self.text_info )     # Run ccextractor
      else:
        self.__log.warning("ccextractor failed to import, nothing to do")
    elif not subtitle_extract.CLI:                                              # Assume other type of file
      self.__log.warning("subtitle extraction not possible")
    else:
      self.sub_status, sub_files = subtitle_extract.subtitle_extract( 
        self.inFile, 
        self.outFile, 
        self.text_info, 
        srt       = self.srt,
      )                                                     # Extract VobSub(s) from the input file and convert to SRT file(s).
      self._createdFiles.extend( sub_files )                                 # Add list of files created by subtitles_extract to list of created files
      if (self.sub_status > 1):                                 # If there weren't nay major errors in the subtitles extraction
        return

    if self.srt:
      srt_files = sub_to_srt(   
        self.outFile, self.text_info,   
        delete_soure = self.sub_delete_source,   
        cpulimit     = self.cpulimit,   
        threads      = self.threads,
      )                                      # Convert subtitles to SRT files

    self._createdFiles.extend( srt_files )

  ##############################################################################
  def _cleanUp(self, *args):
    """Method to delete arbitrary number of files, catching exceptions"""

    for arg in args:
      if arg and os.path.isfile( arg ):
        try:
          os.remove( arg )
        except Excpetion as err:
          self.__log.warning(f"Failed to delete file: {arg} --- {err}")
    return None

  ##############################################################################
  def _ffmpeg_command(self, outFile): 
    """
    A method to generate full ffmpeg command list

    Arguments:
      outFile (str): Full output file path that ffmpeg will create

    Keyword arguments:
      None

    Returns:
      list: Full ffmpeg command to run

    """

    cmd = self._ffmpeg_base( )                                                  # Call method to generate base command for ffmpeg

    cropVals  = cropdetect( self.inFile, threads = self.threads )               # Attempt to detect cropping
    videoKeys = self._videoKeys()                                              # Generator for orderer keys in video_info
    audioKeys = self._audioKeys()                                              # Generator for orderer keys in audio_info
    avOpts    = [True, True]                                                   # Booleans for if all av options have been parsed

    while any( avOpts ):                                                        # While any options left
      try:                                                                      # Try to
        key = next( videoKeys )                                                # Get the next video_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[0] = False                                                      # Set avOpts[0] to False because done with video options
      else:                                                                     # Else, we got a key
        cmd.extend( self.video_info[ key ] )                                   # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is '-filter', we also want the next tag, which is codec
          if cropVals is not None:                                              # If cropVals is NOT None
            if len(self.video_info[key]) != 0:                                  # If not an empty list
              cmd[-1] = f"{cmd[-1]},{cropVals}"                                 # Add cropping to video filter
            else:                                                               # Else, must add the '-vf' flag
              cmd.extend( ["-vf", cropVals] )                                  # Add cropping values
          cmd.extend( self.video_info[ next(videoKeys) ] )                     # Add next options to ffmpeg
      try:                                                                      # Try to
        key = next( audioKeys )                                                # Get the next audio_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[1] = False                                                      # Set avOpts[1] to False because done with audio options
      else:                                                                     # Else, we got a key
        cmd.extend( self.audio_info[ key ] )                                   # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is -'filter', we also want the next tag, which is codec
          cmd.extend( self.audio_info[ next(audioKeys) ] )                     # Add next options to ffmpeg

    cmd.append( outFile )                                                     # Append input and output file paths to the ffmpeg command
    return cmd

  ##############################################################################
  def _ffmpeg_base(self, strict = 'experimental',
       max_muxing_queue_size = 2048):
    """
    A method to generate basic ffmpeg command

    Arguments:
      None

    Keywords arguments:
      strict (str): Specify how strictly to follow the standards.
        Possible values:
          - ‘very’ : strictly conform to an older more strict version of the spec or reference software 
          - ‘strict’ : strictly conform to all the things in the spec no matter what consequences 
          - ‘normal’
          - ‘unofficial’ : allow unofficial extensions 
          - ‘experimental’ : allow non standardized experimental things, experimental (unfinished/work in progress/not well tested) decoders and encoders. Note: experimental decoders can pose a security risk, do not use this for decoding untrusted input. 
      max_muxing_queue_size (int): Should not have to change; see https://trac.ffmpeg.org/ticket/6375

    Returns:
      List containing base ffmpeg command for converting

    """

    if isinstance(self.chapterFile, str) and os.path.isfile(self.chapterFile):  # If the chapter file exits
      self.__log.info( f"Adding chapters from file : {self.chapterFile}" )
      chapters = ["-i", self.chapterFile, "-map_metadata", "1"]                 # Append to command and set meta data mapping from file
    else:
      chapters = ["-map_chapters", "0"]                                         # Else, enable mapping of chapters from source file

    return [
      "ffmpeg", "-nostdin", "-i", self.inFile,
      *chapters,
      "-tune", "zerolatency",                                                   # Enable faster streaming
      "-f", self.container, "-threads", str(self.threads),                      # Set container and number of threads to use
      "-strict", strict,
      "-max_muxing_queue_size", str(max_muxing_queue_size),
    ]

  ##############################################################################
  def _videoKeys(self):
    """
    A generator method to produce next ordered key from video_info attribute

    Arguments:
      None

    Keywords:
      None

    Returns:
      str: Key for the video_info attribute

    """

    for key in self.video_info["order"]:
      yield key

  ##############################################################################
  def _audioKeys(self):
    """
    A generator method to produce next ordered key from audio_info attribute

    Arguments:
      None

    Keyword arguments:
      None.

    Returns:
      str: Key for the audio_info attribute

    """

    for key in self.audio_info["order"]:
      yield key

  ##############################################################################
  def _inprogress_file(self, file):
    fdir, fbase = os.path.split(  file )
    return os.path.join( fdir, f".{fbase}.inprogress" )

  ##############################################################################
  def _being_converted( self, file ):  
    """Method to check if file is currently being convert"""

    s0 = os.path.getsize( file )                                                # Get size of output file
    time.sleep(0.5)                                                             # Wait half a second
    return (s0 != os.path.getsize(file))                                        # Check that size of file has changed

  ##############################################################################
  def _init_logger(self, log_file = None):
    """Function to set up the logger for the package"""

    if self.__fileHandler:                                                      # If there is a file handler defined
      self.__fileHandler.flush()                                               # Flush output to handler
      self.__fileHandler.close()                                               # Close the handler
      self.__log.removeHandler(self.__fileHandler)                               # Remove all handlers
      self.__fileHandler = None                                                # Set fileHandler attribute to None

    if log_file:                                                                # If there was a log file input
      if not os.path.isdir( os.path.dirname( log_file ) ):                      # If the directory the log_file is to be placed in does NOT exist
        dir = os.path.dirname( log_file )                                      # Get directory log file is to be placed in
        if dir != '': os.makedirs( dir )                                       # Create to directory for the log file

      self.__fileHandler = logging.FileHandler( log_file, 'w' )                # Initialize a file handler for the log file
      self.__fileHandler.setLevel(     fileFMT["level"]     )                  # Set the logging level for the log file
      self.__fileHandler.setFormatter( fileFMT["formatter"] )                  # Set the log format for the log file
      self.__log.addHandler(self.__fileHandler)                                  # Add the file log handler to the logger
