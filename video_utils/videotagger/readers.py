"""
To read metadata from MP4 and MKV files

"""

import logging
import os
import re
from subprocess import check_output
from xml.etree import ElementTree as ET
from uuid import uuid4

from mutagen import mp4

from ..config import CACHEDIR
from ..utils.check_cli import check_cli
from .tags import MP42COMMON, MKV2COMMON

try:
    MKVEXTRACT = check_cli('mkvextract')
except:
    MKVEXTRACT = None

def _mp4_extract_cover( info ):
    """
    Write MP4Cover information to temporary file 

    Arguments:
        info  : Dictionary of metadata information in internal format

    Keyword arguments:
        None

    Returns:
        dict: Update info dictionary

    """

    key = 'cover'
    if key in info:
        if isinstance(info[key], (list,tuple)):
            if len(info[key]) == 0:
                return info
            # Set value to first element of list
            info[key] = info[key][0]

        # Set extension based on image type
        ext   = 'jpeg' if info[key].imageformat == info[key].FORMAT_JPEG else 'png'
        # Build path to cover file using random uuid
        cover = os.path.join( CACHEDIR, f'{uuid4().hex}.{ext}' )
        with open(cover, 'wb') as fid:
            fid.write( info[key] )
        info[key] = cover

    return info

def mp4_reader( file_path ):
    """
    Read metadata from MP4 file and parse into 'internal' format

    Arguments:
        file_path (str): Path to MP4 file to extract metadata from

    Keyword arguments:
        None

    Returns:
        dict: Dictionary containing metadata if found, otherwise, emtpy dict

    """

    log  = logging.getLogger(__name__)

    # Create mutagen.mp4.MP4 object
    obj  = mp4.MP4( file_path )
    info = {}
    for mp4_key, val in obj.items():
        if isinstance(val, (tuple,list)):
            # Decode every MP4FreeForm type element in the iterable
            val = [v.decode() if isinstance(v, mp4.MP4FreeForm) else v for v in val]
            # If only one (1) element in iterable, convert to scalar
            if len(val) == 1:
                val = val[0]
        key = MP42COMMON.get(mp4_key, None)

        if key:
            info[key] = val
        else:
            log.debug('Invalid key : %s', mp4_key)

    info = _mp4_extract_cover( info )

    return info

def _mkv_extract_cover( file_path ):
    """
    Run mkvextact to get first attachment from file

    Arguments:
        file_path (str): Path to MKV file

    Keyword arguments:
        None

    Returns:
        str: Path to cover art file if extraction success, empty string otherwise

    """

    # Build path to cover file using random uuid
    cover = os.path.join( CACHEDIR, uuid4().hex )
    try:
        std = check_output( [MKVEXTRACT, file_path, 'attachments', f'1:{cover}'] )
    except:
        return ''

    # Try to get file type from stdout/stderr
    mime_type = re.findall( b'MIME type image/(\w+),', std)

    # If found
    if len(mime_type) == 1:
        ext = mime_type[0].decode()# Decode file type
        new = f'{cover}.{ext}'# Define new file name
        os.rename( cover, new )# Rename the file
        return new# Return path to new file

    os.remove( cover )
    return ''

def mkv_reader( file_path ):
    """
    Read metadata from MKV file and parse into 'internal' format

    Arguments:
        file_path (str): Path to MKV file to extract metadata from

    Keyword arguments:
        None.

    Returns:
        dict: Dictionary containing metadata if found, otherwise, emtpy dict

    """

    log  = logging.getLogger(__name__)
    info = {}
    if MKVEXTRACT is None:
        return info

    try:
        xml = check_output( [MKVEXTRACT, file_path, 'tags'] )
    except:
        return info

    root = ET.fromstring(xml)
    for tag in root.findall('Tag'):
        # Try to find Targets in Tag block
        target = tag.find('Targets')
        if not target:
            continue

        # Get TargetTypeValue as integer
        type_val = int(target.find('TargetTypeValue').text)

        # Iterate over all Simple tags
        for simple in tag.findall('Simple'):
            key     = simple.find('Name').text# Get Name
            val     = simple.find('String').text# Get string
            mkv_key = (type_val, key)# Define MKV key

            # Try to get common (internal) key from MKV2COMMON dictionary
            key = MKV2COMMON.get(mkv_key, None)
            if key:
                info[key] = val
            else:
                log.debug('Invalid key : %s', mkv_key)

    # Add cover to info dictionary
    info['cover'] = _mkv_extract_cover( file_path )

    return info
