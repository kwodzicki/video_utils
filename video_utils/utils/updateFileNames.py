#!/usr/bin/env python3
import os, re

from imdb import IMDb
from ..videotagger import TMDb
from ..videotagger import TVDb
from ..videotagger.Movie import TMDbMovie
from ..videotagger.Episode import TVDbEpisode
from ..plex.plexMediaScanner import plexMediaScanner as PMS

IMDBID   = re.compile( '\.(tt\d+)\.' )
SEASONEP = re.compile( '[sS](\d{2,})[eE](\d{2,})' )
imdb     = IMDb()
tmdb     = TMDb()
tvdb     = TVDb()

def tvRename( topDir, path, metadata, imdbID ):
  fileDir, fileBase = os.path.split(path)                                       # Get dirname and basename
  info = fileBase.split('.')[1:]                                                # Split base name on period and lose first element (episode name)
  info.remove( imdbID )                                                         # Remove IMDb id from list
  info.insert( 0, metadata.getBasename() )
  newPath = os.path.dirname( topDir )
  newPath = metadata.getDirname(newPath) 
  newName = '.'.join(info)
  newPath = os.path.join( newPath, newName )
  print( newPath )                                                       # Join remaining on period
  return True

def movieRename( topDir, path, metadata, imdbID ):
  fileDir, fileBase = os.path.split(path)                                       # Get dirname and basename
  info = fileBase.split('.')[1:]                                                # Split on period and lose first element (movie name)
  mod  = info.pop(0)                                                            # Pop qualifier off of list (i.e., Unrated, etc.)
  info.pop(0)
  info.remove( imdbID )                                                         # Remove the IMDb id from list
  metadata.version = mod
  info.insert( 0, metadata.getBasename() )
  newPath = os.path.dirname( topDir )
  newPath = metadata.getDirname(newPath) 
  newName = '.'.join(info)
  newPath = os.path.join( newPath, newName ) 
  print( newPath )                                                       # Join on period
  return True

def genHardLinks( topDir ):
  '''
  Function to generate hard links to existing files using
  new file nameing convention. Will walk through given directory,
  finding all files with IMDBid in name. Will then get TVDb or
  TMDb information for renaming.
  '''
  imdbIDs  = {}
  for root, dirs, items in os.walk(topDir):                                     # Iterate over all files recursively
    for item in items:                                                          # Iterate over items
      imdbID = IMDBID.findall( item )                                           # Get IMDb ID from file name
      if len(imdbID) == 1:                                                      # If IMDB id
        imdbID = imdbID[0]                                                      # Get only instance
        if imdbID not in imdbIDs: imdbIDs[imdbID] = []                          # If IMDB id not in imdbIDs dictionary, add key with list as value
        imdbIDs[imdbID].append( os.path.join(root, item) )                      # Append path to list under IMDb id
  
  toRemove = []                                                                 # List of all files that can be deleted
  for imdbID, paths in imdbIDs.items():                                         # Iterate over all IMDb IDs in imdbIDs dictioanry
    res = imdb.get_movie( imdbID[2:] )                                          # Get information from imdbpy
    if 'episode of' in res:                                                     # If episode
      fileBase = os.path.basename( paths[0] )
      seasonEp = SEASONEP.findall( fileBase )                                   # GEt season/episode number
      if len(seasonEp) == 1:                                                    # If season episode number found
        season, episode = map(int, seasonEp[0])                                 # Parse into integers
      else:
        print('Failed to find season/ep: {}'.format(paths[0]))
        exit()
      seriesID = res['episode of'].getID()                                      # Get series ID

      res = tvdb.byIMDb(seriesID, season, episode)
      if len(res) != 1:
        print('Incorrect number of results: {}'.format(paths[0]) )
      episode = res[0]
      if not episode.isEpisode:
        print('Not an episode: {}'.format(paths[0]))

      for path in paths:                                                        # Iterate over all files that contain this ID
        if tvRename( topDir, path, episode, imdbID ):                                # If hardlink created
          toRemove.append( path )                                               # Append path to the toRemove list
      exit()
    else:
      # Get TMDbMovie object using IMDb id
      # Use that information to create new file path using getDirname and getBasename
      # Create hard link to old file using new path
      res = tmdb.byIMDb( imdbID )
      if res is None:
        print('Failed for: {}'.format(paths[0]) )
        continue
      movies = res.get('movie_results', None)
      if movies is None:
        print('Failed for: {}'.format(paths[0]) )
        continue
      elif len(movies) != 1:
        print('Too many (or no) movies found: {}'.format(paths[0]))
        continue
      movie = movies[0]
      for path in paths:                                                        # Iterate over all paths with ID
        if movieRename( topDir, path, movie, imdbID ):                             # If hardlink created
          toRemove.append( path )                                               # Append path to the toRemove list
      exit()
  return toRemove                                                               # Return the toRemove list

def updateFileNames(*args):
  for indir in args:
    indir = os.path.split( indir )
    if indir[1] == '':
      indir = indir[0]
    else:
      indir = os.path.join( *indir )
    print( 'Working on: {}'.format( indir ) )
    toRemove = genHardLinks( indir )

    res      = input('Want to run Plex Media Scanner (YES/n): ')
    if res != 'YES':
      print( 'Cancelled' )
      exit()
    # Run plex media scanner

    res  = input('Want to delete old files (YES/n): ')
    if res != 'YES':
      print( 'Cancelled' )
      exit()
    for path in toRemove:
      try:
        print('Removed file')
        #os.remove( path )
      except:
        print('Failed to remove file: {}'.format(path))

    for root, dirs, items in os.walk(indir, topdown=False):
      for dir in dirs:
        if dir[0] == '.': continue
        path = os.path.join( root, dir )
        try:
          os.rmdir( path )
        except:
          print('Failed to remove directory, is full? {}'.format(path) )


