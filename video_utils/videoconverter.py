# Built-in imports
import logging
import os, re, time
from datetime import datetime
from subprocess import PIPE, STDOUT
from multiprocessing import cpu_count

# Parent classes
from . import _sigintEvent, _sigtermEvent, isRunning, LOGDIR
from .mediainfo import MediaInfo
from .comremove import ComRemove
from .utils.ffmpeg_utils   import cropdetect, progress

# Subtitle imports
from .subtitles.opensubtitles import OpenSubtitles
try:
  from .subtitles.vobsub_extract import vobsub_extract
except:
  vobsub_extract = None
try:
  from .subtitles.vobsub_to_srt import vobsub_to_srt
except:
   vobsub_to_srt = None
try:
  from .subtitles.ccextract import ccextract
except:
   ccextract = None

# Metadata imports
from .videotagger.metadata.getMetaData import getMetaData
from .videotagger.metadata.Episode import TVDbEpisode
from .videotagger.metadata.Movie import TMDbMovie
from .videotagger.mp4Tags import mp4Tags
try:
  from .videotagger.mkvTags import mkvTags
except:
  mkvTags = None

# Logging formatter
from ._logging import fileFMT;

from . import POPENPOOL

_sePat = re.compile( r'[sS](\d{2,})[eE](\d{2,})' );                              # Matching pattern for season/episode files; lower/upper case 's' followed by 2 or more digits followed by upper/lower 'e' followed by 2 or more digits followed by ' - ' string

class VideoConverter( ComRemove, MediaInfo, OpenSubtitles ):
  '''
  Name:
     VideoConverter
  Purpose:
     A python class for converting video files h264 encoded files
     in either the MKV or MP4 container. Video files must be
     decodeable by the handbrake video software. All
     audio tracks that will be passed through and AAC format stereo
     downmixes of any mulit-channel audio tracks will be created for
     better compatability. The H264 video code will be used for all
     files with resolutions of 1080P and lower, while H265 will be
     used for all videos with resolution greater than 1080P. 
     The H265 codec can be enabled for lower resolution videos.
  Dependencies:
     ffmpeg, mediainfo
  Author and History:
     Kyle R. Wodzicki     Created 24 Jul. 2017
  '''
  illegal   = ['#','%','&','{','}','\\','<','>','*','?','/','$','!',':','@']
  legal     = ['', '', '', '', '', ' ', '', '', '', '', ' ','', '', '', '']
  __outDir = os.path.expanduser('~')
  __isMP4   = False
  __isMKV   = False

  def __init__(self, 
               outDir       = None,
               logDir       = None,
               in_place      = False, 
               no_ffmpeg_log = False,
               lang          = None, 
               threads       = cpu_count(), 
               container     = 'mp4',
               cpulimit      = 75, 
               x265          = False,
               remove        = False,
               vobsub        = False, 
               srt           = False,
               vobsub_delete = False,
               **kwargs):
    '''
    Keywords:
       out_dir       : Path to output directory. Optional input. 
                        DEFAULT: Place output file(s) in source directory.
       log_dir       : Path to log file directory. Optional input.
                        DEFAULT: Place log file(s) in source directory.
       in_place      : Set to transcode file in place; i.e., do NOT create a 
                         new path to file such as with TV, where
                         ./Series/Season XX/ directories are created
       no_ffmpeg_log : Set to suppress the creation of stdout and stderr log
                        files for ffmpeg and instead pipe the output to
                        /dev/null
       lang          : String or list of strings of ISO 639-2 codes for 
                        subtitle and audio languages to use. 
                        Default is english (eng).
       threads       : Set number of threads to use. Default is to use half
                        of total available.
       cpulimit      : Set to percentage to limit cpu usage to. This value
                        is multiplied by number of threads to use.
                        DEFAULT: 75 per cent.
                        TO DISABLE LIMITING - set to 0.
       remove        : Set to True to remove mkv file after transcode
       vobsub        : Set to extract VobSub file(s). If SRT is set, then
                        this keyword is also set. Setting this will NOT
                        enable downloading from opensubtitles.org as the
                        subtitles for opensubtitles.org are SRT files.
       srt           : Set to convert the extracted VobSub file(s) to SRT
                        format. Also enables opensubtitles.org downloading 
                        if no subtitles are found in the input file.
       vobsub_delete : Set to delete VobSub file(s) after they have been 
                        converted to SRT format. Used in conjunction with
                        srt keyword.
      username       : User name for opensubtitles.org
      userpass       : Password for opensubtitles.org. Recommend that
                        this be the md5 hash of the password and not
                        the plain text of the password for slightly
                        better security
    '''
    super().__init__(**kwargs);
    self.__log = logging.getLogger( __name__ );                                   # Set log to root logger for all instances
    self.container = container
    if vobsub_extract is None:
      self.__log.warning('VobSub extraction is DISABLED! Check that mkvextract is installed and in your PATH');
      self.vobsub = False;
    else:
      self.vobsub = vobsub;
    self.srt = srt;
    if self.srt and (not vobsub_to_srt):
      self.__log.warning('VobSub2SRT conversion is DISABLED! Check that vobsub2srt is installed and in your PATH')

    self.cpulimit = cpulimit;
    self.threads  = threads;


    # Set up all the easy parameters first
    self.outDir        = outDir
    self.logDir        = logDir;
    self.new_log_dir   = None
    self.in_place      = in_place;                                              # Set the in_place attribute based on input value
    self.no_ffmpeg_log = no_ffmpeg_log;                                         # Set the no_ffmpeg_log attribute based on the input value
    self.miss_lang     = [];
    self.x265          = x265;      
    self.remove        = remove;       
    self.vobsub_delete = vobsub_delete;
    self.inFile       = None

    if lang:                                                                    # If lang is set
      self.lang = lang if isinstance(lang, (tuple,list,)) else [lang]           # Set lang attribute to lang if it is a tuple or list instance, else make lang a list
    if (len(self.lang) == 0):							# If lang is empty list
      self.lang = ['eng']                                                       # Set default language to english 
    
    self.chapterFile      = None

    self.video_info       = None                                                # Set video_info to None by default
    self.audio_info       = None                                                # Set audio_info to None by default
    self.text_info        = None                                                # Set text_info to None by default
    self.subtitle_ltf     = None                                                # Array to store subtitle language, track, forced (ltf) tuples
    self.vobsub_status    = None                                                # Set vobsub_status to None by default
    self.srt_status       = None                                                # Set srt_status to None by default
    self.transcode_status = None                                                # Set transcode_status to None by default
    self.tagging_status   = None                                                # Set mp4tags_status to None by default
    
    self.IMDb             = None
    self.metaData         = None
    self.metaKeys         = None
    self.ffmpeg_logTime   = None

    self.is_episode       = False
    self.tagging          = False

    self.v_preset         = 'slow';                                             # Set x264/5 preset to slow
    self.fmt              = 'utf-8';                                            # Set encoding format
    self.encode           = type( 'hello'.encode(self.fmt) ) is str;            # Determine if text should be encoded; python2 vs python3

    self._createdFiles    = [];                                                 # List to store paths to all files created by transcode method
    self.__fileHandler    = None;                                               # logging fileHandler 
  
  @property
  def outDir(self):
    return self.__outDir
  @outDir.setter
  def outDir(self, val):
    if isinstance(val, str):
      if not os.path.isdir( val ):
        os.makedirs( val, True )
      self.__outDir = val
    else:
      self.__outDir = os.path.expanduser('~')

  @property
  def container(self):
    return self.__container
  @container.setter
  def container(self, val):
    self.__container = val.lower();
    self.__isMP4 = (self.__container == 'mp4')
    self.__isMKV = (self.__container == 'mkv')


  ################################################################################
  def transcode( self, inFile, 
        log_file          = None, 
        metaData          = None,
        chapters          = False, 
        removeCommercials = False):
    '''
    Name:
       transcode
    Purpose:
       A python function to get information about an MKV file produced
       by the MakeMKV program and convert the file to a an MP4 with
       x264 or x265 encoding. This function calls many functions to set
       up options to be fed into the HandBrakeCLI command to transcode
       the file. A non-exhaustive list of options chosen are:
            - Set quality rate factor for x264/x265 based on video 
               resolution and the recommended settings found here:
                   https://handbrake.fr/docs/en/latest/workflow/
                   adjust-quality.html
            - Used variable frame rate, which 'preserves the source timing
            - Uses x264 codec for all video 1080P or lower, uses x265 for
               video greater than 1080P, i.e., 4K content.
            - Copy any audio streams with more than two (2) channels 
            - Generate an AAC encoded Dolby Pro Logic II downmix of
               streams with more then two (2) channels channels.
            - Generate an AAC encoded stream for any streams with two (2)
               or fewer channels
            - Extract VobSub subtitle file(s) from the mkv file.
            - Convert VobSub subtitles to SRT files.
       This program will accept both movies and TV episodes, however,
       movies and TV episodes must follow specific naming conventions 
       as specified under in the 'File Naming' section below.
    Inputs:
       inFile  : Full path to MKV file to covert. Make sure that the file names
               follow the following formats for movies and TV shows:
    Outputs:
       Outputs a transcoded video file in the MP4 container and
       subtitle files, based on keywords used. Also returns codes 
       to signal any errors.
    Keywords:
       log_file  : File to write logging information to
       metaData  : Pass in result from previous call to getMetaData
       chapters  : Set if commericals are to be marked with chapters.
                     Default is to cut commericals out of video file
       removeCommercials : Set to remove/mark commercial segments in file
    Return:
        Check .transcode_status
        0 : Everything finished cleanly
        1 : Output file exists
        5 : comskip failed
       10 : No video OR no audio streams
    File Naming:
       MOVIE:
           Title.qualifier.year.imdbID.mkv
              Title -     Title of the movie. Only special character  
                                                 allowed is an apostrophe ('). 
                                                 DO NOT USE PERIODS (.) IN TITLE!
              qualifier - Used to specify if movie is unrated, 
                                                 extended, edition, etc. 
              year      - Year the movie was released.
              imdbID    - The movie's IMDB index, which starts with 
                                                 'tt', and can be found in the URL for the
                                                 IMDB web page. Here is an example for the 
                                                 movie '21' where the IMDB index is after 
                                                 title/: http://www.imdb.com/title/tt0478087/
           If there is no data for a given field, leave it blank. 
           For example: A Movie....mkv would be used for a movie 
           with no qualifier, year, or IMDB index
       TV EPISODE
           Title.imdbID.mkv
              Title  - The title MUST starts with 'sXXeXX - '
                        where sXX corresponds to the season number 
                        and eXX is the episode number. For example,
                        the first episode in a series is usually 
                        named 'Pilot', so the file title would be 
                        's01e01 - Pilot'. Only special character  
                        allowed is an apostrophe (').
                        DO NOT USE PERIODS (.) IN TITLE!
              imdbID - The IMDB index of the episode. See imdbID under
                        MOVIE for more information.
           If there is no data for a given field, leave it blank. For
           example: 'A Movie....mkv' would be used for a movie with
           no qualifier, year, or IMDB index. The same follows for the
           TV episodes. The only field required is the TITLE

    Author and History:
       Kyle R. Wodzicki     Created 29 Dec. 2016
    '''
    if _sigtermEvent.is_set(): return False                                     # If _sigterm has been called, just quit

    _sigintEvent.clear()                                                        # Clear the 'global' kill event that may have been set by SIGINT
    self._createdFiles = []                                                     # Reset created files list
    if not self.file_info( metaData = metaData ): return False                  # If there was an issue with the file_info function, just return
    self._init_logger( log_file );                                              # Run method to initialize logging to file
    if self.video_info is None or self.audio_info is None:                      # If there is not video stream found OR no audio stream(s) found
      self.__log.critical('No video or no audio, transcode cancelled!');        # Print log message
      self.transcode_status = 10;                                               # Set transcode status
      return False;                                                             # Return

    start_time = datetime.now();                                                # Set start date
    self.transcode_status = None;                                               # Reset transcode status to None
    self.ffmpeg_logTime   = None;

    out_file  = '{}.{}'.format( self.out_file, self.container );                # Set the output file path
    prog_file = self._inprogress_file( out_file )                               # Get file name for inprogress conversion; maybe a previous conversion was cancelled

    self.__log.info( 'Output file: {}'.format( out_file ) );                    # Print the output file location
    if os.path.exists( out_file ):                                              # IF the output file already exists
      if not os.path.exists( prog_file ):                                       # If the inprogress file does NOT exists, then conversion completed in previous attempt
        self.__log.info('Output file Exists...Skipping!');                      # Print a message
        self.transcode_status = 1
        if self.remove: os.remove( self.inFile );                              # If remove is set, remove the source file
        if os.path.isfile( self.chapterFile ):                                  # If a .chap file exists
          try:
            os.remove( self.chapterFile )                                       # Delete the file
          except Exception as err:
            self.__log.error( 'Failed to delete chapter file: {}'.format(err) ) # Log error                                                        
        return False;                                                           # Return to halt the function
      elif self._being_converted( out_file ):                                   # Inprogress file exists, check if output file size is changing
        self.__log.info('It seems another process is creating the output file') # The output file size is changing, so assume another process is interacting with it
        return False;
      else:
        msg  = 'It looks like there was a previous attempt to transcode ' + \
               'the file. Re-attempting transcode...' 
        self.__log.info( msg )                                                  # The output file size is changing, so assume another process is interacting with it
        os.remove( out_file )                                                   # Delete the output file for another tyr

    open(prog_file, 'a').close()                                                # Touch inprogress file, acts as a kind of lock

    if removeCommercials:                                                       # If the removeCommercials keywords is set
      if not self.removeCommercials( inFile, chapters = chapters ):            # Run the removeCommericals method
        self.__log.error( 'Error cutting commercials, assuming bad file...' )
        self.transcode_status = 5
        self._cleanUp( prog_file )
        return None

    self.ffmpeg_err_file  = self.ffmpeg_log_file + '.err';                      # Set up path for ffmpeg error file
    self.ffmpeg_log_file += '.log';                                             # Set up path for ffmpeg log file

    self.ffmpeg_cmd = self._ffmpeg_command( out_file );                         # Generate ffmpeg command list
    self._createdFiles.append( out_file )

    if isRunning():
      self.__log.info( 'Transcoding file...' )

      kwargs = {'threads' : self.threads} 
      if self.no_ffmpeg_log:                                                    # If creation of ffmpeg log files is disabled
        kwargs.update(
          {'stdout'             : PIPE, 
           'stderr'             : STDOUT,
           'universal_newlines' : True}
        )                                                                       # Start the ffmpeg command and direct all output to a PIPE and enable universal newlines; this is logging of progess can occur
      else:                                                                     # Else
        kwargs.update(
          {'stdout' : self.ffmpeg_log_file, 
           'stderr' : self.ffmpeg_err_file}
        )
      proc = POPENPOOL.Popen_async( self.ffmpeg_cmd, **kwargs ) 

      if self.no_ffmpeg_log:                                                    # If ffmpeg log files are disabled, we want to know a little bit about what is going on
          proc.applyFunc( progress, kwargs= {'nintervals' : 10} )               # Apply the 'progess' function to the process to monitor ffmpeg progress
      POPENPOOL.wait()

      if os.path.isfile( self.chapterFile ): os.remove( self.chapterFile )      # If the cahpter file exists, delete it
      self.chapterFile = None                                                   # Set chapter file to None for safe measure

    try: 
      self.transcode_status = proc.returncode                              # Set transcode_status      
    except:
      self.transcode_status = -1

    if self.transcode_status == 0:                                              # If the transcode_status IS zero (0)
      self.__log.info( 'Transcode SUCCESSFUL!' )                                # Print information
      self._write_tags( out_file )
      self.get_subtitles( )                                                     # Extract subtitles

      inSize  = os.stat(self.inFile).st_size;                                  # Size of inFile
      outSize = os.stat(out_file).st_size;                                      # Size of out_file
      difSize = inSize - outSize;                                               # Difference in file size
      change  = 'larger' if outSize > inSize else 'smaller';                    # Is out_file smaller or larger than in file
      msg     = 'The new file is {:4.1f}% {} than the original!';               # Set up message to be printed
      self.__log.info( msg.format(abs(difSize)/inSize*100, change) );           # Print the message about the size
          
      if self.remove:                                                           # If remove is set
        self.__log.info( 'Removing the input file...' );                        # Log some information
        os.remove( self.inFile );                                              # Delete the input file if remove is true

      self.__log.info('Duration: {}'.format(datetime.now()-start_time))         # Print compute time

    else:                                                                       # Else, there was an issue with the transcode
      self.__log.critical( 'All transcode attempts failed!!! Removing all created files' ) # Log critical information
      out_file = None                                                           # Set out_file to None, this is returned at end of method
      while len(self._createdFiles) > 0:                                        # Iterate over all files created by program
        try:
          os.remove( self._createdFiles.pop() )
        except:
          pass
    
    self._cleanUp( prog_file )

    return out_file                                                             # Return output file from function, i.e., transcode was success

  ##############################################################################
  def _cleanUp(self, *args):
    ''' Method to delete arbitrary number of files, catching exceptions'''
    for arg in args:
      if arg and os.path.isfile( arg ):
        try:
          os.remove( arg )
        except Excpetion as err:
          self.__log.warning('Failed to delete file: {} --- {}'.format(arg, err))

  ##############################################################################
  def _ffmpeg_command(self, out_file): 
    '''
    Purpose
      A method to generate full ffmpeg command list
    Inputs:
      out_file  : Full output file path that ffmpeg will create
    Outputs:
      Returns list containing full ffmpeg command to run
    Keywords:
      None.
    '''
    cmd = self._ffmpeg_base( )                                                  # Call method to generate base command for ffmpeg

    cropVals  = cropdetect( self.inFile );                                     # Attempt to detect cropping
    videoKeys = self._videoKeys();                                              # Generator for orderer keys in video_info
    audioKeys = self._audioKeys();                                              # Generator for orderer keys in audio_info
    avOpts    = [True, True];                                                   # Booleans for if all av options have been parsed

    while any( avOpts ):                                                        # While any options left
      try:                                                                      # Try to
        key = next( videoKeys );                                                # Get the next video_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[0] = False;                                                      # Set avOpts[0] to False because done with video options
      else:                                                                     # Else, we got a key
        cmd.extend( self.video_info[ key ] );                                   # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is '-filter', we also want the next tag, which is codec
          if cropVals is not None:                                              # If cropVals is NOT None
            if len(self.video_info[key]) != 0:                                  # If not an empty list
              cmd[-1] = '{},{}'.format(cmd[-1], cropVals);                      # Add cropping to video filter
            else:                                                               # Else, must add the '-vf' flag
              cmd.extend( ['-vf', cropVals] );                                  # Add cropping values
          cmd.extend( self.video_info[ next(videoKeys) ] );                     # Add next options to ffmpeg
      try:                                                                      # Try to
        key = next( audioKeys );                                                # Get the next audio_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[1] = False;                                                      # Set avOpts[1] to False because done with audio options
      else:                                                                     # Else, we got a key
        cmd.extend( self.audio_info[ key ] );                                   # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is -'filter', we also want the next tag, which is codec
          cmd.extend( self.audio_info[ next(audioKeys) ] );                     # Add next options to ffmpeg

    cmd.append( out_file );                                                     # Append input and output file paths to the ffmpeg command
    return cmd

  ##############################################################################
  def _ffmpeg_base(self):
    '''
    Purpose
      A method to generate basic ffmpeg command
    Inputs:
      None.
    Outputs:
      Returns list containing command
    Keywords:
      None.
    '''
    cmd  = ['ffmpeg', '-nostdin', '-i', self.inFile]

    if os.path.isfile(self.chapterFile):                                        # If the chapter file exits
      self.__log.info( 'Adding chapters from file : {}'.format(self.chapterFile) )
      cmd += ['-i', self.chapterFile, '-map_metadata', '1']                     # Append to command and set meta data mapping from file
    else:
      cmd += ['-map_chapters', '0']                                             # Else, enable mapping of chapters from source file

    cmd += ['-tune', 'zerolatency']                                             # Enable faster streaming
    cmd += ['-f', self.container, '-threads', str(self.threads)]                # Set container and number of threads to use

    return cmd                                                                  # Return command

  ##############################################################################
  def _write_tags(self, out_file):
    if not isRunning(): return                                                  # If the kill event is set, skip tag writing for faster exit
    if self.metaKeys is None:                                                   # If the metaKeys attribute is None
      self.__log.warning('No metadata to write!!!');                              # Print message that not data to write
    elif self.tagging:                                                          # If mp4tags attribute is True
      if self.__isMP4:
        self.tagging_status = mp4Tags( out_file, metaData = self.metaData );      # Write information to ONLY movie files
      elif self.__isMKV:
        if mkvTags:
          self.tagging_status = mkvTags( out_file, metaData = self.metaData )
        else:
          self.__log.warning( "MKV tagging disabled; check 'mkvpropedit' is installed" ) 
          self.tagging_status = 1
      if self.tagging_status == 0:
        self.__log.info('Metadata tags written.');                                     # Print message if status IS 0
      else:
        self.__log.warning('Metadata tags NOT written!!!');                            # Print message if status is NOT zero
    else:
      self.__log.warning('Metadata tagging disabled!!!');                              # If mp4tags attribute is False, print message

  ##############################################################################
  def file_info( self, inFile, metaData = None):
    '''
    Function to extract some information from the input file name and set up
    some output file variables.
    '''
    if not isRunning(): return False
    try:
      dbID, info = inFile.split('.')[:2]
    except:
      raise Exception('Incorrect file; follow convention') 

    self.__log.info('Setting up some file information...');

    self.tagging  = (self.container == 'mp4') or (self.container == 'mkv')      # Check if container is mp4
 
    # Set up file/directory information
    self.inFile  = inFile if os.path.exists( inFile ) else None;             # Set the inFile attribute for the class to the file input IF it exists, else, set the inFile to None
    if self.inFile is None:                                                    # IF the input file does NOT exist
      self.__log.info( 'File requested does NOT exist. Exitting...' );
      self.__log.info( '   {}'.format(inFile) );
      return False;                                                             # Return, which stops the program

    self.__log.info( 'Input file: {}'.format( self.inFile ) )                           # Print out the path to the input file
    self.chapterFile = os.path.splitext( self.inFile )[0] + '.chap'            # Set chapter file name; same name as source file, but with .chap extension; should be generated by comremove.comchapters()

    seasonEp = _sePat.findall( info ):
    if seasonEp:
      metadata = TVDbEpisode( dbID, *seasonEp )
    else:
      metadata = TMDbMovie( dbID )

    if metadata:
      outFile = metadata.fileBasename()
      if self.in_place:
        outFile = os.path.join( os.path.dirname( self.inFile ), outFile )
      else:
        outFile = os.path.join( self.outDir, metadata.fileDirname(), outFile )
    else:
      
    self._metaData( metaData = metaData )
    

    if self.logDir is None: 
      self.new_log_dir = os.path.join(self.curRootDir, 'Logs')          # Set log_dir to input directory if NOT set on init, else set to log_dir value
    else:
      self.new_log_dir = self.logDir

    self.__log.info('Getting video, audio, information...');                            # If verbose is set, print some output

    self.video_info = self.get_video_info( x265 = self.x265 );                          # Get and parse video information from the file
    if self.video_info is None: return;                    
    self.audio_info = self.get_audio_info( self.lang );                                 # Get and parse audio information from the file
    if self.audio_info is None: return;               

    ### Set up output file path and log file path. NO FILE EXTENSIONS USED HERE!!!
    print( self.video_info['file_info'], self.audio_info['file_info'] )

    self.file_name += [ self.video_info['file_info'], self.audio_info['file_info'] ]

    #if self.IMDb is not None: self.file_name += [self.IMDb];               # Append the IMDB ID to the file name if it is NOT None.

    self.file_name = '.'.join(self.file_name)
    self.__log.debug( 'File name: {}'.format( self.file_name) )

    # Generate file paths for the output file and the ffmpeg log files
    self.ffmpeg_log_file = os.path.join(self.new_log_dir, self.file_name);          # Set the ffmpeg log file path without extension
    self.out_file    = [self.curRootDir, '', self.file_name];                  # Set the output file path without extension
    self._join_out_file( );                                                   # Combine out_file path list into single path with NO movie/episode directory and create directories
    return True;

  ##############################################################################    
  def get_subtitles( self ):
    '''
    Name:
        get_subtitles
    Purpose:
        A python function to get subtitles for a movie/tv show via 
        extracting VobSub(s) from the input file and converting them
        to SRT file(s) OR downloadig them from opensubtitles.org.
        If a file fails to convert, the VobSub files are 
        removed and the program attempts to download if SRTs are 
        requested. If some languages requested were not found in 
        the input file, a download is attempted. If no subtitles
        in input file, a download is attempted. 
    Inputs:
    one.
    Outputs:
        updates vobsub_status and creates/updates list of VobSubs that failed
        vobsub2srt conversion.
        Returns codes for success/failure of extraction. Codes are as follows:
           0 - Completed successfully.
           1 - VobSub(s) and SRT(s) already exist
           2 - Error extracting VobSub(s).
           3 - VobSub(s) are still being extracted.
    Keywords:
        None.
    Dependencies:
        mediainfo  - A CLI for getting information from a file
        mkvextract - A CLI for extracting streams for an MKV file.
        vobsub2srt - A CLI for converting VobSub images to SRT
    Author and History:
        Kyle R. Wodzicki     Created 30 Dec. 2016
    '''

    if not isRunning(): return

    # Extract VobSub(s) and convert to SRT based on keywords
    def opensubs_all():
      '''Local function to download all subtitles from opensubtitles'''
      self.__log.info('Attempting opensubtitles.org search...')                 # Logging information
      self.login()                                                              # Login to the opensubtitles.org API
      self.searchSubs()                                                         # Search for subtitles
      if (self.subs is not None):                                               # If no subtitles are found
        found = 0;                                                              # Initialize found to zero (0)
        for lang in self.subs:                                                  # Iterate over all languages in the sub titles dictionary
          if self.subs[lang] is not None: found+=1                              # If one of the keys under that language is NOT None, then increment found
        if (found > 0):                                                         # If found is greater than zero (0), then subtitles were found
          self.saveSRT( self.out_file )                                         # Download the subtitles
      self.logout()                                                             # Log out of the opensubtitles.org API

    ######
    if (not self.vobsub) and (not self.srt):                                    # If both vobsub AND srt are False
      return                                                                    # Return from the method

    self.text_info = self.get_text_info( self.lang )                            # Get and parse text information from the file
    if self.text_info is None:                                                  # If there is not text information, then we cannot extract anything
      if self.srt:                                                              # If srt subtitles are requested
        opensubs_all()                                                          # Run local function
    elif self.vobsub or self.srt:                                               # Else, if vobsub or srt is set
      if self.format == "MPEG-TS":                                              # If the input file format is MPEG-TS, then must use CCExtractor
        if ccextract:                                                           # If the ccextract function import successfully
          status = ccextract( self.inFile, self.out_file, self.text_info )     # Run ccextractor
        else:
          self.__log.warning('ccextractor failed to import, falling back to opensubtitles.org');
          opensubs_all()                                                        # Run local function
      else:                                                                     # Assume other type of file
        if not vobsub_extract:                                                  # If the vobsub_extract function failed to import
          self.__log.warning('vobsub extraction not possible')
          if self.srt:                                                          # If the srt flag is set
            self.__log.info('Falling back to opensubtitles.org for SRT files')
            opensubs_all()                                                      # Run local function
        else:
          self.vobsub_status, vobsub_files = vobsub_extract( 
            self.inFile, self.out_file, self.text_info, 
            vobsub = self.vobsub,
            srt    = self.srt )                                                 # Extract VobSub(s) from the input file and convert to SRT file(s).
          self._createdFiles.extend( vobsub_files )                             # Add list of files created by vobsub_extract to list of created files
          if (self.vobsub_status < 2) and self.srt:                             # If there weren't nay major errors in the vobsub extraction
            if not vobsub_to_srt:                                               # If SRT output is enabled AND vobsub_to_srt imported correctly
              self.__log.warning('vobsub2srt conversion not possible. Leaving vobsub files.')
            else:
              self.srt_status, srt_files = vobsub_to_srt(   
                self.out_file, self.text_info,   
                vobsub_delete = self.vobsub_delete,   
                cpulimit      = self.cpulimit,   
                threads       = self.threads )                                  # Convert vobsub to SRT files
              self._createdFiles.extend( srt_files )
            failed = [i for i in self.text_info if i['srt'] is False];		# Check for missing srt files
            if len(failed) > 0:							# If missing files found
              self.__log.info('Attempting opensubtitles.org search...')         # Logging information
              self.login()							# Log into opensubtitles
              for i in range(len(self.text_info)):				# Iterate over all entries in text_info
                if self.text_info[i]['srt']: continue;				# If the srt file exists, skip
                self.track_num  = self.text_info[i]['track']
                self.get_forced = self.text_info[i]['forced']
                self.searchSubs( lang = self.text_info[i]['lang3'] )		# Search for subtitles, use lang keyword to override class attribute; do so won't erase self.lang
                tmpOut = self.saveSRT( file = self.out_file )			# Save subtitles, note that this may not actually work if noting was found
                if tmpOut and (len(tmpOut) == 1):
                  if os.path.isfile(tmpOut[0]):					# If the subtitle file exists
                    self.text_info[i]['srt'] = True				# update the srt presence flag
                    self._createdFiles.extend( tmpOut )				# Add subtitle file to list of created files
              self.logout()						        # Log out to of opensubtitles
    else:                                                                       # Else, not subtitle candidates were returned
      self.__log.debug('No subtitle options set')                               # Log some information

  ##############################################################################
  def _join_out_file(self):
    '''
    Name:
       _join_out_file
    Purpose:
       A python function to join a three element list containing
       file path elements for the output file. First element is 
       the root directory, second is empty py default, but can
       contain a directory name that is used when subtitles are
       enabled/found, and third element of the file name.
    Inputs:
       out_file list.
    Outputs:
       None; Resest class attributes.
    Keywords:
       None
    '''
    if isinstance(self.out_file, list):                                         # If the out_file is a list instance
      self.__log.debug( 'Joining output file path' )
      if not self.is_episode:                                                   # If NOT episode
        self.out_file[1] = self.title                                           # Place title in second element
      self.out_file    = os.path.join( *self.out_file );
      self.curRootDir = os.path.dirname( self.out_file )                       # Update new_out_dir incase a title was added to path
    self._create_dirs();                                                        # Create all output directories

  ###################################################################
  def _metaData(self, metaData = None):
    ''''
    Name:
      _metaData
    Purpose:
      Method responsible for checking for IMDb ID and setting
      up information in regard to that
    Inputs:
      None.
    Keywords:
      None.
    Outputs:
      Updates class attributes
    ''' 
    self.metaData = None;                                                               # Default metaData to None;
    self.metaKeys = None;                                                               # Default metaKeys to None;

    self.file_base  = os.path.basename(self.inFile)                                   # Get the base name of the file
    file_split      = self.file_base.split('.')[:-1];                           # Split base name on period and ignore extension 
    self.title      = file_split[0];                                            # Get title of movie or TV show
    self.season_dir = None;
    self.out_file   = None;

    if metaData:
      self.metaData = metaData
    else:
      ID = file_split[-1]
      seasonEp = _sePat.findall( self.file_base )
      if seasonEp: 
        self.is_episode = True
        #kwargs = {'TVDbID' : ID, *map(int, seasonEp[0]) )
        self.metaData = TVDbEpisode(ID, *map(int, seasonEp[0]) )
      else:
        kwargs = {'TMDbID' : ID}
        self.metaData = TVDbEpisode(ID )

      #self.metaData = getMetaData( **kwargs )

    self.metaKeys = self.metaData.keys();                                     # Get keys from the metaData information

    if len(self.metaKeys) == 0:                                               # If no keys returned
      self.__log.warning('Failed to download metadata for file!!!');
      self.__log.warning( 'Metadata tagging is disabled!!!' );                  # Print message that the mp4 tagging is disabled                
      self.tagging = False;                                                   # Disable mp4 tagging
      return False


    ### Determine if the file is an episode of a TV show, or a movie. TV episodes
    ### files begin with the patter 'sXXeXX - ', where XX is a number for the
    ### seasons and episode
    self.file_name = file_split                                                 # Join file base name using periods
    
    if self.metaKeys is None:                                                           # If the metaKeys attribute is None
      se_test = False;                                                                  # Then the se_test is False
    else:                                                                               # Else, the metaKeys attribute is not None
      se_test = ('series title' in self.metaKeys);                                      # Check that 'series title' key in metaKeys
      se_test = ('seriesName'   in self.metaKeys) or  se_test;                          # Check that 'seriesName' key in metaKeys OR previous criteria
      se_test = ('episode'      in self.metaKeys) and se_test;                          # Check that 'episode' key in metaKeys AND previous criteria
      se_test = ('season'       in self.metaKeys) and se_test;                          # Check that 'season'  key in metaKeys AND previous criteria

    if self.is_episode:
      outDir = self.tv_dir( self.metaData.getFilePath() )                                 # Reset output directory to original directory
    else:                                                                               # Else the file is a movie
      self.is_episode  = False;                                                         # Set is_episode to False
      outDir = self.mov_dir( self.metaData.getFilePath() )                                 # Reset output directory to original directory

    return True

  ##############################################################################
  def _videoKeys(self):
    '''
    Name:
      _videoKeys
    Purpose:
      A generator method to produce next ordered key from video_info
      attribute
    Inputs:
      None.
    Outputs:
      Key for the video_info attribute
    Keywords:
      None.
    '''
    for i in range( len(self.video_info['order']) ):                            # Iterate over all values in the 'order' tuple
      yield self.video_info['order'][i];                                        # Yield the key

  ##############################################################################
  def _audioKeys(self):
    '''
    Name:
      _audioKeys
    Purpose:
      A generator method to produce next ordered key from audio_info
      attribute
    Inputs:
      None.
    Outputs:
      Key for the audio_info attribute
    Keywords:
      None.
    '''
    for i in range( len(self.audio_info['order']) ):                            # Iterate over all values in the 'order' tuple
      yield self.audio_info['order'][i];                                        # Yield the key

  ##############################################################################
  def _inprogress_file(self, file):
    fdir, fbase = os.path.split(  file )
    return os.path.join( fdir, '.{}.inprogress'.format(fbase) )

  ##############################################################################
  def _being_converted( self, file ):  
    '''Method to check if file is currently being convert'''
    s0 = os.path.getsize( file )                                                # Get size of output file
    time.sleep(0.5)                                                             # Wait half a second
    return (s0 != os.path.getsize(file))                                        # Check that size of file has changed

  ##############################################################################
  def _create_dirs( self ):
    self.__log.debug( 'Creating output directories' )
    if not os.path.isdir( self.curRootDir  ): os.makedirs( self.curRootDir  );            # Check if the new output directory exists, if it does NOT, create the directory
    if not self.no_ffmpeg_log:                                                              # If HandBrake log files are NOT disabled
      if not os.path.isdir( self.new_log_dir     ): os.makedirs( self.new_log_dir );        # Create log directory if it does NOT exist

  ##############################################################################
  def _init_logger(self, log_file = None):
    '''
    Function to set up the logger for the package
    '''
    if self.__fileHandler:                                                      # If there is a file handler defined
      self.__fileHandler.flush();                                               # Flush output to handler
      self.__fileHandler.close();                                               # Close the handler
      self.__log.removeHandler(self.__fileHandler);                               # Remove all handlers
      self.__fileHandler = None;                                                # Set fileHandler attribute to None

    if log_file:                                                                # If there was a log file input
      if not os.path.isdir( os.path.dirname( log_file ) ):                      # If the directory the log_file is to be placed in does NOT exist
        dir = os.path.dirname( log_file );                                      # Get directory log file is to be placed in
        if dir != '': os.makedirs( dir );                                       # Create to directory for the log file

      self.__fileHandler = logging.FileHandler( log_file, 'w' );                # Initialize a file handler for the log file
      self.__fileHandler.setLevel(     fileFMT['level']     );                  # Set the logging level for the log file
      self.__fileHandler.setFormatter( fileFMT['formatter'] );                  # Set the log format for the log file
      self.__log.addHandler(self.__fileHandler);                                  # Add the file log handler to the logger
