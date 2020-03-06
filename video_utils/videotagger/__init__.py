import logging
import json
from urllib.request import urlopen
import requests

from .API import BaseAPI, KEYS
from .Person import Person
from . import Movie
from . import Series
from . import Episode

log = logging.getLogger(__name__)
log.setLevel( logging.DEBUG )
sh  = logging.StreamHandler()
sh.setFormatter( logging.Formatter( '%(asctime)s [%(levelname)-4.4s] %(message)s' ) )
sh.setLevel(logging.DEBUG)
log.addHandler( sh )

class TMDb( BaseAPI ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__log = logging.getLogger(__name__)

  def search( self, title = None, episode = None, seasonEp = None, year = None, page = None ):
    params = {'query' : title}
    if page: params['page'] = page

    json = self._getJSON( self.TMDb_URLSearch, **params )
    if json:
      items = json['results']
      for i in range( len(items) ): 
        item = items.pop(0)
        if (item['media_type'] == 'movie'):
          item = Movie.TMDbMovie( data = item )
          self.__log.info( 'Found movie: {}'.format(item) )
        elif (item['media_type'] == 'tv'):
          item = Series( data = item )
          self.__log.info( 'Found series: {}'.format(item) )
        elif (item['media_type'] == 'person'):
          item = Person( data = item )
          self.__log.info( 'Found person: {}'.format(item) )
        else:
          continue
        items.append( item ) 
      return items
    return []
  
  #################################
  def byIMDb( self, IMDbID ):
    if (IMDbID[:2] != 'tt'): IMDbID = 'tt{}'.format(IMDbID)
    params = {'external_source' : 'imdb_id'}
    url  = self.TMDb_URLFind.format( IMDbID )
    json = self._getJSON( url, **params )
    if json:
      for key, val in json.items():
        for i in range( len(val) ): 
          item = val.pop(0)
          if (key == 'movie_results'):
            val.append( Movie.TMDbMovie( item['id'] ) ) 
          elif (key == 'person_resutls'):
            val.append( Person( item['id'] ) ) 
          elif (key == 'tv_results'):
            val.append( Series.TMDbSeries( item['id'] ) ) 
          elif (key == 'tv_episode_results'):
            val.append( Episode.TMDbEpisode( item['id'] ) ) 
          #elif (key == 'tv_season_results'):
          #  val.append( Season( item ) )
          else:
            print(key) 
      return json
    return None 

class TVDb( BaseAPI ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__log = logging.getLogger(__name__)

  def search( self, title = None, episode = None, seasonEp = None, year = None, page = None ):
    params = {'name' : title}
    if page: params['page'] = page

    json = self._getJSON( self.TVDb_URLSearch, **params )
    if json:
      items = json['data']
      for i in range( len(items) ): 
        item = items.pop(0)
        if ('seriesName' in item):
          if seasonEp:
            item = Episode.TVDbEpisode( item['id'], *seasonEp ) 
          else:
            item = Series.TVDbSeries( item['id'] )
        items.append( item ) 
      return items
    return []
  
  #################################
  def byIMDb( self, IMDbID, season=None, episode=None ):
    if (IMDbID[:2] != 'tt'): IMDbID = 'tt{}'.format(IMDbID)
    params = {'imdbId' : IMDbID}
    json = self._getJSON( self.TVDb_URLSearch, **params )
    if json:
      data = []
      for item in json.get('data', []):
        if season and episode:
          tmp = Episode.TVDbEpisode( item['id'], season, episode )
        else:
          tmp = Series.TVDbSeries( item['id'] )
        if tmp:
          data.append( tmp  )
      return data
    return None 
