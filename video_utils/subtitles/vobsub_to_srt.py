import logging
import os, time;
from subprocess import call, Popen, DEVNULL, STDOUT;
from .srt_cleanup import srt_cleanup;

if call(['which', 'vobsub2srt'], stdout = DEVNULL, stderr = STDOUT) != 0:
  msg = 'vobsub2srt is NOT installed';
  logging.getLogger(__name__).error( msg );
  raise Exception( msg );

try:
  from video_utils.utils.limitCPUusage import limitCPUusage;
except:
  limitCPUusage = None;

def vobsub_to_srt( out_file, text_info, vobsub_delete = False, cpulimit = None, threads = 1 ):
	'''
	Name:
		vobsub_to_srt
	Purpose:
		A python function to convert VobSub(s) to SRT(s). Will convert all
		VobSub(s) in the output directory as long as a matching SRT file
		does NOT exist.
	Inputs:
		None.
	Outputs:
		updates vobsub_status and creates/updates list of VobSubs that failed
		vobsub2srt conversion.
		Returns codes for success/failure of extraction. Codes are as follows:
			 0 - Completed successfully.
			 1 - SRT(s) already exist
			 2 - No VobSub(s) to convert.
			 3 - Some VobSub(s) failed to convert.
	Keywords:
		None.
	Dependencies:
		vobsub2srt - A CLI for converting VobSub images to SRT
	Author and History:
		Kyle R. Wodzicki     Created 30 Dec. 2016
	'''
	def procBlock(threads = None):
		'''
		A function that checks to see if the number of running 
		conversions matches the number of threads allowed.
		Blocks execution until one of the processes finishes.
		'''
		condition = len(proc) > 0 if threads is None else len(proc) == threads;     # Condition for while loop
		while condition:                                                            # While the condition is met
			for i in range( len(proc) ):                                              # Iterate over the VobSub2SRT Instances
				if proc[i].poll() is not None:                                          # Poll the jth instance and if it is NOT None, then work on that file
					if proc[i].returncode == 0:                                           # If return code is zero (0), the VobSub2SRT completed sucessfully
						text_info[proc_textID[i]]['srt'] = True;                            # Set srt exists flag in text_info dictionary to True
						status = srt_cleanup( proc_files[i] + '.srt' );                     # Run SRT music notes on the file
						log.info( fmt.format(proc_textID[i]+1,n_tags) + ' - Finished' );    # Print logging information
					else:                                                                 # If poll does NOT return zero, then VobSub2SRT did NOT complete sucessfully
						log.warning( fmt.format(proc_textID[i]+1,n_tags) + ' - FAILED' );   # Print logging information
						failed += 1;                                                        # Increment failed conversion counter by one (1)
					proc.remove(  proc[i] );                                              # Remove the Popen instances from p_id
					proc_files.remove( proc_files[i] );                                   # Remove the file associate with that Popen instance from p_id_files
					proc_textID.remove( proc_textID[i] );                                 # Remove the text_info index associated with process
					if type(cpulimit) is int and cpulimit > 0:                            # If cpulimit variable is type int and greater than zero (0)
						cpuID[i].communicate();                                             # Wait for the CPU subprocess to finish
						cpuID.remove( cpuID[i] );                                           # Remove the p_id from the list
					break;                                                                # break out of the for loop so that another instance may be started/indexing of lists is not in error
			time.sleep(0.5);                                                          # Sleep for 1/2 second so Python does not use a large amount of CPU in the while loop
			condition = len(proc) > 0 if threads is None else len(proc) == threads;   # Re check condition for while loop

	# Main code of function
	log = logging.getLogger(__name__);                                            # Initialize logger
	if text_info is None: return 2, text_info;                                    # If text info has not yet been defined, return
	log.info('Converting VobSub(s) to SRT(s)...');                                # Print logging info
	proc, proc_files, proc_textID = [], [], [];                                   # Get number of subtitle files and initialize list to store Popen instances in and list to store files corresponding to Popen instances                   
	cpuID   = [];                                                                 # Initialize cpuLimit pid list
	fmt     = '  {:2d} of {:2d}';                                                 # Format for counter in logging
	skipped = 0;                                                                  # Counter for number of SRT(s) that already exist
	failed  = 0;                                                                  # Counter for failed conversions
	n_tags  = len(text_info);                                                     # Get number of entries in dictionary
	for i in range(n_tags):                                                       # Iterate over all VobSub file(s)
		info = text_info[i];                                                        # Store current info in info
		file = out_file + info['ext'];                                              # Generate file name for subtitle file
		if os.path.exists(file + '.srt'):                                           # If the srt output file already exists
			log.info( fmt.format(i+1,n_tags) + ' - Exists...Skipping');               # Print logging information
			text_info[i]['srt'] = True;                                               # Set srt exists flag in text_info dictionary to True
			skipped += 1;                                                             # Increment skipped by one (1)
			continue;                                                                 # Continue
		else:                                                                       # Else, the srt file does NOT exist
			log.info( fmt.format(i+1,n_tags) + ' - Converting');                      # Print logging information
			cmd = ['vobsub2srt'];                                                     # Initialize cmd as list containing 'vobsub2srt'
			if info['lang2'] != '' and info['lang3'] != '':                           # If the two(2) and three (3) character language codes are NOT empty
				cmd.extend( ['--tesseract-lang', info['lang3']] );                      # Append tesseract language option
				cmd.extend( ['--lang', info['lang2']] );                                # Append language option
			cmd.append( file );                                                       # Append input file to cmd
			proc.append( Popen( cmd, stdout = DEVNULL, stderr = STDOUT ) );           # Run command and dump all output and errors to /dev/null
			proc_files.append( file );                                                # Append the ith subtitle file path to the p_id_files list
			proc_textID.append( i );                                                  # Text_info index for the process
			if limitCPUusage:                                                         # If the function imported properly
        if (type(cpulimit) is int) and (cpulimit > 0):                          # If the cpulimit variable is an integer and greater than zero (0)
				  cpuID.append( limitCPUusage( proc[-1].pid, cpulimit, single=True ) ); # Run cpu limit command
			procBlock( threads );                                                     # Test if maximum number of threads reached, if it has been reached, will wait for a thread to finish before new one opens
	procBlock();                                                                  # Wait for all threads to finish
	if vobsub_delete:        					        															      # If vobsub_delete is True
		log.info('Deleting VobSub(s)');                                             # Log some information
		for j in text_info:																						      	      # Iterate over all keys in the text_info dictionary
			sub_file = file = out_file + j['ext']+ '.sub';                            # Set the sub_file path
			idx_file = file = out_file + j['ext']+ '.idx';                            # Set the idx_file path
			if os.path.isfile(sub_file): os.remove(sub_file);							            # If the sub_file exists, the delete it
			if os.path.isfile(idx_file): os.remove(idx_file);									        # If the sub_file exists, the delete it
	if failed > 0:                                                                # If the length of failed is greater than zero
		return 3, text_info;                                                        # Some SRTs failed to convert
	elif skipped == n_tags:                                                       # Else, if skipped equals the number of tages requested
		return 1, text_info;                                                        # All SRTs existed OR no vobsubs to convert
	else:                                                                         # Else,
		return 0, text_info;                                                        # All SRTs converted 