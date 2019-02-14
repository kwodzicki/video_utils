import logging;
import os, subprocess;

def vobsub_extract( in_file, out_file, text_info, vobsub = False, srt = False ):
	'''
	Name:
		vobsub_extract
	Purpose:
		A python function to extract VobSub(s) from a file and convert them
		to SRT file(s). If a file fails to convert, the VobSub files are 
		removed and the program continues. A message is printed
	Inputs:
				None.
	Outputs:
		updates vobsub_status and creates/updates list of VobSubs that failed
		vobsub2srt conversion.
		Returns codes for success/failure of extraction. Codes are as follows:
			 0 - Completed successfully.
			 1 - VobSub(s) already exist
			 2 - No VobSub(s) to extract
			 3 - Error extracting VobSub(s).
	Keywords:
		None.
	Dependencies:
		mkvextract - A CLI for extracting streams for an MKV file.
	Author and History:
		Kyle R. Wodzicki     Created 30 Dec. 2016
	'''
	log = logging.getLogger(__name__);
	if text_info is None: return 2;                                               # If text info has not yet been defined, return
	status  = 0;                                                                  # Default status to zero (0)
	extract = ['mkvextract', 'tracks', in_file];                                  # Initialize list to store command for extracting VobSubs from MKV files
	for i in range( len(text_info) ):                                             # Iterate over tags in dictionary making sure they are in numerical order
		id   = text_info[i]['mkvID'];                                               # Get track ID
		file = out_file + text_info[i]['ext'];                                      # Generate file name for subtitle file
		if os.path.exists(file + '.sub'): text_info[i]['vobsub'] = True;            # Set vobsub exists in text_info dictionary to True
		srtTest = (srt    and not os.path.exists(file + '.srt'));                   # Test for srt True and the srt file does NOT exist
		vobTest = (vobsub and not os.path.exists(file + '.sub'));                   # Test for vobsub True and the sub file does NOT exist
		if srtTest or vobTest: extract.append( id + ':' + file + '.sub');           # If srtTest or vobTest is true, add VobSub extraction of given subtitle track to the mkvextract command list
# 			if self.srt is True: self.text_info[i].update( {'out_file': file } );       # If the srt keyword IS True, append the file to the files list
	if len(extract) == 3:  
		return 1;  
	else:  
		while True:                                                                 # Loop forever
			try:  
				tmp = subprocess.check_output(['pgrep', 'mkvextract']);								  # Check for instance of mkvextract
				log.info('Waiting for a mkvextract instance to finish...');             # logging info
				time.sleep(15);                                                         # If pgrep return (i.e., no error thrown), then sleep 15 seconds
			except:  
				log.info('Extracting VobSubs...');                                      # logging info
				with open(os.devnull, 'w') as null:  
					status = subprocess.call( extract, stdout = null, stderr = null );    # Run command and dump all output and errors to /dev/null
				break;                                                                  # Pret the while loop
		if status == 0:  
			for i in range( len(text_info) ): text_info[i]['vobsub'] = True;  
			return 0;                                                                 # Error extracting VobSub(s)
		else:  
			return 3;