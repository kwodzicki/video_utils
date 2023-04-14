"""
For flagging/removing commericals

The ComRemove class is designed to use the comskip CLI (and ffmpeg) to
identify and label (via chapters) or remove (via ffmpeg) the commercial
segments.

"""

import logging
import os
from datetime import timedelta

from . import config, POPENPOOL
from .utils.check_cli import check_cli
from .utils.ffmpeg_utils import get_video_length, FFMetaData
from .utils.handlers import RotatingFile

try:
    COMSKIP = check_cli( 'comskip' )
except:
    logging.getLogger(__name__).error(
        "comskip is NOT installed or not in your PATH!"
    )
    COMSKIP = None


#from .utils.subproc_manager import SubprocManager

# Following code may be useful for fixing issues with audio in
# video files that cut out
# ffmpeg -copyts -i "concat:in1.ts|in2.ts" -muxpreload 0 -muxdelay 0 -c copy joint.ts

def file_remove( *args ):
    """
    Delete any number of files

    """

    log = logging.getLogger(__name__)
    for arg in args:
        try:
            os.remove(arg)
        except:
            log.debug( 'Error removing file: %s', arg )          # Log a warning

class ComRemove( ):
    """
    For identifying/removing commericals in video

    """

    # _comskip = ['comskip', '--hwassist', '--cuvid', '--vdpau']
    _comskip = ['comskip']
    _comcut  = ['ffmpeg', '-nostdin', '-y', '-i']
    _comjoin = ['ffmpeg', '-nostdin', '-y', '-i']

    ########################################################
    def __init__(self, **kwargs):
        """
        Initialize the COmRemove class

        Keyword arguments:
            iniDir (str): Path to directory containing .ini files for
                comskip settigs. If set, will try to find
                .ini file with same name as TV show series,
                falling back to comskip.ini if not found.
                Default is to use .ini included in pacakge.
            threads (int): Number of threads comskip is allowed to use
            cpulimit (int): Set limit of cpu usage per thread
            verbose  (bool): Depricated

        """

        super().__init__( **kwargs )
        self.__log = logging.getLogger(__name__)

        threads = kwargs.get('threads',  None)
        if not isinstance(threads, int):
            threads = POPENPOOL.threads

        # Get ini directory from kwargs
        ini_dir = kwargs.get('iniDir', None)
        # If no iniDir keyword, then try to get from environment variables
        if ini_dir is None:
            ini_dir = os.environ.get('COMSKIP_INI_DIR', None)
        # If no environment variable, try to get from config
        if ini_dir is None:
            ini_dir = config.CONFIG.get('COMSKIP_INI_DIR', None)

        # If ini_dir is NOT None by this point, check if the directory exist
        if ini_dir is not None:
            if not os.path.isdir( ini_dir ):
                ini_dir = None

        # Try to get comskip_log file path from kwargs
        comskip_log = kwargs.get('comskip_log', None)
        if comskip_log is None:
            comskip_log = config.get_comskip_log( self.__class__.__name__ )

        self.ini_dir     = ini_dir
        self.threads     = threads
        self.comskip_log = comskip_log
        self.cpulimit    = kwargs.get('cpulimit', None)
        self.verbose     = kwargs.get('verbose',  None)
        self.__outdir    = None
        self.__fileext   = None

    ########################################################
    def remove_commercials(self, in_file, chapters=False, name='' ):
        """
        Main method for commercial identification and removal.

        Arguments:
            in_file (str): Full path of file to run commercial removal on

        Keyword arguments:
            chapters (bool): Set for non-destructive commercial 'removal'.
                If set, will generate .chap file containing show segment and
                commercial break chapter info for FFmpeg.
            name (str): Name of series or movie (Plex convention). Required
                if trying to use specific comskip.ini file

        Returns:
            If chapters is True, returns string to ffmpeg metadata file on
                success, False otherwise.
                if Chapters is False, returns True on success, False otherwise

        """
        # Store input file directory in attribute
        self.__outdir  = os.path.dirname( in_file )
        # Store Input file extension in attrubute
        self.__fileext = os.path.splitext(in_file)[-1]

        # Set some default values
        edl_file  = None
        tmp_files = None
        cut_file  = None
        status    = False

        # Attempt to run comskip and get edl file path
        edl_file  = self.comskip( in_file, name=name )

        # If no valid edl_file, then just return the status
        if edl_file is None:
            return status

        # If edl_file size is zero (0), no commercials detected
        if os.path.getsize( edl_file ) == 0:
            status = True
            file_remove(edl_file)
        elif chapters:
            # Want to mark commericals as chapters
            status = self.comchapter( in_file, edl_file )
            file_remove(edl_file)
        else:
            # Want to cut out the commericals from the video file
            tmp_files = self.comcut( in_file, edl_file )
            if tmp_files:
                cut_file = self.comjoin( tmp_files )
            if cut_file:
                self.check_size( in_file, cut_file )
                status = True

        self.__outdir  = None
        self.__fileext = None

        return status

    ########################################################
    def comskip(self, in_file, name = ''):
        """
        Method to run the comskip CLI to locate commerical breaks in the input file

        Arguments:
            in_file (str): Full path of file to run comskip on

        Keyword arguments:
            name (str): Name of series or movie (Plex convention). Required
                if trying to use specific comskip.ini file

        Returns:
            Path to .edl file produced by comskip IF the 
            comskip runs successfully. If comskip does not run
            successfully, then None is returned.

        """

        if not COMSKIP:
            self.__log.info('comskip utility NOT found!')
            return None

        self.__log.info( 'Running comskip to locate commercial breaks')

        # If no outdir set, store input file directory in attribute
        if self.__outdir is None:
            self.__outdir  = os.path.dirname( in_file )
        # Store Input file extension in attrubute
        if self.__fileext is None:
            self.__fileext = os.path.splitext(in_file)[-1]

        cmd = self._comskip.copy()
        cmd.append( f'--threads={self.threads}' )
        cmd.append( f'--ini={self._get_ini(name=name)}' )

        # Get file path with no extension
        tmp_file  = os.path.splitext( in_file )[0]
        edl_file  = f"{tmp_file}.edl"
        txt_file  = f"{tmp_file}.txt"
        logo_file = f"{tmp_file}.logo.txt"

        cmd.append( f"--output={self.__outdir}" )
        cmd.extend( [in_file, self.__outdir] )
        self.__log.debug( 'comskip command: %s', ' '.join(cmd) )

        if self.comskip_log:
            kwargs = {
                'stdout'             : RotatingFile( self.comskip_log ),
                'universal_newlines' : True,
            }
        else:
            kwargs = {}
        proc = POPENPOOL.popen_async(cmd, threads = self.threads, **kwargs)

        # Wait for 8 hours for comskip to finish; this should be more than enough time
        if not proc.wait( timeout = 8 * 3600 ):
            self.__log.error('comskip NOT finished after 8 hours; killing')
            proc.kill()
        self.__log.info('comskip ran successfully')

        if proc.returncode not in (0, 1):
            self.__log.warning('There was an error with comskip')
            file_remove(txt_file, edl_file, logo_file)
            return None

        if proc.returncode == 1:
            self.__log.info('No commericals detected!')
        elif not os.path.isfile( edl_file ):
            self.__log.warning('No EDL file was created; trying to convert TXT file')
            edl_file = self.convert_txt( txt_file, edl_file )
        file_remove(txt_file, logo_file)
        return edl_file

    ########################################################
    def comchapter(self, in_file, edl_file):
        """
        Create ffmpeg metadata file with chapter information for commercials.

        The edl file created by comskip is parsed into an FFMETADATA file. This
        file can then be passed to ffmpeg to create chapters in the output file
        marking show and commercial segments.

        Arguments:
            in_file (str): Full path of file to run comskip on
            edl_file (str): Full path of .edl file produced by

        Returns:
            str: Path to ffmpeg metadata file

        """

        self.__log.info('Generating metadata file')

        show_seg    = 'Show Segment \#{}'
        com_seg     = 'Commercial Break \#{}'
        segment     = 1
        commercial  = 1
        # Initial start time of the show segment; i.e., the beginning of the recording
        seg_start   = 0.0

        fdir, fbase = os.path.split( in_file )
        fname, _    = os.path.splitext( fbase )
        # Generate file name for chapter metadata
        metafile    = os.path.join( fdir, f"{fname}.chap" )

        file_length  = get_video_length(in_file)

        ffmeta      = FFMetaData()
        with open(edl_file, 'r') as fid:
            info = fid.readline()
            while info:
                # Get the start and ending times of the commercial as float
                com_start, com_end = map(float, info.split()[:2])
                # If the start of the commercial is NOT near the very beginning of the file
                if com_start > 1.0:
                    # From seg_start to com_start is NOT commercial
                    title = show_seg.format(segment)
                    ffmeta.add_chapter( seg_start, com_start, title )
                    self.__log.debug(
                        '%s - %0.2f to %0.2f s',
                        title, seg_start, com_start
                    )
                    # From com_start to com_end is commercial
                    title = com_seg.format(commercial)
                    ffmeta.add_chapter( com_start, com_end, title )
                    self.__log.debug(
                        '%s - %0.2f to %0.2f s',
                        title, com_start, com_end,
                    )
                    # Increment counters
                    segment    += 1
                    commercial += 1

                # The start of the next segment of the show is the end time
                # of the current commerical break
                seg_start = com_end
                info     = fid.readline()

        # If the time differences is greater than a few seconds
        if (file_length - seg_start) >= 5.0:
            ffmeta.add_chapter( seg_start, file_length, show_seg.format(segment) )

        ffmeta.save( metafile )

        return metafile

    ########################################################
    def comcut(self, in_file, edl_file):
        """
        Method to create intermediate files that do NOT contain comercials.

        Arguments:
            in_file (str): Full path of file to run comskip on
            edl_file (str): Full path of .edl file produced by

        Returns:
            list: File paths for the intermediate files created if successful.
                Else, returns None.

        """

        self.__log.info('Cutting out commercials')
        cmd_base = self._comcut + [in_file]
        # List for all temporary files
        tmpfiles = []
        # Set file number counter to zero
        fnum     = 0
        # Initial start time of the show segment; i.e., the beginning of the recording
        seg_start = timedelta( seconds = 0.0 )

        with open(edl_file, 'r') as fid:
            info     = fid.readline()
            procs    = []
            while info:
                com_start, com_end = info.split()[:2]
                com_start   = timedelta( seconds = float(com_start) )
                com_end     = timedelta( seconds = float(com_end) )
                # If the start of the commercial is NOT near the very beginning of the file
                if com_start.total_seconds() > 1.0:
                    seg_dura = com_start - seg_start
                    outfile  = f"tmp_{fnum:03d}{self.__fileext}"
                    outfile  = os.path.join(self.__outdir, outfile)
                    cmd      = (
                        cmd_base +
                        ['-ss', str(seg_start), '-t', str(seg_dura), '-c', 'copy', outfile]
                    )
                    tmpfiles.append( outfile )
                    procs.append( POPENPOOL.popen_async( cmd, threads=1 ) )

                # The start of the next segment of the show is the end time
                # of the current commerical break
                seg_start = com_end
                info     = fid.readline()
                fnum    += 1

        POPENPOOL.wait()
        # If one or more of the process failed
        if sum(p.returncode for p in procs) != 0:
            self.__log.critical( 'There was an error cutting out commericals!' )
            file_remove( *tmpfiles )
            tmpfiles = None

        self.__log.debug('Removing the edl_file')
        file_remove( edl_file )
        return tmpfiles

    ########################################################
    def comjoin(self, tmpfiles):
        """
        Method to join intermediate files that do NOT contain comercials into one file.

        Arguments:
            tmpfiles (list): Full paths of intermediate files to join

        Returns:
            Returns path to continous file created by joining
                intermediate files if joining is successful. Else
                returns None.

        """

        self.__log.info( 'Joining video segments into one file')
        infiles = '|'.join( tmpfiles )
        infiles = f"concat:{infiles}"
        outfile = f"tmp_nocom{self.__fileext}"
        outfile = os.path.join(self.__outdir, outfile)

        cmd     = self._comjoin + [infiles, '-c', 'copy', '-map', '0', outfile]
        proc    = POPENPOOL.popen_async( cmd )
        proc.wait()
        for fname in tmpfiles:
            self.__log.debug('Deleting temporary file: %s', fname)
            file_remove( fname )
        if proc.returncode == 0:
            return outfile

        file_remove( outfile )
        return None

    ########################################################
    def check_size(self, in_file, cut_file):
        """
        Check that the file with no commercials is a reasonable size

        A check to see if too much has been removed. If the file size is sane,
        then just replace the input file with the cut file (one with no commercials).
        If the file size is NOT sane, then the cut file is removed and the original 
        input file is saved.
        Borrowed from https://github.com/ekim1337/PlexComskip

        Arguments:
            in_file (str): Full path of file to run comskip on
            cut_file (str): Full path of file with NO commercials

        Returns:
            None

        """

        self.__log.debug( "Running file size check to make sure too much wasn't removed")
        in_file_size  = os.path.getsize( in_file  )
        cut_file_size = os.path.getsize( cut_file )
        replace       = False
        if 1.1 > float(cut_file_size) / float(in_file_size) > 0.5:
            msg = 'Output file size looked sane, replacing the original: %s -> %s'
            replace = True
        elif 1.01 > float(cut_file_size) / float(in_file_size) > 0.99:
            msg = 'Output file size was too similar; keeping original: %s -> %s'
        else:
            msg = 'Output file size looked odd (too big/too small); keeping original: %s -> %s'
        self.__log.info(
            msg, self.__size_fmt(in_file_size), self.__size_fmt(cut_file_size)
        )

        if replace:
            os.rename( cut_file, in_file )
        else:
            file_remove( cut_file )

    ########################################################
    def convert_txt( self, txt_file, edl_file ):
        """
        Convert txt file created by comskip to edl_file

        Arguments:
            txt_file (str): Path to txt_file
            edl_file (str): Path to edl_file

        Keyword arguments:
            None

        Returns:
            str: Path to edl file

        """

        if not os.path.isfile(txt_file):
            self.__log.error('TXT file does NOT exist!')
            return None
        if os.stat(txt_file).st_size == 0:
            self.__log.warning('TXT file is empty!')
            return None

        with open(txt_file, 'r') as txt, open(edl_file, 'w') as edl:
            line = txt.readline()
            rate = int(line.split()[-1])/100.0
            line = txt.readline()# Read past a line
            line = txt.readline()# Read line
            while line != '':
                start, end = [float(i)/rate for i in line.rstrip().split()]
                edl.write( f'{start:0.2f} {end:0.2f} 0{os.linesep}' )
                line = txt.readline()
        return edl_file

    ########################################################
    def _get_ini( self, name='' ):
        """
        Method to get name of .ini file to use for commercial removal

        Arguments:
            None.

        Keyword arguments:
            name (str): Plex formatted TV series or Movie name.

        Returns:
            str: Path to Comskip INI file to use for commercial removal

        """

        # If no ini_dir, then return path to bundled ini file
        if self.ini_dir is None:
            return config.COMSKIPINI

        ini = 'comskip' if name == '' else name
        ini = os.path.join( self.ini_dir, f'{ini}.ini' )
        if os.path.isfile( ini ):
            return ini

        return None

    ########################################################
    def __size_fmt(self, num, suffix='B'):
        """
        Private method for determining the size of a file in a human readable format
          
        Borrowed from https://github.com/ekim1337/PlexComskip

        Arguments:
            num (int) : File size

        """

        for unit in ['','K','M','G','T','P','E','Z']:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Y{suffix}"
