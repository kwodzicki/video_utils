"""
Utilities for converting VobSubs to SRT

"""

import logging
import os

from ..utils.check_cli import check_cli
from ..utils.subproc_pool import PopenThread
from .srt_utils import srt_cleanup

CLINAME = 'vobsub2srt'
try:
    CLI = check_cli( CLINAME )
except:
    logging.getLogger(__name__).warning( "%s is NOT installed", CLINAME )
    CLI = None

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
        int: Updates vobsub_status and creates/updates list of VobSubs that
            failed vobsub2srt conversion.
            Returns codes for success/failure of extraction. Codes are as follows:

              - 0 : Completed successfully.
              - 1 : SRT(s) already exist
              - 2 : No VobSub(s) to convert.
              - 3 : Some VobSub(s) failed to convert.

    Dependencies:
        vobsub2srt - A CLI for converting VobSub images to SRT

    """

    log = logging.getLogger(__name__)
    if text_info is None:
        return 2, ''
    log.info('Converting VobSub(s) to SRT(s)...')

    # Generate file name for subtitle file
    basename = f"{out_file}{text_info['ext']}"
    srtname  = f"{basename}.srt" 
    if os.path.exists( srtname ):
        log.info( "%s Exists...Skipping", srtname )
        text_info['srt'] = True
        return 1, srtname

    # Initialize cmd as list containing 'vobsub2srt'
    cmd = [ CLI ]
    # If the two(2) and three (3) character language codes are NOT empty
    if text_info['lang2'] != '' and text_info['lang3'] != '':
        cmd.extend( ['--tesseract-lang', text_info['lang3']] )
        cmd.extend( ['--lang', text_info['lang2']] )
    cmd.append( basename )

    proc = PopenThread( cmd, cpulimit=cpulimit )
    proc.start()
    proc.wait()
    if proc.returncode != 0:
        return 2, ''

    try:
        _ = srt_cleanup( srtname )
    except Exception as err:
        log.error( 'Failed to convert VobSub to SRT : %s', err )
        return 3, ''

    text_info['srt'] = True

    # If vobsub_delete is True
    if delete_source:
        log.info('Deleting VobSub')
        # Generate file names for sub and idx files
        sub_file = f"{basename}.sub"
        idx_file = f"{basename}.idx"
        if os.path.isfile(sub_file):
            os.remove(sub_file)
        if os.path.isfile(idx_file):
            os.remove(idx_file)

    return 0, srtname
