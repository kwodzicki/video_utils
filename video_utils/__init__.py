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

    json = self._getJSON( self.URLSearch, **params )
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
    return None 
  
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
    params = {'query' : title}
    if page: params['page'] = page

    json = self._getJSON( self.URLSearch, **params )
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
    return None 
  
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
"""   
###
def parseRating( rating ):
  '''Function to parse information from the rating data'''
  mpaa = None;                                                                  # Set mpaa to None as default
  for r in rating['results']:                                                   # Iterate over items in the results list
    if r['iso_3166_1'] == 'US':                                                 # If the iso 3166 tag is US
      mpaa = r['rating'];                                                       # Set the mpaa rating
      break;                                                                    # Break the loop
  return mpaa;
###
def parseCrew( crew ):
  '''Function to parse information from the crew data'''
  director, writer = [], [];                                                    # Initialize director and writer as lists
  for person in crew:                                                           # Iterate over everyone in crew
    if person['job'] == 'Director':                                             # If person is a director
      director.append( person );                                                # Append to director list
    elif person['job'] == 'Writer':                                             # If person is a writer
      writer.append( person );                                                  # Append to writer list   
  return director, writer;                                                      # Return director and writer lists
###
def sortCast( cast ):
  return sorted(cast, key=lambda x: x['order'])[:30];
###
def parseRelease( release ):
  '''Function to parse information from the release data'''
  year, mpaa = None, None;                                                      # Initialize year and rating to None
  for i in release['results']:                                                  # Iterate over releases for all countries
    if i['iso_3166_1'] == 'US':                                                 # If the release is for the US
      for j in i['release_dates']:                                              # Iterate over the release dates
        if j['type'] == 3:                                                      # If the release type is 3, i.e., theatrical release
          year = int( j['release_date'][:4] );                                  # Set year to the year of the release
          if j['certification'] != '': mpaa = j['certification'];               # If the certification string is NOT empty, set the mpaa rating
          return year, mpaa;                                                    # Return the year and rating to break the loop
  return year, mpaa;                                                            # Return the year and rating        
###
def downloadInfo( url, external = False, attempts = 3 ):
  '''Function to download and parse json data from the API'''
  attempt = 0;                                                                  # Initialize attempt to zero (0)
  url += ('&' if external else '?') + 'api_key=' + tmdb_key;                    # Append the API key to the url
  
  while attempt < attempts:                                                     # While attempt is less than attempts
    try:                                                                        # Try;
      response = urlopen( url ).read();                                         # Get the JSON response from the URL
    except:                                                                     # On exceptiong
      attempt += 1;                                                             # Increment attempt
    else:                                                                       # If try was successful
      break;                                                                    # Break the while loop if the line above did NOT raise exception
  if attempt == attempts:                                                       # If the attempt is equal to the maximum number of attempts
    log.warning('Failed to access themoviedb.org API!!!');                      # Log a warning
    return None;                                                                # Return None
  if type(response) is not str: response = str(response, 'utf-8');              # Convert response to a string
  return json.loads( response );                                                # Parse the response and return it
"""
