import logging;
import os
from subprocess import call, check_output, DEVNULL, STDOUT;

from ..utils.checkCLI import checkCLI

CLIName = 'mkvextract'
try:
  CLI = checkCLI( CLIName )
except:
  logging.getLogger(__name__).error( '{} is NOT installed'.format(CLIName) )
  CLI = None 


def vobsub_extract( in_file, out_file, text_info, vobsub = False, srt = False ):
  """
  A python function to extract VobSub(s) from a file and convert them
    to SRT file(s). If a file fails to convert, the VobSub files are 
    removed and the program continues. A message is printed

  Arguments:
    None

  Keyword arguments:
    None.

  Returns:
    int: Updates vobsub_status and creates/updates list of VobSubs that failed vobsub2srt conversion.
                Returns codes for success/failure of extraction. Codes are as follows:
                   0 - Completed successfully.
                   1 - VobSub(s) already exist
                   2 - No VobSub(s) to extract
                   3 - Error extracting VobSub(s).
                  10 - mkvextract not found/installed
  Dependencies:
    mkvextract - A CLI for extracting streams for an MKV file.
  """

  log     = logging.getLogger(__name__);
  files   = []                                                                  # List to stroe all files created during extraction
  if CLI is None:
    log.warning( '{} CLI not found; cannot extract!'.format(CLIName) )
    return 10, files

  if text_info is None: return 2, files;                                        # If text info has not yet been defined, return

  status  = 0;                                                                  # Default status to zero (0)
  extract = [CLI, 'tracks', in_file];                                  # Initialize list to store command for extracting VobSubs from MKV files

  for i in range( len(text_info) ):                                             # Iterate over tags in dictionary making sure they are in numerical order
    id   = text_info[i]['mkvID'];                                               # Get track ID
    file = out_file + text_info[i]['ext'];                                      # Generate file name for subtitle file
    if os.path.exists(file + '.sub'): text_info[i]['vobsub'] = True;            # Set vobsub exists in text_info dictionary to True
    srtTest = (srt    and not os.path.exists(file + '.srt'));                   # Test for srt True and the srt file does NOT exist
    vobTest = (vobsub and not os.path.exists(file + '.sub'));                   # Test for vobsub True and the sub file does NOT exist
    if srtTest or vobTest:                                                      # If srtTest or vobTest is true
      subFile  = '{}.sub'.format(file)
      idxFile  = '{}.idx'.format(file)
      files   += [subFile, idxFile]
      extract.append( '{}:{}'.format(id, subFile) )                             # Add VobSub extraction of given subtitle track to the mkvextract command list

  if len(extract) == 3:  
    return 1, files  
  else:  
    while True:                                                                 # Loop forever
      try:  
        tmp = check_output(['pgrep', CLIName]);                                     # Check for instance of mkvextract
        log.info('Waiting for a {} instance to finish...'.format(CLIName));         # logging info
        time.sleep(15);                                                         # If pgrep return (i.e., no error thrown), then sleep 15 seconds
      except:  
        log.info('Extracting VobSubs...');                                      # logging info
        status = call( extract, stdout = DEVNULL, stderr = STDOUT );            # Run command and dump all output and errors to /dev/null
        break;                                                                  # Pret the while loop
    files = [f for f in files if os.path.isfile(f)]                             # Update files list to include only those files that actually exist
    if status == 0:  
      for i in range( len(text_info) ): text_info[i]['vobsub'] = True;  
      return 0, files                                                           # Error extracting VobSub(s)
    else:  
      return 3, files
