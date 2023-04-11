import logging
import os, re
from subprocess import check_output
from xml.etree import ElementTree as ET
from uuid import uuid4

from mutagen import mp4

from ..config import CACHEDIR
from ..utils.check_cli import check_cli 
from . import MP42COMMON, MKV2COMMON

try:
  MKVEXTRACT = check_cli('mkvextract')
except:
  MKVEXTRACT = None

def _mp4ExtractCover( info ):
  """
  Write MP4Cover information to temporary file 

  Arguments:
    info  : Dictionary of metadata information in internal format

  Keyword arguments:
    None

  Returns:
    dict: Update info dictionary

  """

  key = 'cover'                                                                         # Key for the info dictionary to use
  if key in info:                                                                       # If key is in info
    if isinstance(info[key], (list,tuple)):                                             # If value is iterable
      if len(info[key]) == 0:                                                           # If length zero
        return info                                                                     # Return info
      else:                                                                             # Else
        info[key] = info[key][0]                                                        # Set value to first element of list
    ext   = 'jpeg' if info[key].imageformat == info[key].FORMAT_JPEG else 'png'         # Set extension based on image type
    cover = os.path.join( CACHEDIR, '{}.{}'.format(uuid4().hex,ext) )                   # Build path to cover file using random uuid
    with open(cover, 'wb') as fid:                                                      # Open file for binary writing
      fid.write( info[key] )                                                            # Write image data
    info[key] = cover                                                                   # Set info[key] to the cover file path

  return info
    
def mp4Reader( filePath ):
  """
  Read metadata from MP4 file and parse into 'internal' format

  Arguments:
    filePath (str): Path to MP4 file to extract metadata from

  Keyword arguments:
    None

  Returns:
    dict: Dictionary containing metadata if found, otherwise, emtpy dict

  """

  log  = logging.getLogger(__name__)
  obj  = mp4.MP4( filePath )                                                            # Create mutagen.mp4.MP4 object
  info = {}                                                                             # Initialize empty dictionary
  for mp4Key, val in obj.items():                                                       # Iterate over key/value pairs in MP4
    if isinstance(val, (tuple,list)):                                                   # If value is an iterable
      val = [v.decode() if isinstance(v, mp4.MP4FreeForm) else v for v in val]          # Decode every MP4FreeForm type element in the iterable
      if len(val) == 1:                                                                 # If only one (1) element in iterable
        val = val[0]                                                                    # Take just that value
    key = MP42COMMON.get(mp4Key, None)                                                  # Get common key if exists 

    if key:                                                                             # If common key found
      info[key] = val                                                                   # Update info dictionary
    else:
      log.debug('Invalid key : {}'.format(mp4Key))                                      # Debug info

  info = _mp4ExtractCover( info )

  return info

def _mkvExtractCover( filePath ):
  """
  Run mkvextact to get first attachment from file

  Arguments:
    filePath (str): Path to MKV file

  Keyword arguments:
    None

  Returns:
    str: Path to cover art file if extraction success, empty string otherwise

  """

  cover = os.path.join( CACHEDIR, uuid4().hex )                                         # Build path to cover file using random uuid
  try:                                                                                  # Try to 
    std = check_output( [MKVEXTRACT, filePath, 'attachments', '1:{}'.format(cover)] )   # Extract cover
  except:                                                                               # On exception
    return ''                                                                           # Set cover to empty string

  mimeType = re.findall(b'MIME type image/(\w+),', std)                                 # Try to get file type from stdout/stderr
  if len(mimeType) == 1:                                                                # If found
    ext = mimeType[0].decode()                                                          # Decode file type
    new = '{}.{}'.format(cover, ext)                                                    # Define new file name
    os.rename( cover, new )                                                             # Rename the file
    return new
  else:                                                                                 # Else
    os.remove( cover )                                                                  # Delete the cover
    return ''                                                                           # Set cover to emty string

def mkvReader( filePath ):
  """
  Read metadata from MKV file and parse into 'internal' format

  Arguments:
    filePath (str): Path to MKV file to extract metadata from

  Keyword arguments:
    None.

  Returns:
    dict: Dictionary containing metadata if found, otherwise, emtpy dict

  """

  log  = logging.getLogger(__name__)
  info = {}                                                                             # Initialize info as empty dictionary
  if MKVEXTRACT is None: return info                                                    # If the MKVEXTRACT command was not found at import, return emtpy dictionary
    
  try:                                                                                  # Try to
    xml = check_output( [MKVEXTRACT, filePath, 'tags'] )                                # Get tags in XML format
  except:                                                                               # If failed
    return info                                                                         # Return info

  root = ET.fromstring(xml)                                                             # Get root of XML
  for tag in root.findall('Tag'):                                                       # Iterate over all Tag keys
    target = tag.find('Targets')                                                        # Try to find Targets in Tag block
    if target:                                                                          # If a target found
      typeVal = int(target.find('TargetTypeValue').text)                                # Get TargetTypeValue as integer
      for simple in tag.findall('Simple'):                                              # Iterate over all Simple tags
        key    = simple.find('Name').text                                               # Get Name
        val    = simple.find('String').text                                             # Get string
        mkvKey = (typeVal, key)                                                         # Define MKV key
        key    = MKV2COMMON.get(mkvKey, None)                                           # Try to get common (internal) key from MKV2COMMON dictionary
        if key:                                                                         # If common key found
          info[key] = val                                                               # Update info dictionary
        else:                                                                           # Else
          log.debug('Invalid key : {}'.format(mkvKey))                                  # Debug info


  info['cover'] = _mkvExtractCover( filePath )                                          # Add cover to info dictionary
 
  return info                                                                           # Return info
