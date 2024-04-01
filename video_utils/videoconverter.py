"""
For converting/transcoding video files

The class defined here is the 'main' class of the entire package,
transcoding files, tagging the output, extracting/converting subtitles.

"""

import logging
import os
import re
import time
from datetime import datetime

from . import __name__ as __pkg_name__
from . import __version__ as __pkg_version__
from . import POPENPOOL

from .mediainfo import MediaInfo
from .comremove import ComRemove
from .utils import _sigintEvent, _sigtermEvent, isRunning, thread_check
from .utils import hdr_utils
from .utils.handlers import RotatingFile
from .utils.ffmpeg_utils   import cropdetect, extract_hevc, FFmpegProgress

from .subtitles import opensubtitles
from .subtitles import ccextract
from .subtitles import subtitle_extract
from .subtitles import sub_to_srt

from .videotagger import getMetaData

from .config import get_comskip_log, get_transcode_log, fileFMT

# Matching pattern for season/episode files; lower/upper case 's' followed by
# 2 or more digits followed by upper/lower 'e' followed by 2 or more digits
# followed by ' - ' string
SE_PAT = re.compile( r'[sS](\d{2,})[eE](\d{2,})' )

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
            **kwargs,
        ):
        """
        Keyword arguments:
            outdir   (str): Path to output directory. Optional input. 
                DEFAULT: Place output file(s) in source directory.
            logdir  (str): Path to log file directory. Optional input.
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
        self.__log = logging.getLogger( __name__ )
        self.container = container
        self.srt       = srt
        self.cpulimit  = cpulimit if isinstance(cpulimit, int) else 75
        self.threads   = thread_check( threads )

        self.subtitles = False
        if subtitle_extract.CLI is None:
            self.__log.warning(
                "Subtitlte extraction is DISABLED! Check that mkvextract is "
                "installed and in your PATH"
            )
        else:
            self.subtitles = subtitles

        # Set up all the easy parameters first
        self.outdir        = kwargs.get('outdir', None)
        self.logdir        = kwargs.get('logdir', None)
        self.in_place      = in_place
        self.comdetect     = comdetect

        self.miss_lang     = []
        self.x265          = x265
        self.remove        = remove
        self.sub_delete_source = sub_delete_source
        self.infile = None
        self.outfile = None
        self.hevc_file = None
        self.others_file = None
        self.dolby_vision_file = None
        self.hdr10plus_file = None
        self._prog_file = None

        if transcode_log is None:
            self.transcode_log = get_transcode_log(
                self.__class__.__name__,
                logdir=self.logdir,
            )
        else:
            self.transcode_log = transcode_log

        if comskip_log is None:
            self.comskip_log = get_comskip_log(
                self.__class__.__name__,
                logdir=self.logdir,
            )
        else:
            self.comskip_log = comskip_log

        if lang:
            self.lang = lang if isinstance(lang, (tuple,list,)) else [lang]
        if len(self.lang) == 0:
            self.lang = ["eng"]

        self.chapter_file     = None
        self.video_info       = None
        self.audio_info       = None
        self.text_info        = None
        self.subtitle_ltf     = None
        self.sub_status       = None
        self.srt_status       = None
        self.transcode_status = None
        self.tagging_status   = None

        self.metadata         = None

        self.tagging          = False

        self.v_preset         = 'slow'

        self._start_time = None
        self._created_files   = None
        self.__file_handler   = None

    @property
    def outdir(self):
        """Output directory for transcoded and extra files"""

        return self.__outdir

    @outdir.setter
    def outdir(self, val):
        if isinstance(val, str):
            os.makedirs( val, exist_ok=True )
            self.__outdir = val
        else:
            self.__outdir = os.path.expanduser('~')

    @property
    def container(self):
        """Video container; e.g., mp4 or mkv"""

        return self.__container

    @container.setter
    def container(self, val):
        self.__container = val.lower()

    def transcode( self, infile,
          log_file  = None,
          metadata  = None,
          chapters  = False,
          **kwargs
    ):
        """
        Actually transcode a file

        Designed mainly with MKV file produced by MakeMKV in mind, this method
        acts to setup options to be fed into the ffmpeg CLI to transcode
        the file. A non-exhaustive list of options chosen are

            - Set quality rate factor for x264/x265 based on video resolution
                and the recommended settings found here:
                https://handbrake.fr/docs/en/latest/workflow/adjust-quality.html
            - Used variable frame rate, which 'preserves the source timing
            - Uses x264 codec for all video 1080P or lower, uses x265 for
                video greater than 1080P, i.e., 4K content.
            - Copy any audio streams with more than two (2) channels 
            - Extract VobSub subtitle file(s) from the mkv file.
            - Convert VobSub subtitles to SRT files.

        This program will accept both movies and TV episodes, however,
        movies and TV episodes must follow specific naming conventions 
        as specified under in the 'File Naming' section below.

        Arguments:
            infile (str): Full path to MKV file to covert. Make sure that the file names
                follow the following formats for movies and TV shows:

        Keyword arguments:
            log_file (str): File to write logging information to
            metadata (dict): Pass in result from previous call to getMetaData
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

        if _sigtermEvent.is_set():
            return False

        # Clear the 'global' kill event that may have been set by SIGINT
        _sigintEvent.clear()

        # If there was an issue with the file_info function, just return
        if not self.file_info( infile, metadata = metadata ):
            return False

        # Run method to initialize logging to file
        self._init_logger( log_file )

        # If there is not video stream found OR no audio stream(s) found
        if self.video_info is None or self.audio_info is None:
            self.__log.critical("No video or no audio, transcode cancelled!")
            self.transcode_status = 10
            return False

        self._start_time = datetime.now()
        self.chapter_file = None
        self.transcode_status = None
        self._created_files = []

        # Set the output file path and file name for inprogress conversion;
        # maybe a previous conversion was cancelled
        if self.is_hdr:
            self.__log.info("HDR content detected; forcing MKV file")
            outfile = f"{self.outfile}.mkv"
        else:
            outfile = f"{self.outfile}.{self.container}"

        self.__log.info( "Output file: %s", outfile )

        self._prog_file = self._check_outfile_exists( outfile )
        if self._prog_file is None:
            return False

        # Touch inprogress file, acts as a kind of lock
        with open(self._prog_file, mode='a', encoding='ascii') as _:
            pass

        # If the comdetect keywords is set; if key not given use class-wide setting
        if not self._comdetect(chapters, **kwargs):
            return None

        self.__log.info( "Transcoding file..." )

        self.hdr_metadata()

        # Append outfile to list of created files
        self._created_files.append(outfile)

        # Generate ffmpeg command list
        ffmpeg_cmd = self._ffmpeg_command(self.hevc_file or outfile)

        # Initialize ffmpeg progress class
        prog = FFmpegProgress(nintervals=10)
        stderr = RotatingFile(
            self.transcode_log,
            callback=prog.progress,
        )

        try:
            proc = POPENPOOL.popen_async(
                ffmpeg_cmd,
                threads=self.threads,
                stderr=stderr,
                universal_newlines=True,
            )
        except:
            proc = None
        else:
            proc.wait()

        try:
            self.transcode_status = proc.returncode
        except:
            self.transcode_status = -1

        outfile = self.transcode_postprocess(outfile)

        # Clean up chapter file
        self.chapter_file = self._clean_up(self.chapter_file)

        if isRunning():
            self._prog_file = self._clean_up(self._prog_file)

        return outfile

    def transcode_postprocess(self, outfile):
        """
        To handle result of transcoding

        Based on the result of the FFmpeg subprocess, handle what happens
        to output and intermediate files.

        Note that HDR videos are a special case where the FFmpeg actually
        outputs 2 files: one with just video and one with everything else.
        These files are then joined together using mkvmerge to create final
        output file.

        Arguments:
            outfile (str): Name of the output file created by FFmpeg

        Returns:
            str | None : If everything went as planned, then the path to
                the output file is returned. On failure, None is returned.

        """

        # If the transcode failed
        if self.transcode_status != 0:
            # If the application is NOT running
            if not self.isRunning():
                return outfile

            # If made here, then app is sitll running, so other issue
            self.__log.critical(
                "All transcode attempts failed : %s. Removing all created files.",
                self.infile,
            )
            self._created_files = self._clean_up(*self._created_files)
            return None

        self.__log.info( "Transcode SUCCESSFUL!" )
        
        if self.hevc_file:
            self.hevc_file = hdr_utils.ingect_hdr(
                self.hevc_file,
                self.dolby_vision_file,
                self.hdr10plus_file,
            )

            cmd = ["mkvmerge", "-o", outfile, self.hevc_file, self.others_file]
            proc = POPENPOOL.popen_async(cmd)
            proc.wait()

            if proc.returncode != 0:
                self.__log.error('Issue running mkvmerge! Removing all created files')
                self._created_files = self._clean_up(*self._created_files)
                return None

        if self.metadata:
            self.metadata.write_tags(outfile)

        self.get_subtitles()
        self._compression_ratio(outfile)
        self._remove_source()

        self.__log.info(
            "Duration: %s",
            datetime.now()-self._start_time
        )

        return outfile

    def hdr_metadata(self):
        """
        To get HDR metdata from input file

        We check to see if the file has any HDR information.
        If it does, then we extract the HEVC video stream so that we can
        try to get any Dolby Vision and/or HDR10+ metadata from the files.
        We also have to re-evalute that video encoding settings based on
        HDR color metadata for the video and (if any) DV/HDR10+ data.

        In the case of HDR content, the FFmpeg transcode command that is run
        actually creates two (2) files; one with the transcoded video stream
        and another with audio, chapter, etc. information. This is done so
        that any Dolby Vision/HDR10+ metadata can be injected back into the
        re-encoded HEVC stream.

        """

        if not self.is_hdr:
            # Possibly redudant, but ensure all are set to None
            self.hevc_file = None
            self.others_file = None
            self.dolby_vision_file = None
            self.hdr10plus_file = None
            
            return

        # Use self.outfile as has not extension yet
        self.__log.info("Attempting to get HDR metadat; extracting HEVC stream")
        self.hevc_file = extract_hevc(self.infile, self.outfile)

        if self.hevc_file is None:
            return
        
        # Could check the is_dolby_vision and is_hdr10plus properties here...
        self.dolby_vision_file = hdr_utils.dovi_extract(self.hevc_file)
        self.hdr10plus_file = hdr_utils.hdr10plus_extract(self.hevc_file)

        if self.dolby_vision_file is None and self.hdr10plus_file is None:
            return

        self.__log.info("Rebuilding video_info with HDR metadata")
        self.video_info = self.get_video_info(
            x265=self.x265,
            dolby_vision_file=self.dolby_vision_file,
            hdr10plus_file=self.hdr10plus_file,
        )

        self.others_file = f"{self.outfile}.mka"

    def file_info( self, infile, metadata = None):
        """
        Extract some information from the input file name

        Extracts information from the input file name and sets up some
        output file variables.
        
        Arguments:
            infile (str): Full path of file

        Keyword arguments:
            metadata (dict): Metadata for file; if none entered, will
                attempt to get metadata from TMDb or TVDb

        Returns:
            None

        """

        if not isRunning():
            return False

        self.__log.info("Setting up some file information...")

        # Set up file/directory information
        # Set the infile attribute for the class to the file input IF it
        # exists, else, set the infile to None
        self.infile  = infile if os.path.exists( infile ) else None
        if self.infile is None:
            self.__log.info("File requested does NOT exist. Exitting..." )
            self.__log.info("   %s", infile )
            return False

        self.__log.info( "Input file: %s", self.infile )
        self.__log.info( "Getting video, audio, information...")

        # Get and parse video information from the file
        self.video_info = self.get_video_info( x265 = self.x265 )
        if self.video_info is None:
            return None
        # Get and parse audio information from the file
        self.audio_info = self.get_audio_info( self.lang )
        if self.audio_info is None:
            return None

        # Set outdir to dirname of infile if in_place is set
        outdir = os.path.dirname(self.infile) if self.in_place else self.outdir

        # Try to get metadata
        self.metadata = getMetaData(self.infile) if metadata is None else metadata

        # If metadata is valid
        if self.metadata:
            self.metadata.addComment(
                f"File converted and tagged using {__pkg_name__} version {__pkg_version__}"
            )
            outfile = self.metadata.get_basename()
            if not self.in_place:
                # Set outdir based on self.outdir and get_dirname() method
                outdir = self.metadata.get_dirname( root = self.outdir )
        else:
            # Set outfile to infile basename without extension
            outfile = os.path.splitext( os.path.basename( self.infile ) )[0]

        os.makedirs( outdir, exist_ok=True )

        # Create full path to output file; no extension
        outfile      = os.path.join( outdir, outfile )
        extra_info   = self.video_info["file_info"] + self.audio_info["file_info"]
        self.outfile = '.'.join( [outfile] + extra_info )
        return True

    def get_subtitles( self, *args, **kwargs ):
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
            Updates sub_status and creates/updates list of VobSubs that
                failed vobsub2srt conversion.

        Return codes:
            - 0 : Completed successfully.
            - 1 : VobSub(s) and SRT(s) already exist
            - 2 : Error extracting VobSub(s).
            - 3 : VobSub(s) are still being extracted.

        Dependencies:
            - mkvextract : A CLI for extracting streams for an MKV file.
            - vobsub2srt : A CLI for converting VobSub images to SRT

        """

        if not isRunning():
            return

        # If both subtitles AND srt are False
        if (not self.subtitles) and (not self.srt):
            return

        # Get and parse text information from the file
        self.text_info = self.get_text_info( self.lang )
        if self.text_info is None:
            return

        # If the input file format is MPEG-TS, then must use CCExtractor
        if self.format == "MPEG-TS":
            if not ccextract.CLI:
                self.__log.warning("ccextractor failed to import, nothing to do")
                return

            srt_files = ccextract.ccextract(
                self.infile, self.outfile, self.text_info
            )

            self._created_files.extend( srt_files )

            return

        if not subtitle_extract.CLI:
            self.__log.warning("subtitle extraction not possible")
            return

        self.sub_status, sub_files = subtitle_extract.subtitle_extract(
            self.infile,
            self.outfile,
            self.text_info,
            srt = self.srt,
        )
        # Add list of files created by subtitles_extract to list of created files
        self._created_files.extend( sub_files )
        # If there were major errors in the subtitles extraction
        if self.sub_status > 1:
            return

        if self.srt:
            srt_files = sub_to_srt(
                self.outfile, self.text_info,
                delete_soure = self.sub_delete_source,
                cpulimit     = self.cpulimit,
                threads      = self.threads,
            )

            self._created_files.extend( srt_files )

    def _clean_up(self, *args):
        """Method to delete arbitrary number of files, catching exceptions"""

        to_clean = [
            *args,
            self.hevc_file,
            self.others_file,
            self.dolby_vision_file,
            self.hdr10plus_file,
        ]
        for arg in to_clean:
            if not isinstance(arg, str) or not os.path.isfile(arg):
                continue
            try:
                os.remove( arg )
            except Exception as err:
                self.__log.warning(
                    "Failed to delete file: %s ---> %s",
                    arg,
                    err,
                )

    def _ffmpeg_command(self, video_file):
        """
        A method to generate full ffmpeg command list

        Arguments:
            video_file (str): Full output file path that ffmpeg will create

        Keyword arguments:
            None

        Returns:
            list: Full ffmpeg command to run

        """

        cmd = self._ffmpeg_base( )

        # Attempt to detect cropping
        crop_vals  = cropdetect( self.infile, threads = self.threads )
        video_keys = self._video_keys()
        audio_keys = self._audio_keys()
        # Booleans for if all av options have been parsed
        #av_opts    = [True, True]

        for key in video_keys:
            cmd.extend(self.video_info[key])
            if key == '-filter':
               if crop_vals is not None:
                   if len(self.video_info[key]) != 0:
                       # Add cropping to video filter
                       cmd[-1] = f"{cmd[-1]},{crop_vals}"
                   else:
                       # Add cropping values
                       cmd.extend( ["-vf", crop_vals] )
               # Add next options to ffmpeg
               cmd.extend(self.video_info[next(video_keys)])

        if self.others_file is not None:
            cmd.append(video_file)

        for key in audio_keys:
            cmd.extend(self.audio_info[key])
            if key == '-filter':
                cmd.extend(self.audio_info[next(audio_keys)])

        if isinstance(self.chapter_file, str) and os.path.isfile(self.chapter_file):
            cmd.extend(["-map_metadata", "1"])
        else:
            cmd.extend(["-map_chapters", "0"])
 
        if self.others_file is not None:
            cmd.append(self.others_file)
        else:
            cmd.append(video_file)

        return cmd

    def _ffmpeg_base(
            self,
            strict='experimental',
            max_muxing_queue_size=4096,
        ):
        """
        A method to generate basic ffmpeg command

        Arguments:
            None

        Keywords arguments:
            strict (str): Specify how strictly to follow the standards.
                Possible values:
                    - ‘very’ : strictly conform to an older more strict
                        version of the spec or reference software 
                    - ‘strict’ : strictly conform to all the things in the
                        spec no matter what consequences 
                    - ‘normal’
                    - ‘unofficial’ : allow unofficial extensions 
                    - ‘experimental’ : allow non standardized experimental
                        things, experimental (unfinished/work in progress/not
                        well tested) decoders and encoders. Note: experimental
                        decoders can pose a security risk, do not use this for
                        decoding untrusted input. 
            max_muxing_queue_size (int): Should not have to change;
                see https://trac.ffmpeg.org/ticket/6375

        Returns:
            List containing base ffmpeg command for converting

        """

        if isinstance(self.chapter_file, str) and os.path.isfile(self.chapter_file):
            self.__log.info("Adding chapters from file : %s", self.chapter_file )
            chapters = ["-i", self.chapter_file]
        else:
            chapters = []

        if self.is_hdr:
            fmt = ["-f", "hevc", "-bsf:v", "hevc_mp4toannexb"]
        else:
            fmt = ["-f", self.container]

        return [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i", self.infile,
            *chapters,
            "-tune", "zerolatency",
            *fmt,
            "-threads", str(self.threads),
            "-strict", strict,
            "-max_muxing_queue_size", str(max_muxing_queue_size),
        ]

    def _check_outfile_exists(self, outfile):
        """
        Check if output file exists

        Will run some checks to see if output file exists.
        The main check is the existence of the output file. If the
        output file DOES exist, check that a .inprogres file exists.
        if that file does NOT exist, then assume the output file actually
        exists (i.e., is not currently being created). If the .inprogress
        file exists AND the output file size is changing, then assume another
        instance is currently converting. Otherwise, asssume old/failed 
        conversion and delete output file.

        Arguments:
            outfile (str) : Path to output file

        Returns:
            None, str : Path to .inprogress file if output file is bogus,
                else None.

        """

        prog_file = self._inprogress_file( outfile )
        if os.path.exists( outfile ):
            # If the inprogress file does NOT exists, then conversion
            # completed in previous attempt
            if not os.path.exists( prog_file ):
                self.__log.info("Output file Exists...Skipping!")
                self.transcode_status = 1
                if self.remove:
                    self._clean_up( self.infile )
                self.chapter_file = self._clean_up( self.chapter_file )
                return None
            if self._being_converted( outfile ):
                self.__log.info("It seems another process is creating the output file")
                return None

            self.__log.info(
                "It looks like there was a previous attempt to transcode "
                "the file. Re-attempting transcode..."
            )
            self._clean_up( outfile )
        return prog_file

    def _comdetect(self, chapters, **kwargs):
        """
        Try to detect commercials

        Attempt to detect commecials and mark with chapters in file or
        remove the commercial sections completely.

        Arguments:
            chapters (bool): Set if commericals are to be marked with chapters.
        
        Keyword arguments:
            comdetect (bool): Set to remove/mark commercial segments in file
            **kwargs : All other ignored

        Returns:
            bool : True if commerical detection disabled/succes,
                False othewise

        """

        if not kwargs.get('comdetect', self.comdetect):
            return True

        name = ''
        if self.metadata is not None:
            name = (
                str(self.metadata.Series)
                if self.metadata.isEpisode else
                str(self.metadata)
            )
        status = self.remove_commercials(
            self.infile,
            chapters = chapters,
            name = name

        )
        # If string instance, then is path to chapter file
        if isinstance(status, str):
            # Set chatper file attribute to status; i.e., path to chapter file
            self.chapter_file = status
        elif not status:
            self.transcode_status = 5
            if isRunning():
                self.__log.error( "Error cutting commercials, assuming bad file..." )
                self._prog_file = self._clean_up( self._prog_file )
            return False

        return True

    def _compression_ratio(self, outfile):
        """
        Calculate and log outfile compression ratio

        Arguments:
            outfile (str) : Path to output file

        Returns:
            None.

        """

        in_size  = os.stat(self.infile).st_size# Size of infile
        out_size = os.stat(outfile).st_size# Size of out_file
        self.__log.info(
            "The new file is %4.1f%% %s than the original",
            abs(in_size-out_size)/in_size*100,
            'larger' if out_size > in_size else 'smaller',
        )

    def _remove_source(self):
        """To remove infile"""

        if self.remove:
            self.__log.info( "Removing the input file..." )
            self._clean_up( self.infile )


    def _video_keys(self):
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

    def _audio_keys(self):
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

    def _inprogress_file(self, outfile):
        """
        Build path to .inprogress file

        Arguments:
            outfile (str) : Path to output file to create .inprogress file for

        Returns:
            str : Path to .inprogress file

        """

        fdir, fbase = os.path.split( outfile )
        return os.path.join( fdir, f".{fbase}.inprogress" )

    def _being_converted( self, fpath ):
        """Method to check if file is currently being convert"""

        fsize = os.path.getsize( fpath )
        time.sleep(0.5)
        return fsize != os.path.getsize(fpath)# Check that size of file has changed

    def _init_logger(self, log_file = None):
        """Function to set up the logger for the package"""

        # If there is a file handler defined
        if self.__file_handler:
            self.__file_handler.flush()
            self.__file_handler.close()
            self.__log.removeHandler(self.__file_handler)
            self.__file_handler = None

        if not isinstance(log_file, str):
            return

        os.makedirs(
            os.path.dirname( log_file ),
            exist_ok = True,
         )

        self.__file_handler = logging.FileHandler( log_file, 'w' )
        self.__file_handler.setLevel(     fileFMT["level"]     )
        self.__file_handler.setFormatter( fileFMT["formatter"] )
        self.__log.addHandler(self.__file_handler)
