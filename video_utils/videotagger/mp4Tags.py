import logging
import os, sys, re
from mutagen import mp4

from .utils import download
try:                                                                            # Try to...
  from .metadata.getMetaData import getMetaData                                 # Import getMetaData function from makemkv_to_mp4
except:                                                                         # On exception...
  getMetaData = None                                                            # Set getMetaData to None
  
'''
A note from the mutagen package:
The freeform ‘----‘ frames use a key in the format ‘----:mean:name’ where ‘mean’
is usually ‘com.apple.iTunes’ and ‘name’ is a unique identifier for this frame.
The value is a str, but is probably text that can be decoded as UTF-8. Multiple
values per key are supported.
'''

freeform = lambda x: '----:com.apple.iTunes:{}'.format( x );                                # Function to return freeform tag
################################################################################
def encode( input ):
  '''Function to encode data to correct type'''
  if type(input) is list:                                                             # If the input is type list
    try:                                                                        # Try to...
      return [ str.encode( i['name'] ) for i in input ];                  # Convert to binary strings taking the 'name' of every element of i
    except:                                                                     # On exception
      return [ str.encode( i ) for i in input ];                          # Convert each element to binary string
  else:                                                                               # Else, not a list
    return [ str.encode( input ) ];                                             # Just get binary string
################################################################################
def getPlot( metaData, short = False ):
  '''Function to parse plot information'''
  for tag in ["plot outline", "plot"]:                                          # Iterate over the two tags
    if tag in metaData:                                                         # If the tag is in metaData dictionary
      tmp = metaData[tag];                                                      # Set tmp to metaData[tag]
      if type(tmp) is not list: tmp = [ tmp ];                                  # If tmp is NOT a list, make it a list
      for i in tmp:                                                             # Iterate over every element of tmp
        if short:                                                               # If the short keyword is set, try to return the short (<240 characters) plot
          if len(i) < 240: return i;                                            # If the length of i is less than 240 characters, return i
        else:                                                                   # Else, short is NOT set so attempt to return long plot
          if len(i) > 240: return i;                                            # If the length of i is greater than 240 characters, return the plot
  return None;                                                                  # If made it here, nothing matched criteria so return None.
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
    IMDbid    : Set to the IMDb id to use for file.
                 Default tries to get from file name.
    metaData : Set to result of previous call to
                 imdb.IMDb().get_movie(). Default is to 
                 download the data.
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
  for key, val in metaData.toMP4().items():
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
