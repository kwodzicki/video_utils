#!/usr/bin/env python3
#+
# Name:
#   splitOnChapter
# Purpose:
#   A python script to split a video file based on chapters.
#   the idea is that if a TV show is ripped with multiple 
#   episodes in one file, assuming all episodes have the 
#   same number of chapters, one can split the file into
#   individual episode files.
# Inputs:
#   inFile  : Full path to the file that is to be split.
#   nChaps  : The number of chapters in each episode.
# Outputs:
#   Outputs n files, where n is equal to the total number
#   of chapters in the input file divided by nChaps.
# Keywords:
#   None.
# Author and History:
#   Kyle R. Wodzicki     Created 01 Feb. 2018
#-

import subprocess, os, json
from datetime import timedelta

def splitOnChapter(inFile, nChap):
	if type(nChap) is not int: nChap = int(nChap);                                # Ensure that nChap is type int
	cmd = ['ffprobe', '-i', inFile, '-print_format', 'json', 
	       '-show_chapters', '-loglevel', 'error'];                               # Command to get chapter information
	try:                                                                          # Try to...
		chaps = str(subprocess.check_output( cmd ), 'utf-8');                       # Get chapter information from ffprobe
		chaps = json.loads( chaps )['chapters'];                                    # Parse the chapter information
	except:                                                                       # On exception
		print('Failed to get chapter information');                                 # Print a message
		return;                                                                     # Return
	
	cmd = ['ffmpeg', '-v', 'quiet', '-stats', 
	       '-ss', '', 
	       '-i', inFile,
	        '-codec', 'copy', '-map', '0',
	       '-t', '', ''];                                                         # Set up list for command to split file
	fmt = 'split_{:03d}.' + inFile.split('.')[-1];                                # Set file name for split files
	num = 0;                                                                      # Set split file number
	for i in range(0, len(chaps), nChap):                                         # Iterate over chapter ranges
		fName   = fmt.format(num);                                                  # Set file name
		s, e    = i, i+nChap-1
		start   = timedelta( seconds = float(chaps[s]['start_time']) + 0.05 );      # Get chapter start time
		end     = timedelta( seconds = float(chaps[e]['end_time'])   - 0.05 );      # Get chapter end time
		dur     = end - start;                                                      # Get chapter duration
		cmd[5]  = str(start);                                                       # Set start offset to string of start time
		cmd[-2] = str(dur);                                                         # Set duration to string of dur time
		cmd[-1] = os.path.join( os.path.dirname(inFile), fName );                   # Set output file

		with open(os.devnull, 'w') as devnull:                                      # Open /dev/null for writing
			proc = subprocess.Popen(cmd, stderr=devnull);                             # Write errors to /dev/null
		proc.communicate();                                                         # Wait for command to complete
		if proc.returncode != 0:                                                    # If return code is NOT zero
			print('FFmpeg had an error!');                                            # Print message
			return;                                                                   # Return
		num += 1;                                                                   # Increment split number

if __name__ == "__main__":
	import argparse;                                                              # Import library for parsing
	parser = argparse.ArgumentParser(description="Split on Chapter");             # Set the description of the script to be printed in the help doc, i.e., ./script -h
	parser.add_argument("file",          type=str, help="Input file to split"); 
	parser.add_argument("-n", "--nchap", type=int, help="Number of chapters per track"); 
	args = parser.parse_args();                                                   # Parse the arguments

	splitOnChapter( args.file, args.nchap );