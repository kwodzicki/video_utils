import logging
import os, time;
from subprocess import call, Popen, DEVNULL, STDOUT;
from .srt_cleanup import srt_cleanup;

if call(['which', 'vobsub2srt'], stdout = DEVNULL, stderr = STDOUT) != 0:
  msg = 'vobsub2srt is NOT installed';
  logging.getLogger(__name__).error( msg );
  raise Exception( msg );


from video_utils.utils.subprocManager import subprocManager;

def vobsub_to_srt( out_file, text_info, vobsub_delete = False, cpulimit = None, threads = None ):
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
  log = logging.getLogger(__name__);                                            # Initialize logger
  if text_info is None: return 2, text_info;                                    # If text info has not yet been defined, return
  log.info('Converting VobSub(s) to SRT(s)...');                                # Print logging info
  fmt     = '  {:2d} of {:2d} - {}';                                            # Format for counter in logging
  subproc = subprocManager(cpulimit = cpulimit, threads = threads);             # Initialize subprocManager
  subproc._logFMT = fmt;                                                        # Set format for counter in the subprocManager

  failed  = 0;
  skipped = 0;  
  files   = [];
  n_tags  = len(text_info);                                                     # Get number of entries in dictionary
  for i in range(n_tags):                                                       # Iterate over all VobSub file(s)
    info = text_info[i];                                                        # Store current info in info
    file = out_file + info['ext'];                                              # Generate file name for subtitle file
    if os.path.exists(file + '.srt'):                                           # If the srt output file already exists
      log.info( fmt.format( i+1, n_tags, 'Exists...Skipping' ) );               # Print logging information
      text_info[i]['srt'] = True;                                               # Set srt exists flag in text_info dictionary to True
      skipped += 1;                                                             # Increment skipped by one (1)
      continue;                                                                 # Continue
    else:                                                                       # Else, the srt file does NOT exist
      log.info( fmt.format( i+1, n_tags, 'Adding to queue' ) );                 # Print logging information
      cmd = ['vobsub2srt'];                                                     # Initialize cmd as list containing 'vobsub2srt'
      if info['lang2'] != '' and info['lang3'] != '':                           # If the two(2) and three (3) character language codes are NOT empty
        cmd.extend( ['--tesseract-lang', info['lang3']] );                      # Append tesseract language option
        cmd.extend( ['--lang', info['lang2']] );                                # Append language option
      files.append(file);
      cmd.append( file );                                                       # Append input file to cmd
      subproc.addProc( cmd, single = True );                                    # Add command to queue
  subproc.run();                                                                # Run all the commands

  for i in range( len(subproc.returncodes) ):                                   # Iterate over all the return codes
    if subproc.returncodes[i] == 0:                                             # If the return code is zero (0)
      text_info[i]['srt'] = True;                                               # Set srt exists flag in text_info dictionary to True
      status = srt_cleanup( files[i] + '.srt' );                                # Run SRT music notes on the file
    else:                                                                       # Else
      failed += 1;                                                              # Increment failed by one (1)

  if vobsub_delete:                                                             # If vobsub_delete is True
    log.info('Deleting VobSub(s)');                                             # Log some information
    for j in text_info:                                                         # Iterate over all keys in the text_info dictionary
      sub_file = file = out_file + j['ext']+ '.sub';                            # Set the sub_file path
      idx_file = file = out_file + j['ext']+ '.idx';                            # Set the idx_file path
      if os.path.isfile(sub_file): os.remove(sub_file);                         # If the sub_file exists, the delete it
      if os.path.isfile(idx_file): os.remove(idx_file);                         # If the sub_file exists, the delete it
  if failed > 0:                                                                # If the length of failed is greater than zero
    return 3, text_info;                                                        # Some SRTs failed to convert
  elif skipped == n_tags:                                                       # Else, if skipped equals the number of tages requested
    return 1, text_info;                                                        # All SRTs existed OR no vobsubs to convert
  else:                                                                         # Else,
    return 0, text_info;                                                        # All SRTs converted   