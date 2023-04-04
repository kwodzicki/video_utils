"""
Wrapper class for mediainfo CLI

"""

import logging
import re
import json
import subprocess as subproc


cmd  = ['mediainfo', '--version']
try:
    proc = subproc.Popen( cmd, stdout = subproc.PIPE, stderr = subproc.PIPE )
except:
    MediaInfoLib = None
else:
    stdout, stderr = proc.communicate()
    MediaInfoLib = (
        re.findall( b'v(\d+(?:.\d+)+)', stdout )[0]
        .decode()
        .split('.')
    )
    del proc, stdout, stderr

del cmd

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

def mediainfo( fname ):
    """
    Parse mediainfo JSON output

    Parse the JSON formatted output of the mediainfo
    command into a format that is similar to that 
    parsed from the OLDXML style

    """

    cmd  = ['mediainfo', '--Full', '--Output=JSON', fname]
    res  = subproc.check_output( cmd )
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

    def __init__( self, inFile = None, **kwargs ):
        """
        Initialize MediaInfo class

        The mediainfo CLI is run with full output to XML format. The XML data
        returned is then parsed into a dictionary using the xml.etree library.

        Arguments:
           None

        Keyword arguments:
           inFile (str): Path of file to run mediainfo on
           Various others...

        Returns:
          MediaInfo object

        """

        super().__init__(**kwargs)
        self.__log  = logging.getLogger(__name__)
        self.inFile = inFile

    @property
    def inFile(self):
        return self.__inFile
    @inFile.setter
    def inFile(self, value):
        self.__inFile = value
        if self.__inFile is None:
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

    ##############################################################################
    def __parse_output(self):
        """Method that will run when the file attribute is changed"""

        self.__log.info('Running mediainfo command...')
        xmlstr = subproc.check_output( self.cmd  + [self.inFile] )
        root   = ET.fromstring( xmlstr )
        data   = {}

        # Iterate over all tracks in the XML tree
        for track in root[0].findall('track'):
            tag = track.attrib['type']
            if 'typeorder' in track.attrib or 'streamid' in track.attrib:
                if tag not in data:
                    data[ tag ] = [ ]
                data[ tag ].append( {} )
            else:
                data[ tag ] = [ {} ]

        # Iterate over all tracks in the XML tree
        for track in root[0].findall('track'):
            tag, order = track.attrib['type'], 0
            old_tag, tag_cnt = '', 0
            if 'typeorder' in track.attrib:
                order = int( track.attrib['typeorder'] ) - 1
            elif 'streamid' in track.attrib:
                order = int( track.attrib['streamid'] ) - 1

            # Iterate over all elements in the track
            for elem in track.iter():
                cur_tag = elem.tag
                if cur_tag == old_tag:
                    cur_tag += '/String'
                    if tag_cnt > 1:
                        cur_tag += str(tag_cnt)
                    tag_cnt += 1
                else:
                    tag_cnt = 0
                old_tag = elem.tag
                if '.' in elem.text:
                    try:
                        data[tag][order][cur_tag] = float(elem.text)
                    except:
                        data[tag][order][cur_tag] = elem.text
                else:
                    try:
                        data[tag][order][cur_tag] = int(elem.text)
                    except:
                        data[tag][order][cur_tag] = elem.text
        self.__mediainfo = None if len(data) == 0 else data

    def __eq__(self, other):

        return self.__mediainfo == other

    def _check_languages(self, languages, track_lang):
        """
        Check if track language matches any defined languges

        """

        if languages:
            for lang in languages:
                if lang != track_lang and track_lang != '':
                    return False
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
            lang1  = track.get( 'Language_String',  '' )
            lang2  = track.get( 'Language_String2', '' )
            title  = track.get( 'Title',            f"Source Track: {track_id}" )

            # If n_chan is of type string, split number of channels for the
            # audio stream on forward slash, convert all to integer type,
            # take maximum; some DTS streams have 6 or 7 channel layouts
            if type(n_chan) is str:
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
        resolution = None
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
        if video_data['Height'] <= 480:
            resolution = 480
            info['-opts'].extend( ['-crf', '22'] )
        elif video_data['Height'] <= 720:
            resolution =  720
            info['-opts'].extend( ['-crf', '23'] )
        elif video_data['Height'] <= 1080:
            resolution = 1080
            info['-opts'].extend( ['-crf', '24'] )
        else:#if video_data['Height'] <= 2160:
            resolution = 2160
            #info['-opts'].extend( ['-crf', '26'] )
            info['-opts'].extend( ['-x265-params', 'crf=24:pools=none'] )
        if resolution is None:
            return None

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
        for language in languages:
            for track in self.__mediainfo['Text']:
                lang3  = track.get( 'Language_String3', '' )
                if (not mpegts) and (language != lang3):
                    continue
                idx    = track.get( 'StreamOrder',       '' )
                lang1  = track.get( 'Language_String',   '' )
                lang2  = track.get( 'Language_String2',  '' )
                elems  = track.get( 'count_of_elements', '' )
                frames = track.get( 'Frame_count',       '' )
                if 'Forced' in track:
                    forced = track['Forced'].lower() == 'yes'
                else:
                    forced = False

                lang = ''
                if lang3 != '':
                    lang = lang3# Append 2 character language code
                elif lang2 != '':
                    lang = lang2# Append 3 character language code
                elif lang1 != '':
                    lang = lang1# Append full language string

                # Append the number of VobSub images to the sub_elems list
                # Or number of vobsub frames
                if elems  != '':
                    n_elems.append( int(elems) )
                elif frames != '':
                    n_elems.append( int(frames) )
                else:
                    n_elems.append( 0 )

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
            if max_elems > 0:
                if (elem / max_elems) < 0.1:
                    info[i]['ext']    += '.forced'
                    info[i]['forced']  = True

        if len(info) > 0:
            return info

        return None
