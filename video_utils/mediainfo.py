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
  MediaInfoLib = re.findall( b'v(\d+(?:.\d+)+)', stdout )[0].decode().split('.') # Find all instances of version string and get numbers
  del proc, stdout, stderr
del cmd

def numConvert( val ):
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
        trackType = track['@type']
        if trackType not in out:
            out[ trackType ] = []
        out[ trackType ].append(
            {key : numConvert(val) for key, val in track.items()}
        )

    for val in out.values():
        val.sort( key=lambda x: x.get('@typeorder', 0) )

    return out
 
class MediaInfo( object ):
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
    self.cmd    = ['mediainfo', '--Full', '--Output={}'.format(OUTPUT_FMT) ]  # The base command for mediainfo; just add [self.inFile]
    self.inFile = inFile

  ################################################################################
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
#      self.__parse_output()
  @property
  def format(self):
    """Full name of file format; e.g., MPEG-4, Matroska"""

    if self.__mediainfo:
      return self.__mediainfo['General'][0]['Format']
    else:
      return None

  ##############################################################################
  def __getitem__(self, key):
    """Method for easily getting key from mediainfo; similar to dict[key]"""

    return self.__mediainfo[key]

  ##############################################################################
  def __setitem__(self, key, value):
    """Method for easily setting key in mediainfo; similar to dict[key] = value"""

    self.__mediainfo[key] = value

  ##############################################################################
  def get(self, *args):
    """Method for geting mediainfo keys; similar to dict.get()"""

    return self.__mediainfo.get(*args)

  ##############################################################################
  def keys(self):
    """Method for geting mediainfo keys; similar to dict.keys()"""

    return self.__mediainfo.keys()

  ##############################################################################
  def videoSize(self):
    """ 
    Method to get dimensions of video

    Returns:
      tuple: Video (width, height) if video stream exists. None otherwise.

    """

    tmp = self.get('Video', [])
    if len(tmp) > 0:
      try:
        return (tmp[0]['Width'], tmp[0]['Height'],)
      except:
        pass
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
        fileSize   = self.__mediainfo['General'][0]['FileSize'  ]
        streamSize = self.__mediainfo['Video'  ][0]['StreamSize']
      except:
        return False
      else:
        return fileSize > streamSize
    return None

  ##############################################################################
  def __parse_output(self):
    """Method that will run when the file attribute is changed"""

    self.__log.info('Running mediainfo command...')                              # If verbose is set, print some output
    xmlstr = subproc.check_output( self.cmd  + [self.inFile] )                # Run the command
    root   = ET.fromstring( xmlstr )                                           # Parse xml tree
    data   = {}
    for track in root[0].findall('track'):                                      # Iterate over all tracks in the XML tree
      tag = track.attrib['type']                                               # Get track type
      if 'typeorder' in track.attrib or 'streamid' in track.attrib:             # If typeorder is in the track.attrib dictionary
        if tag not in data: data[ tag ] = [ ]                                  # If the tag is NOT in the self.__mediainfo dictionary then create empty list in dictionary under track type in dictionary
        data[ tag ].append( {} )                                               # Append empty dictionary to list
      else:                                                                     # Else, typeorder is NOT in the track.attrib dictionary
        data[ tag ] = [ {} ]                                                   # create list with dictionary under track type in dictionary
  
    for track in root[0].findall('track'):                                      # Iterate over all tracks in the XML tree
      tag, order = track.attrib['type'], 0
      old_tag, tag_cnt = '', 0                                                 # initialize old_tag to an empty string and tag_cnt to zero (0)
      if 'typeorder' in track.attrib:
        order = int( track.attrib['typeorder'] ) - 1
      elif 'streamid' in track.attrib:
        order = int( track.attrib['streamid'] ) - 1
      for elem in track.iter():                                                 # Iterate over all elements in the track
        cur_tag = elem.tag                                                     # Set the cur_tag to the tag of the element in the track
        if cur_tag == old_tag:                                                  # If the current tag is the same as the old tag
          cur_tag += '/String'                                                 # Append string to the tag
          if tag_cnt > 1: cur_tag += str(tag_cnt)                              # If the tag_cnt is greater than one (1), then append the number to the tag
          tag_cnt += 1                                                         # Increment that tag_cnt by one (1);
        else:                                                                   # Else
          tag_cnt = 0                                                          # Set tag_cnt to zero (0)
        old_tag = elem.tag                                                     # Set the old_tag to the tag of the element in the track
        if '.' in elem.text:                                                    # If there is a period in the text of the current element
          try:                                                                  # Try to convert the text to a float
            data[tag][order][cur_tag] = float(elem.text)
          except:
            data[tag][order][cur_tag] = elem.text
        else:                                                                   # Else there is not period in the text of the current element
          try:                                                                  # Try to convert the text to an integer
            data[tag][order][cur_tag] = int(elem.text)
          except:
            data[tag][order][cur_tag] = elem.text
    self.__mediainfo = None if len(data) == 0 else data

  ################################################################################
  def __eq__(self, other): return self.__mediainfo == other

  ################################################################################
  def _checkLanguages(self, languages, trackLang):
    if languages:                                                                       # If languages defined
      for lang in languages:                                                            # Iterate over languages
        if lang != trackLang and trackLang != '':                                       # If the track language does NOT match the current language AND it is not an empty string
          return False                                                                  # Return False; i.e., no match
    return True                                                                         # Return True

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

    self.__log.info('Parsing audio information...')                              # If verbose is set, print some output
    if self.__mediainfo is None:         
      self.__log.warning('No media information!')                                # Print a message
      return None         
    if 'Audio' not in self.__mediainfo:         
      self.__log.warning('No audio information!')                                # Print a message
      return None        
    if language is not None and not isinstance( language, (list, tuple) ):              # If language defined and not iterable
      language = (language,)                                                            # Convert to tuple
  
    info = {
        '-map'       : [],
        '-codec'     : [],
        '-title'     : [],
        '-language'  : [],
        'order'      : ('-map', '-codec', '-title', '-language'),
        'file_info'  : [],
    }                                                 # Initialize a dictionary for storing audio information
    track_id  = '1'                                                             # Initialize a variable for counting the track number.
    track_num = 0
    for track in self.__mediainfo['Audio']:                                   # Iterate over all audio information
      lang3 = track.get( 'Language_String3', '' )
      if not self._checkLanguages( language, lang3 ): continue                          # If track language does not match requested, skip it
      fmt   = track.get( 'Format',           '' )
      nCH   = track.get( 'Channels',         '' )
      lang1 = track.get( 'Language_String',  '' )
      lang2 = track.get( 'Language_String2', '' )
      title = track.get( 'Title',            f"Source Track: {track_id}" )
      if type(nCH) is str: nCH = max( map( int, nCH.split('/') ) )                    # If nCH is of type string, split number of channels for the audio stream on forward slash, convert all to integer type, take maximum; some DTS streams have 6 or 7 channel layouts 
      lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_'                    # Set default language to English
      try:
          mapping = track['StreamOrder'].split('-')                          # Try to split StreamOrder on hyphen
      except:
          mapping = ['0', str(track['StreamOrder'])]                                 # On exception, assume StreamOrder is integer; convert to string and create own mapping
      mapping = ':'.join( mapping )                                                  # Join mapping list on colon
      info['file_info'].append( '-'.join( (lang2 + fmt).split() ) )                   # Append the language and format for the second strem, which is a copy of the orignal stream

      if nCH > 2:                                                                     # If there are more than 2 audio channels
        info['-map'     ].extend( [ '-map', mapping]                     )             # Append the track number to the --audio list
        info['-codec'   ].extend( [f"-c:a:{track_num}", 'copy'] )             # Append audio codecs to faac and copy
        info['-title'   ].append(  f"-metadata:s:a:{track_num}" )             # Append  audio track names
        info['-title'   ].append(  f"title={title} - {fmt}"    )
        info['-language'].append(  f"-metadata:s:a:{track_num}"  )             # Append  audio track names
        info['-language'].append(  f"language={lang3}"          )
      else:                                                                           # Else, there are 2 or fewer channels
        info['-map'  ].extend( [ '-map', mapping]                     )                # Append the track number to the --audio list
        info['-codec'].extend( [f"-c:a:{track_num}", 'copy'] )                # Append audio codecs to faac and copy
        info['-title'].append(  f"-metadata:s:a:{track_num}" )                # Append  audio track names
        if nCH == 2:                                                                  # If there are only 2 audio channels
          info['-title'].append( 'title=stereo' )
        else:                                                                         # Else, must be only a single channel
          info['-title'].append( 'title=mono'   )

        info['-language'].append( f"-metadata:s:a:{track_num}" )              # Append  audio track names
        info['-language'].append( f"language={lang3}"          )

      track_id   = str( int(track_id) + 1 )                                           # Increment audio track
      track_num += 1

    if len(info['-map']) == 0:                                                          # If the --audio list is NOT empty
      self.__log.warning(  'NO audio stream(s) selected...')                            # If verbose is set, print some output
      return None;

    return info                                                                         # If audio info was parsed, i.e., the '--audio' tag is NOT empty, then set the audio_info to the info dictionary      

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
     
    self.__log.info('Parsing video information...')                              # If verbose is set, print some output
    if self.__mediainfo is None:       
      self.__log.warning('No media information!')                                # Print a message
      return None        
    if 'Video' not in self.__mediainfo:        
      self.__log.warning('No video information!')                                # Print a message
      return None              
    if len( self.__mediainfo['Video'] ) > 1:         
      self.__log.error('More than one (1) video stream...Stopping!')             # Print a message
      return None                                                              # If the video has multiple streams, return
    encoder    = ''
    filters    = []
    resolution = None
    video_data = self.__mediainfo['Video'][0]                                  # Data for only video stream; done so var name is shorter
    video_tags = video_data.keys()                                             # Get all keys in the dictionary  
    try:
        mapping = video_data['StreamOrder'].split('-')                         # Try to split the StreamOrder data on hyphen
    except:
        mapping = ['0', str( video_data['StreamOrder'] )]                      # If there is an exception, assume StreamOrder is an integer and create mapping
    mapping = ':'.join( mapping )                                              # Join mapping using colon

    info = { 
        'order' : ('-map', '-filter', '-opts'),
    }
    for tag in info['order']: info[tag] = []

    info['-map'].extend( ['-map', mapping] )                                    # Initialize a dictionary for storing video information

    if video_data['Height'] <= 1080 and not x265:                               # If the video is 1080 or smaller and x265 is NOT set
      encoder = 'x264'
      info['-opts'].extend( 
        [
            '-c:v',       'libx264',
            '-preset',    'slow',                        # Set the video codec preset
            '-profile:v', 'high',                        # Set the video codec profile
            '-level',     '4.0',                        # Set the video codec level
        ]
      )
    else:                                                                       # Else, the video is either large or x265 has be requested
      encoder  = 'x265'
      bitDepth = video_data.get('Bit_depth', '')
      info['-opts'].extend( 
        [
            '-c:v',       'libx265',
            '-preset',    'slow',                          # Set the video codec preset
            'profile:v', f'main{bitDepth}',                      # Set the video codec profile
            '-level',     '5.0',                          # Set the video codec level
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
    if resolution is None: return None                                         # If resolution is NOT set, return None

    # I cannot remember why there is the extra check for 'Frame_rate_mode'
    # Removing for now, but will test with some MakeMKV files    
    if ('Scan_type' in video_tags):
      if video_data['Scan_type'].upper() != 'PROGRESSIVE':
        info['-filter'].append( 'yadif' )
#    if 'Scan_type' in video_tags and 'Frame_rate_mode' in video_tags:
#      if video_data['Scan_type'].upper() != 'PROGRESSIVE':
#        if video_data['Frame_rate_mode']  == 'CFR': 
#          info['-filter'].append( 'yadif' )

    info['file_info'] = [f'{resolution}p', encoder]
  
    if 'Display_aspect_ratio' in video_tags and \
       'Original_display_aspect_ratio' in video_tags:
      if video_data['Display_aspect_ratio'] != \
         video_data['Original_display_aspect_ratio']:
        x,y    = video_data['Display_aspect_ratio/String'].split(':')          # Get the x and y values of the display aspect ratio
        width  = video_data['Height'] * float(x)/float(y)                      # Compute new pixel width based on video height times the display ratio
        width -= (width % 16)                                                  # Ensure pixel width is multiple of 16
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
      Dictionary containing the 3 different language strings, the output
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

    self.__log.info('Parsing text information...')                               # If verbose is set, print some output
    if self.__mediainfo is None:       
      self.__log.warning('No media information!')                                # Print a message
      return None         
    if 'Text' not in self.__mediainfo:         
      self.__log.warning('No text information!')                                 # Print a message
      return None      
    if not isinstance( languages, (list, tuple) ): languages = (languages,)       # If language input is a scalar, convert to tuple

   
    mpegts = (self.__mediainfo['General'][0]['Format'] == 'MPEG-TS')

    j, n_elems, info = 0, [], []                                                 # Initialize a counter, a list for all out file extensions, a list to store the number of elements in each text stream, and a dictionary
    for language in languages:                                                         # Iterate over all languages
      for track in self.__mediainfo['Text']:                                             # Iterate over all text information
        lang3  = track.get( 'Language_String3', '' )
        if (not mpegts) and (language != lang3): continue                                               # If the track language does NOT matche the current language
        idx    = track.get( 'StreamOrder',       '' )                                   # Get track ID returning empty string if not in dictionary
        lang1  = track.get( 'Language_String',   '' )
        lang2  = track.get( 'Language_String2',  '' )
        elems  = track.get( 'count_of_elements', '' )
        frames = track.get( 'Frame_count',       '' )
        if 'Forced' in track:
          forced = True if track['Forced'].lower() == 'yes' else False
        else:
          forced = False

        if lang3 != '':  
          lang = lang3                                                # Append 2 character language code if language is present
        elif lang2 != '':   
          lang = lang2                                                # Append 3 character language code if language is present
        elif lang1 != '':  
          lang = lang1                                                # Append full language string

        if elems  != '':                                                          # If elems variable is NOT an empty string
          n_elems.append( int(elems) )                                           # Append the number of VobSub images to the sub_elems list
        elif frames != '':                                                        # If frames variable is NOT an empty string
          n_elems.append( int(frames) )                                          # Append the number of VobSub images to the sub_frames list
        else:                                                                     # If neither variable has a value
          n_elems.append( 0 )                                                    # Append zero

        info.append( 
            {
                'mkvID'  : idx ),
                'format' : track.get('Format', ''), 
                'lang1'  : lang1,
                'lang2'  : lang2,
                'lang3'  : lang3,
                'ext'    : f".{j}.{lang}",
                'forced' : forced,
                'track'  : j,
                'vobsub' : False,
                'srt'    : False,                                        # Update a dictionary to the list. vobsub and srt tags indicate whether a file exists or not
            }
        )
        j+=1                                                                     # Increment sub title track number counter
    if len(n_elems) == 0:                                                         # If subtitle streams were found
      self.__log.warning(  'NO text stream(s) in file...')                         # If verbose is set, print some output
      return None  

    # Double check forced flag
    max_elems = float( max(n_elems) )                                          # Get maximum number of elements over all text streams
    for i in range(len(n_elems)):                                               # Iterate over all extensions
      if max_elems > 0:                                                         # If the maximum number of elements in a text stream is greater than zero
        if (n_elems[i] / max_elems) < 0.1:   
          info[i]['ext']    += '.forced'                                       # If the number of VobSub images in a given track less than 10% of the number of images in the track with the most images, assume it contains forced subtitle and append '.forced' to the extension
          info[i]['forced']  = True

    if len(info) > 0:                                                           # If text info was parsed, i.e., the info dictionary is NOT empty,
      return info                                                              # Return the info dictionary

    return None                                                              # Return None
