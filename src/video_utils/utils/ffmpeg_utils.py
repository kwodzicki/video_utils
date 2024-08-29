"""
FFMpeg utilities

"""

import logging
import os
import time
import re
import json
from datetime import datetime, timedelta
from subprocess import Popen, run, check_output, PIPE, STDOUT, DEVNULL

import numpy as np

from .. import POPENPOOL
from . import isRunning

# Regex pattern for locating file duration in ffmpeg ouput
PROGPAT = re.compile(r'time=(\d{2}:\d{2}:\d{2}.\d{2})')
# Regex pattern for extracting crop information
CROPPAT = re.compile(r'(?:crop=(-?\d+):(-?\d+):(-?\d+):(-?\d+))')
# Regex pattern for video resolution
RESPAT = re.compile(r'(\d{3,5}x\d{3,5})')
# Regex pattern for locating file processing location
# DURPAT  = re.compile(r'Duration: (\d{2}:\d{2}:\d{2}.\d{2})')
DURPAT = re.compile(r'Duration: ([^,]*)')
# String formatter for conversion progress
ESTCOMP = 'Estimated Completion Time: %s'

# Array for conversion of hour/minutes/seconds to total seconds
TOSEC = np.array([3600, 60, 1], dtype=np.float32)
# Base numpy chunk
CHUNK = np.full((128, 4), np.nan)

# Default time_base for chapters
TIME_BASE = '1/1000000000'
# Padding before beginning of chapter
PREROLL = -1.0
# Padding after end of chapter
POSTROLL = 1.0

# Threshold for cropping. If the ratio of crop size to original is >= this
# value, no cropping done. The width and height are check separately
CROPTHRES = 0.95

# Format for FFMETADATA file header
HEADERFMT = ';FFMETADATA{}' + os.linesep
# Format string for a FFMETADATA metadata tag
METADATAFMT = '{}={}' + os.linesep
# Format of CHAPTER block in FFMETADATA file
CHAPTERFMT = [
    '[CHAPTER]',
    'TIMEBASE={}',
    'START={}',
    'END={}',
    'title={}',
    '',
]
# Join CHAPTER block format list on operating system line separator
CHAPTERFMT = os.linesep.join(CHAPTERFMT)

# Mapping for scaling/formatting HDR data
MASTERING_MAP = {
    "G": {
        "factor": 50000,
        "tags": ("green_x", "green_y"),
    },
    "B": {
        "factor": 50000,
        "tags": ("blue_x", "blue_y"),
    },
    "R": {
        "factor": 50000,
        "tags": ("red_x", "red_y"),
    },
    "WP": {
        "factor": 50000,
        "tags": ("white_point_x", "white_point_y"),
    },
    "L": {
        "factor": 10000,
        "tags": ("max_luminance", "min_luminance"),
    },
}


class FFMetaData:
    """For creating a FFMetaData file for input into ffmpeg CLI"""

    def __init__(self, version=1):

        self._version = version
        self._metadata = {}
        self._chapters = []
        self._chapter = 1

    def add_metadata(self, **kwargs):
        """
        Method to add new metadata tags to FFMetaData file

        Arguments:
            None

        Keyword arguments:
            **kwargs : Any key/value pair where key is a valid metadata tag
                and value is the value for the tag.

        Returns:
            None

        """

        self._metadata.update(kwargs)

    def add_chapter(self, *args, **kwargs):
        """
        Method to add chapter marker to FFMetaData file

        Arguments:
            If one (1) input:
                Must be Chapter instance
            If three (3) inputs:
                start  : Start time of chapter (float or datetime.timedelta)
                end    : End time of chapter (float or datetime.timedelta)
                title  : Chapter title (str)

        Keyword arguments:
            time_base : String of form 'num/den’, where num and den are
                integers. If the time_base is missing then start/end times
                are assumed to be in nanosecond. Ignored if NOT three (3)
                inputs.

        Returns:
            None

        """

        if len(args) == 1:
            chapter = args[0]
        elif len(args) == 3:
            if isinstance(args[0], timedelta):
                start = args[0].total_seconds()
            if isinstance(args[1], timedelta):
                end = args[1].total_seconds()

            chapter = Chapter()
            time_base = kwargs.get('time_base', TIME_BASE)
            if isinstance(time_base, str):
                # Get the numberator and denominator as integers
                num, den = map(int, time_base.split('/'))
                # Do den/num to get factor to go from seconds to time_base
                factor = den / num
            else:
                raise Exception(
                    "time_base must be a string of format 'num/den'!",
                )
            chapter.time_base = time_base
            # Get total seconds from timedelta, apply factor,
            # then convert to integer
            chapter.start = round(start * factor)
            # Do same for end time
            chapter.end = round(end * factor)
            chapter.title = args[2]
        else:
            raise Exception("Incorrect number of arguments!")

        # If chapter title matches generic title
        if re.match(r'Chapter\s\d?', chapter.title):
            # Reset chapter number title
            chapter.title = f"Chapter {self._chapter:02d}"

        # Append tuple of information to _chapters attribute
        self._chapters.append(chapter.to_ffmetadata())
        self._chapter += 1

    def save(self, fpath):
        """
        Method to write ffmetadata to file

        Arguments:
            fpath (str): Full path of file to write to

        Keyword arguments:
          None

        Returns:
          str: Returns the fpath input

        """

        with open(fpath, mode='w', encoding='utf8') as fid:
            # Write header to file
            fid.write(HEADERFMT.format(self._version))

            for key, val in self._metadata.items():
                # Write metadata
                fid.write(METADATAFMT.format(key, val))

            # Add space between header/metadata and chapter(s)
            fid.write(os.linesep)
            # Iterate over all chapters
            for info in self._chapters:
                # Write the chapter info
                fid.write(info)
                fid.write(os.linesep)

        self._chapters = []
        self._chapter = 1
        return fpath


class Chapter:
    """Represents a chapter in a video file"""

    def __init__(self, chapter=None):
        self._data = chapter if isinstance(chapter, dict) else {}

    def __repr__(self):
        return f"<{self.title} : {self.start_time}s --> {self.end_time}s>"

    @property
    def num(self) -> int:
        return int(
            self.time_base.split('/')[0]
        )

    @property
    def den(self) -> int:
        return int(
            self.time_base.split('/')[1]
        )

    @property
    def time_base(self):
        """Time base for start/end values"""

        return self._data.get('time_base', TIME_BASE)

    @time_base.setter
    def time_base(self, val):

        # Set time_base to new value
        self._data['time_base'] = val
        # Get new numerator and denominator
        start_time = self.start_time
        # Set start_time to current start_time;
        # will trigger conversion of start
        if isinstance(start_time, float):
            self.start_time = start_time
        end_time = self.end_time
        # Set end_time to current end_time; will trigger conversion of end
        if isinstance(end_time, float):
            self.end_time = end_time

    @property
    def start(self) -> int:
        """Start time of chapter, in time base units"""

        return int(self._data.get('start', 0))

    @start.setter
    def start(self, val: str | int):
        val = int(val)
        self._data['start'] = val
        self._data['start_time'] = self.base2seconds(val)

    @property
    def end(self) -> int:
        """End time of chapter, in time base units"""

        return int(self._data.get('end', 0))

    @end.setter
    def end(self, val: str | int):
        val = int(val)
        self._data['end'] = val
        self._data['end_time'] = self.base2seconds(val)

    @property
    def start_time(self) -> float:
        """Start time of chapter in seconds"""

        return float(self._data.get('start_time', 0))

    @start_time.setter
    def start_time(self, val: str | int | float):
        val = float(val)
        self._data['start_time'] = val
        self._data['start'] = self.seconds2base(val)

    @property
    def end_time(self) -> float:
        """End time of chapter in seconds"""

        return float(self._data.get('end_time', 0))

    @end_time.setter
    def end_time(self, val: str | int | float):
        val = float(val)
        self._data['end_time'] = val
        self._data['end'] = self.seconds2base(val)

    @property
    def title(self):
        """Chapter title"""

        key = 'tags'
        if key in self._data:
            return self._data[key].get('title', '')
        return None

    @title.setter
    def title(self, val):

        key = 'tags'
        tags = self._data.get(key, None)
        if not isinstance(tags, dict):
            self._data[key] = {}
        self._data[key]['title'] = val

    def _convert_timebase(self, in_int, in_float, time_base):
        """
        Convert to new time_base

        Arguments:
            in_int     : Value of time in time_base units
            in_float   : Value of time in seconds
            time_base : str contianing new time_base

        Keyword arguments:
            None

        Returns:
            tuple: (in_int, in_float) where in_int is in requested time_base

        """

        # If requested time_base NOT match time_base
        if time_base != self.time_base:
            # Get numerator and denominator of new time_base
            num, den = map(int, time_base.split('/'))
            # Cross multiply original time_base with new time_base
            factor = (self.num * den) / (self.den * num)
            # Convert integer time to new base, return float
            return round(in_int * factor), in_float
        return in_int, in_float

    def to_ffmetadata(self):
        """Method that returns information in format for FFMETADATA file"""

        return CHAPTERFMT.format(
            self.time_base,
            self.start,
            self.end,
            self.title,
        )

    def base2seconds(self, val):
        """Method that converts value in time_base units to seconds"""

        return val * self.num / self.den

    def seconds2base(self, val):
        """Method that converts value in seconds to time_base units"""

        return round(val * self.den / self.num)

    def get_start(self, time_base=None):
        """Get chapter start time in time_base and seconds units"""

        if time_base:
            return self._convert_timebase(*self.get_start(), time_base)
        return self.start, self.start_time

    def get_end(self, time_base=None) -> tuple:
        """Method to return chapter end time in time_base and seconds units"""

        if time_base:
            return self._convert_timebase(*self.get_end(), time_base)
        return self.end, self.end_time

    def add_offset(self, offset: float, flag: int = 2) -> None:
        """
        To adjust the start, end, or both times

        Arguments:
            offset (float): Offset time in seconds

        Keyword arguments:
            flag (int): Set to:
                0 - to add offset to start time,
                1 - to add offset to end time,
                2 - (default) add offset to start and end
        Returns:
            None: updates internal attributes

        """

        if isinstance(offset, timedelta):
            offset = offset.total_seconds()
        if flag == 2:
            self.start_time += offset  # offset start time
            self.end_time += offset  # Offset end time
        elif flag == 1:  # If flag is 1
            self.end_time += offset  # Offset end_time
        elif flag == 0:
            self.start_time += offset  # Offset start time


def cropdetect_cmd(
    infile: str,
    start_time: timedelta,
    seg_len: timedelta,
    threads: int | None,
) -> list[str]:
    """
    Generate ffmpeg command list for crop detection

    Arguments:
        infile (str) : File to read from
        start_time (timedelta) : Start time for segment
        seg_len (timedelta) : Length of segment for crop detection
        threads (int) : number of threads to let ffmpeg use

    Keyword arguments:
        None.

    Returns:
        list : Command to be run using subprocess.Popen

    """

    if not isinstance(start_time, timedelta):
        raise Exception('start_time must be datetime.timedelta object')
    if not isinstance(seg_len, timedelta):
        raise Exception('seg_len must be datetime.timedelta object')

    opts = ['-threads', str(threads)] if isinstance(threads, int) else []
    opts = opts + [
        '-ss', str(start_time),
        '-i', infile,
        '-max_muxing_queue_size', '1024',
        '-t', str(seg_len),
        '-vf', 'cropdetect',
        '-f', 'null',
        '-',
    ]

    # Return the list with command
    return ['ffmpeg', '-nostats'] + opts


def cropdetect(
    infile: str,
    video_res: tuple[int] | None,
    seg_len: int | float = 20,
    threads: int | None = None,
) -> str | None:
    """
    Use FFmpeg to to detect a cropping region for video files

    Arguments:
        infile (str): Path to input file for crop detection
        video_res (tuple): Tuple of ints specifying the video width/height

    Keyword arguments:
        seg_len : Length of video, in seconds, starting from beginning to use
            for crop detection, default is 20 seconds
        threads (int): Number of threads to use when running ffmpeg to
            detect crop

    Returns:
        FFmpeg video filter in the format :code:`crop=w:h:x:y` or
             None if no cropping detected

    """

    log = logging.getLogger(__name__)

    # Counter for number of crop regions detected
    n_crop = 0
    # Initialize list of 4 lists for crop parameters
    whxy = [[] for i in range(4)]
    seg_len = timedelta(seconds=seg_len)
    start_time = timedelta(seconds=0)
    crop = CHUNK.copy()

    log.debug('Detecting crop using chunks of length %s', seg_len)

    detect = True
    while detect and isRunning():
        detect = False
        log.debug('Checking crop starting at %s', start_time)
        # Generate command for crop detection
        cmd = cropdetect_cmd(infile, start_time, seg_len, threads)
        # Start the command, piping stdout and stderr to a pipe
        with Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            universal_newlines=True,
        ) as proc:
            line = " "
            while line != '':
                line = proc.stdout.readline()
                # Try to find pattern in line
                whxy = CROPPAT.search(line)
                if not whxy:
                    continue

                if not detect:
                    detect = True
                # If the current row is outside of the number of rows
                if n_crop == crop.shape[0]:
                    # Concat a new chunk onto the array
                    crop = np.concatenate([crop, CHUNK], axis=0)
                # Split the string on colon
                crop[n_crop, :] = np.array(
                    tuple(map(int, whxy.groups()))
                )
                n_crop += 1

        start_time += timedelta(seconds=60 * 5)

    # Compute maximum across all values
    good, _ = np.where(crop[:, :2] > 0)
    if good.size == 0:
        log.debug('No valid cropping values detected')
        return None

    x_width, y_width = np.nanmax(crop[good, :], axis=0)[:2]

    # Compute ratio of cropping width and height to source width and height
    x_check = x_width / video_res[0]
    y_check = y_width / video_res[1]

    # If crop width and height are atleast 50% of video width and height

    if (x_check <= 0.5) or (y_check <= 0.5):
        log.debug('No cropping region detected')
        return None

    # If the crop size is the same as the input size
    if (x_width == video_res[0]) and (y_width == video_res[1]):
        log.debug('Crop size same as input size, NOT cropping')
        return None

    if (x_check >= CROPTHRES) and (y_check >= CROPTHRES):
        log.debug(
            'Crop size very similar to input size (%0.0fx%0.0f vs. %dx%d), '
            'NOT cropping',
            x_width,
            y_width,
            *video_res,
        )
        return None

    if x_check >= CROPTHRES:
        # If x ratio is above CROPTHRES, then set xWidth to resolution width
        x_width = video_res[0]
    if y_check >= CROPTHRES:
        # If y ratio is above CROPTHRES, then set yWidth to resolution height
        y_width = video_res[1]

    # Compute x-offset, this is half of the difference between video width and
    # crop width because applies to both sizes of video
    x_offset = (video_res[0] - x_width) // 2
    # Compute x-offset, this is half of the difference between video height and
    # crop height because applies to both top and bottom of video
    y_offset = (video_res[1] - y_width) // 2

    crop = (x_width, y_width, x_offset, y_offset)
    crop = map(int, crop)
    crop = list(map(str, crop))

    log.debug('Values for crop: %s', crop)
    return 'crop=' + ':'.join(crop)


def total_seconds(*args):
    """
    Convert time strings to the total number of seconds represented by the time

    Arguments:
        *args: One or more time strings of format HH:MM:SS

    Keyword arguments:
        None.

    Returns:
        Returns a numpy array of total number of seconds in time

    """

    # Iterate over all arugments, splitting on colon (:), converting to numpy
    # array, and converting each time element to seconds
    times = [
        np.array(arg.split(':'), dtype=np.float32) * TOSEC
        for arg in args
    ]
    # Convert list of numpy arrays to 2D numpy array, then compute sum of
    # seconds across second dimension
    return np.array(times).sum(axis=1)


class FFmpegProgress:
    """
    Monitor FFMpeg progress

    Class for monitoring output from ffmpeg to determine how much
    time remains in the conversion.

    """

    def __init__(self, interval: float = 60.0, nintervals: int | None = None):
        """

        Arguments:
            None

        Keyword arguments:
            interval (float): The update interval, in seconds, to log time
                remaining info. Default is sixty (60) seconds, or 1 minute.
            nintervals (int): Set to number of updates you would like to be
                logged about progress. Default is to log as many updates as
                it takes at the interval requested. Setting this keyword will
                override the value set in the interval keyword.
                Note that the value of interval will be used until the
                first log, after which point the interval will be updated
                based on the remaing conversion time and the requested
                number of updates

        Returns:
            Object

        """

        self.log = logging.getLogger(__name__)
        # Initialize t0 and t1 to the same time; i.e., now
        self.time0 = self.time1 = time.time()
        self.dur = None
        self.interval = interval
        self.nintervals = nintervals

    def progress(self, in_val):
        """Get progress of FFMpeg transcode"""

        if isinstance(in_val, Popen):
            self._subprocess(in_val)
        else:
            self._process_line(in_val)

    def _subprocess(self, proc):
        if proc.stdout is None:
            self.log.error(
                'Subprocess stdout is None type! No progess to print!'
            )
            return
        if not proc.universal_newlines:
            self.log.error(
                'Must set universal_newlines to True in call to Popen! '
                'No progress to print!',
            )
            return

        # Read a line from stdout for while loop start
        line = proc.stdout.readline()
        while line != '':
            self._process_line(line)
            line = proc.stdout.readline()

    def _process_line(self, line):

        # If the file duration has NOT been set yet
        if self.dur is None:
            # Try to find the file duration pattern in the line
            tmp = DURPAT.findall(line)
            if len(tmp) == 1:
                # Compute the total number of seconds in the file,
                # take element zero as returns list
                self.dur = total_seconds(tmp[0])[0]
        # Else, if the amount of time between the last logging and now is
        # greater or equal to the interval
        elif (time.time() - self.time1) >= self.interval:
            # Update the time at which we are logging
            self.time1 = time.time()
            # Look for progress time in the line
            tmp = PROGPAT.findall(line)
            # If progress NOT found; or multiple found, return
            if len(tmp) != 1:
                return
            # Compute the elapsed time
            elapsed = self.time1 - self.time0
            # Compute total number of seconds comverted so far, take element
            # zero as returns list
            prog = total_seconds(tmp[0])[0]
            # Ratio of real-time seconds per seconds of video processed
            ratio = elapsed / prog
            # Multiply ratio by the number of seconds of video left to convert
            remain = ratio * (self.dur - prog)
            # Compute estimated completion time
            end_time = datetime.now() + timedelta(seconds=remain)
            # Log information
            self.log.info(ESTCOMP, end_time)
            if (self.nintervals is not None) and (self.nintervals > 1):
                self.nintervals -= 1
                self.interval = remain / float(self.nintervals)


def progress(
    proc: Popen,
    interval: float = 60.0,
    nintervals: int | None = None,
) -> None:
    """
    Determine how much time remains in the conversion.

    Arguments:
        proc (Popen): A subprocess.Popen instance. The stdout of Popen must
            be set to subprocess.PIPE and the stderr must be set to
            subprocess.STDOUT so that all information runs through
            stdout. The universal_newlines keyword must be set to True
            as well

    Keyword arguments:
        interval  (float): The update interval, in seconds, to log time
            remaining info. Default is sixty (60) seconds, or 1 minute.
        nintervals (int): Set to number of updates you would like to be logged
            about progress. Default is to log as many updates as it takes
            at the interval requested. Setting this keyword will
            override the value set in the interval keyword.
            Note that the value of interval will be used until the
            first log, after which point the interval will be updated
            based on the remaing conversion time and the requested
            number of updates

    Returns:
        Returns nothing. Does NOT wait for the process to finish so MUST
            handle that in calling function

    """

    log = logging.getLogger(__name__)
    if proc.stdout is None:
        log.error(
            'Subprocess stdout is None type! No progess to print!'
        )
        return
    if not proc.universal_newlines:
        log.error(
            'Must set universal_newlines to True in call to Popen! '
            'No progress to print!',
        )
        return

    # Initialize t0 and t1 to the same time; i.e., now
    time0 = time1 = time.time()
    dur = None
    line = proc.stdout.readline()
    while line != '':
        if dur is None:
            # Try to find the file duration pattern in the line
            tmp = DURPAT.findall(line)
            # If the pattern is found
            if len(tmp) == 1:
                # Compute the total number of seconds in the file, take
                # element zero as returns list
                dur = total_seconds(tmp[0])[0]
        # Else, if the amount of time between the last logging and now is
        # greater or equal to the interval
        elif (time.time() - time1) >= interval:
            # Update the time at which we are logging
            time1 = time.time()
            # Look for progress time in the line
            tmp = PROGPAT.findall(line)
            # If progress time found
            if len(tmp) == 1:
                # Compute the elapsed time
                elapsed = time1 - time0
                # Compute total number of seconds comverted so far, take
                # element zero as returns list
                prog = total_seconds(tmp[0])[0]
                # Ratio of real-time seconds per seconds of video processed
                ratio = elapsed / prog
                # Multiply ratio by number of seconds of video left to convert
                remain = ratio * (dur - prog)
                # Compute estimated completion time
                end_time = datetime.now() + timedelta(seconds=remain)
                log.info(ESTCOMP, end_time)
                if (nintervals is not None) and (nintervals > 1):
                    nintervals -= 1
                    interval = remain / float(nintervals)
        line = proc.stdout.readline()
    return


def get_video_length(in_file: str) -> float:
    """Returns float length of video, in seconds"""

    with Popen(['ffmpeg', '-i', in_file], stdout=PIPE, stderr=STDOUT) as proc:
        info = proc.stdout.read().decode()
    dur = DURPAT.findall(info)
    if len(dur) == 1:
        hour, minute, second = [float(i) for i in dur[0].split(':')]
        return hour * 3600.0 + minute * 60.0 + second
    return 86400.0


def check_integrity(fpath: str) -> bool:
    """
    Test the integrity of a video file.

    Runs ffmpeg with null output, checking errors for 'overread'.
    If overread found, then return False, else True

    Arguments:
        fpath (str): Full path of file to check

    Keyword arguments:
        None

    Returns:
        bool: True if no overread errors, False otherwise

    """

    cmd = [
        'ffmpeg',
        '-nostdin',
        '-v', 'error',
        '-threads', '1',
        '-i', fpath,
        '-f', 'null',
        '-',
    ]
    with Popen(
        cmd,
        stdout=PIPE,
        stderr=STDOUT,
        universal_newlines=True,
    ) as proc:
        line = proc.stdout.readline()
        while line != '':
            if 'overread' in line:
                return False
            line = proc.stdout.readline()
    return True


def get_chapters(fpath):
    """
    Function for extract chapter information from video

    Arguments:
        fpath (str): Path of file to extract chapter information from

    Keyword arguments:
        None

    Returns:
        List of Chapter objects if chapters exist, None otherwise

    """

    log = logging.getLogger(__name__)
    cmd = [
        'ffprobe',
        '-i', fpath,
        '-print_format', 'json',
        '-show_chapters',
        '-loglevel', 'error',
    ]
    try:
        chaps = str(check_output(cmd), 'utf-8')
    except:
        log.error('Failed to get chapter information')
        return None
    return [Chapter(chap) for chap in json.loads(chaps)['chapters']]


def get_hdr_opts(fpath):
    """
    Function to get HDR x265 options

    Arguments:
        fpath (str) : Path of file to get HDR options for

    Returns:
        None, tuple

    """

    log = logging.getLogger(__name__)
    cmd = [
        "ffprobe",
        "-hide_banner",
        "-loglevel", "quiet",
        "-select_streams", "v",
        "-print_format", "json",
        "-show_frames",
        "-read_intervals", "%+#1",
        "-i", fpath,
    ]

    try:
        info = json.loads(
            check_output(cmd)
        )
    except Exception as err:
        log.error("Failed to get HDR information: %s", err)
        return None

    info = info.get('frames', [])
    if len(info) < 1:
        log.warning("No frame information found")
        return None

    info = info[0]

    opts = [
        "hdr-opt=1",
        "repeat-headers=1",
        "colorprim=" + info.get("color_primaries", "bt2020"),
        "transfer=" + info.get("color_transfer", "smpte2084"),
        "colormatrix=" + info.get("color_space", "bt2020nc"),
    ]

    side_data = info.get("side_data_list", [])
    if len(info) < 1:
        log.info("No side_data_list found!")
        return opts

    master_display = get_mastering_display_metadata(side_data)
    if master_display:
        opts.append(master_display)

    max_cll = get_content_light_level_metadata(side_data)
    if max_cll:
        opts.append(max_cll)

    return info.get("pix_fmt", None), opts


def get_mastering_display_metadata(side_data):
    """
    Extract mastering display metadata

    Arguments:
        side_data (list) : Dicts containing HDR metadata

    Returns:
        dict

    """

    log = logging.getLogger(__name__)
    out = {}
    for data in side_data:
        if data.get("side_data_type", "") != "Mastering display metadata":
            continue

        for label, channel_data in MASTERING_MAP.items():
            vals = []
            for i, tag in enumerate(channel_data["tags"]):
                if tag not in data:
                    continue
                try:
                    tmp = tuple(map(int, data[tag].split("/")))
                except Exception as err:
                    log.debug("Failed to split channel data : %s", err)
                    return None
                if len(tmp) != 2:
                    log.debug("Did not get 2-elements from split!")
                    return None

                vals.append(
                    tmp[0] / (tmp[1] / channel_data["factor"])
                )
            if len(vals) != 2:
                return None
            out[label] = vals

        out = [
            f"{key}({val[0]:0.0f},{val[1]:0.0f})"
            for key, val in out.items()
        ]
        return "master-display=" + "".join(out)

    return None


def get_content_light_level_metadata(side_data):
    """
    Extract content light level metadata

    Arguments:
        side_data (list) : Dicts containing HDR metadata

    Returns:
        dict

    """

    for data in side_data:
        if data.get("side_data_type", "") != "Content light level metadata":
            continue

        max_content = data.get("max_content", 0)
        max_average = data.get("max_average", 0)

        return f"max-cll={max_content},{max_average}"

    return None


def extract_hevc(in_file, out_file):
    """
    Extract HEVC stream from file

    """

    out_file = f"{out_file}.hevc"
    cmd = [
        "ffmpeg",
        "-i", in_file,
        "-v", "error",
        "-stats",
        "-c:v", "copy",
        "-an", "-sn", "-dn",
        "-bsf:v", "hevc_mp4toannexb",
        "-f", "hevc",
        out_file,
    ]

    proc = run(cmd, stderr=DEVNULL, check=False)
    if proc.returncode == 0:
        return out_file

    if os.path.isfile(out_file):
        os.remove(out_file)
    return None


def partial_extract(
    in_file: str,
    out_file: str,
    start_offset: float | timedelta,
    duration: float | timedelta,
    chapter_file: str | None = None,
) -> bool:
    """
    Function for extracting video segement

    Arguments:
        in_file (str): Path of file to extract segment from
        out_file (str): Path of file to extract segment to
        start_offset (float,timedelta): Segment start time in input file.
            If float, units must be seconds.
        duration (float,timedelta): Segment duration
            If float, units must be seconds.

    Keyword arguments:
        chapter_file (str): Path to ffmetadata file specifying chapters
            for new segment

    Returns:
        bool: True on successful extraction, False otherwise

    """

    # Ensure start_offset is timedelta
    if not isinstance(start_offset, timedelta):
        start_offset = timedelta(seconds=start_offset)

    # Ensure duration is timedelta
    if not isinstance(duration, timedelta):
        duration = timedelta(seconds=duration)

    cmd = ['ffmpeg', '-y', '-v', 'quiet', '-stats']
    # Set starting read position and read for durtation for input file
    cmd += ['-ss', str(start_offset), '-t', str(duration)]
    cmd += ['-i', in_file]
    if chapter_file:
        # Add chapter file to command
        cmd += ['-i', chapter_file, '-map_chapters', '1']
    # Set codec to copy and map stream to all
    cmd += ['-codec', 'copy']
    # Set start time and duration for output  file
    cmd += ['-ss', '0', '-t', str(duration)]
    cmd += [out_file]
    proc = run(cmd, stderr=DEVNULL, check=False)
    return proc.returncode == 0


def split_on_chapter(in_file: str, n_chapters: int | list[int]) -> None:
    """
    Split a video file based on chapters.

    The idea is that if a TV show is ripped with multiple episodes in
    one file, assuming all episodes have the same number of chapters,
    one can split the file into individual episode files.

    Arguments:
        in_file (str): Full path to the file that is to be split.
        n_chapters (int,list): The number of chapters in each episode.

    Keyword arguments:
        None

    Returns:
        Outputs n files, where n is equal to the total number
            of chapters in the input file divided by n_chaps.

    """

    # Get all chapters from file
    chapters = get_chapters(in_file)
    if not chapters:
        return

    # If n_chapters is iterable
    if isinstance(n_chapters, (tuple, list)):
        # Ensure all values are integers
        n_chapters = [int(n) for n in n_chapters]
    elif not isinstance(n_chapters, int):
        # Ensure that n_chap is type int
        n_chapters = int(n_chapters)

    # Get input file directory and base name
    in_dir, _ = os.path.split(in_file)

    # Get input file name and extension
    _, in_ext = os.path.splitext(in_file)

    ffmeta = FFMetaData()
    split_fmt = 'split_{:03d}' + in_ext
    chap_name = 'split.chap'
    num = 0  # Set split file number
    s_id = 0  # Set chater starting number
    while s_id < len(chapters):
        # Get number of chapters to process; i.e., width of video segment
        e_id = s_id + (
            n_chapters[num]
            if isinstance(n_chapters, (tuple, list)) else
            n_chapters
        )
        # Set local preroll
        preroll = PREROLL if s_id > 0 else 0.0
        # Set local postroll
        postroll = POSTROLL if e_id < len(chapters) else 0.0
        # Subset chapters
        chaps = chapters[s_id:e_id]
        # Get chapter start time
        start = chaps[0].start_time
        # Get chapter end time
        end = chaps[-1].end_time
        # Set start time for segement with preroll adjustment
        start_d = timedelta(seconds=start + preroll)
        # Set segment duration with postroll adjustment
        dur = timedelta(seconds=end + postroll) - start_d
        # Determine number of chapers;
        # may be less than width if use fixed width
        for i, chap in enumerate(chaps):
            if i == 0:  # First chapter
                # Set chapter start offset to zero
                chap.add_offset(-start, 0)
                # Set chapter end offset to PREROLL greater than start to
                # compensate for pre-roll
                chap.add_offset(-start - preroll, 1)
            elif i == (len(chaps) - 1):  # If on last chapter
                # Adjust starting
                chap.add_offset(-start - preroll, 0)
                # Set end_time to segment duration
                chap.end_time = dur.total_seconds()
            else:
                # Adjust start and end times compenstating for pre-roll
                chap.add_offset(-start - preroll)
            ffmeta.add_chapter(chap)

        # Set output segement file path
        split_file = os.path.join(in_dir, split_fmt.format(num))
        # Set segment chapter file
        chap_file = os.path.join(in_dir, chap_name)
        # Create the FFMetaData file
        ffmeta.save(chap_file)
        if not partial_extract(
            in_file,
            split_file,
            start_d,
            dur,
            chapter_file=chap_file,
        ):
            break

        num += 1  # Increment split number
        s_id = e_id  # Set s_id to e_id
    os.remove(chap_file)  # Remove the chapter file


def combine_mp4_files(out_file: str, *args: str) -> None:
    """
    Combine multiple (2+) mp4 files into a single mp4 file

    Arguments:
        out_file (str): Output (combined) file path
        *args (str): Any number of input file paths

    Keyword arguments:
        None

    Returns:
        None

    """

    log = logging.getLogger(__name__)
    if len(args) < 2:
        log.critical('Need at least two (2) input files!')
        return

    # Iterate over input files and create intermediate TS file paths
    tmp_files = ['.'.join(f.split('.')[:-1]) + '.ts' for f in args]

    # List with options for creating intermediate files
    cmd_ts = [
        'ffmpeg', '-y', '-nostdin',
        '-i', '',
        '-c', 'copy',
        '-bsf:v', 'h264_mp4toannexb',
        '-f', 'mpegts', ''
    ]

    # List with options for combining TS files back into MP4
    cmd_concat = [
        'ffmpeg', '-nostdin',
        '-i', 'concat:' + '|'.join(tmp_files),
        '-c', 'copy',
        '-bsf:a', 'aac_adtstoasc',
        out_file
    ]

    for arg, tmp in zip(args, tmp_files):
        # Set input/output files in the cmd_ts list
        cmd_ts[4], cmd_ts[-1] = arg, tmp
        proc = POPENPOOL.popen_async(cmd_ts.copy())

    proc.wait()
    POPENPOOL.wait()
    proc = POPENPOOL.popen_async(cmd_concat)
    proc.wait()

    for tmp in tmp_files:  # Iterate over the temporary files
        if os.path.isfile(tmp):  # If the file exists
            os.remove(tmp)  # Delete it


def _test_file():
    """This is a grabage function used only for testing during development."""

    infile = os.path.join(
        '/derechoPool',
        'Archive',
        'video_utils_test_files',
        'bluray',
        'tmdb156022..mkv',
    )
    outfile = os.path.join(os.path.dirname(infile), 'tmp1.mp4')

    cmd = ['ffmpeg', '-nostdin', '-y', '-i', infile]
    cmd += ['-c:v', 'libx264']
    cmd += ['-c:a', 'copy']
    cmd += ['-threads', '1']
    cmd += [outfile]
    print(' '.join(cmd))

    with Popen(
        cmd,
        stdout=PIPE,
        stderr=STDOUT,
        universal_newlines=True,
    ) as proc:
        progress(proc, interval=10.0, nintervals=None)

    # proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    # progress(proc, interval=10.0, nintervals=None)
    # proc.communicate()
