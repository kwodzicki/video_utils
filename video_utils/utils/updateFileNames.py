#!/usr/bin/env python3
import os, re, shutil

try:
  from imdb import IMDb
except:
  imdb = None
  print('imdbpy not installed, things will break!')
else:
  imdb = IMDb()

from ..videotagger import TMDb
from ..videotagger import TVDb
from ..videotagger.Movie import TMDbMovie
from ..videotagger.Episode import TVDbEpisode
from ..plex.plexMediaScanner import plexMediaScanner as PMS

IMDBID   = re.compile( '\.(tt\d+)\.' )
SEASONEP = re.compile( '[sS](\d{2,})[eE](\d{2,})' )
tmdb     = TMDb()
tvdb     = TVDb()

def tvRename( topDir, path, imdbID, seriesID, rootdir = None, **kwargs ):
  fileDir, fileBase = os.path.split(path)                                       # Get dirname and basename
  seasonEp = SEASONEP.findall( fileBase )                                   # GEt season/episode number
  if len(seasonEp) == 1:                                                    # If season episode number found
    season, episode = map(int, seasonEp[0])                                 # Parse into integers
  else:
    print('Failed to find season/ep: {}'.format(path))
    exit()
  if 'tvdb' in seriesID:
    ep = TVDbEpisode( seriesID, season, episode, **kwargs)
  else:
    res = tvdb.byIMDb(seriesID, season, episode, **kwargs)
    if res is None or len(res) != 1:
      print('Incorrect number of results: {}'.format(path) )
      return False 
    ep = res[0]
  if ep.isSeries:                                                               # If it is series
    ep = TVDbEpisode( ep.id, season, episode )                                  # Try to get episode
  if not ep.isEpisode:                                                          # If still not episode
    print('Not an episode: {}'.format(path))                                    # Print message
    return False                                                                # Return

  info = fileBase.split('.')[1:]                                                # Split base name on period and lose first element (episode name)
  info.remove( imdbID )                                                         # Remove IMDb id from list
  info.insert( 0, ep.getBasename() )
  newDir = rootdir if rootdir is not None else os.path.dirname( topDir )
  newDir = ep.getDirname(newDir) 
  if not os.path.isdir( newDir ):
    os.makedirs( newDir )

  newName = '.'.join(info)
  newPath = os.path.join( newDir, newName )
  if os.path.isfile( newPath ):
    print( 'Source         : {}'.format(path) )
    print( 'Already Exists : {}'.format(newPath) )
    return newDir

  try:
    shutil.copy( path, newPath )
  except:
    return False
  else:
    ep.writeTags( newPath )
    shutil.copystat( path, newPath )
    print( 'Source         : {}'.format(path) )
    print( 'Copy created   : {}'.format(newPath) )
    print()
  return newDir

def movieRename( topDir, path, metadata, imdbID, rootdir = None):
  fileDir, fileBase = os.path.split(path)                                       # Get dirname and basename
  info = fileBase.split('.')[1:]                                                # Split on period and lose first element (movie name)
  mod  = info.pop(0)                                                            # Pop qualifier off of list (i.e., Unrated, etc.)
  info.pop(0)
  info.remove( imdbID )                                                         # Remove the IMDb id from list
  metadata.setVersion( mod )
  info.insert( 0, metadata.getBasename() )
  newDir = rootdir if rootdir is not None else os.path.dirname( topDir )
  newDir = metadata.getDirname(newDir) 
  if not os.path.isdir( newDir ):
    os.makedirs( newDir )
  newName = '.'.join(info)
  newPath = os.path.join( newDir, newName ) 
  if os.path.isfile( newPath ):
    print( 'Source         : {}'.format(path) )
    print( 'Already Exists : {}'.format(newPath) )
    return newDir

  try:
    shutil.copy( path, newPath )
  except:
    return False
  else:
    metadata.writeTags( newPath )
    shutil.copystat( path, newPath )
    print( 'Source         : {}'.format(path) )
    print( 'Copy created   : {}'.format(newPath) )
    print()
  return newDir

def genHardLinks( topDir, rootdir = None, **kwargs ):
  """
  Function to generate hard links to existing files using
  new file nameing convention. Will walk through given directory,
  finding all files with IMDBid in name. Will then get TVDb or
  TMDb information for renaming.

  """

  imdbIDs  = {}

  if os.path.isfile(topDir):
    imdbID = IMDBID.findall( topDir )                                           # Get IMDb ID from file name
    if len(imdbID) == 1:                                                      # If IMDB id
      imdbID = imdbID[0]                                                      # Get only instance
      if imdbID not in imdbIDs:
        imdbIDs[imdbID] = []                                                  # If IMDB id not in imdbIDs dictionary, add key with list as value
      imdbIDs[imdbID].append( topDir )                      # Append path to list under IMDb id
  else:
    for root, dirs, items in os.walk(topDir):                                     # Iterate over all files recursively
      for item in items:                                                          # Iterate over items
        imdbID = IMDBID.findall( item )                                           # Get IMDb ID from file name
        if len(imdbID) == 1:                                                      # If IMDB id
          imdbID = imdbID[0]                                                      # Get only instance
          if imdbID not in imdbIDs:
            imdbIDs[imdbID] = []                                                  # If IMDB id not in imdbIDs dictionary, add key with list as value
          imdbIDs[imdbID].append( os.path.join(root, item) )                      # Append path to list under IMDb id
 
  toRemove = []                                                                 # List of all files that can be deleted
  toScan   = []
  for imdbID, paths in imdbIDs.items():                                         # Iterate over all IMDb IDs in imdbIDs dictioanry
    res = imdb.get_movie( imdbID[2:] )                                          # Get information from imdbpy
    if 'episode of' in res:                                                     # If episode
      seriesID = res['episode of'].getID()                                      # Get series ID
#      fileBase = os.path.basename( paths[0] )
#      seasonEp = SEASONEP.findall( fileBase )                                   # GEt season/episode number
#      if len(seasonEp) == 1:                                                    # If season episode number found
#        season, episode = map(int, seasonEp[0])                                 # Parse into integers
#      else:
#        print('Failed to find season/ep: {}'.format(paths[0]))
#        exit()
#      seriesID = res['episode of'].getID()                                      # Get series ID
#      res = tvdb.byIMDb(seriesID, season, episode)
#      if res is None or len(res) != 1:
#        print('Incorrect number of results: {}'.format(paths[0]) )
#        continue
#      episode = res[0]
#      if not episode.isEpisode:
#        print('Not an episode: {}'.format(paths[0]))
#        continue
      for path in paths:                                                        # Iterate over all files that contain this ID
        newDir = tvRename( topDir, path, imdbID, seriesID, rootdir, **kwargs) 
        if newDir:                                                              # If hardlink created
          toScan.append( newDir )
          toRemove.append( path )                                               # Append path to the toRemove list
    else:
      # Get TMDbMovie object using IMDb id
      # Use that information to create new file path using getDirname and getBasename
      # Create hard link to old file using new path
      res = tmdb.byIMDb( imdbID, **kwargs )
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
        if movieRename( topDir, path, movie, imdbID, rootdir ):                    # If hardlink created
          toRemove.append( path )                                               # Append path to the toRemove list

  return toScan, toRemove                                                               # Return the toRemove list

def updateSpecials(season00, dbID, rootdir, **kwargs):
  toRemove = []
  for root, dirs, items in os.walk(season00):
    for item in items:
      path = os.path.join(root, item)
      if os.path.isfile(path):
        seasonEp = re.findall( r'[sS](\d{2,})[eE](\d{2,})', item )
        if len(seasonEp) == 1:
          imdbID = IMDBID.findall( item )                                           # Get IMDb ID from file name
          if len(imdbID) == 1:                                                      # If IMDB id
            imdbID = imdbID[0]                                                      # Get only instance
          newDir  = tvRename( season00, path, imdbID, dbID, rootdir ) 
          if newDir:                                                              # If hardlink created
            toRemove.append( path )                                               # Append path to the toRemove list
  return None, toRemove
  

def updateFileNames(*args, rootdir = None, dbID = None, **kwargs):
  """
  Function to iterate over Plex Library directories to rename

  Arguments:
    *args: A bunch of comma separated paths. These can either be top level
             Library directories OR individual directories within a library.
             If they are individual directories within a library, then
             must set the rootdir keyword for things to work correctly.

  Keyword arguments:
    rootdir (str): Set if scanning a subset of directories in a library
                  directory. For example, if renaming files in Westworld
                  and the args path is /path/to/TV Shows/Westworld, then
                  should set rootdir=/path/to/TV Shows
    dbID (str): Force a given TV series ID
    **kwargs: Various other keywords, including the dvdOrder key

  Returns:
    None

  """

  for arg in args:
    for item in os.listdir(arg):
      indir = os.path.join(arg, item)
      #if not os.path.isdir(indir):
        #print( item )
        #exit()
        #continue
      if rootdir:
        tmp = rootdir
      else:
        tmp = arg

      if os.path.basename(tmp) == '':
        section = os.path.basename( os.path.dirname(tmp) )
      else:
        section = os.path.basename(tmp)

      root  = os.path.dirname(tmp)
      indir = os.path.split( indir )
      if indir[1] == '':
        indir = indir[0]
      else:
        indir = os.path.join( *indir )
      print( 'Working on: {}'.format( indir ) )
      if dbID:
        scanDirs, toRemove = updateSpecials( indir, dbID, root, **kwargs )
      else:
        scanDirs, toRemove = genHardLinks( indir, rootdir = root, **kwargs)
       
      if len(toRemove) != 0:
        res      = input('Want to run Plex Media Scanner (YES/n): ')
        if res == 'YES':
          # Run plex media scanner
          PMS('scan', 'refresh', section=section)#, directory=rootdir if rootdir is not None else indir)

          res  = input('Want to delete old files (YES/n): ')
          if res == 'YES':
            for path in toRemove:
              try:
                os.remove( path )
              except:
                print('Failed to remove file: {}'.format(path))
              else:
                print('Removed file : {}'.format(path))

            for root, dirs, items in os.walk(indir, topdown=False):
              for dir in dirs:
                if dir[0] == '.': continue
                path = os.path.join( root, dir )
                try:
                  os.rmdir( path )
                except:
                  print('Failed to remove directory, is full? {}'.format(path) )
                else:
                  print('Removed directory : {}'.format(path) )
            #PMS('scan', 'refresh', section=section)#, directory=rootdir if rootdir is not None else indir)
    PMS('scan', 'refresh', section=section)#, directory=rootdir if rootdir is not None else indir)

