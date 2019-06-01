import logging;
import re;
import subprocess as subproc;
from xml.etree import ElementTree as ET;

from video_utils.audio.DolbyDownmix import getDownmixFilter;

cmd  = ['mediainfo', '--version']
proc = subproc.Popen( cmd, stdout = subproc.PIPE, stderr = subproc.PIPE );
stdout, stderr = proc.communicate()
MediaInfoLib = re.findall( b'v(\d+(?:.\d+)+)', stdout )[0].decode().split('.'); # Find all instances of version string and get numbers
del cmd, proc, stdout, stderr;                                                  # Remove unneccesary variables

if int(MediaInfoLib[0]) > 17:                                                   # If the major version is greater than 17
  output_fmt = 'OLDXML';                                                        # Set the output format to OLDXML
elif (int(MediaInfoLib[0]) == 17) and (int(MediaInfoLib[1]) >= 10):             # Else, if the major version is 17 and the minor version is greater or equal to 10
  output_fmt = 'OLDXML';                                                        # Set the output format to OLDXML
else:                                                                           # Else
  output_fmt = 'XML';                                                           # Set output format to XML


class mediainfo( object ):
  def __init__( self, in_file = None ):
    '''
    Name:
       mediainfo
    Purpose:
       A python function to act as a wrapper for the 
       mediainfo CLI. The mediainfo command is run
       with full output to XML format. The XML data
       returned is then parsed into a dictionary
       using the xml.etree library.
    Inputs:
       file  : Full path to the file to get inforamtion
                 from.
    Outputs:
       Returns a dictionary of parsed information
       from the mediainfo CLI. The dictionary is
       arrange by information type (i.e., General
       Video, Audio, Text), with all the same keys
       as are present in the mediainfo command.
    Keywords:
       None.
    Dependencies:
      re, subprocess, xml
    Author and History:
       Kyle R. Wodzicki     Created 12 Sep. 2017
       
      Modified 14 Dec. 2018 by Kyle R. Wodzicki
        Changes mediainfo output type from XML to OLDXML as
        the xml tags have changes in newer versions.
    '''
    super().__init__();
    self.log     = logging.getLogger(__name__);
    self.cmd     = ['mediainfo', '--Full', '--Output={}'.format(output_fmt) ];  # The base command for mediainfo; just add [self.in_file]
    self.in_file = in_file;
  ################################################################################
  @property
  def in_file(self):
    return self.__in_file
  @in_file.setter
  def in_file(self, value):
    self.__in_file = value;
    if self.__in_file is None:
      self.__mediainfo = None;
    else:
      self.__parse_output();
  @property
  def format(self):
    if self.__mediainfo:
      return self.__mediainfo['General'][0]['Format'];
    else:
      return None;
  ##############################################################################
  def __getitem__(self, key):
    '''Method for easily getting key from mediainfo; acts a dict'''
    return self.__mediainfo[key]
  ##############################################################################
  def __setitem__(self, key, value):
    '''Method for easily setting key in mediainfo; acts a dict'''
    self.__mediainfo[key] = value
  ##############################################################################
  def keys(self):
    '''Method for geting mediainfo keys; acts a dict'''
    return self.__mediainfo.keys();
  ##############################################################################
  def __parse_output(self):
    ''' Method that will run when the file attribute is changed'''
    self.log.info('Running mediainfo command...');                              # If verbose is set, print some output
    xmlstr = subproc.check_output( self.cmd  + [self.in_file] );                # Run the command
    root   = ET.fromstring( xmlstr );                                           # Parse xml tree
    data   = {}
    for track in root[0].findall('track'):                                      # Iterate over all tracks in the XML tree
      tag = track.attrib['type'];                                               # Get track type
      if 'typeorder' in track.attrib or 'streamid' in track.attrib:             # If typeorder is in the track.attrib dictionary
        if tag not in data: data[ tag ] = [ ];                                  # If the tag is NOT in the self.__mediainfo dictionary then create empty list in dictionary under track type in dictionary
        data[ tag ].append( {} );                                               # Append empty dictionary to list
      else:                                                                     # Else, typeorder is NOT in the track.attrib dictionary
        data[ tag ] = [ {} ];                                                   # create list with dictionary under track type in dictionary
  
    for track in root[0].findall('track'):                                      # Iterate over all tracks in the XML tree
      tag, order = track.attrib['type'], 0;
      old_tag, tag_cnt = '', 0;                                                 # initialize old_tag to an empty string and tag_cnt to zero (0)
      if 'typeorder' in track.attrib:
        order = int( track.attrib['typeorder'] ) - 1;
      elif 'streamid' in track.attrib:
        order = int( track.attrib['streamid'] ) - 1;
      for elem in track.iter():                                                 # Iterate over all elements in the track
        cur_tag = elem.tag;                                                     # Set the cur_tag to the tag of the element in the track
        if cur_tag == old_tag:                                                  # If the current tag is the same as the old tag
          cur_tag += '/String';                                                 # Append string to the tag
          if tag_cnt > 1: cur_tag += str(tag_cnt);                              # If the tag_cnt is greater than one (1), then append the number to the tag
          tag_cnt += 1;                                                         # Increment that tag_cnt by one (1);
        else:                                                                   # Else
          tag_cnt = 0;                                                          # Set tag_cnt to zero (0)
        old_tag = elem.tag;                                                     # Set the old_tag to the tag of the element in the track
        if '.' in elem.text:                                                    # If there is a period in the text of the current element
          try:                                                                  # Try to convert the text to a float
            data[tag][order][cur_tag] = float(elem.text);
          except:
            data[tag][order][cur_tag] = elem.text;
        else:                                                                   # Else there is not period in the text of the current element
          try:                                                                  # Try to convert the text to an integer
            data[tag][order][cur_tag] = int(elem.text);
          except:
            data[tag][order][cur_tag] = elem.text;
    self.__mediainfo = None if len(data) == 0 else data;
  ################################################################################
  def __eq__(self, other): return self.__mediainfo == other;
  ################################################################################
  def get_audio_info( self, language, PLII = True ):
    '''
    Name:
      get_audio_info
    Purpose:
      A python function for getting audio stream information from a video
      file using information from the mediainfo command and parsing it 
      into a dictionary in a format that allows for input in the the 
      HandBrakeCLI command for transcoding.
    Inputs:
      language   : A scalar or list containing language(s) for audio tracks.
                    Must be ISO 639-2 codes.
    Outputs:
      Returns a dictionary with information in a format for input into 
      the HandBrakeCLI command.
    Keywords:
      PLII    : Toggles downmix format; If True (default), will use
                 Dolby Pro Logic II, if False, will use Dolby Pro Logic
    Dependencies:
      logging
    Author and History:
      Kyle R. Wodzicki     Created 30 Dec. 2016
      
      Modified 29 Jul. 2017 by Kyle R. Wodzicki
        Added some code to remove duplicate downmixed audio streams 
        that have the same language. Code follows a large comment block.
      Modified 14 Dec. 2018 by Kyle R. Wodzicki
        Cleans up some code and comments.
    '''
    self.log.info('Parsing audio information...');                              # If verbose is set, print some output
    if self.__mediainfo is None:         
      self.log.warning('No media information!');                                # Print a message
      return None;         
    if 'Audio' not in self.__mediainfo:         
      self.log.warning('No audio information!');                                # Print a message
      return None;        
    if not isinstance( language, (list, tuple) ): language = (language,);       # If language input is a scalar, convert to tuple
  
    info = {'-map'       : [],
            '-codec'     : [],
            '-filter'    : [],
            '-b'         : [],
            '-title'     : [],
            '-language'  : [],
            'order'      : ('-map', '-filter', '-codec', '-b', '-title', '-language'),
            'a_lang'     : [],
            'file_info'  : []};                                                 # Initialize a dictionary for storing audio information
    track_id  = '1';                                                             # Initialize a variable for counting the track number.
    track_num = 0;
    for lang in language:                                                       # Iterate over all languages
      for track in self.__mediainfo['Audio']:                                   # Iterate over all audio information
        lang3 = track['Language/String3'] if 'Language/String3' in track else '';
        if lang != lang3 and lang3 != '': continue;                             # If the track language does NOT match the current language AND it is not an empty string
        # id    = track['ID']               if 'ID'               in track else '';
        fmt   = track['Format']           if 'Format'           in track else '';
        nCH   = track['Channel_s_']       if 'Channel_s_'       in track else '';
        lang1 = track['Language/String']  if 'Language/String'  in track else '';
        lang2 = track['Language/String2'] if 'Language/String2' in track else '';
        title = track['Title']            if 'Title'            in track else 'Source Track: {}'.format(track_id);
        if type(nCH) is str: nCH = max( [int(j) for j in nCH.split('/')] );     # If nCH is of type string, split number of channels for the audio stream on forward slash, convert all to integer type, take maximum; some DTS streams have 6 or 7 channel layouts 
        lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_';                    # Set default language to English
        info['file_info'].append( lang2 + 'AAC' );                              # Append language and AAC to the file_info list in the dictionary; AAC is always the first audio track
        info['a_lang'].append( lang2 );                                         # Append language for the AAC stream to the a_lang list
        try:
            mapping = track['StreamOrder'].split('-');                          # Try to split StreamOrder on hyphen
        except:
            mapping = ['0', str(track['StreamOrder'])];                         # On exception, assume StreamOrder is integer; convert to string and create own mapping
        mapping = ':'.join( mapping );                                          # Join mapping list on colon
        if nCH > 2:                                                             # If there are more than 2 audio channels
          # Downmixed channel information
          dMixTitle = 'Dolby Pro Logic II' if PLII else 'Dolby Pro Logic';      # Track title based on PLII keyword
          info['-map'].extend(   ['-map', mapping]                         );   # Append the track number to the --audio list
          info['-codec'].extend( ['-c:a:{}'.format(track_num), 'aac']      );   # Append audio codecs to faac and copy
          info['-b'].extend(     ['-b:a:{}'.format(track_num), '192k']     );   # Append audio codec bit rate. 'na' used for the copy codec
          info['-filter'].append( '-filter:a:{}'.format(track_num)         );   # Append the audio mixdowns to Dolby Prologic II and a filler of 'na'
          info['-filter'].append( getDownmixFilter( PLII = PLII )          );   # Set filte for downmixing
          info['-title'].append( '-metadata:s:a:{}'.format(track_num)      );   # Append  audio track names
          info['-title'].append( 'title={}'.format( dMixTitle )            );
          info['-language'].append( '-metadata:s:a:{}'.format(track_num)   );   # Append  audio track names
          info['-language'].append( 'language={}'.format(lang3)            );
          track_num += 1

          # Copied channel information
          info['-map'].extend(    ['-map', mapping]                        );   # Append the track number to the --audio list
          info['-codec'].extend(  ['-c:a:{}'.format(track_num), 'copy']    );   # Append audio codecs to faac and copy
          info['-title'].append( '-metadata:s:a:{}'.format(track_num)      );   # Append  audio track names
          info['-title'].append( 'title={} - {}'.format(title, fmt)        );
          info['-language'].append( '-metadata:s:a:{}'.format(track_num)   );   # Append  audio track names
          info['-language'].append( 'language={}'.format(lang3)            );

          # Extra info
          info['a_lang'].append( lang2 );                                       # Append language for the copied stream to the a_lang list
          info['file_info'].append( lang2 + fmt );                              # Append the language and format for the second strem, which is a copy of the orignal stream
        else:                                                                   # Else, there are 2 or fewer channels
          if fmt != 'AAC':                                                      # If the format of the audio is NOT AAC
            info['-map'].extend(   ['-map', mapping]                       );   # Append the track number to the --audio list
            info['-codec'].extend( ['-c:a:{}'.format(track_num), 'aac']    );   # Append audio codecs to faac and copy
            info['-b'].extend(     ['-b:a:{}'.format(track_num), '192k']   );   # Append audio codec bit rate. 'na' used for the copy codec
          else:                                                                 # Else, the stream is only 2 channels and is already AAC
            info['-map'].extend(    ['-map', mapping]                      );   # Append the track number to the --audio list
            info['-codec'].extend(  ['-c:a:{}'.format(track_num), 'copy']  );   # Append audio codecs to faac and copy

          info['-title'].append( '-metadata:s:a:{}'.format(track_num) );     # Append  audio track names
          if nCH == 2:                                                          # If there are only 2 audio channels
            info['-title'].append( 'title=stereo' );
          else:                                                                 # Else, must be only a single channel
            info['-title'].append( 'title=mono'   );

          info['-language'].append( '-metadata:s:a:{}'.format(track_num) );     # Append  audio track names
          info['-language'].append( 'language={}'.format(lang3)          );

        track_id = str( int(track_id) + 1 );                                    # Increment audio track
        track_num += 1;
    if len(info['-map']) == 0:                                                  # If the --audio list is NOT empty
      self.log.warning(  'NO audio stream(s) selected...');                     # If verbose is set, print some output
      return None;
    else:
      # The following lines of code remove duplicate audio tracks based on the
      # audio track name and language. This is done primarily so that there
      # are not multiple downmixed tracks in the same language. For example.
      # if a movie has both Dolby and DTS 5.1 surround tracks, the code above
      # will set to have a Dolby Pro Logic II downmix of both the Dolby and DTS
      # streams, as well as direct copies of them. However, the below code
      # will remove the DTS downmix (if the Dolby stream is before it and vice
      # versa) so that there is one downmix and two copies of the different
      # streams.
      i = 0;                                                                    # Set i counter to zero
      while i < len(info['-map']):                                              # While i is less than then number of entries in --audio
        j = i+2;                                                                # Set j to one more than i
        while j < len(info['-map']):                                            # Re loop over all entries in the dictionary lists
          if info['-title'][i+1] == info['-title'][j+1] and \
             info['a_lang'][i+1] == info['a_lang'][j+1]:  
            for k in info: 
              del info[k][j];                                                   # If the name and language for elements i and j of the info dictionary match, remove the information at element j
              del info[k][j];                                                   # If the name and language for elements i and j of the info dictionary match, remove the information at element j
          else:  
            j += 2;                                                             # Else, the language and name do NOT match, so increment j
        i += 2;                                                                 # Increment i
      
      info['file_info'] = '.'.join( info['file_info'] )
      return info;                                                              # If audio info was parsed, i.e., the '--audio' tag is NOT empty, then set the audio_info to the info dictionary      
  ################################################################################
  def get_video_info( self, x265 = False ):
    '''
    Name:
      get_video_info
    Purpose:
      A python function for getting video stream information from a video file
      using information from the mediainfo command and parsing it into a 
      dictionary in a format that allows for input in the the HandBrakeCLI 
      command for transcoding. Rate factors for different resolutions are the 
      mid-points from the ranges provided by 
      https://handbrake.fr/docs/en/latest/workflow/adjust-quality.html
         RF 18-22 for 480p/576p Standard Definition
         RF 19-23 for 720p High Definition
         RF 20-24 for 1080p Full High Definition
         RF 22-28 for 2160p 4K Ultra High Definition
      The settings used in this program are as follows
         22 -  480p/576p
         23 -  720p
         24 - 1080p
         26 - 2060p
    Inputs:
      None.
    Outputs:
      Returns a dictionary with information in a format for input into 
      the HandBrakeCLI command.
    Keywords:
      x265 - Set to force x265 encoding.
    Dependencies:
      logging
    Author and History:
      Kyle R. Wodzicki     Created 30 Dec. 2016
      Modified 14 Dec. 2018 by Kyle R. Wodzicki
        Cleans up some code and comments.
    '''     
    self.log.info('Parsing video information...');                              # If verbose is set, print some output
    if self.__mediainfo is None:       
      self.log.warning('No media information!');                                # Print a message
      return None;        
    if 'Video' not in self.__mediainfo:        
      self.log.warning('No video information!');                                # Print a message
      return None;              
    if len( self.__mediainfo['Video'] ) > 2:         
      self.log.error('More than one (1) video stream...Stopping!');             # Print a message
      return None;                                                              # If the video has multiple streams, return
    encoder    = '';
    filters    = [];
    resolution = None;
    video_data = self.__mediainfo['Video'][0];                                  # Data for only video stream; done so var name is shorter
    video_tags = video_data.keys();                                             # Get all keys in the dictionary  
    try:
        mapping = video_data['StreamOrder'].split('-');                         # Try to split the StreamOrder data on hyphen
    except:
        mapping = ['0', str( video_data['StreamOrder'] )];                      # If there is an exception, assume StreamOrder is an integer and create mapping
    mapping = ':'.join( mapping );                                              # Join mapping using colon

    info       = { 'order' : ('-map', '-filter', '-opts') }
    for tag in info['order']: info[tag] = [];

    info['-map'].extend( ['-map', mapping] );                                    # Initialize a dictionary for storing video information

    if video_data['Height'] <= 1080 and not x265:                               # If the video is 1080 or smaller and x265 is NOT set
      encoder = 'x264'
      info['-opts'].extend( ['-c:v',       'libx264'] );
      info['-opts'].extend( ['-preset',    'slow']    );                        # Set the video codec preset
      info['-opts'].extend( ['-profile:v', 'high']    );                        # Set the video codec profile
      info['-opts'].extend( ['-level',     '4.0']     );                        # Set the video codec level
    else:                                                                       # Else, the video is either large or x265 has be requested
      encoder = 'x265'
      info['-opts'].extend( ['-c:v',      'libx265'] );
      info['-opts'].extend( ['-preset',   'slow']    );                          # Set the video codec preset
      if 'Bit_depth' in video_data:
        if video_data['Bit_depth'] == 10:
          info['-opts'].extend( ['-profile:v', 'main10']    );                  # Set the video codec profile
        elif video_data['Bit_depth'] == 12:
          info['-opts'].extend( ['-profile:v', 'main12']    );                  # Set the video codec profile
      else:
        info['-opts'].extend( ['-profile:v', 'main']    );                      # Set the video codec profile
      info['-opts'].extend( ['-level',    '5.0']     );                          # Set the video codec level

    # Set resolution and rate factor based on video height
    if video_data['Height'] <= 480:
      resolution = 480
      info['-opts'].extend( ['-crf', '22'] );
    elif video_data['Height'] <= 720:
      resolution =  720;
      info['-opts'].extend( ['-crf', '23'] );
    elif video_data['Height'] <= 1080:
      resolution = 1080;
      info['-opts'].extend( ['-crf', '24'] );
    elif video_data['Height'] <= 2160:
      resolution = 2160;
      info['-opts'].extend( ['-crf', '26'] );
    if resolution is None: return None;                                         # If resolution is NOT set, return None
    
    if 'Scan_type' in video_tags and 'Frame_rate_mode' in video_tags:
      if video_data['Scan_type'].upper() != 'PROGRESSIVE':
        if video_data['Frame_rate_mode']  == 'CFR': 
          info['-filter'].append( 'yadif' )

    info['file_info'] = '{}p.{}'.format( resolution, encoder );
  
    if 'Display_aspect_ratio' in video_tags and \
       'Original_display_aspect_ratio' in video_tags:
      if video_data['Display_aspect_ratio'] != \
         video_data['Original_display_aspect_ratio']:
        x,y    = video_data['Display_aspect_ratio/String'].split(':');          # Get the x and y values of the display aspect ratio
        width  = video_data['Height'] * float(x)/float(y);                      # Compute new pixel width based on video height times the display ratio
        width -= (width % 16);                                                  # Ensure pixel width is multiple of 16
        info['-fitler'].append(
          'setsar={:.0f}:{:.0f}'.format(width, video_data['Width'])
        )

    if len(info['-filter']) > 0:
      info['-filter'] = ['-vf', ','.join(info['-filter'])];
    return info;
  ################################################################################
  def get_text_info( self, language ):
    '''
    Name:
      get_text_info
    Purpose:
      A method for getting text stream information from a
      video file using information from the mediainfo command and 
      parsing it into a dictionary in a format that allows for use 
      in either the the vobsub_extract or ccextract functions to extract 
      the text to  individual files and/or convert the text to SRT format.
    Inputs:
      language   : A scalar or list containing language(s) for audio tracks.
                    Must be ISO 639-2 codes.
                    Note that language selection is not currently
                    available for mpeg transport streams with CC
                    muxed into video as mediainfo gives no information
                    on CC languagues (20190217)
    Outputs:
      Returns a dictionary where each entry contains the 3 different
      language strings, the output extension to be used on the
      subtitle file, and the  MKV ID used to identify tracks in 
      MKVToolNix for each text stream of interest. Returns None if NO 
      text streams found.
    Keywords:
      None
    Dependencies:
      logging
    Author and History:
      Kyle R. Wodzicki     Created 13 Jan. 2017
      
      Modified 14 Dec. 2018 by Kyle R. Wodzicki
        Cleans up some code and comments.
    ''' 
    self.log.info('Parsing text information...');                               # If verbose is set, print some output
    if self.__mediainfo is None:       
      self.log.warning('No media information!');                                # Print a message
      return None;         
    if 'Text' not in self.__mediainfo:         
      self.log.warning('No text information!');                                 # Print a message
      return None;      
    if not isinstance( language, (list, tuple) ): language = (language,);       # If language input is a scalar, convert to tuple
    
    if self.__mediainfo['General'][0]['Format'] == 'MPEG-TS':
      return self.__parse_mpegTS( language );
    else:
      return self.__parse_vobsub( language );
  ##############################################################################
  def __parse_vobsub(self, language):
    '''
    Name:
      __parse_vobsub
    Purpose:
      A private method for parsing text information for vobsub
      subtitle format
    '''
    j, n_elems, info = 0, [], [];                                                 # Initialize a counter, a list for all out file extensions, a list to store the number of elements in each text stream, and a dictionary
    for lang in language:                                                         # Iterate over all languages
      for track in self.__mediainfo['Text']:                                             # Iterate over all text information
        lang3  = track['Language/String3']  if 'Language/String3' in track else ''; 
        if lang != lang3: continue;                                               # If the track language does NOT matche the current language
        id     = track['ID']                if 'ID'                in track else '';
        lang1  = track['Language/String']   if 'Language/String'   in track else '';
        lang2  = track['Language/String2']  if 'Language/String2'  in track else '';
        elems  = track['count_of_elements'] if 'count_of_elements' in track else '';
        frames = track['Frame_count']       if 'Frame_count'       in track else '';
        if 'Forced' in track:
          forced = True if track['Forced'].lower() == 'yes' else False;
        else:
          forced = False
        ext = '.' + str( j );                                                     # Append sub title track number to file
        if lang3 != '':  
          ext = ext + '.' + lang3;                                                # Append 2 character language code if language is present
        elif lang2 != '':   
          ext = ext + '.' + lang2;                                                # Append 3 character language code if language is present
        elif lang1 != '':  
          ext = ext + '.' + lang1;                                                # Append full language string
        if elems  != '':                                                          # If elems variable is NOT an empty string
          n_elems.append( int(elems) );                                           # Append the number of VobSub images to the sub_elems list
        elif frames != '':                                                        # If frames variable is NOT an empty string
          n_elems.append( int(frames) );                                          # Append the number of VobSub images to the sub_frames list
        else:                                                                     # If neither variable has a value
          n_elems.append( 0 );                                                    # Append zero
        info.append( {'mkvID'  : str( int(id)-1 ),
                      'lang1'  : lang1,
                      'lang2'  : lang2,
                      'lang3'  : lang3,
                      'ext'    : ext, 
                      'forced' : forced,
                      'track'  : j,
                      'vobsub' : False,
                      'srt'    : False} );                                        # Update a dictionary to the list. vobsub and srt tags indicate whether a file exists or not
        j+=1;                                                                     # Increment sub title track number counter
    if len(n_elems) == 0:                                                         # If subtitle streams were found
      self.log.warning(  'NO text stream(s) in file...');                         # If verbose is set, print some output
      return None;  
    else:
      # Double check forced flag
      max_elems = float( max(n_elems) );                                          # Get maximum number of elements over all text streams
      for i in range(len(n_elems)):                                               # Iterate over all extensions
        if max_elems > 0:                                                         # If the maximum number of elements in a text stream is greater than zero
          if n_elems[i] / max_elems < 0.1:   
            info[i]['ext']    += '.forced';                                       # If the number of VobSub images in a given track less than 10% of the number of images in the track with the most images, assume it contains forced subtitle and append '.forced' to the extension
            info[i]['forced']  = True;
      if len(info) > 0:                                                           # If text info was parsed, i.e., the info dictionary is NOT empty,
        return info;                                                              # Return the info dictionary
      else:                                                                       # Else
        return None;                                                              # Return None
  ##############################################################################
  def __parse_mpegTS(self, language):
    '''
    Name:
      __parse_mpegTS
    Purpose:
      A private method for parsing text information for CC 
      in mpeg transport stream data recorded by Plex DVR;


      Note (20190219): while this method will parse information 
      from all the text streams in the file, the ccextract
      function currently only extracts the first CC stream as
      there is not clear documentation on how to extract 
      specific streams and mediainfo does not return any
      language information for the streams
      '''
    j, n_elems, info = 0, [], [];                                                 # Initialize a counter, a list for all out file extensions, a list to store the number of elements in each text stream, and a dictionary
    for lang in language:                                                         # Iterate over all languages
      for track in self.__mediainfo['Text']:                                             # Iterate over all text information
        lang3  = track['Language/String3']  if 'Language/String3' in track else ''; 
        # The following line is commented because language information not available for DCCTV in mediainfo output, but may be in future
        # if lang != lang3: continue;                                               # If the track language does NOT matche the current language
        id     = track['ID']                if 'ID'                in track else '';
        lang1  = track['Language/String']   if 'Language/String'   in track else '';
        lang2  = track['Language/String2']  if 'Language/String2'  in track else '';
        elems  = track['count_of_elements'] if 'count_of_elements' in track else '';
        frames = track['Frame_count']       if 'Frame_count'       in track else '';
        if 'Forced' in track:
          forced = True if track['Forced'].lower() == 'yes' else False;
        else:
          forced = False
        ext = '.' + str( j );                                                     # Append sub title track number to file
        if lang3 != '':  
          ext = ext + '.' + lang3;                                                # Append 2 character language code if language is present
        elif lang2 != '':   
          ext = ext + '.' + lang2;                                                # Append 3 character language code if language is present
        elif lang1 != '':  
          ext = ext + '.' + lang1;                                                # Append full language string
        if elems  != '':                                                          # If elems variable is NOT an empty string
          n_elems.append( int(elems) );                                           # Append the number of VobSub images to the sub_elems list
        elif frames != '':                                                        # If frames variable is NOT an empty string
          n_elems.append( int(frames) );                                          # Append the number of VobSub images to the sub_frames list
        else:                                                                     # If neither variable has a value
          n_elems.append( 0 );                                                    # Append zero
        info.append( {'lang1'  : lang1,
                      'lang2'  : lang2,
                      'lang3'  : lang3,
                      'ext'    : ext, 
                      'forced' : forced,
                      'track'  : j,
                      'vobsub' : False,
                      'srt'    : False} );                                        # Update a dictionary to the list. vobsub and srt tags indicate whether a file exists or not
        j+=1;                                                                     # Increment sub title track number counter
    if len(n_elems) == 0:                                                         # If subtitle streams were found
      self.log.warning(  'NO text stream(s) in file...');                         # If verbose is set, print some output
      return None;  
    else:
      # Double check forced flag
      max_elems = float( max(n_elems) );                                          # Get maximum number of elements over all text streams
      for i in range(len(n_elems)):                                               # Iterate over all extensions
        if max_elems > 0:                                                         # If the maximum number of elements in a text stream is greater than zero
          if n_elems[i] / max_elems < 0.1:   
            info[i]['ext']    += '.forced';                                       # If the number of VobSub images in a given track less than 10% of the number of images in the track with the most images, assume it contains forced subtitle and append '.forced' to the extension
            info[i]['forced']  = True;
      if len(info) > 0:                                                           # If text info was parsed, i.e., the info dictionary is NOT empty,
        return info;                                                              # Return the info dictionary
      else:                                                                       # Else
        return None;                                                              # Return None
