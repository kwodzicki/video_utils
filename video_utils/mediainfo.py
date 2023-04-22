"""
Wrapper class for mediainfo CLI

"""

import logging
import re
import json
from subprocess import check_output

try:
    output = check_output( ['mediainfo', '--version'] )
except:
    MediaInfoLib = None
else:
    MediaInfoLib = (
        re.findall( rb'v(\d+(?:.\d+)+)', output )[0]
        .decode()
        .split('.')
    )

def num_convert( val ):
    """
    Convert string to int/float

    """

    if not isinstance(val, str):
        return val

    if val.isdigit():
        return int(val)

    try:
        return float( val )
    except:
        return val

def set_resolution(video_height):
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
        return 480, ['-crf', '22']
    if video_height <= 720:
        return 720, ['-crf', '23']
    if video_height <= 1080:
        return 1080, ['-crf', '24']

    return 2160, ['-x265-params', 'crf=24:pools=none']

def mediainfo( fname ):
    """
    Parse mediainfo JSON output

    Parse the JSON formatted output of the mediainfo
    command into a format that is similar to that 
    parsed from the OLDXML style

    """

    cmd  = ['mediainfo', '--Full', '--Output=JSON', fname]
    res  = check_output( cmd )
    data = json.loads(res)

    out = {}
    for track in data['media']['track']:
        track_type = track['@type']
        if track_type not in out:
            out[ track_type ] = []
        out[ track_type ].append(
            {key : num_convert(val) for key, val in track.items()}
        )

    for val in out.values():
        val.sort( key=lambda x: x.get('@typeorder', 0) )

    return out

class MediaInfo( ):
    """Class that acts as wrapper for mediainfo CLI"""

    def __init__( self, infile = None, **kwargs ):
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
        self.__log  = logging.getLogger(__name__)
        self.infile = infile

    @property
    def infile(self):
        """Return the input file path"""
        return self.__infile
    @infile.setter
    def infile(self, value):
        """Set the input file path"""
        self.__infile = value
        if self.__infile is None:
            self.__mediainfo = None
        else:
            self.__mediainfo = mediainfo( value )
#          self.__parse_output()
    @property
    def format(self):
        """Full name of file format; e.g., MPEG-4, Matroska"""

        if self.__mediainfo:
            return self.__mediainfo['General'][0]['Format']
        return None

    def __getitem__(self, key):
        """Method for easily getting key from mediainfo; similar to dict[key]"""

        return self.__mediainfo[key]

    def __setitem__(self, key, value):
        """Method for easily setting key in mediainfo; similar to dict[key] = value"""

        self.__mediainfo[key] = value

    def get(self, *args):
        """Method for geting mediainfo keys; similar to dict.get()"""

        return self.__mediainfo.get(*args)

    def keys(self):
        """Method for geting mediainfo keys; similar to dict.keys()"""

        return self.__mediainfo.keys()

    def videoSize(self):
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

    ##############################################################################
    def isValidFile(self):
        """ 
        Check if file is valid.

        This is done by checking that the size of the first video stream is less than
        the size of the file. This many not work in all cases, but seems to be
        true for MPEGTS files.

        """

        if self.__mediainfo:
            try:
                file_size   = self.__mediainfo['General'][0]['FileSize'  ]
                stream_size = self.__mediainfo['Video'  ][0]['StreamSize']
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

    ################################################################################
    def get_audio_info( self, language = None ):
        """ 
        Get audio stream information from a video

        Audio stream information is obtained using information from the mediainfo
        command and parsing it into a dictionary in a format that allows for input
        into ffmpeg command for transcoding.

        Arguments:
            None

        Keyword arguments:
            language (str,list): Language(s) for audio tracks. Must be ISO 639-2 codes.

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
        if language is not None and not isinstance( language, (list, tuple) ):
            language = (language,)

        info = {
            '-map'       : [],
            '-codec'     : [],
            '-title'     : [],
            '-language'  : [],
            'order'      : ('-map', '-codec', '-title', '-language'),
            'file_info'  : [],
        }
        track_id  = '1'
        track_num = 0
        for track in self.__mediainfo['Audio']:
            lang3 = track.get( 'Language_String3', '' )

            # If track language does not match requested, skip it
            if not self._check_languages( language, lang3 ):
                continue

            fmt    = track.get( 'Format',           '' )
            n_chan = track.get( 'Channels',         '' )
            #lang1  = track.get( 'Language_String',  '' )
            lang2  = track.get( 'Language_String2', '' )
            title  = track.get( 'Title',            f"Source Track: {track_id}" )

            # If n_chan is of type string, split number of channels for the
            # audio stream on forward slash, convert all to integer type,
            # take maximum; some DTS streams have 6 or 7 channel layouts
            if isinstance(n_chan, str):
                n_chan = max( map( int, n_chan.split('/') ) )

            # Set default language to English
            lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_'
            try:
                mapping = track['StreamOrder'].split('-')
            except:
                mapping = ['0', str(track['StreamOrder'])]
            mapping = ':'.join( mapping )

            info['file_info'].append( '-'.join( (lang2 + fmt).split() ) )

            # If there are more than 2 audio channels
            if n_chan > 2:
                info['-map'     ].extend( [ '-map', mapping]            )
                info['-codec'   ].extend( [f"-c:a:{track_num}", 'copy'] )
                info['-title'   ].append(  f"-metadata:s:a:{track_num}" )
                info['-title'   ].append(  f"title={title} - {fmt}"     )
                info['-language'].append(  f"-metadata:s:a:{track_num}" )
                info['-language'].append(  f"language={lang3}"          )
            else:
                info['-map'  ].extend( [ '-map', mapping]            )
                info['-codec'].extend( [f"-c:a:{track_num}", 'copy'] )
                info['-title'].append(  f"-metadata:s:a:{track_num}" )
                info['-title'].append(
                    'title=stereo'
                    if n_chan == 2 else
                    'title=mono'
                )
                info['-language'].append( f"-metadata:s:a:{track_num}" )
                info['-language'].append( f"language={lang3}"          )

            track_id   = str( int(track_id) + 1 )
            track_num += 1

        if len(info['-map']) == 0:
            self.__log.warning( 'NO audio stream(s) selected...' )
            return None

        return info

    ################################################################################
    def get_video_info( self, x265 = False ):
        """
        Get video stream information from a video

        Video stream information is obtained using information from the mediainfo
        command and parsing it into a dictionary in a format that allows for input
        into ffmpeg command for transcoding. Rate factors for different resolutions
        are the mid-points from the ranges provided by:
        https://handbrake.fr/docs/en/latest/workflow/adjust-quality.html

            - RF 18-22 for 480p/576p Standard Definition
            - RF 19-23 for 720p High Definition
            - RF 20-24 for 1080p Full High Definition
            - RF 22-28 for 2160p 4K Ultra High Definition

        Rate factors used:
            - 22 :  480p/576p
            - 23 :  720p
            - 24 : 1080p
            - 24 : 2060p

        Arguments:
            None

        Keyword arguments:
            x265 (bool): Set to force x265 encoding.

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
        if len( self.__mediainfo['Video'] ) > 1:
            self.__log.error('More than one (1) video stream...Stopping!')
            return None

        encoder    = ''
        video_data = self.__mediainfo['Video'][0]
        video_tags = video_data.keys()

        # Get stream order; check for integer
        try:
            mapping = video_data['StreamOrder'].split('-')
        except:
            mapping = ['0', str( video_data['StreamOrder'] )]
        mapping = ':'.join( mapping )

        info = {
            'order' : ('-map', '-filter', '-opts'),
        }
        for tag in info['order']:
            info[tag] = []

        info['-map'].extend( ['-map', mapping] )

        if video_data['Height'] <= 1080 and not x265:
            encoder = 'x264'
            info['-opts'].extend(
                [
                    '-c:v',       'libx264',
                    '-preset',    'slow',
                    '-profile:v', 'high',
                    '-level',     '4.0',
                ]
            )
        else:
            encoder   = 'x265'
            bit_depth = video_data.get('BitDepth', '')
            info['-opts'].extend(
                [
                    '-c:v',        'libx265',
                    '-preset',     'slow',
                    '-profile:v', f'main{bit_depth}',
                    '-level',      '5.0',
                ]
            )

        # Set resolution and rate factor based on video height
        resolution, crf_opts = set_resolution( video_data['Height'] )
        info['-opts'].extend( crf_opts )

        # I cannot remember why there is the extra check for 'Frame_rate_mode'
        # Removing for now, but will test with some MakeMKV files
        if 'Scan_type' in video_tags:
            if video_data['Scan_type'].upper() != 'PROGRESSIVE':
                info['-filter'].append( 'yadif' )
#        if 'Scan_type' in video_tags and 'Frame_rate_mode' in video_tags:
#          if video_data['Scan_type'].upper() != 'PROGRESSIVE':
#            if video_data['Frame_rate_mode']  == 'CFR':
#              info['-filter'].append( 'yadif' )

        info['file_info'] = [f'{resolution}p', encoder]

        if 'Display_aspect_ratio' in video_tags and \
           'Original_display_aspect_ratio' in video_tags:
            if video_data['Display_aspect_ratio'] != \
               video_data['Original_display_aspect_ratio']:
                xpix, ypix = video_data['Display_aspect_ratio/String'].split(':')
                width      = video_data['Height'] * float(xpix)/float(ypix)
                width     -= (width % 16)
                info['-filter'].append(
                    f"setsar={width:.0f}:{video_data['Width']:.0f}" 
                )

        if len(info['-filter']) > 0:
            info['-filter'] = ['-vf', ','.join(info['-filter'])]
        return info

    ################################################################################
    def get_text_info( self, languages ):
        """
        Get text stream information from a video

        Video stream information is obtained using information from the mediainfo
        command and parsing it into a dictionary in a format for use in either the
        :meth:`video_utils.subtitles.subtitle_extract` or 
        :meth:`video_utils.subtitles.ccextract` functions to extract the text to
        individual files and/or convert the text to SRT format.

        Arguments:
            language (str,list): Language(s) for text streams.Must be ISO 639-2 codes.
                Note that language selection is not currently
                available for mpeg transport streams with CC
                muxed into video as mediainfo gives no information
                on CC languagues (20190217)

        Keyword arguments:
            None

        Returns:
            dict : Dictionary containing the 3 different language strings, the output
                extension to be used on the subtitle file, and the MKV ID used
                to identify tracks in MKVToolNix for each text stream of interest.
                Returns None if NO text streams found.

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
        if not isinstance( languages, (list, tuple) ):
            languages = (languages,)

        mpegts = self.__mediainfo['General'][0]['Format'] == 'MPEG-TS'

        # Initialize a counter, a list for all out file extensions,
        # a list to store the number of elements in each text stream,
        # and a dictionary
        j, n_elems, info = 0, [], []
        for track in self.__mediainfo['Text']:
            lang3  = track.get( 'Language_String3', '' )
            if (not mpegts) and (lang3 not in languages):
                continue
            idx    = track.get( 'StreamOrder',       ''  )
            lang1  = track.get( 'Language_String',   ''  )
            lang2  = track.get( 'Language_String2',  ''  )
            elems  = track.get( 'ElementCount',      '0' )
            frames = track.get( 'FrameCount',        '0' )

            forced = track.get('Forced', '').upper() == 'YES'

            # Iterate over the 3 language code formats and add to list
            # ONLY if they are not an empty string. Then, we take the
            # zeroth element if there are any elements, else we just use
            # an empty string
            lang = [_lang for _lang in (lang3, lang2, lang1) if _lang != '']
            lang = lang[0] if len(lang) > 0 else ''

            # Append the number of VobSub images to the sub_elems list
            # Or number of vobsub frames
            n_elems.append( max(int(elems), int(frames), 0) )

            track_info = {
                'format' : track.get('Format', ''), 
                'lang1'  : lang1,
                'lang2'  : lang2,
                'lang3'  : lang3,
                'ext'    : f".{j}.{lang}",
                'forced' : forced,
                'track'  : j,
                'vobsub' : False,
                'srt'    : False,
            }
            if not mpegts:
                track_info.update( {'mkvID' : idx} )

            info.append(track_info)
            j+=1

        if len(n_elems) == 0:
            self.__log.warning(  'NO text stream(s) in file...')
            return None

        # Double check forced flag
        # Get maximum number of elements over all text streams
        max_elems = float( max(n_elems) )
        for i, elem in enumerate(n_elems):
            if max_elems > 0 and (elem / max_elems) < 0.1:
                info[i]['ext']    += '.forced'
                info[i]['forced']  = True

        if len(info) > 0:
            return info

        return None
