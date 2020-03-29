import logging

import os, re
from ..videotagger.metadata.getTMDb_Info import getTMDb_Info
from ..videotagger.metadata.getTVDb_Info import getTVDb_Info


SEASONEP = re.compile( r'[sS](\d{2,4})[eE](\d{2,4})' )

def rename2Plex( file ):
  '''
  Function to rename file to Plex compatible naming based
  on TVDb ID or TMDb ID in file name.
  Assumes using input file convention outlined in docs.
  See following for Plex conventions:
    https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/
    https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/
  Inputs:
    file  : Full path to file
  Keywords:
    None.
  Returns:
    Returns path to file; new name if renamed, input name if not renamed,
    and metadata from TVDb or TMDb, if found
  '''
  log = logging.getLogger(__name__)
  fileDir, fileBase = os.path.split(file)
  fileBase, fileExt = os.path.splitext( fileBase )

  seasonEp = SEASONEP.findall( fileBase )
  if (len(seasonEp) == 1): 
    log.info( 'File is episode: {}'.format(file) )
    TVDbID = fileBase.split('.')[0]
    info = getTVDb_Info( TVDbID = TVDbID, seasonEp = tuple( map(int, seasonEp[0]) ) )
    if info:
      fName = 'S{:02d}E{:02d} - {}.{}{}'.format(
        info['airedSeason'], info['airedEpisodeNumber'], info['episodeName'], 
        TVDbID, fileExt
      )
 
  else:
    log.info( 'File is movie: {}'.format(file) )
    TMDbID, extra = fileBase.split('.')
    info = getTMDb_Info( TMDbID = TMDbID )
    if info:
      fName = '{} ({}).{}.{}{}'.format(
          info['title'], info['year'], extra, TMDbID, fileExt
      )
  if info: 
    newFile = os.path.join( fileDir, fName )    
    log.info( 'Renaming file: {} ---> {}'.format(file, newFile) )
    os.rename( file, newFile )
    return newFile, info

  return file, None
