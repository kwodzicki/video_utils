import logging;
def video_info_parse( mediainfo, x265 = False ):
	'''
	Name:
		video_info_parse
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
		mediainfo  : Dictionary containing information returned from a call to
		              the mediainfo() function.
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
	log = logging.getLogger(__name__);
	log.info('Parsing video information...');                                     # If verbose is set, print some output
	if mediainfo is None:       
		log.warning('No media information!');                                       # Print a message
		return None;        
	if 'Video' not in mediainfo:        
		log.warning('No video information!');                                       # Print a message
		return None;			        
	if len( mediainfo['Video'] ) > 2:         
		log.error('More than one (1) video stream...Stopping!');                    # Print a message
		return None;                                                                # If the video has multiple streams, return
	info = {'resolution' : '', \
					'quality'    : '', \
					'v_codec'    : '', \
					'v_level'    : '', \
					'scan_type'  : 'P'};                                                  # Initialize a dictionary for storing audio information
	video_tags = mediainfo['Video'][0].keys();                                    # Get all keys in the dictionary	
	if mediainfo['Video'][0]['Height'] <= 1080 and not x265:                      # If the video is 1080 or smaller and x265 is NOT set
		info['v_codec'],info['v_level'],info['v_profile'] = 'x264','4.0','high';    # If video is 1080 or less AND x265 is False, set codec to h264 level to 4.0
	else:                                                                         # Else, the video is either large or x265 has be requested
		info['v_codec'],info['v_level'],info['v_profile'] = 'x265','5.0','main';    # If video is greater than 1080, set codec to h265 and level to 5.0
		if 'Bit_depth' in mediainfo['Video'][0]:
			if mediainfo['Video'][0]['Bit_depth'] == 10:
				info['v_profile'] = 'main10';
			elif mediainfo['Video'][0]['Bit_depth'] == 12:
				info['v_profile'] = 'main12';
	# Set resolution and rate factor based on video height
	if mediainfo['Video'][0]['Height'] <= 480:
		info['resolution'], info['quality'] =  '480', '22';
	elif mediainfo['Video'][0]['Height'] <= 720:
		info['resolution'], info['quality'] =  '720', '23';
	elif mediainfo['Video'][0]['Height'] <= 1080:
		info['resolution'], info['quality'] = '1080', '24';
	elif mediainfo['Video'][0]['Height'] <= 2160:
		info['resolution'], info['quality'] = '2160', '26';
	info['resolution']+='p';
	if 'Scan_type' in video_tags and 'Frame_rate_mode' in video_tags:
		if mediainfo['Video'][0]['Scan_type'].upper() != 'PROGRESSIVE':
			if mediainfo['Video'][0]['Frame_rate_mode']  == 'CFR': 
				info['scan_type'] = 'I';                                                # Set scan_type to I, or interlaced. A deinterlace setting will be set based on this
	info['file_info'] = info['resolution'] + '.' + info['v_codec'];
	if info['resolution'] == '':
		return None;
	elif info['v_codec'] == 'x264':                                               # If we are to encode using the h264 codec
		info['v_codec_preset']  = '--x264-preset';                                  # Set the video codec preset
		info['v_codec_level']   = '--h264-level';                                   # Set the video codec level
		info['v_codec_profile'] = '--h264-profile';                                 # Set the video codec profile
	elif info['v_codec'] == 'x265':                                               # If we are to encode using the h265 codec
		info['v_codec_preset']  = '--x265-preset';                                  # Set the video codec preset
		info['v_codec_level']   = '--h265-level';                                   # Set the video codec level
		info['v_codec_profile'] = '--h265-profile';                                 # Set the video codec profile

	if 'Display_aspect_ratio' in video_tags and \
	   'Original_display_aspect_ratio' in video_tags:
		if mediainfo['Video'][0]['Display_aspect_ratio'] != \
		   mediainfo['Video'][0]['Original_display_aspect_ratio']:
			x,y    = mediainfo['Video'][0]['Display_aspect_ratio/String'].split(':'); # Get the x and y values of the display aspect ratio
			width  = mediainfo['Video'][0]['Height'] * float(x)/float(y);             # Compute new pixel width based on video height times the display ratio
			width -= (width % 16);                                                    # Ensure pixel width is multiple of 16
			info['aspect'] = '{:.0f}:{:.0f}'.format(
			  width, mediainfo['Video'][0]['Width']
			)
	return info;