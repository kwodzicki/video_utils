import logging;
def text_info_parse( mediainfo, language ):
	'''
	Name:
		text_info_parse
	Purpose:
		A python function for getting text stream information from a
		video file using information from the mediainfo command and 
		parsing it into a dictionary in a format that allows for use 
		in the vobsub_extract command to extract the text to  individual
		files and/or convert the text to SRT format.
	Inputs:
		mediainfo  : Dictionary containing information returned from a call to
		              the mediainfo() function.
	  language   : A scalar or list containing language(s) for audio tracks.
	                Must be ISO 639-2 codes.
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
	log = logging.getLogger(__name__);
	log.info('Parsing text information...');                                      # If verbose is set, print some output
	if mediainfo is None:       
		log.warning('No media information!');                                       # Print a message
		return None;         
	if 'Text' not in mediainfo:         
		log.warning('No text information!');                                        # Print a message
		return None;			
	if not isinstance( language, (list, tuple) ): language = (language,);         # If language input is a scalar, convert to tuple

	j, n_elems, info = 0, [], [];                                                 # Initialize a counter, a list for all out file extensions, a list to store the number of elements in each text stream, and a dictionary
	for lang in language:                                                         # Iterate over all languages
		for track in mediainfo['Text']:                                             # Iterate over all text information
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
				ext = ext + '.' + lang2;                                    					  # Append 3 character language code if language is present
			elif lang1 != '':  
				ext = ext + '.' + lang1;                              							    # Append full language string
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
		log.warning(  'NO text stream(s) in file...');                              # If verbose is set, print some output
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