import logging
import os

from ..utils.checkCLI import checkCLI

CLIName = 'vobsub2srt'
try:
  CLI = checkCLI( CLIName )
except:
  logging.getLogger(__name__).warning( f"{CLIName} is NOT installed" )
  CLI = None

from ..utils.subprocPool import PopenThread
from .srtUtils import srtCleanup

def vobsub_to_srt( out_file, text_info, delete_source=False, cpulimit=None, **kwargs ):
  """
  Convert VobSub(s) to SRT(s).

  Will convert all VobSub(s) in the output directory as long as a matching SRT file
  does NOT exist.

  Arguments:
    None

  Keyword arguments:
    None

  Returns:
    int: Updates vobsub_status and creates/updates list of VobSubs that failed vobsub2srt conversion.
    Returns codes for success/failure of extraction. Codes are as follows:

      - 0 : Completed successfully.
      - 1 : SRT(s) already exist
      - 2 : No VobSub(s) to convert.
      - 3 : Some VobSub(s) failed to convert.

  Dependencies:
    vobsub2srt - A CLI for converting VobSub images to SRT

  """

  log   = logging.getLogger(__name__)                                          # Initialize logger
  if text_info is None: return 2, ''                                        # If text info has not yet been defined, return
  log.info('Converting VobSub(s) to SRT(s)...')                                # Print logging info

  fname = f"{out_file}{info['ext']}.srt"                                              # Generate file name for subtitle file
  if os.path.exists( fname ):                                             # If the srt output file already exists
    log.info( f"{fname} Exists...Skipping" )               # Print logging information
    text_info['srt'] = True                                               # Set srt exists flag in text_info dictionary to True
    return 1, fname

  cmd = [ CLI ]                                                             # Initialize cmd as list containing 'vobsub2srt'
  if text_info['lang2'] != '' and text_info['lang3'] != '':                           # If the two(2) and three (3) character language codes are NOT empty
    cmd.extend( ['--tesseract-lang', text_info['lang3']] )                      # Append tesseract language option
    cmd.extend( ['--lang', text_info['lang2']] );                                # Append language option
  cmd.append( fname )                                                       # Append input file to cmd
 
  proc = PopenThread( cmd, cpulimit=cpulimit ) 
  proc.start()
  proc.wait()
  if proc.returncode != 0:                                             # If the return code is zero (0)
    return 2, ''

  try:
    status = srtCleanup( fname )                                       # Run SRT music notes on the file
  except Exception as err:
    log.error( f'Failed to convert VobSub to SRT : {err}')
    return 3, '' 

  text_info['srt'] = True                                               # Set srt exists flag in text_info dictionary to True

  if delete_source:                                                           # If vobsub_delete is True
    log.info('Deleting VobSub')                                             # Log some information
    sub_file = f"{out_file}{info['ext']}.sub"                                              # Generate file name for subtitle file
    idx_file = f"{out_file}{info['ext']}.idx"                                              # Generate file name for subtitle file
    if os.path.isfile(sub_file): os.remove(sub_file)                         # If the sub_file exists, the delete it
    if os.path.isfile(idx_file): os.remove(idx_file)                         # If the sub_file exists, the delete it

  return 0, fname                                                             # All SRTs converted   
