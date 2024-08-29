"""
Wrapper class for mediainfo CLI

"""

import logging
import json
from subprocess import check_output

from .utils.ffmpeg_utils import get_hdr_opts


class MediaInfo:
    """Class that acts as wrapper for mediainfo CLI"""

    def __init__(self, infile: str | None = None, **kwargs):
        """
        Initialize MediaInfo class

        The mediainfo CLI is run with full output to XML format. The XML data
        returned is then parsed into a dictionary using the xml.etree library.

        Arguments:
           None

        Keyword arguments:
           infile (str): Path of file to run mediainfo on
           Various others...

        Returns:
          MediaInfo object

        """

        super().__init__(**kwargs)
        self.__log = logging.getLogger(__name__)
        self.infile = infile

    @property
    def infile(self) -> str | None:
        """Return the input file path"""
        return self.__infile

    @infile.setter
    def infile(self, value):
        """Set the input file path"""
        self.__infile = value
        if self.__infile is None:
            self.__mediainfo = None
        else:
            self.__mediainfo = mediainfo(value)
#          self.__parse_output()

    @property
    def format(self) -> str | None:
        """Full name of file format; e.g., MPEG-4, Matroska"""

        if self.__mediainfo:
            return self.__mediainfo['General'][0]['Format']
        return None

    @property
    def video_size(self) -> tuple[int] | None:
        """
        Method to get dimensions of video

        Returns:
          tuple: Video (width, height) if video stream exists. None otherwise.

        """

        tmp = self.get('Video', [])
        try:
            return (tmp[0]['Width'], tmp[0]['Height'],)
        except:
            return None

    @property
    def is_sd(self) -> bool | None:
        """Is file standard definition"""

        try:
            return self.video_size[1] <= 480
        except:
            return None

    @property
    def is_hd(self) -> bool | None:
        """Is file high definition"""

        try:
            return not self.is_sd and self.video_size[1] <= 1080
        except:
            return None

    @property
    def is_uhd(self) -> bool | None:
        """Is file high definition"""

        try:
            return self.video_size[1] > 1080
        except:
            return None

    @property
    def hdr_format(self) -> str:

        video = self.__mediainfo.get('Video', [])
        if len(video) < 1:
            return ""

        return video[0].get("HDR_Format_String", "")

    @property
    def is_dolby_vision(self) -> bool:

        return "DOLBY VISION" in self.hdr_format.upper()

    @property
    def is_hdr10(self) -> bool:

        return "HDR10" in self.hdr_format.upper()

    @property
    def is_hdr10plus(self) -> bool:

        return "HDR10+" in self.hdr_format.upper()

    @property
    def is_hdr(self) -> bool:

        return self.is_dolby_vision or self.is_hdr10 or self.is_hdr10plus

    def __getitem__(self, key):
        """
        Method for easily getting key from mediainfo

        Similar to dict[key]

        """

        return self.__mediainfo[key]

    def __setitem__(self, key, value):
        """
        Method for easily setting key in mediainfo

        Similar to dict[key] = value

        """

        self.__mediainfo[key] = value

    def get(self, *args):
        """Method for geting mediainfo keys; similar to dict.get()"""

        return self.__mediainfo.get(*args)

    def keys(self) -> list:
        """Method for geting mediainfo keys; similar to dict.keys()"""

        return self.__mediainfo.keys()

    def is_valid_file(self) -> bool | None:
        """
        Check if file is valid.

        This is done by checking that the size of the first video stream is
        less than the size of the file. This many not work in all cases,
        but seems to be true for MPEGTS files.

        """

        if self.__mediainfo:
            try:
                file_size = self.__mediainfo['General'][0]['FileSize']
                stream_size = self.__mediainfo['Video'][0]['StreamSize']
            except:
                return False
            return file_size > stream_size
        return None

    def __eq__(self, other):

        return self.__mediainfo == other

    def _check_languages(self, languages, track_lang):
        """
        Check if track language matches any defined languges

        """

        if languages:
            return track_lang in languages
        return True

    def get_audio_info(
        self,
        language: str | list[str] | None = None,
    ) -> dict | None:
        """
        Get audio stream information from a video

        Audio stream information is obtained using information from the
        mediainfo command and parsing it into a dictionary in a format that
        allows for input into ffmpeg command for transcoding.

        Arguments:
            None

        Keyword arguments:
            language (str,list): Language(s) for audio tracks.
                Must be ISO 639-2 codes.

        Returns:
            dict: Information in a format for input into the ffmpeg command.

        """

        self.__log.info('Parsing audio information...')
        if self.__mediainfo is None:
            self.__log.warning('No media information!')
            return None
        if 'Audio' not in self.__mediainfo:
            self.__log.warning('No audio information!')
            return None

        if isinstance(language, str):
            language = [language]
        elif isinstance(language, list):
            language = language.copy()

        info = {
            '-map': [],
            '-codec': [],
            '-title': [],
            '-language': [],
            'order': ('-map', '-codec', '-title', '-language'),
            'file_info': [],
        }
        track_id = '1'
        track_num = 0

        # Run a check for audio track languages. Ran into case where movie
        # only had non-English languages and so would not convert movie.
        # So, here we will update
        nmatch = 0
        track_langs = []
        for track in self.__mediainfo['Audio']:
            lang3 = track.get('Language_String3', '')
            track_langs.append(lang3)

            # Count number of tracks match request language
            nmatch += self._check_languages(language, lang3)

        if nmatch == 0:
            self.__log.warning(
                "Failed to find any audio tracks matching requested "
                "language(s): %s. Adding language of first audio track "
                "to the search: %s",
                language,
                track_langs[0],
            )
            language.append(track_langs[0])

        for track in self.__mediainfo['Audio']:
            lang3 = track.get('Language_String3', '')

            # If track language does not match requested, skip it
            if not self._check_languages(language, lang3):
                continue

            fmt = track.get('Format', '')
            n_chan = track.get('Channels', '')
            # lang1  = track.get( 'Language_String',  '' )
            lang2 = track.get('Language_String2', '')
            title = track.get('Title', f"Source Track: {track_id}")

            # If n_chan is of type string, split number of channels for the
            # audio stream on forward slash, convert all to integer type,
            # take maximum; some DTS streams have 6 or 7 channel layouts
            if isinstance(n_chan, str):
                n_chan = max(
                    map(int, n_chan.split('/'))
                )

            # Set default language to English
            lang2 = lang2.upper() + '_' if lang2 != '' else 'EN_'
            try:
                mapping = track['StreamOrder'].split('-')
            except:
                mapping = ['0', str(track['StreamOrder'])]
            mapping = ':'.join(mapping)

            info['file_info'].append(
                '-'.join((lang2 + fmt).split())
            )

            # If there are more than 2 audio channels
            if n_chan > 2:
                info['-map'].extend(['-map', mapping])
                info['-codec'].extend([f"-c:a:{track_num}", 'copy'])
                info['-title'].append(f"-metadata:s:a:{track_num}")
                info['-title'].append(f"title={title} - {fmt}")
                info['-language'].append(f"-metadata:s:a:{track_num}")
                info['-language'].append(f"language={lang3}")
            else:
                info['-map'].extend(['-map', mapping])
                info['-codec'].extend([f"-c:a:{track_num}", 'copy'])
                info['-title'].append(f"-metadata:s:a:{track_num}")
                info['-title'].append(
                    'title=stereo'
                    if n_chan == 2 else
                    'title=mono'
                )
                info['-language'].append(f"-metadata:s:a:{track_num}")
                info['-language'].append(f"language={lang3}")

            track_id = str(int(track_id) + 1)
            track_num += 1

        if len(info['-map']) == 0:
            self.__log.warning('NO audio stream(s) selected...')
            return None

        return info

    def get_video_info(
        self,
        x265: bool = False,
        dolby_vision_file: str | None = None,
        hdr10plus_file: str | None = None,
    ) -> dict | None:
        """
        Get video stream information from a video

        Video stream information is obtained using information from the
        mediainfo command and parsing it into a dictionary in a format that
        allows for input into ffmpeg command for transcoding. Rate factors for
        different resolutions are the mid-points from the ranges provided by:
        https://handbrake.fr/docs/en/latest/workflow/adjust-quality.html

            - RF 18-22 for 480p/576p Standard Definition
            - RF 19-23 for 720p High Definition
            - RF 20-24 for 1080p Full High Definition
            - RF 22-28 for 2160p 4K Ultra High Definition

        Rate factors used:
            - 22 :  480p/576p
            - 23 :  720p
            - 24 : 1080p
            - 20 : 2160p

        Arguments:
            None

        Keyword arguments:
            x265 (bool): Set to force x265 encoding.
            dolby_vision_file (str) : Path to Dolby Vision metadata file
            hdr10plus_file (str) : Path to HDF10+ metadata file

        Returns:
            dict: Information in a format for input into the ffmpeg command.

        """

        self.__log.info('Parsing video information...')
        if self.__mediainfo is None:
            self.__log.warning('No media information!')
            return None
        if 'Video' not in self.__mediainfo:
            self.__log.warning('No video information!')
            return None
        if len(self.__mediainfo['Video']) > 1:
            self.__log.error('More than one (1) video stream...Stopping!')
            return None

        encoder = ''
        video_data = self.__mediainfo['Video'][0]

        # Get stream order; check for integer
        try:
            mapping = video_data['StreamOrder'].split('-')
        except:
            mapping = ['0', str(video_data['StreamOrder'])]
        mapping = ':'.join(mapping)

        info = {
            'order': ('-map', '-filter', '-opts'),
        }
        for tag in info['order']:
            info[tag] = []

        info['-map'].extend(['-map', mapping])

        # Set resolution and rate factor based on video height
        resolution, crf = set_resolution(video_data['Height'])

        if resolution <= 1080 and not x265:
            encoder = 'x264'
            info['-opts'].extend(
                [
                    '-c:v', 'libx264',
                    '-preset', 'slow',
                    '-profile:v', 'high',
                    '-level', '4.0',
                    '-crf', str(crf),
                ]
            )
        else:
            encoder = 'x265'
            bit_depth = video_data.get('BitDepth', '')
            opts = self.get_x265_opts(
                video_data,
                crf,
                dolby_vision_file,
                hdr10plus_file,
            )

            info['-opts'].extend(
                [
                    '-c:v', 'libx265',
                    '-preset', 'slow',
                    '-profile:v', f'main{bit_depth}',
                    '-level', '5.1',
                    *opts,
                ]
            )

        # Deinterlace video; send_frame is one frame for each frame
        if video_data.get('ScanType', '').upper() == 'INTERLACED':
            info['-filter'].append('bwdif=send_frame:auto:all')

        info['file_info'] = [f'{resolution}p', encoder]

        aspect_filter = aspect_adjust(video_data)
        if aspect_filter:
            info['-filter'].append(aspect_filter)

        if len(info['-filter']) > 0:
            info['-filter'] = ['-vf', ','.join(info['-filter'])]
        return info

    def get_x265_opts(
        self,
        video_data: dict,
        crf: int,
        dolby_vision_file: str | None,
        hdr10plus_file: str | None,
    ) -> list[str]:
        """
        Get options for x265 encoding

        Build options for x265, namely HDR encoding flags

        """

        x265_opts = ["pools=none", f"crf={crf}"]
        hdr_opts = get_hdr_opts(self.infile)
        if hdr_opts is None:
            return ["-x265-params", ":".join(x265_opts)]

        pix_fmt, hdr_opts = hdr_opts

        opts = ["-pix_fmt", pix_fmt]
        x265_opts.extend(hdr_opts)

        # Define a maximum for vbv-maxrate at 20 Mbps
        # Try to get max bit rate from video_data (using maxrate as default).
        # Then take the smaller of the 2 values and convert to Kbps
        maxrate = 20 * 10**6
        vbv_maxrate = video_data.get('BitRate', maxrate)
        vbv_maxrate = min(vbv_maxrate, maxrate) // 1000
        vbv_bufsize = 2 * vbv_maxrate

        x265_opts.extend(
            [f"vbv-maxrate={vbv_maxrate}", f"vbv-bufsize={vbv_bufsize}"]
        )

        if dolby_vision_file:
            x265_opts.extend(
                [
                    "dolby-vision-profile=8.1",
                    f"dolby-vision-rpu={dolby_vision_file}",
                ]
            )
        if hdr10plus_file:
            x265_opts.extend(
                ["dhdr10-opt=1", f"dhdr10-info={hdr10plus_file}"]
            )

        return opts + ["-x265-params", ":".join(x265_opts)]

    def get_text_info(self, languages: str | list[str]) -> dict | None:
        """
        Get text stream information from a video

        Video stream information is obtained using information from the
        mediainfo command and parsing it into a dictionary in a format for
        use in either the :meth:`video_utils.subtitles.subtitle_extract` or
        :meth:`video_utils.subtitles.ccextract` functions to extract the text
        to individual files and/or convert the text to SRT format.

        Arguments:
            language (str,list): Language(s) for text streams.
                Must be ISO 639-2 codes.
                Note that language selection is not currently
                available for mpeg transport streams with CC
                muxed into video as mediainfo gives no information
                on CC languagues (20190217)

        Keyword arguments:
            None

        Returns:
            dict : Dictionary containing the 3 different language strings,
                the output extension to be used on the subtitle file, and the
                MKV ID used to identify tracks in MKVToolNix for each text
                stream of interest. Returns None if NO text streams found.

        Note:
            (20190219) - While this method will parse information from all the
            text streams in the file, the ccextract
            function currently only extracts the first CC stream as
            there is not clear documentation on how to extract
            specific streams and mediainfo does not return any
            language information for the streams

        """

        self.__log.info('Parsing text information...')
        if self.__mediainfo is None:
            self.__log.warning('No media information!')
            return None
        if 'Text' not in self.__mediainfo:
            self.__log.warning('No text information!')
            return None
        if isinstance(languages, str):
            languages = [languages]
        else:
            languages = languages.copy()

        mpegts = self.__mediainfo['General'][0]['Format'] == 'MPEG-TS'

        # Initialize a counter, a list for all out file extensions,
        # a list to store the number of elements in each text stream,
        # and a dictionary
        j, n_elems, info = 0, [], []
        for track in self.__mediainfo['Text']:
            lang3 = track.get('Language_String3', '')
            if (not mpegts) and (lang3 not in languages):
                continue
            idx = track.get('StreamOrder', '')
            lang1 = track.get('Language_String', '')
            lang2 = track.get('Language_String2', '')
            elems = track.get('ElementCount', '0')
            frames = track.get('FrameCount', '0')

            forced = track.get('Forced', '').upper() == 'YES'

            # Iterate over the 3 language code formats and add to list
            # ONLY if they are not an empty string. Then, we take the
            # zeroth element if there are any elements, else we just use
            # an empty string
            lang = [_lang for _lang in (lang3, lang2, lang1) if _lang != '']
            lang = lang[0] if len(lang) > 0 else ''

            # Append the number of VobSub images to the sub_elems list
            # Or number of vobsub frames
            n_elems.append(max(int(elems), int(frames), 0))

            track_info = {
                'format': track.get('Format', ''),
                'lang1': lang1,
                'lang2': lang2,
                'lang3': lang3,
                'ext': f".{j}.{lang}",
                'forced': forced,
                'track': j,
                'vobsub': False,
                'srt': False,
            }
            if not mpegts:
                track_info.update({'mkvID': idx})

            info.append(track_info)
            j += 1

        if len(n_elems) == 0:
            self.__log.warning('NO text stream(s) in file...')
            return None

        # Double check forced flag
        # Get maximum number of elements over all text streams
        max_elems = float(max(n_elems))
        for i, elem in enumerate(n_elems):
            if max_elems > 0 and (elem / max_elems) < 0.1:
                info[i]['ext'] += '.forced'
                info[i]['forced'] = True

        if len(info) > 0:
            return info

        return None


def aspect_adjust(video_data: dict) -> str:
    """
    Check video aspect ratio

    Have run into movies that are 'widescreen', but the
    aspect ratio gets goofy and is displayed as full screen.
    This function acts to fix that by checking the Display and
    Original aspect ratios and adjust the aspect ratio accordingly.

    Arguments:
        video_data (dict) : Information about video stream from mediainfo.

    Returns:
        str : Empty string if no adjustment needed,
            otherwise is a video filter.

    """

    dar = video_data.get('DisplayAspectRatio', None)
    odar = video_data.get('OriginalDisplayAspectRatio', None)
    if (dar is None) or (odar is None) or (dar == odar):
        return ''

    xpix, ypix = video_data['DisplayAspectRatio_String'].split(':')
    width = video_data['Height'] * float(xpix) / float(ypix)
    width -= (width % 16)

    return f"setsar={width:.0f}:{video_data['Width']:.0f}"


def num_convert(val: str) -> int | float | str:
    """
    Convert string to int/float

    """

    if not isinstance(val, str):
        return val

    if val.isdigit():
        return int(val)

    try:
        return float(val)
    except:
        return val


def set_resolution(video_height: int) -> tuple[int]:
    """
    Determine video resolution

    Given the height (in pixels) of the video,
    determine the resolution and the constant
    rate factor for transcoding.

    Arguments:
        video_height (int) : The height (in pixles) of
            the source video.

    Returns:
        tuple : Resolution of the video (int) and the
            constant rate factor options (list) for ffmpeg

    """

    if video_height <= 480:
        return 480, 22
    if video_height <= 720:
        return 720, 23
    if video_height <= 1080:
        return 1080, 24

    return 2160, 20


def mediainfo(fname: str) -> dict:
    """
    Parse mediainfo JSON output

    Parse the JSON formatted output of the mediainfo
    command into a format that is similar to that
    parsed from the OLDXML style

    """

    cmd = ['mediainfo', '--Full', '--Output=JSON', fname]
    res = check_output(cmd)
    data = json.loads(res)

    out = {}
    for track in data['media']['track']:
        track_type = track['@type']
        if track_type not in out:
            out[track_type] = []
        out[track_type].append(
            {key: num_convert(val) for key, val in track.items()}
        )

    for val in out.values():
        val.sort(key=lambda x: x.get('@typeorder', 0))

    return out
