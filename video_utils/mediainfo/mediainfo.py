import re;
from subprocess import check_output;
from xml.etree import ElementTree as ET;

def mediainfo( file ):
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
	xmlstr = check_output( ['mediainfo', '--Full', '--Output=OLDXML', file] );
	root   = ET.fromstring( xmlstr );

	out_info = {};                                                                # Initialize out_info dictionary
	for track in root[0].findall('track'):                                        # Iterate over all tracks in the XML tree
		tag = track.attrib['type'];                                                 # Get track type
		if 'typeorder' in track.attrib or 'streamid' in track.attrib:               # If typeorder is in the track.attrib dictionary
			if tag not in out_info: out_info[ tag ] = [ ];                            # If the tag is NOT in the out_info dictionary then create empty list in dictionary under track type in dictionary
			out_info[ tag ].append( {} );													  									# Append empty dictionary to list
		else:                                                                       # Else, typeorder is NOT in the track.attrib dictionary
			out_info[ tag ] = [ {} ];													  									    # create list with dictionary under track type in dictionary

	for track in root[0].findall('track'):                                        # Iterate over all tracks in the XML tree
		tag, order = track.attrib['type'], 0;
		old_tag, tag_cnt = '', 0;                                                   # initialize old_tag to an empty string and tag_cnt to zero (0)
		if 'typeorder' in track.attrib:
			order = int( track.attrib['typeorder'] ) - 1;
		elif 'streamid' in track.attrib:
			order = int( track.attrib['streamid'] ) - 1;
		for elem in track.iter():                                                   # Iterate over all elements in the track
			cur_tag = elem.tag;	                                                      # Set the cur_tag to the tag of the element in the track
			if cur_tag == old_tag:                                                    # If the current tag is the same as the old tag
				cur_tag += '/String';                                                   # Append string to the tag
				if tag_cnt > 1: cur_tag += str(tag_cnt);                                # If the tag_cnt is greater than one (1), then append the number to the tag
				tag_cnt += 1;                                                           # Increment that tag_cnt by one (1);
			else:                                                                     # Else
				tag_cnt = 0;                                                            # Set tag_cnt to zero (0)
			old_tag = elem.tag;                                                       # Set the old_tag to the tag of the element in the track
			if '.' in elem.text:                                                      # If there is a period in the text of the current element
				try:                                                                    # Try to convert the text to a float
					out_info[tag][order][cur_tag] = float(elem.text);
				except:
					out_info[tag][order][cur_tag] = elem.text;
			else:                                                                     # Else there is not period in the text of the current element
				try:                                                                    # Try to convert the text to an integer
					out_info[tag][order][cur_tag] = int(elem.text);
				except:
					out_info[tag][order][cur_tag] = elem.text;
	return out_info;