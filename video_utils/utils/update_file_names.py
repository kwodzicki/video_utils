"""
To update file naming convention

"""

import sys
import os
import re
import shutil

try:
    from imdb import IMDb
except:
    imdb = None
    print('imdbpy not installed, things will break!')
else:
    imdb = IMDb()

from ..videotagger import TMDb
from ..videotagger import TVDb
from ..videotagger.episode import TVDbEpisode
from ..plex.plex_media_scanner import plex_media_scanner as PMS

IMDBID   = re.compile( r'\.(tt\d+)\.' )
SEASONEP = re.compile( r'[sS](\d{2,})[eE](\d{2,})' )
tmdb     = TMDb()
tvdb     = TVDb()

def tv_rename( topdir, path, imdbID, seriesID, rootdir = None, **kwargs ):
    """
    To rename TV episodes to new convention

    """

    _, fbase = os.path.split(path)
    seasonEp = SEASONEP.findall( fbase )
    if len(seasonEp) == 1:# If season episode number found
        season, episode = map(int, seasonEp[0])# Parse into integers
    else:
        print(f'Failed to find season/ep: {path}')
        sys.exit()
    if 'tvdb' in seriesID:
        ep = TVDbEpisode( seriesID, season, episode, **kwargs)
    else:
        res = tvdb.byIMDb(seriesID, season, episode, **kwargs)
        if res is None or len(res) != 1:
            print(f'Incorrect number of results: {path}' )
            return False
        ep = res[0]

    if ep.isSeries:
        ep = TVDbEpisode( ep.id, season, episode )
    if not ep.isEpisode:
        print(f'Not an episode: {path}')
        return False

    # Split base name on period and lose first element (episode name)
    info = fbase.split('.')[1:]
    info.remove( imdbID )# Remove IMDb id from list
    info.insert( 0, ep.get_basename() )
    newdir = rootdir if rootdir is not None else os.path.dirname( topdir )
    newdir = ep.get_dirname(newdir)
    os.makedirs( newdir, exist_ok=True)

    newname = '.'.join(info)
    newpath = os.path.join( newdir, newname )
    if os.path.isfile( newpath ):
        print( f'Source         : {path}' )
        print( f'Already Exists : {newpath}' )
        return newdir

    try:
        shutil.copy( path, newpath )
    except:
        return False

    ep.write_tags( newpath )
    shutil.copystat( path, newpath )
    print( f'Source         : {path}' )
    print( f'Copy created   : {newpath}' )
    print()
    return newdir

def movie_rename( topdir, path, metadata, imdbID, rootdir = None):
    """
    To rename movies to new convention

    """

    _, fbase = os.path.split(path)

    # Split on period and lose first element (movie name)
    info = fbase.split('.')[1:]
    mod  = info.pop(0)# Pop qualifier off of list (i.e., Unrated, etc.)
    info.pop(0)
    info.remove( imdbID )
    metadata.setVersion( mod )
    info.insert( 0, metadata.get_basename() )
    newdir = rootdir if rootdir is not None else os.path.dirname( topdir )
    newdir = metadata.get_dirname(newdir)
    os.makedirs( newdir, exist_ok=True )
    newname = '.'.join(info)
    newpath = os.path.join( newdir, newname )
    if os.path.isfile( newpath ):
        print( f'Source         : {path}' )
        print( f'Already Exists : {newpath}' )
        return newdir

    try:
        shutil.copy( path, newpath )
    except:
        return False

    metadata.write_tags( newpath )
    shutil.copystat( path, newpath )
    print( f'Source         : {path}' )
    print( f'Copy created   : {newpath}' )
    print()
    return newdir

def gen_hard_links( topdir, rootdir = None, **kwargs ):
    """
    Function to generate hard links to existing files using
    new file nameing convention. Will walk through given directory,
    finding all files with IMDBid in name. Will then get TVDb or
    TMDb information for renaming.

    """

    imdbIDs  = {}

    if os.path.isfile(topdir):
        imdbID = IMDBID.findall( topdir )# Get IMDb ID from file name
        if len(imdbID) == 1:# If IMDB id
            imdbID = imdbID[0]# Get only instance
            if imdbID not in imdbIDs:
                # If IMDB id not in imdbIDs dictionary, add key with list as value
                imdbIDs[imdbID] = []
            imdbIDs[imdbID].append( topdir )# Append path to list under IMDb id
    else:
        for root, _, items in os.walk(topdir):
            for item in items:
                imdbID = IMDBID.findall( item )# Get IMDb ID from file name
                if len(imdbID) != 1:
                    continue
                imdbID = imdbID[0]# Get only instance
                if imdbID not in imdbIDs:
                    # If IMDB id not in imdbIDs dictionary, add key with list as value
                    imdbIDs[imdbID] = []
                # Append path to list under IMDb id
                imdbIDs[imdbID].append( os.path.join(root, item) )

    to_remove = []
    to_scan   = []
    # Iterate over all IMDb IDs in imdbIDs dictioanry
    for imdbID, paths in imdbIDs.items():
        res = imdb.get_movie( imdbID[2:] )# Get information from imdbpy
        if 'episode of' in res:
            seriesID = res['episode of'].getID()# Get series ID
            for path in paths:# Iterate over all files that contain this ID
                newdir = tv_rename( topdir, path, imdbID, seriesID, rootdir, **kwargs)
                if newdir:# If hardlink created
                    to_scan.append( newdir )
                    to_remove.append( path )
        else:
            # Get TMDbMovie object using IMDb id
            # Use that information to create new file path using get_dirname and get_basename
            # Create hard link to old file using new path
            res = tmdb.byIMDb( imdbID, **kwargs )
            if res is None:
                print(f'Failed for: {paths[0]}' )
                continue
            movies = res.get('movie_results', None)
            if movies is None:
                print(f'Failed for: {paths[0]}' )
                continue
            if len(movies) != 1:
                print(f'Too many (or no) movies found: {paths[0]}')
                continue
            movie = movies[0]
            for path in paths:
                if movie_rename( topdir, path, movie, imdbID, rootdir ):
                    to_remove.append( path )

    return to_scan, to_remove

def update_specials(season00, dbID, rootdir, **kwargs):
    """
    Update special episodes?

    """

    to_remove = []
    for root, _, items in os.walk(season00):
        for item in items:
            path = os.path.join(root, item)
            if not os.path.isfile(path):
                continue
            seasonEp = re.findall( r'[sS](\d{2,})[eE](\d{2,})', item )
            if len(seasonEp) == 1:
                imdbID = IMDBID.findall( item )
                if len(imdbID) == 1:
                    imdbID = imdbID[0]
                newdir = tv_rename( season00, path, imdbID, dbID, rootdir )
                if newdir:
                    to_remove.append( path )

    return None, to_remove


def update_file_names(*args, rootdir = None, dbID = None, **kwargs):
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
            tmp = rootdir if rootdir else arg

            section = (
                os.path.basename( os.path.dirname(tmp) )
                if os.path.basename(tmp) == '' else
                os.path.basename(tmp)
            )

            root  = os.path.dirname(tmp)
            indir = os.path.split( indir )
            indir = indir[0] if indir[1] == '' else os.path.join( *indir )

            print( f'Working on: {indir}' )
            if dbID:
                _, to_remove = update_specials( indir, dbID, root, **kwargs )
            else:
                _, to_remove = gen_hard_links( indir, rootdir = root, **kwargs)

            if len(to_remove) == 0:
                continue

            res = input('Want to run Plex Media Scanner (YES/n/exit): ')
            if res == 'exit':
                sys.exit()

            if res != 'YES':
                continue
            # Run plex media scanner
            PMS(section)

            res  = input('Want to delete old files (YES/n/exit): ')
            if res == 'exit':
                sys.exit()
            if res != 'YES':
                continue

            for path in to_remove:
                try:
                    os.remove( path )
                except:
                    print(f'Failed to remove file: {path}')
                else:
                    print(f'Removed file : {path}')

            for root, dirs, _ in os.walk(indir, topdown=False):
                for dir_name in dirs:
                    if dir_name[0] == '.':
                        continue
                    path = os.path.join( root, dir_name )
                    try:
                        os.rmdir( path )
                    except:
                        print(f'Failed to remove directory, is full? {path}' )
                    else:
                        print(f'Removed directory : {path}' )
        PMS(section)
