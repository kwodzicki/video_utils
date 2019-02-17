#!/usr/bin/env python
import logging;
import os;
from video_utils.videotagger.metadata.getIMDb_ID import getIMDb_ID;

def file_rename( in_file ):
  log               = logging.getLogger(__name__);
  log.debug( 'Getting information from file name' );

  fileDir           = os.path.dirname(  in_file );
  fileBase          = os.path.basename( in_file );                              # Get base name of input file
  series, se, title = fileBase.split(' - ');                                    # Split the file name on ' - '; not header information of function
  title             = title.split('.');                                         # Split the title on period; this is to get file extension
  ext               = title[-1];                                                # Get the file extension; last element of list
  title             = '.'.join(title[:-1]);                                     # Join all but last element of title list using period; will rebuild title
  log.debug('Attempting to get IMDb ID')
  imdbId            = getIMDb_ID( in_file );                                    # Try to get IMDb id

  if not imdbId: 
    log.warning( 'No IDMb ID! Renaming file without it')
    imdbId = '';                                                                # If no IMDb id found, set imdbId to emtpy string

  new = '{} - {}.{}.{}'.format(se.lower(), title, imdbId, ext);                 # Build new file name
  new = os.path.join( fileDir, new );                                           # Build new file path
  os.rename( in_file, new );                                                    # Rename the file
  return new;
  
if __name__ == "__main__":
  import sys;
  if len(sys.argv) == 2:
    file_rename( sys.argv[1] )