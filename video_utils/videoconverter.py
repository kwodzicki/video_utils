# Built-in imports
import logging;
import os, re;
from datetime import datetime;


# Parent classes
from .mediainfo import mediainfo;
from .utils.ffmpeg_utils   import cropdetect;
from .utils.subprocManager import subprocManager;

# Subtitle imports
from .subtitles.opensubtitles import opensubtitles;
try:
  from .subtitles.vobsub_extract import vobsub_extract;
except:
  vobsub_extract = None;
try:
  from .subtitles.vobsub_to_srt import vobsub_to_srt;
except:
   vobsub_to_srt = None;
try:
  from .subtitles.ccextract import ccextract;
except:
   ccextract = None;

# Metadata imports
from .videotagger.metadata.getMetaData import getMetaData;
from .videotagger.mp4Tags import mp4Tags;

# Logging formatter
from ._logging import fileFMT;

class videoconverter( mediainfo, subprocManager ):
  '''
  Name:
     videoconverter
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
     os, re
     HandBrakeCLI
  Author and History:
     Kyle R. Wodzicki     Created 24 Jul. 2017
     
     Modified 29 Jul. 2017 by Kyle R. Wodzicki
       Fixed some issues with the file_info function that caused 
       weird things to happen when a TV Show was input. The issue
       was the result of how the IMDbPY class returns data; 
       i.e., I had to use the .keys function to get the keys as
       opposed to an x in y statement with a dictionary. This was
       a simple coding error. Also added some code in the 
       audio_info_parse function to remove duplicate downmixed 
       audio streams that have the same language.
     Modified 02 Sep. 2017 by Kyle R. Wodzicki
       Added the get_mediainfo funcation which switches from multiple
       subprocess calls of the mediainfo CLI to one call with all
       information returned in XML format. XML tree is then parsed
       in the video, audio, and text parsing functions.
     Modified 12 Sep. 2017 by Kyle R. Wodzicki
       Added opensubtitles integration where subtitles are
       downloaded from opensubtitles.org if NONE are present
       in the input file AND/OR download missing languages.
       Furture development could include more robust handling
       of forced (i.e., foreign) subtitles.
       Also added better logging through the logging module.
  '''
  illegal = ['#','%','&','{','}','\\','<','>','*','?','/','$','!',':','@']
  legal   = ['', '', '', '', '', ' ', '', '', '', '', ' ','', '', '', '']
  def __init__(self,
               out_dir       = None,
               log_dir       = None,
               in_place      = False, 
               no_ffmpeg_log = False,
               language      = None, 
               threads       = None, 
               container     = 'mp4',
               cpulimit      = 75, 
               x265          = False,
               remove        = False, 
               vobsub        = False, 
               srt           = False,
               vobsub_delete = False,
               username      = None,
               userpass      = None):
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
                        files for HandBrakeCLI and instead pipe the output to
                        /dev/null
       language      : Comma separated string of ISO 639-2 codes for 
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
    super().__init__();
    self.log = logging.getLogger( __name__ );                                   # Set log to root logger for all instances

    self.container    = container.lower();
    self.mp4tags      = (self.container == 'mp4');

    if vobsub_extract is None:
      self.log.warning('VobSub extraction is DISABLED! Check that mkvextract is installed and in your PATH');
      self.vobsub = False;
    else:
      self.vobsub = vobsub;
    self.srt = srt;
    if self.srt and (not vobsub_to_srt):
      self.log.warning('VobSub2SRT conversion is DISABLED! Check that vobsub2srt is installed and in your PATH')

    self.cpulimit = cpulimit;
    self.threads  = threads;


    # Set up all the easy parameters first
    self.out_dir       = out_dir;
    self.log_dir       = log_dir;
    self.in_place      = in_place;                                              # Set the in_place attribute based on input value
    self.no_ffmpeg_log = no_ffmpeg_log;                                         # Set the no_ffmpeg_log attribute based on the input value
    self.language      = ['eng'] if language is None else language.split(',');  # Set default language to None, i.e., use all languages  
    self.miss_lang     = [];
    self.x265          = x265;      
    self.remove        = remove;       
    self.vobsub_delete = vobsub_delete;
    self.username      = username;
    self.userpass      = userpass;
    
    self.handbrake        = None;
    self.video_info       = None;                                               # Set video_info to None by default
    self.audio_info       = None;                                               # Set audio_info to None by default
    self.text_info        = None;                                               # Set text_info to None by default
    self.subtitle_ltf     = None;                                               # Array to store subtitle language, track, forced (ltf) tuples
    self.vobsub_status    = None;                                               # Set vobsub_status to None by default
    self.srt_status       = None;                                               # Set srt_status to None by default
    self.transcode_status = None;                                               # Set transcode_status to None by default
    self.mp4tags_status   = None;                                               # Set mp4tags_status to None by default
    self.oSubs            = None;                                               # Set attribute of opensubtitles to None
    
    self.IMDb_ID          = None;
    self.metaData         = None;
    self.metaKeys         = None;
    self.ffmpeg_logTime       = None;

    self.v_preset         = 'slow';                                             # Set self.handbrake preset to slow
    self.fmt              = 'utf-8';                                            # Set encoding format
    self.encode           = type( 'hello'.encode(self.fmt) ) is str;            # Determine if text should be encoded; python2 vs python3

    self.__fileHandler    = None;                                               # logging fileHandler 
################################################################################
  def transcode( self, in_file, log_file = None ):
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
                   https://self.handbrake.fr/docs/en/latest/workflow/
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
       in_file  : Full path to MKV file to covert. Make sure that the file names
               follow the following formats for movies and TV shows:
    Outputs:
       Outputs a transcoded video file in the MP4 container and
       subtitle files, based on keywords used. Also returns codes 
       to signal any errors.
    Keywords:
       log_file  : File to write logging information to
    Return codes:
        0 : Everything finished cleanly
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

       Modified 01 Jan. 2017 by Kyle R. Wodzicki
          Changed to a function and added check for multithreading when only 
          half the number of cores are used for CPUs with 4 or more cores.
       Modified 11 Jan. 2017 by Kyle R. Wodzicki
          Added the srt and vobsub_delete keywords. If the srt keyword is set to
          True, then srt files will be created. If the vobsub_delete keyword is 
          ALSO set, then the VobSub files will be deleted after the conversion.
          Setting delete without setting srt does NOTHING. These keys are passed
          to the vobsub_extract function.
       Modified 12 Jan. 2017 by Kyle R. Wodzicki:
          Added the vobsub keyword and changed so that output files are placed
          in their own directory if VobSub or SRT file(s) are to be created,
          i.e., If not subtitle file(s) are created, the movie is output to the 
          top level of the out_dir, else, a folder is created with out_dir that
          matches the title name of the movie from the input file and then
          subtitle file(s) and the MP4 file are saved to that directory.
       Modified 14 Jan. 2017 by Kyle R. Wodzicki
          Updated header information for better clarity.
    '''
    if not self.file_info( in_file ): return False;                             # If there was an issue with the file_info function, just return
    self._init_logger( log_file );                                              # Run method to initialize logging to file
    if self.video_info is None or self.audio_info is None:                      # If there is not video stream found OR no audio stream(s) found
      self.log.critical('No video or no audio, transcode cancelled!');          # Print log message
      self.transcode_status = 10;                                               # Set transcode status
      return False;                                                             # Return
    try:
      start_time = datetime.now();                                              # Set start date
    except:
      start_time = None;                                                        # If datetime CANNOT be imported, set start time to None
    self.transcode_status = None;                                               # Reset transcode status to None
    self.ffmpeg_logTime   = None;
    self.get_subtitles( );                                                      # Extract subtitles

    ############################################################################
    ###    TRANSCODE     TRANSCODE     TRANSCODE     TRANSCODE               ###
    ############################################################################
    out_file = '{}.{}'.format( self.out_file, self.container );                 # Set the output file path
    self.log.info( 'Output file: {}'.format( out_file ) );                      # Print the output file location
    if os.path.exists( out_file ):                                              # IF the output file already exists
      self.log.info('Output file Exists...Skipping!');                          # Print a message
      if self.remove: os.remove( self.in_file );                                # If remove is set, remove the source file
      return False;                                                             # Return to halt the function

    self.ffmpeg_err_file  = self.ffmpeg_log_file + '.err';                      # Set up path self.handbrake error file
    self.ffmpeg_log_file += '.log';                                             # Set up path self.handbrake log file

    self.ffmpeg_cmd  = ['ffmpeg', '-nostdin', '-i', self.in_file]
    self.ffmpeg_cmd.extend( ['-tune', 'zerolatency', '-map_chapters', '0'] );   # Base command for HandBrake
    self.ffmpeg_cmd.extend( ['-f', self.container] );                           # Append container flag
    self.ffmpeg_cmd.extend( ['-threads', str(self.threads)] );                  # Set number of threads to use
    
    cropVals  = cropdetect( self.in_file );                                     # Attempt to detect cropping
    videoKeys = self._videoKeys();                                              # Generator for orderer keys in video_info
    audioKeys = self._audioKeys();                                              # Generator for orderer keys in audio_info
    avOpts    = [True, True];                                                   # Booleans for if all av options have been parsed
    
    while any( avOpts ):                                                        # While any options left
      try:                                                                      # Try to
        key = next( videoKeys );                                                # Get the next video_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[0] = False;                                                      # Set avOpts[0] to False because done with video options
      else:                                                                     # Else, we got a key
        self.ffmpeg_cmd.extend( self.video_info[ key ] );                       # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is '-filter', we also want the next tag, which is codec
          if cropVals is not None:                                              # If cropVals is NOT None
            if len(self.video_info[key]) != 0:                                  # If not an empty list
              self.ffmpeg_cmd[-1] = '{},{}'.format(
                self.ffmpeg_cmd[-1], cropVals
              );                                                                # Add cropping to video filter
            else:                                                               # Else, must add the '-vf' flag
              self.ffmpeg_cmd.extend( ['-vf', cropVals] );                      # Add cropping values
          self.ffmpeg_cmd.extend( self.video_info[ next(videoKeys) ] );         # Add next options to ffmpeg
      try:                                                                      # Try to
        key = next( audioKeys );                                                # Get the next audio_info key
      except:                                                                   # On exception, no more keys to get
        avOpts[1] = False;                                                      # Set avOpts[1] to False because done with audio options
      else:                                                                     # Else, we got a key
        self.ffmpeg_cmd.extend( self.audio_info[ key ] );                       # Add data to the ffmpeg command
        if key == '-filter':                                                    # If the key is -'filter', we also want the next tag, which is codec
          self.ffmpeg_cmd.extend( self.audio_info[ next(audioKeys) ] );         # Add next options to ffmpeg

    self.ffmpeg_cmd.append( out_file );                                         # Append input and output file paths to the self.handbrake command

    print( self.ffmpeg_cmd )
    self.log.info( 'Transcoding file...' )

    if self.no_ffmpeg_log:                                                      # If creation of HandBrake log files is disabled
      self.addProc( self.ffmpeg_cmd );                                          # Start the HandBrakeCLI command and direct all output to /dev/null
    else:                                                                       # Else
      self.addProc( self.ffmpeg_cmd, 
        stdout = self.ffmpeg_log_file, stderr = self.ffmpeg_err_file
      );                                                                        # Start the HandBrakeCLI command and direct all output to /dev/null
    self.run();
    self.transcode_status = self.returncodes[0];                                # Set transcode_status      

    if self.transcode_status == 0:                                              # If the transcode_status IS zero (0)
      self.log.info( 'Transcode SUCCESSFUL!' );                                 # Print information
    else:                                                                       # Else, there was an issue with the transcode
      self.log.critical( 'All transcode attempts failed!!!' );                  # Log critical information
      return False;                                                             # Return False from function, i.e., transcode failed

    if self.metaKeys is None:                                                   # If the metaKeys attribute is None
      self.log.warning('No metadata to write!!!');                              # Print message that not data to write
    elif self.mp4tags:                                                          # If mp4tags attribute is True
      self.mp4tags_status = mp4Tags( out_file, metaData = self.metaData );      # Write information to ONLY movie files
      if self.mp4tags_status == 0:
        self.log.info('MP4 Tags written.');                                     # Print message if status IS 0
      else:
        self.log.warning('MP4 Tags NOT written!!!');                            # Print message if status is NOT zero
    else:
      self.log.warning('MP4 Tagging disabled!!!');                              # If mp4tags attribute is False, print message

    inSize  = os.stat(self.in_file).st_size;                                    # Size of in_file
    outSize = os.stat(out_file).st_size;                                        # Size of out_file
    difSize = inSize - outSize;                                                 # Difference in file size
    change  = 'larger' if outSize > inSize else 'smaller';                      # Is out_file smaller or larger than in file
    msg     = 'The new file is {:4.1f}% {} than the original!';                 # Set up message to be printed
    self.log.info( msg.format(abs(difSize)/inSize*100, change) );               # Print the message about the size
          
    if self.remove:                                                             # If remove is set
      self.log.info( 'Removing the input file...' );                            # Log some information
      os.remove( self.in_file );                                                # Delete the input file if remove is true
    if start_time is not None:                                                  # If the start_time is NOT none, then print the computation time
      self.log.info('Duration: {}'.format(datetime.now()-start_time)+'');       # Print compute time
    self.handbrake = None;
    return out_file;                                                            # Return output file from function, i.e., transcode was success
  ##############################################################################
  def file_info( self, in_file ):
    '''
    Function to extract some information from the input file name and set up
    some output file variables.
    '''
    self.log.info('Setting up some file information...');

    self.mp4tags = (self.container == 'mp4');
    
    # Set up file/directory information
    self.in_file  = in_file if os.path.exists( in_file ) else None;             # Set the in_file attribute for the class to the file input IF it exists, else, set the in_file to None
    if self.in_file is None:                                                    # IF the input file does NOT exist
      self.log.info( 'File requested does NOT exist. Exitting...' );
      self.log.info( '   ' + in_file );
      return False;                                                             # Return, which stops the program
    self.log.info( 'Input file: '   + self.in_file );                           # Print out the path to the input file
    if self.out_dir is None: self.out_dir = os.path.dirname(in_file);           # Set the output directory based on input file OR on output directory IF input
    if self.log_dir is None: self.log_dir = os.path.join(self.out_dir, 'logs'); # Set log_dir to input directory if NOT set on init, else set to log_dir value
    self.tv_dir  = os.path.join( self.out_dir, 'TV Shows');                     # Generate output path for TV Shows
    self.mov_dir = os.path.join( self.out_dir, 'Movies');                       # Generate output path for Movies

    # Getting information from IMDb.com
    self.IMDb_ID  = self.in_file.split('.')[-2];
    self.metaData = None;                                                       # Default metaData to None;
    self.metaKeys = None;                                                       # Default metaKeys to None;
    if self.IMDb_ID[:2] == 'tt' and self.mp4tags:
      self.metaData = getMetaData( self.IMDb_ID );
      self.metaKeys = self.metaData.keys();                                     # Get keys from the metaData information
      if len(self.metaKeys) == 0:                                               # If no keys returned
        self.log.warning('Failed to download metadata for file!!!');
        self.log.warning( 'MP4 tagging is disabled!!!' );                       # Print message that the mp4 tagging is disabled                
        self.mp4tags = False;                                                   # Disable mp4 tagging
    elif self.mp4tags:
      self.log.warning('IMDb ID not in file name!');
    else:
      self.log.info('MP4 tagging is disabled.');

#   self.new_out_dir = self.out_dir;                                            # Reset output directory to original directory
    self.file_base  = os.path.basename(self.in_file);                           # Get the base name of the file
    file_split      = self.file_base.split('.')[:-1];                           # Split base name on period and ignore extension 
    self.title      = file_split[0];                                            # Get title of movie or TV show
    self.season_dir = None;
    self.out_file   = None;
    ### Determine if the file is an episode of a TV show, or a movie. TV episodes
    ### files begin with the patter 'sXXeXX - ', where XX is a number for the
    ### seasons and episode
    re_test = re.match(re.compile(r's\d{2}e\d{2} - '), self.file_base);         # Test for if the file name starts with a specific pattern, then it is an episode
    if self.metaKeys is None:                                                   # If the metaKeys attribute is None
      se_test = False;                                                          # Then the se_test is False
    else:                                                                       # Else, the metaKeys attribute is not None
      se_test = ('series title' in self.metaKeys or \
                  'seriesName'  in self.metaKeys) and \
                  'season'      in self.metaKeys and \
                  'episode'     in self.metaKeys;                               # Test if there is a series title AND season AND episode tag in the imdb information
    if re_test or se_test:                                                      # If either the pattern test (re_test) OR the IMDb information test (se_test) is true, assume it's an episode
      self.is_episode  = True;                                                  # Set is_episode to True
      self.year        = None;
      self.new_out_dir = self.tv_dir;                                           # Reset output directory to original directory
      if file_split[-1][:2] == 'tt' or file_split[-1][:2] == '':                # If the first two characters of the last element of the split file name are 'tt' OR it is an empty string
        self.file_name = file_split[:-1];                                       # Join file base name using periods EXCLUDING the IMDB id
      else:                                                                     # If the first two characters of the last element of the split file name are NOT 'tt'
        self.file_name = file_split;                                            # Join file base name using periods
      if se_test:
        try:                                                                    # Try to use the seriesName tag from the metaData
          st = self.metaData['seriesName'];                                     # Set Series directory name
        except:                                                                 # If this tag does NOT exist, use the series title tag
          st = self.metaData['series title'];                                   # Set Series directory name
        if self.encode: st = st.encode(self.fmt);                               # Encode if python2
        for n in range( len(self.illegal) ):                                    # Iterate over all illegal characters
          if self.illegal[n] in st:                                             # If an illegal character is found in the string
              st = st.replace(self.illegal[n], self.legal[n]);                    # Replace the character with a legal character
        self.new_out_dir = os.path.join(self.new_out_dir, st);                  # Set Series directory name
        sn = 'Season {:02d}'.format(self.metaData['season']);                   # Set up name for Season Directory
        self.new_out_dir = os.path.join(self.new_out_dir, sn);                  # Add the season directory to the output directory
        if re_test is False:                                                    # If the re_test is False
          self.file_name[0] = 's{:02d}e{:02d} - {}'.format(
            self.metaData['season'], self.metaData['episode'], self.file_name[0]
          )
    else:                                                                       # Else the file is a movie
      self.is_episode  = False;                                                 # Set is_episode to False
      self.new_out_dir = self.mov_dir;                                          # Reset output directory to original directory
      self.file_name   = file_split[:-2];                                       # Join file base name using periods EXCLUDING the year and IMDB id
      self.year        = file_split[-2];                                        # Get movie year and IMDB id from the file name; the second last and last elements, respectively
      if self.year != '': self.title = '{} - {}'.format(self.title, self.year); # Append movie year to title variable

    self.log.info('Getting video, audio, information...');                      # If verbose is set, print some output

    self.video_info = self.get_video_info( x265 = self.x265 );                  # Get and parse video information from the file
    if self.video_info is None: return;                    
    self.audio_info = self.get_audio_info( self.language );                     # Get and parse audio information from the file
    if self.audio_info is None: return;               

    ### Set up output file path and log file path. NO FILE EXTENSIONS USED HERE!!!
    if self.is_episode:                                                         # If the file is an episode, set up file name with video info, and audio info
        self.file_name += [ self.video_info['file_info'], 
                            self.audio_info['file_info'] ];
    else:                                                                       # Else, file is a movie, set up file name with year, video info, audio info, and IMDB ID
        self.file_name += [ self.year,
                            self.video_info['file_info'],
                            self.audio_info['file_info'] ];
    if self.IMDb_ID is not None: self.file_name += [self.IMDb_ID];              # Append the IMDB ID to the file name if it is NOT None.

    self.file_name = '.'.join(self.file_name)
    self.log.debug( 'File name: {}'.format( self.file_name) )
    # Generate file paths for the output file and the ffmpeg log files
    self.ffmpeg_log_file = os.path.join(self.log_dir, self.file_name);          # Set the self.handbrake log file path without extension
    if self.in_place: self.new_out_dir = self.out_dir;                          # If the in_place keyword was set, then overwrite the new_out_dir with the input files directory path
    self.out_file    = [self.new_out_dir, '', self.file_name];                  # Set the output file path without extension
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

    # Extract VobSub(s) and convert to SRT based on keywords
    def opensubs_all():
      '''Local function to download all subtitles from opensubtitles'''
      self.log.info('Attempting opensubtitles.org search...');                  # Logging information
      self.oSubs = opensubtitles('', imdb = self.IMDb_ID, 
                          lang     = ','.join(self.language), 
                          username = self.username, 
                          userpass = self.userpass);                            # Initialize opensubtitles instance
      self.oSubs.login();                                                       # Login to the opensubtitles.org API
      self.oSubs.searchSubs();                                                  # Search for subtitles
      if self.oSubs.subs is None:                                               # If no subtitles are found
        self._join_out_file( );                                                 # Combine out_file path list into single path with NO movie/episode directory and create directories
      else:                                                                     # Else, some subtitles were found
        found = 0;                                                              # Initialize found to zero (0)
        for lang in self.oSubs.subs:                                            # Iterate over all languages in the sub titles dictionary
          if self.oSubs.subs[lang] is not None: found+=1;                       # If one of the keys under that language is NOT None, then increment found
        if found > 0:                                                           # If found is greater than zero (0), then subtitles were found
          self._join_out_file( self.title );                                    # Combine out_file path list into single path with movie/episode directory and create directories
          self.oSubs.file = self.out_file;                                      # Set movie/episode file path in opensubtitles class so that subtitles have same naming as movie/episode
          self.oSubs.saveSRT();                                                 # Download the subtitles
        else:                                                                   # Else, no subtitles were found
          self._join_out_file( );                                               # Combine out_file path list into single path with NO movie/episode directory and create directories
      self.oSubs.logout();                                                      # Log out of the opensubtitles.org API

    
    ######
    if (not self.vobsub) and (not self.srt):                                    # If both vobsub AND srt are False
      self._join_out_file( );                                                   # Combine out_file path list into single path with NO movie/episode directory and create directories
      return;                                                                   # Return from the method

    self.text_info = self.get_text_info( self.language );                       # Get and parse text information from the file
    if self.text_info is None:                                                  # If there is not text information, then we cannot extract anything
      if self.srt:                                                              # If srt subtitles are requested
        opensubs_all();                                                         # Run local function
    elif self.vobsub or self.srt:                                               # Else, if vobsub or srt is set
      if self.format == "MPEG-TS":                                              # If the input file format is MPEG-TS, then must use CCExtractor
        if ccextract:                                                           # If the ccextract function import successfully
          self._join_out_file( self.title );                                    # Build output directory with directory for episode/movie that will contain video and subtitle files
          status = ccextract( self.in_file, self.out_file, self.text_info );    # Run ccextractor
        else:
          self.log.warning('ccextractor failed to import, falling back to opensubtitles.org');
          opensubs_all();                                                       # Run local function
      else:                                                                     # Assume other type of file
        if not vobsub_extract:                                                  # If the vobsub_extract function failed to import
          self.log.warning('vobsub extraction not possible');
          if self.srt:                                                          # If the srt flag is set
            self.log.info('Falling back to opensubtitles.org for SRT files');
            opensubs_all();                                                     # Run local function
        else:
          self._join_out_file( self.title );                                    # Combine out_file path list into single path with movie/episode directory and create directories
          self.vobsub_status = vobsub_extract( 
            self.in_file, self.out_file, self.text_info, 
            vobsub = self.vobsub,
            srt    = self.srt );                                                # Extract VobSub(s) from the input file and convert to SRT file(s).
          if (self.vobsub_status < 2) and self.srt:                             # If there weren't nay major errors in the vobsub extraction
            if not vobsub_to_srt:                                               # If SRT output is enabled AND vobsub_to_srt imported correctly
              self.log.warning('vobsub2srt conversion not possible. Leaving vobsub files.');
            else:
              self.srt_status, self.text_info = vobsub_to_srt(   
                self.out_file, self.text_info,   
                vobsub_delete = self.vobsub_delete,   
                cpulimit      = self.cpulimit,   
                threads       = self.threads );                                 # Convert vobsub to SRT files

              failed = [i for i in self.text_info if i['srt'] is False];        # Check for missing srt files
              if len(failed) > 0:                                               # If missing files found
                self._join_out_file( self.title );                              # Combine out_file path list into single path with movie/episode directory and create directories
                self.log.info('Attempting opensubtitles.org search...');        # Logging information
                self.oSubs = opensubtitles(self.out_file,   
                                imdb     = self.IMDb_ID,   
                                username = self.username,   
                                userpass = self.userpass);                      # Initialize opensubtitles instance
                self.oSubs.login();                                             # Log into opensubtitles
                for i in range(len(self.text_info)):                            # Iterate over all entries in text_info
                  if self.text_info[i]['srt']: continue;                        # If the srt file exists, skip
                  self.oSubs.lang       = self.text_info[i]['lang3'];           # Set the language for the subtitle search
                  self.oSubs.track_num  = self.text_info[i]['track'];           # Set the track number for the subtitle search
                  self.oSubs.get_forced = self.text_info[i]['forced'];          # Set the forced flag for the subtitle search
                  self.oSubs.searchSubs();                                      # Search for subtitles
                  self.oSubs.saveSRT();                                         # Save subtitles, note that this may not actually work if noting was found
                  tmpOut = self.out_file + self.text_info[i]['ext'] + '.srt';   # Temporary output file for check
                  if os.path.isfile(tmpOut): self.text_info[i]['srt'] = True;   # If the subtitle file exists, update the srt presence flag.
                self.oSubs.logout();                                            # Log out to of opensubtitles
    else:                                                                       # Else, not subtitle candidates were returned
      self.log.debug('No subtitle options set');                                # Log some information
      self._join_out_file( );                                                   # Combine out_file path list into single path with NO movie/episode directory and create directories
##############################################################################
  def _join_out_file(self, title = None ):
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
       title : Title to place into the second element of the.
                DEFAULT is no title.
    '''
    if isinstance(self.out_file, list):                                         # If the out_file is a list instance
      self.log.debug( 'Joining output file path' )
      if title is not None: self.out_file[1] = title;                           # If title is set, place in second element
      self.out_file    = os.path.join( *self.out_file );
      self.new_out_dir = os.path.dirname( self.out_file );
    self._create_dirs();                                                        # Create all output directories
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
  def _create_dirs( self ):
    self.log.debug( 'Creating output directories' )
    if not os.path.isdir( self.out_dir     ): os.makedirs( self.out_dir );      # Check if the output directory exists, if it does NOT, create the directory
    if not os.path.isdir( self.new_out_dir ): os.makedirs( self.new_out_dir );  # Check if the new output directory exists, if it does NOT, create the directory
    if not self.no_ffmpeg_log:                                                      # If HandBrake log files are NOT disabled
      if not os.path.isdir( self.log_dir     ): os.makedirs( self.log_dir );    # Create log directory if it does NOT exist
  ##############################################################################
  def _init_logger(self, log_file = None):
    '''
    Function to set up the logger for the package
    '''
    if self.__fileHandler:                                                      # If there is a file handler defined
      self.__fileHandler.flush();                                               # Flush output to handler
      self.__fileHandler.close();                                               # Close the handler
      self.log.removeHandler(self.__fileHandler);                               # Remove all handlers
      self.__fileHandler = None;                                                # Set fileHandler attribute to None

    if log_file:                                                                # If there was a log file input
      if not os.path.isdir( os.path.dirname( log_file ) ):                      # If the directory the log_file is to be placed in does NOT exist
        dir = os.path.dirname( log_file );                                      # Get directory log file is to be placed in
        if dir != '': os.makedirs( dir );                                       # Create to directory for the log file

      self.__fileHandler = logging.FileHandler( log_file, 'w' );                # Initialize a file handler for the log file
      self.__fileHandler.setLevel(     fileFMT['level']     );                  # Set the logging level for the log file
      self.__fileHandler.setFormatter( fileFMT['formatter'] );                  # Set the log format for the log file
      self.log.addHandler(self.__fileHandler);                                  # Add the file log handler to the logger