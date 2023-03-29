import logging
import os
from subprocess import call, check_output, DEVNULL, STDOUT

from ..utils.checkCLI import checkCLI

CLIName = 'mkvextract'
try:
  CLI = checkCLI( CLIName )
except:
  logging.getLogger(__name__).error( f"{CLIName} is NOT installed" )
  CLI = None 

def checkFilesExist( files ):
    """
    Check that all files exist

    If any of the files in the input list do NOT
    exist, than will return False

    Arguments:
        files (array-like) : List of files to check if exist

    Returns:
        bool : True if all of the files exists, False otherwise

    """

    for f in files:
        if not os.path.isfile(f):
            return False
    return True

def genSubInfo( out_base, stream ):
    """
    Generate information for subtitle streams
    
    Build a dict that contains subtitle type and list of
    output subtitle files after extraction

    Arguments:
        out_base (str) : Base output file name that information for
            subtitle files will be appended to
        stream (dict) : Information about given text stream for
            build/extrating text files

    Returns:
        dict

    """
 
    fmt, ext = stream['format'], stream['ext']
    base = f"{out_base}{ext}"

    if fmt == 'UTF-8':
        return dict(subtype='srt',    files=[f"{base}.srt"])
    elif fmt == 'VobSub':
        return dict(subtype='vobsub', files=[f"{base}.srt", f"{base}.idx"])
    elif fmt == 'PGS':
        return dict(subtype='pgs',    files=[f"{base}.sup"])

    return None

def subtitle_extract( in_file, out_base, text_info, **kwargs ): 
    """
    Extract subtitle(s) from a file and convert them to SRT file(s).
    
    If a file fails to convert, the VobSub files are removed and the program continues.
    
    Arguments:
      in_file (str): File to extract subtitles from
      out_file (str): Base name for output file(s)
      text_info (dict): Data returned by call to :meth:`video_utils.mediainfo.MediaInfo.get_text_info`
    
    Keyword arguments:
      srt (bool): Set to convert vobsub to srt format; Default does NOT convert file
    
    Returns:
      int: Updates vobsub_status and creates/updates list of VobSubs that failed vobsub2srt conversion.
      Returns codes for success/failure of extraction. Codes are as follows:
    
        -  0 : Completed successfully
        -  1 : VobSub(s) already exist
        -  2 : No VobSub(s) to extract
        -  3 : Error extracting VobSub(s).
        - 10 : mkvextract not found/installed
    
    Dependencies:
      mkvextract - A CLI for extracting streams for an MKV file.
    
    """

    log    = logging.getLogger( __name__ )

    if CLI is None:
        log.warning( f"{CLIName} CLI not found; cannot extract!" )
        return 10, None 
    
    if text_info is None:
        log.warning( 'No text stream information; cannot extract anything' )
        return 4, None
    
    files   = {}
    extract = [CLI, 'tracks', in_file]                                  # Initialize list to store command for extracting VobSubs from MKV files

    for i, stream in enumerate(text_info): 
        subInfo  = genSubInfo( out_base, stream )
        if checkFilesExist( subInfo['files'] ):
            stream[ subInfo['subtype'] ] = True
            continue

        files[i] = subInfo 
        extract.append( f"{stream['mkvID']}:{subInfo['files'][0]}" )
 
    if len(extract) == 3:  
        return 1, files  
    
    log.info('Extracting Subtitles...')                                      # logging info
    log.debug( extract )
    status = call( extract, stdout = DEVNULL, stderr = STDOUT )            # Run command and dump all output and errors to /dev/null
   
    if status != 0:
        return 3, files
     
    for ii, ff in files.items():
        text_info[ii][ ff['subtype'] ] = (
            checkFilesExist( ff['files'] )
        )

    return 0, files                                                           # Error extracting VobSub(s)
