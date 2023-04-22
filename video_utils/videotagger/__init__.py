"""
Tag video files

Download and write metadata to video files from
TMDb or TVDb

"""

import logging
import os
import re
import time

from .utils import is_id
from .api import BaseAPI
from .person import Person
from . import movie as _movie
from . import series as _series
from . import episode as _episode

SEASONEP = re.compile(r'[sS](\d{2,})[eE](\d{2,})')

class TMDb( BaseAPI ):
    """Class for high-level interaction with TMDb API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__log = logging.getLogger(__name__)

    def search( self, title = None, episode = None, seasonEp = None, year = None, page = None ):
        """
        Search TMDb for a given Movie or TV episode

        Keyword arguments:
            title (str) : Title of movie OR title of TV Series
            episode (str) : Title of TV series episode
            seasonEp (tuple) : The season and episode number of the
                TV series episode

        """

        params = {'query' : title}
        if page:
            params['page'] = page

        json = self._get_json( self.TMDb_URLSearch, **params )
        if not json:
            return []
        items = json['results']
        for _ in range( len(items) ):
            item = items.pop(0)
            if item['media_type'] == 'movie':
                item = _movie.TMDbMovie( data = item )
                self.__log.info( 'Found movie: %s', item )
            elif item['media_type'] == 'tv':
                item = _series.TMDbSeries( data = item )
                self.__log.info( 'Found series: %s', item )
            elif item['media_type'] == 'person':
                item = Person( data = item )
                self.__log.info( 'Found person: %s', item )
            else:
                continue
            items.append( item )
        return items

    def byIMDb( self, IMDbID, **kwargs ):
        """
        Search TMDb for a given Movie or TV episode using IMDb ID

        """

        if IMDbID[:2] != 'tt':
            IMDbID = f'tt{IMDbID}'
        params = {'external_source' : 'imdb_id'}
        url  = self.TMDb_URLFind.format( IMDbID )
        json = self._get_json( url, **params )
        if not json:
            return None
        for key, val in json.items():
            for _ in range( len(val) ):
                item = val.pop(0)
                if key == 'movie_results':
                    val.append( _movie.TMDbMovie( item['id'] ) )
                elif key == 'person_resutls':
                    val.append( Person( item['id'] ) )
                elif key == 'tv_results':
                    val.append( _series.TMDbSeries( item['id'] ) )
                elif key == 'tv_episode_results':
                    season  = item['season_number']
                    episode = item['episode_number']
                    val.append( _episode.TMDbEpisode( item['id'], season, episode ) )
                #elif (key == 'tv_season_results'):
                #  val.append( Season( item ) )
                  #print(key)
        return json

class TVDb( BaseAPI ):
    """Class for high-level interaction with TMDb API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__log = logging.getLogger(__name__)

    def search( self, title=None, episode=None, seasonEp=None, year=None, page=None, nresults=10 ):
        """
        Search TVDb for a given Movie or TV episode

        """

        params = {'name' : title}
        if page:
            params['page'] = page

        json = self._get_json( self.TVDb_URLSearch, **params )
        if (not isinstance(json, dict)) or ('data' not in json):
            return []

        # Take first nresults
        items = json['data'][:nresults]
        for _ in range( len(items) ):
            item = items.pop(0)
            if 'seriesName' in item:
                item = _series.TVDbSeries( item['id'] )
                # Not sure what this is supposed to do
                #if year is not None and item.air_date is not None:
                #    try:
                #        test = item.air_date.year != year
                #    except:
                #        test = False
                #        continue
                if seasonEp:
                    item = _episode.TVDbEpisode( item, *seasonEp )
                time.sleep(0.5)# Sleep for request limit
            if item.title is not None:
                items.append( item )
        return items

    def byIMDb( self, IMDbID, season=None, episode=None, **kwargs ):
        """
        Search TVDb for a given Movie or TV episode using IMDb series ID 

        """

        if IMDbID[:2] != 'tt':
            IMDbID = f'tt{IMDbID}'
        params = {'imdbId' : IMDbID}
        json = self._get_json( self.TVDb_URLSearch, **params )
        if not json:
            return None
        data = []
        for item in json.get('data', []):
            if season and episode:
                tmp = _episode.TVDbEpisode( item['id'], season, episode, **kwargs )
            else:
                tmp = _series.TVDbSeries( item['id'], **kwargs )
            if tmp:
                data.append( tmp  )
        return data

def getMetaData( fpath=None, dbID=None, seasonEp=None, version='', **kwargs ):
    """
    Get Movie or Episode object based on information from file name or dbID
    
    Arguments:
        None

    Keyword arguments:
        fpath (str): Full path, or base name of file to get
            information for. MUST match naming conventions
        dbID (str): TVDb or TMDb to use for file; overrides any
            information parsed from file name
        seasonEP (tuple,list): Season and episode number
        version (str): Version for movie; e.g., Extended Edition

    Returns:
        A TMDbMovie, TMDbEpisode, TVDbMovie, or TVDbEpisode object

    """

    log = logging.getLogger(__name__)

    if seasonEp is None:
        seasonEp = ()

    if fpath:
        _, fbase = os.path.split( fpath )
        # If there are NOT 2 elements in season ep
        if len(seasonEp) != 2:
            # Use regex to try to find season and episode number
            seasonEp = SEASONEP.findall(fbase)
            # If there is one match to regex patter
            if len(seasonEp) == 1:
                seasonEp = seasonEp[0]

        if not isinstance(dbID, str):
            tmp = os.path.splitext(fbase)[0].split('.')
            # If tvdb or tmdb in the first four (4) characters, use first value as DB id
            if is_id(tmp[0]):
                dbID = tmp[0]
            # Else, if seasonEp was parsed from file name
            elif len(seasonEp) == 2:
                try:
                    dbID = tmp[1]# Assume second value is dbID
                except:
                    dbID = ''
            # Else, assume is movie
            else:
                try:
                    dbID = tmp[2]# Assume third value is dbID
                except:
                    dbID = ''
            # Assume second value is version (Extended Edition, Director's Cut, etc.)
            if not version:
                try:
                    version = tmp[1]
                except:
                    version = ''
    elif dbID is None:
        raise Exception('Must input file or dbID')

    if not is_id( dbID ):
        return None

    out = None
    if dbID[:4] == 'tvdb':
        if len(seasonEp) == 2:
            out = _episode.TVDbEpisode( dbID, *seasonEp, **kwargs )
        else:
            out = _movie.TVDbMovie( dbID, version=version, **kwargs )
    elif dbID[:4] == 'tmdb':
        if len(seasonEp) == 2:
            out = _episode.TMDbEpisode( dbID, *seasonEp, **kwargs )
        else:
            out = _movie.TMDbMovie( dbID, version=version, **kwargs )

    log.debug( 'Found metadata: %s', out )

    return out
