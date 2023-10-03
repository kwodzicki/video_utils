"""
Tag video files

Download and write metadata to video files from
TMDb or TVDb

"""

import logging
import os
import re
import time
from datetime import datetime
from difflib import SequenceMatcher

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

    def search( self, title = None, episode = None, seasonEp = None, year = None, page = None, **kwargs ):
        """
        Search TMDb for a given Movie or TV episode

        Keyword arguments:
            title (str) : Title of movie OR title of TV Series
            episode (str) : Title of TV series episode
            seasonEp (tuple) : The season and episode number of the
                TV series episode

        """

        self.__log.debug("Searching TMDb")
        params = {'query' : title}
        if page:
            params['page'] = page

        json = self._get_json( self.TMDb_URLSearch, **params )
        if not json:
            return []
        items = json['results']
        for _ in range( len(items) ):
            item  = items.pop(0)
            mtype = item.get('media_type', '')
            if mtype not in ('person', 'movie', 'tv'):
                continue

            if mtype == 'person':
                items.append(
                    Person( data = item, **kwargs )
                )
                self.__log.info( 'Found %s: %s', mtype, items[-1])
                continue

            rel_date = item.get('release_date', None)
            if year:
                if not isinstance(rel_date, datetime):
                    continue
                if year != rel_date.year:
                    continue

            if mtype == 'movie':
                item = _movie.TMDbMovie( data = item, **kwargs )
            else:
                item = _series.TMDbSeries( data = item, **kwargs )
            self.__log.info( 'Found %s: %s', mtype, items[-1])

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

    def search( self, title=None, episode=None, seasonEp=None, year=None, dvdOrder=None, page=None, nresults=10, **kwargs ):
        """
        Search TVDb for a given Movie or TV episode

        """

        if title is None:
            return [] 
        
        self.__log.debug("Searching TVDb")
        params = {'name' : title}
        if page:
            params['page'] = page

        json = self._get_json( self.TVDb_URLSearch, **params )
        if (not isinstance(json, dict)) or ('data' not in json):
            return []

        # Take first nresults
        best_ratio = 0.0
        series     = None
        for item in json['data'][:nresults]:
            time.sleep(0.5)# Sleep for request limit
            if 'seriesName' not in item:
                continue

            item = _series.TVDbSeries( item['id'], **kwargs )
            # Check item season info against user requested season number
            if isinstance(item, _series.TVDbSeries) and seasonEp is not None:
                if not item.season:
                    self.__log.debug(
                        'No season info in series %s, but requested season %d',
                        item,
                        seasonEp[0],
                    )
                    continue
                if seasonEp[0] > int( item.season ):
                    self.__log.debug(
                        'Series "%s" has too few seasons: %s vs. %d requested',
                        item,
                        item.season,
                        seasonEp[0],
                    )
                    continue

            # If years are valid and NOT match, skip
            if year is not None and item.air_date is not None:
                if item.air_date.year != year:
                    self.__log.debug(
                        'Aired year mismatch : %d vs. %d requested',
                        item.air_date.year,
                        year,
                    )
                    continue

            # Get ratio of match between user input title and that of series.
            # We use the 'name' attribute as it does NOT have (year) in it.
            title_match = SequenceMatcher(
                None,
                item.get('name', ''),
                title,
            ).ratio()

            # If match is better than best match, then update best_ratio and
            # the series object
            if title_match > best_ratio:
                best_ratio = title_match
                series     = item

        if not isinstance(series, _series.TVDbSeries):
            return [] 

        if isinstance(dvdOrder, bool):
            # If bool type, then user set, so use their option
            return [
                 _episode.TVDbEpisode(series, *seasonEp, dvdOrder=dvdOrder, **kwargs)
            ]

        # We want to get DVD and Aired order and compare episode names

        aired = _episode.TVDbEpisode(series, *seasonEp, dvdOrder=False, **kwargs)
        dvd   = _episode.TVDbEpisode(series, *seasonEp, dvdOrder=True,  **kwargs)
        if aired == dvd:
            return [aired]

        return [
            compare_aired_dvd(title, year, seasonEp, episode, aired, dvd)
        ]

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

def compare_aired_dvd(title, year, season_ep, episode, aired, dvd):
    """
    Compare aired and dvd order

    Arguments:
        title (str) : Title of the series/movie
        year (int) : Release year of the series/movie
        season_ep (list) : The [season #, episode #] for the series/movie.
            Will be None is determined to be movie.
        episode (str) : Name of the episode of the series.
            Will be None is determined to be movie.
        aired (list) : List of aired-order results returned from search
        dvd (list) : List of dvd-order results fretruend from search

    """

    log = logging.getLogger(__name__)

    # If made here, we have one (1) result for both aired and dvd, so
    # check if season_ep si defined. If not, then assume movie and return
    if season_ep is None or episode is None:
        return _movie.get_basename( title, year ), None

    # If made here, the matches for both aired and dvd order of episode
    # so we get episode title match for aired order title dvd order tile
    # versus the file name episode tiltle
    aired_ratio = SequenceMatcher(None, episode, aired.title).ratio()
    dvd_ratio   = SequenceMatcher(None, episode,   dvd.title).ratio()

    # If the similarity ratio for aired is >= DVD, assume aired order, else dvd
    if aired_ratio >= dvd_ratio:
        log.info('Assuming aired order based on episode file name')
        return aired

    log.info('Assuming dvd order based on episode file name')
    return dvd

#    return metadata.get_basename(), metadata
