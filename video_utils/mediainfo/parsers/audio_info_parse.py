import logging
def audio_info_parse( mediainfo, language ):
	'''
	Name:
		audio_info_parse
	Purpose:
		A python function for getting audio stream information from a video
		file using information from the mediainfo command and parsing it 
		into a dictionary in a format that allows for input in the the 
		HandBrakeCLI command for transcoding.
	Inputs:
		mediainfo  : Dictionary containing information returned from a call to
		              the mediainfo() function.
	  language   : A scalar or list containing language(s) for audio tracks.
	                Must be ISO 639-2 codes.
	Outputs:
		Returns a dictionary with information in a format for input into 
		the HandBrakeCLI command.
	Keywords:
		None.
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
	log = logging.getLogger(__name__)
	log.info('Parsing audio information...');                                     # If verbose is set, print some output
	if mediainfo is None:         
		log.warning('No media information!');                                       # Print a message
		return None;         
	if 'Audio' not in mediainfo:         
		log.warning('No audio information!');                                       # Print a message
		return None;			  
	if not isinstance( language, (list, tuple) ): language = (language,);         # If language input is a scalar, convert to tuple

	info = {'a_track'   : [],
					'a_codec'   : [],
					'a_mixdown' : [],
					'a_name'    : [],
					'a_bitrate' : [],
					'a_lang'    : [],
					'file_info' : []};                                                    # Initialize a dictionary for storing audio information
	track_id = '1';                                                               # Initialize a variable for counting the track number.
	for lang in language:                                                         # Iterate over all languages
		for track in mediainfo['Audio']:                                            # Iterate over all audio information
			lang3 = track['Language/String3'] if 'Language/String3' in track else '';
			if lang != lang3 and lang3 != '': continue;                             # If the track language does NOT match the current language AND it is not an empty string
			id    = track['ID']               if 'ID'               in track else '';
			fmt   = track['Format']           if 'Format'           in track else '';
			nCH   = track['Channel_s_']       if 'Channel_s_'       in track else '';
			lang1 = track['Language/String']  if 'Language/String'  in track else '';
			lang2 = track['Language/String2'] if 'Language/String2' in track else '';
			title = track['Title']            if 'Title'            in track else '';
			if type(nCH) is str: nCH = max( [int(j) for j in nCH.split('/')] );       # If nCH is of type string, split number of channels for the audio stream on forward slash, convert all to integer type, take maximum; some DTS streams have 6 or 7 channel layouts 
			lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_';                      # Set default language to English
			info['file_info'].append( lang2 + 'AAC' );                                # Append language and AAC to the file_info list in the dictionary; AAC is always the first audio track
			info['a_lang'].append( lang2 );                                           # Append language for the AAC stream to the a_lang list
			if nCH > 2:                                                               # If there are more than 2 audio channels
				info['a_track'].extend(   [track_id,  track_id] );                      # Append the track number to the a_track list
				info['a_mixdown'].extend( ['dpl2', 'na'] );                             # Append the audio mixdowns to Dolby Prologic II and a filler of 'na'
				info['a_codec'].extend(   ['faac', 'copy'] );                           # Append audio codecs to faac and copy
				info['a_bitrate'].extend( ['192',  'na'] );                             # Append audio codec bit rate. 'na' used for the copy codec
				info['a_name'].extend(['"Dolby Pro Logic II"','"'+title+' - '+fmt+'"']);# Append  audio track names
				info['a_lang'].append( lang2 );                                         # Append language for the copied stream to the a_lang list
				info['file_info'].append( lang2 + fmt );                                # Append the language and format for the second strem, which is a copy of the orignal stream
			else:                                                                     # Else, there are 2 or fewer channels
				if fmt != 'AAC':                                                        # If the format of the audio is NOT AAC
					info['a_track'].append( track_id );                                   # Append track_id to a_track data
					info['a_codec'].append( 'faac' );                                     # Append faac to a_codec data
					info['a_bitrate'].append( '192' );                                    # Append 192 to a_bitrate data
				else:                                                                   # Else, the stream is only 2 channels and is already AAC
					info['a_track'].append( track_id );                                   # Append track_id to a_track data
					info['a_codec'].append( 'copy:aac' );                                 # Append copy:aac to a_codec data
					info['a_bitrate'].append( '' );                                       # Append '' to a_bitrate data
				if nCH == 2:                                                            # If there are only 2 audio channels
					info['a_mixdown'].append( 'stereo' );                                 # Append stereo to a_mixdown
					info['a_name'].append( '"Stereo"' );                                  # Append Stereo to a_name
				else:                                                                   # Else, must be only a single channel
					info['a_mixdown'].append( 'mono' );                                   # Append mono to a_mixdown
					info['a_name'].append( '"Mono"' );                                    # Append Mono to a_name
			
			track_id = str( int(track_id) + 1 );                                      # Increment audio track

	if len(info['a_track']) == 0:                                                 # If the a_track list is NOT empty
		log.warning(  'NO audio stream(s) selected...');                            # If verbose is set, print some output
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
		i = 0;                                                                      # Set i counter to zero
		while i < len(info['a_track']):                                             # While i is less than then number of entries in a_track
			j = i+1;                                                                  # Set j to one more than i
			while j < len(info['a_track']):                                           # Re loop over all entries in the dictionary lists
				if info['a_name'][i] == info['a_name'][j] and \
					 info['a_lang'][i] == info['a_lang'][j]:  
					for k in info: del info[k][j];                                        # If the name and language for elements i and j of the info dictionary match, remove the information at element j
				else:  
					j += 1;                                                               # Else, the language and name do NOT match, so increment j
			i += 1;                                                                   # Increment i
		for i in info:   
			delim = '.'	if i == 'file_info' else ',';                                 # If i is 'file_info', set the delimiter to period (.), else set it to comma (,)
			info[i] = delim.join( info[i] );                                          # Join the information using the delimiter
		return info;                                                                # If audio info was parsed, i.e., the 'a_track' tag is NOT empty, then set the audio_info to the info dictionary		