#!/usr/bin/env python3

import logging
import os, re

import argparse

from video_utils.plex.plexMediaScanner import plexMediaScanner as PMS
from video_utils.plex.utils import plexFile_Info
from video_utils.videotagger.metadata.getTVDb_Info import getTVDb_Info

episode = re.compile( r'([sS]\d{2,4}[eE]\d{2,4})' )

renamedEpisodes = []
renamedMovies   = []
seriesIDs       = {}
def isEpisode( fileName ):
  '''
  Function to check if is episode.
  Uses regex pattern to check for SxxEyy in path
  '''
  res = episode.findall( fileName )
  return len(res) == 1

def replaceIMDbID( path, newID=None ):
  '''
  Function to replace the IMDb ID in the file
  name with a new ID
  '''
  if not newID: return path

  dirName, baseName = os.path.split( path )
  baseName     = baseName.split('.')
  baseName[-2] = str(newID)
  baseName     = '.'.join( baseName )
  return os.path.join( dirName, baseName )

def renameEpisode( path ):
  '''
  Function to create hard link to original file
  with new file name
  '''
  log = logging.getLogger(__name__)
  log.debug( 'Found episode: {}'.format(path) )
  dirName = os.path.basename( os.path.dirname( path ) )
  if ('season' not in dirName.lower()):
    log.info('File in subdirectory, creating hardlink')
    seasonDir = os.path.dirname( os.path.dirname( path ) )
    series    = os.path.basename( os.path.dirname( seasonDir ) )
    target    = os.path.join( seasonDir, os.path.basename( path ) )
    if (series not in seriesIDs):
      baseName = os.path.basename( target ).split('.')[0]
      plexFile = '{} - {}'.format(series, baseName) 
      title, year, seasonEp, episode, ext = plexFile_Info( plexFile )
      seriesIDs[series] = None
      info = getTVDb_Info(episode, title = title, seasonEp = seasonEp, year = year)
      if info and ('seriesId' in info):
        seriesIDs[series] = info['seriesId']
      else:
        log.warning('Failed to get series ID from TVDb: {}'format(path) )      
    if (series in seriesIDs):
      target = replaceIMDbID( target, seriesIDs[series] )      

    log.info( 'Creating hard link: {} --> {}'.format(path, target) )
    return True 
  return False

def renameMovie( path ):
  print( 'Found movie: {}'.format(path) )

res = input('Are you sure you want to do this? (type: YeS sIr) ')
if (res != 'YeS sIr'):
  print('Cancelled')
  exit()

def updateFileNames( rootDir ):
  log = logging.getLogger(__name__)
  for root, dirs, items in os.walk( rootDir ):
    for item in items:
      path = os.path.join( root, item )
      if os.path.isfile( path ):
        if isEpisode( item ):
          if renameEpisode( path ):
            renamedEpisodes.append( path )
        else:
          if renameMovie( path ):
            renamedMovies.append( path )
  
  if (len(renamedEpisodes) < 0):
    log.info( 'Scanning TV Shows to update with new paths' )
    PMS('scan', section='TV Shows', directory=args.tv)
  
    log.info( 'Deleting old files' )
    for path in renamedEpisodes:
      log.debug( 'Deleting: {}'.format( path ) )
  
    log.info( 'Rescanning TV Shows to remove old paths' )
    PMS('scan', section='TV Shows', directory=args.tv)
  
  if (len(renamedMovies) < 0):
    log.info( 'Scanning Movis to update with new paths' )
    PMS('scan', section='Movies', directory=args.movie)
  
    log.info( 'Deleting old files' )
    for path in renamedMovies:
      log.debug( 'Deleting: {}'.format( path ) )
  
    log.info( 'Rescanning Movies to remove old paths' )
    PMS('scan', section='Movies', directory=args.movie)
  
