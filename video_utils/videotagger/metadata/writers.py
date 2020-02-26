import logging
import os, sys, re
from mutagen import mp4
from xml.etree import ElementTree as ET
from subprocess import Popen, STDOUT, DEVNULL

from ...utils.checkCLI import checkCLI
from .utils import download

try:                                                                        # Try to...
  from .metadata.getMetaData import getMetaData                           # Import getMetaData function from makemkv_to_mp4
except:                                                                     # On exception...
  getMetaData = None
 
try:
  checkCLI( 'mkvpropedit' )
except:
  logging.getLogger(__name__).error('mkvpropedit NOT installed')
  raise


################################################################################
def mp4Tags( file, metaData = None ):
  '''
  Name:
    mp4Tags
  Purpose:
    A function to parse information from the IMDbPY API and
    write Tag data to MP4 files.
  Inputs:
    file   : Full path of file to write metadata to.
  Outputs:
    Returns following values based on completion.
       0 : Completed successfully.
       1 : Input was NOT and MP4
       2 : IMDb ID was not valid
       3 : Failed to download information from IMDb AND themoviedb.org
       4 : Writing tags is NOT possible
       5 :  Failed when trying to remove tags from file.
       6 : Failed when trying to write tags to file.
      10 : IMDbPY not installed AND getTMDb_Info failed to import
      11 : File is too large
  Keywords:
    metaData : Set to result of .toMP4() method of metaData object
  Dependencies:
    mutagen
  Author and History: 
    Kyle R. Wodzicki     Created 18 Feb. 2018
  '''
  log = logging.getLogger(__name__);                                                  # Set up a logger
  log.debug( 'Testing file is MP4' );                                                 # Debugging information
  if not file.endswith('.mp4'):                                                       # If the input file does NOT end in '.mp4'
    log.error('Input file is NOT an MP4!!!'); return 1;                         # Print message and return code one (1)

  log.debug( 'Testing file too large' );                                              # Debugging information
  if os.stat(file).st_size > sys.maxsize:                                             # If the file size is larger than the supported maximum size
    log.error('Input file is too large!'); return 11;                           # Print message and return code eleven (11)
    
  if metaData is None:                                                                # IF the metaData key is NOT set
    log.debug( 'No metadata input, attempting to download' );                   # Debugging information
    metaData = getMetaData( file )                           # Get the metaData from imdb.com and themoviedb.org
  if metaData is None:
    log.warning('Failed to download metaData! Tag(s) NOT written!');            # Log a warning that the metaData failed to download
    return 3;                                                                   # Return code 3
  else:
    metaData = metaData.toMP4()

  filedir, filebase = os.path.dirname( file ), os.path.basename( file );              # Get the directory and baseanem of the file

  log.debug('Loading file using mutagen.mp4.MP4');                              # Debugging information
  handle = mp4.MP4(file);                                                       # Initialize mutagen MP4 handler
  log.debug('Attempting to add tag block to file');                             # Debugging information
  try:                                                                          # Try to...
    handle.add_tags();                                                          # Add new tags to the file
  except mp4.error as e:                                                        # On exception, catch the error
    if 'already exists' in e.__str__():                                         # If the error is that the tag block already exists
      log.debug('MP4 tags already exist in file.');                             # Debugging information
      pass;                                                                     # Pass
    else:                                                                       # Else, adding is not possible
      log.error('Could NOT add tags to file!');                                 # Log an error
      return 4;                                                                 # Return code 4
  try:                                                                          # Try to...
    handle.delete();                                                            # Remove all old tags.
  except mp4.error as e:                                                        # On exception, catch the error
    log.error( e.__str__() );                                                   # Log the error
    return 5;                                                                   # Return code 5
  log.debug('Setting basic inforamtion');                                       # Debugging information
  for key, val in metaData.items():
    if key == 'covr' and val != '':
      log.debug('Attempting to get coverart');                                    # Debugging information
      fmt  = mp4.AtomDataType.PNG if val.endswith('png') else mp4.AtomDataType.JPEG;# Set format for the image
      data = download( val )
      if data is not None:
        val = [ mp4.MP4Cover( data, fmt ) ];                                        # Add image to file
      else:
        continue
    handle[key] = val

  log.debug('Saving tags to file');                                             # Debugging information
  try:                                                                          # Try to...
    handle.save();                                                              # Save the tags
  except:                                                                       # On exception
    log.error('Failed to save tags to file!');                                  # Log an error
    return 6
  return 0;

################################################################################
def addTarget( ele, level ):
  tags = ET.SubElement(ele, 'Tag')
  targ = ET.SubElement(tags, 'Targets')
  ET.SubElement(targ, 'TargetTypeValue').text = str(level)
  return tags

################################################################################
def addTag( ele, key, val ):
  if isinstance(val, (list,tuple,)):
    if isinstance(val[0], bytes):
      val = [v.decode() for v in val]
    val = ','.join(map(str, val))
  elif isinstance(val, bytes):
    val = val.decode()

  simple = ET.SubElement(ele, 'Simple')
  ET.SubElement(simple, 'Name').text   = key
  ET.SubElement(simple, 'String').text = val

################################################################################
def mkvTags( file, metaData = None ):
  '''
  Name:
      mkvTags
  Purpose:
      A function to parse information from the IMDbPY API and
      write Tag data to MP4 files.
  Inputs:
      file   : Full path of file to write metadata to.
  Outputs:
      Returns following values based on completion.
           0 : Completed successfully.
           1 : Input was NOT and MKV
           2 : IMDb ID was not valid
           3 : Failed to download information from IMDb AND themoviedb.org
           4 : Writing tags is NOT possible
           5 :    Failed when trying to remove tags from file.
           6 : Failed when trying to write tags to file.
          10 : IMDbPY not installed AND getTMDb_Info failed to import
          11 : File is too large
  Keywords:
      metaData : Set to result of .toMKV() method from metaData object
  Dependencies:
      mkvpropedit
  Author and History: 
      Kyle R. Wodzicki     Created 18 Feb. 2018
  '''
  log = logging.getLogger(__name__);                                              # Set up a logger
  log.debug( 'Testing file is MKV' );                                             # Debugging information
  if not file.endswith('.mkv'):                                                   # If the input file does NOT end in '.mp4'
    log.error('Input file is NOT an MKV!!!'); return 1;                         # Print message and return code one (1)

  log.debug( 'Testing file too large' );                                          # Debugging information
  if os.stat(file).st_size > sys.maxsize:                                         # If the file size is larger than the supported maximum size
    log.error('Input file is too large!'); return 11;                           # Print message and return code eleven (11)
      
  if metaData is None:                                                            # IF the metaData key is NOT set
    log.debug( 'No metadata input, attempting to download' );                   # Debugging information
    metaData = getMetaData( file )
  if metaData is None:
    log.warning('Failed to download metaData! Tag(s) NOT written!');            # Log a warning that the metaData failed to download
    return 3;                                                                   # Return code 3
  else:
    metaData = metaData.toMKV()

  fileDir, fileBase = os.path.dirname( file ), os.path.basename( file );          # Get the directory and baseanem of the file

  log.debug('Setting basic inforamtion');                                       # Debugging information
  top  = ET.Element('Tags')
  tags = {}

  coverFile = None
  for key, val in metaData.items():
    if key == 'covr':
      coverFile = download( val, saveDir = fileDir )
    else:
      TargetTypeValue, tag = key
      if TargetTypeValue not in tags:      
        tags[TargetTypeValue] = addTarget( top, TargetTypeValue )
      addTag( tags[TargetTypeValue], tag, val )

  fileDir   = os.path.dirname( file )
  xmlFile   = os.path.join( fileDir, 'tags.xml' )

  ET.ElementTree(top).write( xmlFile ) 

  cmd = ['mkvpropedit', file, '-t', 'all:{}'.format(xmlFile)]

  if coverFile and os.path.isfile( coverFile ):                                         # If the 'full-size cover url' is in the metaData
    cmd += ['--attachment-name', 'Cover art']
    cmd += ['--add-attachment',   coverFile] 

  log.debug('Saving tags to file');                                             # Debugging information
   
  proc = Popen(cmd, stdout = DEVNULL, stderr = STDOUT)
  proc.wait()
  
  try:
    os.remove( xmlFile )
  except:
    pass

  try:
    os.remove( coverFile )
  except:
    pass
  
  if (proc.returncode != 0): 
    log.error('Failed to save tags to file!');                                  # Log an error
    return 6
 
  return 0;
