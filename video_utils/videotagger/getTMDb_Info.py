import logging
import json


from urllib.request import urlopen

try:
  from ...api_keys import tmdb as tmdb_key                  # Attempt to import the API key from the api_keys module
except:
  tmdb_key = os.environ.get('TMDB_API_KEY', None)         # On exception, try to get the API key from the TMDB_API_KEY environment variable

if not tmdb_key:
  msg = "API key for TMDb could NOT be imported!";
  logging.getLogger(__name__).error( msg );
  raise Exception( msg );

import requests
from ...config import TMDb as TMDb_config

class TMDbBaseAPI( object ):
  URLBase   = 'https://api.themoviedb.org/3'
  URLImage  = 'http://image.tmdb.org/t/p/original'
  __api_key = tmdb_key
  def __init__(self):
    self.__log = logging.getLogger(__name__)

  #################################
  def _getRequest(self, url, **kwargs):
    '''
    Purpose:
      Method to issue requests.get()
    Inputs:
      All accepted by requests.get()
    Keywords:
      All accepted by requests.get()
    Outputs:
      requests Response object
    '''
    resp = None
    if ('api_key' not in kwargs):
      kwargs['api_key'] = self.__api_key
    try:
      resp  = requests.get( url, params=kwargs )
    except Exception as err:
      self.__log.error( 'TMDb request failed: {}'.format(err) )
    else:
      if not resp.ok:
        self.__log.error( 'TMDb request is not okay' )
        resp = self._closeRequest( resp )
    return resp
  #################################
  def _closeRequest(self, resp):
    '''
    Purpose:
      Method to close Response object
    Inputs:
      resp   : Response object
    Keywords:
      None
    Outputs:
      Returns None
    '''
    try:
      resp.close()
    except:
      pass
    return None
  #################################
  def _getJSON(self, *args, **kwargs):
    '''
    Purpose:
      Method to try to get JSON data from request
    Inputs:
      All accepted by requests.get()
    Keywords:
      All accepted by requests.get()
    Outputs:
      Dictionary with JSON data if success, else, None
    '''
    json = None
    resp = self._getRequest(*args, **kwargs)
    if resp:
      try:
        json = resp.json()
      except Exception as err:
        self.__log.error('Failed to get JSON data')
      resp = self._closeRequest( resp )
    return json


class TMDbBase( TMDbBaseAPI ):
  _isMovie   = False
  _isSeries  = False
  _isEpisode = False
  _isPersion = False
  URL        = None
  def __init__(self, info = None):
    super().__init__()
    self._data = {}
    if info:
      self._data.update( info )

  @property
  def isMovie(self):
    return self._isMovie
  @property
  def isSeries(self):
    return self._isSeries
  @property
  def isEpisode(self):
    return self._isEpisode
  @property
  def isPerson(self):
    return self._isPerson

  def __setitem__(self, key, item):
    self._data[key] = item
  def __getitem__(self, key):
    return self._data[key]
  def keys(self):
    return self._data.keys()

  def _getExtra(self, *keys):
    if self.URL:
      for key in keys:
        if (key not in self._data):
          URL  = '{}/{}'.format(self.URL, key)
          json = self._getJSON(URL)
          if json:
            self._data[key] = json

  def getID(self):
    if ('id' in self._data):
      return self._data['id']
    return None
  def getIMDbID(self):
    if ('external_ids' in self._data) and ('imdb_id' in self._data['external_ids']):
      return self._data['external_ids']['imdb_id']
    return None

class Movie( TMDbBase ):
  def __init__(self, info):
    super().__init__(info)
    self._isMovie = True

class Series( TMDbBase ):
  URL   = '{}/tv/{}'
  extra = ['external_ids', 'content_ratings']
  def __init__(self, info=None, ID=None):
    if not info and not ID:
      raise Exception( 'Must input info or ID' )
    super().__init__(info)
    if not info:
      self.URL = self.URL.format( self.URLBase, ID )
      json     = self._getJSON( self.URL, append_to_response=','.join(self.extra) )
      if json:
        self._data.update(json) 
    else:
      self.URL = self.URL.format( self.URLBase, self['id'] )
      self._getExtra( *self.extra )

    self._isSeries = True

class Episode( TMDbBase ):
  URL = '{}/tv/{}/season/{}/episode/{}'
  def __init__(self, info = None):
    super().__init__(info)
    self.URL = self.URL.format(
      self.URLBase, self['show_id'], self['season_number'], self['episode_number']
    )
    self._getExtra( 'external_ids' )
    self._isEpisode = True

  def getSeriesID(self):
    return self['show_id']
  def getSeries(self):
    return Series( ID = self['show_id'] )

class Person( TMDbBase ):
  def __init__(self, info):
    super().__init__(info)
    self._isPerson = True



#######################################################################################
class TMDb( TMDbBaseAPI ):
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.__log = logging.getLogger(__name__)

  def search( self, title = None, episode = None, seasonEp = None, year = None, page = None ):
    params = {'query' : title}
    if page: params['page'] = page

    url  = '{}/search/multi'.format(self.URLBase)

    json = self._getJSON( url, **params )
    if json:
      items = json['results']
      for i in range( json['total_results'] ): 
        item = items.pop(0)
        if (item['media_type'] == 'movie'):
          items.append( Movie( item ) ) 
        elif (item['media_type'] == 'tv'):
          items.append( Series( item ) ) 
        elif (item['media_type'] == 'person'):
          items.append( Person( item ) ) 
      return items
    return None 
  
  #################################
  def byIMDb( self, IMDbID ):
    if (IMDbID[:2] != 'tt'): IMDbID = 'tt{}'.format(IMDbID)
    params = {'external_source' : 'imdb_id'}
    url  = '{}/find/{}'.format(self.URLBase, IMDbID)
    json = self._getJSON( url, **params )
    if json:
      for key, val in json.items():
        for i in range( len(val) ): 
          item = val.pop(0)
          if (key == 'movie_results'):
            val.append( Movie( item ) ) 
          elif (key == 'person_resutls'):
            val.append( Person( item ) ) 
          elif (key == 'tv_results'):
            val.append( Series( item ) ) 
          elif (key == 'tv_episode_results'):
            val.append( Episode( item ) ) 
          elif (key == 'tv_season_results'):
            val.append( Season( item ) )
          else:
            print(key) 
      return json
    return None 
   
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

##################
def getTVInfo( info, attempts = 3 ):
  '''Function to get information about TV Episodes/series'''
  log = logging.getLogger(__name__);
  if 'season_number'  not in info or \
     'episode_number' not in info or \
     'show_id'        not in info:
    return {};
  else:   
    show_id = info['show_id'];
    season  = info['season_number'];
    episode = info['episode_number']
  outData = {'season'  : season, 
             'episode' : episode};

  # Work on series information
  url    = TMDb_config['urlSeries'].format( show_id );                          # Set series info URL
  series = downloadInfo( url, attempts = attempts );                            # Get series info
  if series is None:                                                            # If downloadInfo returned None
    log.warning('Failed to get series information!');                           # Log a warning
  else:                                                                         # Else...
    if 'name'   in series: outData['seriesName'] = series.pop('name');          # Add series name to output dictionary
    if 'genres' in series: outData['genre']      = series.pop('genres');        # Set the genres
    if 'production_companies' in series:                                        # If 'production companies' in info
      outData['production companies'] = series.pop('production_companies');     # Set the production companies tag to list of the names of the production companies
    if 'first_air_date' in series:                                              # If first_air_date in the series dictionary
      outData['first_air_date'] = series.pop('first_air_date');                 # Add it to the outdata
    outData.update( series );
  if 'seriesName' not in outData: return {};                                    # If the 'seriesName' tag is NOT in the dictionary by now, just return

  # Work on rating information
  rating = downloadInfo( url + '/content_ratings', attempts = attempts );       # Attempt to download rating information
  if rating is None:
    log.warning('Failed to get rating information!');
  else:
    rating = parseRating( rating );                                             # Parse the rating information
    if rating is not None: outData['mpaa'] = ' ' + rating;                      # Prepend space to the rating and add to output dictionary

  # Work on some episode specific information
  url     = TMDb_config['urlEpisode'].format(show_id, season, episode);         # Set URL for episode data download
  episode = downloadInfo( url, attempts = attempts );                           # Download some episode data
  if episode is None:                                                           # If downloadInfo return None
    log.warning('Failed to get episode information!');                          # Log an error
  else:                                                                         # Else...
    if 'name'       in episode: outData['title'] = episode.pop('name');         # Set episode name in output
    if 'overview'   in episode: outData['plot']  = [episode.pop('overview')];   # Set episode plot in output
    if 'still_path' in episode: 
      if type(episode['still_path']) is str:                                    # If still_path is type string
        outData['full-size cover url'] = TMDb_config['urlImage']+episode['still_path'];      # Set poster path
    if 'crew' in episode:                                                       # if the crew tag is NOT in the episode dictionary
      crew = parseCrew( episode.pop('crew') );                                  # Parse crew information
      if len(crew[0]) > 0: outData['director'] = crew[0];                       # Add director(s) to output dictionary
      if len(crew[1]) > 0: outData['writer']   = crew[1];                       # Add writers(s) to output dictionary
    else:                                                                       # Else...
      log.warning('No crew information for the episode...');                    # Log a warning
    outData.update( episode );
  # Work on credits information
  credits = downloadInfo( url + '/credits', attempts = attempts );              # Download episode credits
  if credits is None:
    log.warning('Failed to get credits information');                           # Log an error
  else:
    if 'cast' in credits: 
      outData['cast'] = sortCast( credits['cast'] );                            # Set episode cast in output
    else:
      log.warning('No cast information in the credits...');                     # Log an error

  return outData;

###################################################################
def getMovieInfo( info, attempts = 3 ):
  '''Function to get information about Movies'''
  log = logging.getLogger(__name__);
  outData = {}
  url     = TMDb_config['urlMovie'].format(info['id']);                         # Set URL for movie

  # Work on movie base information
  data = downloadInfo( url, attempts = attempts );                              # Get the movie data
  if data is None:
    log.warning('Failed to get movie base information');
  else:
    if 'title'                in data: outData['title'] = data['title'];
    if 'overview'             in data: outData['plot']  = [data['overview']];
    if 'genres'               in data: outData['genre'] = data['genres'];
    if 'poster_path'          in data:
      if type(data['poster_path']) is str:                                      # If poster_path is type string
        outData['full-size cover url']  = TMDb_config['urlImage']+data['poster_path'];       # Set post url
    if 'production_companies' in data: 
      outData['production companies'] = data['production_companies'];

  # Work on movie credit information
  credits = downloadInfo( url + '/credits', attempts = attempts );              # Download credits 
  if credits is None:                                                           # If None is returned from downloadInfo
    log.warning('Failed to get movie credit information');                      # Log a warning
  else:                                                                         # Else, something must have downloaded
    if 'crew' in credits:                                                       # If crew is NOT in the credits dictionary
      crew = parseCrew( credits['crew'] );                                      # Parse the crew information
      if len(crew[0]) > 0: outData['director'] = crew[0];                       # Add director(s) to output dictionary
      if len(crew[1]) > 0: outData['writer']   = crew[1];                       # Add writers(s) to output dictionary
    else:                                                                       # Else...
      log.warning('No crew information in the credits...');                     # Log a warning
    if 'cast' in credits:                                                       # If cast is NOT in the credits dictionary
      outData['cast'] = sortCast( credits['cast'] );                            # Sort the cast
    else:                                                                       # Else...
      log.warning('No cast information in the credits...');                     # Log a warning

  # Work on movie release information
  release = downloadInfo( url + '/release_dates', attempts = attempts );        # Download release information
  if release is None:                                                           # If None is returned from downloadInfo
    log.warning('Failed to get movie release information');                     # Log a warning
  else:
    year, mpaa = parseRelease( release );                                       # Parse the year and rating data based on release information
    if year is not None: outData['year'] = year;                                # If year is NOT None, add to the output dictionary
    if mpaa is not None: outData['mpaa'] = mpaa;                                # If mpaa is NOT None, add to the output dictionary

  return outData;                                                               # Return the data

###################################################################
def getTMDb_Info(IMDb_ID, attempts = None, logLevel = 30):
  '''
  Name:
    getTMDb_Info
  Purpose:
    A main python class and a collection of parser functions
    to retrieve information from themoviedb.org based on 
    IMDb IDs. Both movie and tv data can be downloaded and parsed.
  Author and History:
    Kyle R. Wodzicki     Created Dec. 2017
  
    Modified 20 Jan. 2018
      Added a 'is_episode' boolean to the self.data dictionary
      so that the tv database could be moved to the getMetaData
      function so that both this function and the getIMDb_Info
      function are not downloading the same data.
  '''
  log = logging.getLogger(__name__);                                            # Initialize a logger
  if not attempts: attempts = 3;
#   if logLevel is None: logLevel = logging.INFO;                                 # Set the default logging level
#   log.setLevel( logLevel );                                                     # Actually set the logging level
  tmdb = TMDb( IMDb_ID );                                                       # Initialize instance of the TMDb class
  movie, tv = False, False;                                                     # Initialize movie and tv variables to False

  log.info('Attempting to get information from themoviedb.org...');             # Log some information
  info = downloadInfo( TMDb_config['urlFind'].format(IMDb_ID), True, attempts );# Search themoviedb.org using the IMDb ID
  if info is None:                                                              # If no information was return, then there was an issue
    log.warning('Failed to find matching content on themoviedb.org!');          # Log a warning message
  elif 'movie_results' in info and 'tv_episode_results' in info:                # Else, if the two keys are in the dictionary
    if len(info['movie_results']) == 1:                                         # If the length of movie results is one (1)
      movie = getMovieInfo(info['movie_results'][0], attempts);                 # Parse the movie data
    if len(info['tv_episode_results']) == 1:                                    # Else, if the length of tv/episode results is one (1)
      tv = getTVInfo(info['tv_episode_results'][0], attempts);                  # Parse the episode data
    if (movie and tv) or tv:                                                    # If both movie and TV data returned OR just TV data returned, assume TV
      tmdb.data['is_episode'] = True;                                           # Set is episod to Ture
      tmdb.data.update( tv );                                                   # Update the tmdb.data with the TV information
    elif movie:                                                                 # Else, only movie data was returned
      tmdb.data.update( movie );                                                # Update the tmdb.data with the movie information
    if len(tmdb.data.keys()) > 1:                                               # If there is more than one key ('is_episode' is always present) in the data attribute...
      log.info('Information downloaded from themoviedb.org!');                  # Print log information for success
    else:                                                                       # Else, something went wrong
      log.warning('Failed to get information from themoviedb.org!');            # Log a warning
      log.warning('More than one movie or TV show returned?');                  # Log a warning
  else:                                                                         # Else, tags may have changed in the API
    log.warning('Something went wrong with the API...Tag changes in JSON?');    # Log a warning
  return tmdb;                                                                  # Return the TMDb class instance

"""
###################################################################
class TMDb( object ):
  def __init__(self, IMDb_ID):
    self.IMDb_ID = IMDb_ID
    self.data    = {'is_episode' : False};
  
  ####################
  def keys(self):
    '''Return a list of valid keys.'''
    return list( self.data.keys() )
  def has_key(self, key):
    '''Return true if a given section is defined.'''
    try:
      self.__getitem__(key)
    except KeyError:
      return False
    return True
  def getID(self):
    '''Return the IMDb ID in the same convesion as is used in IMDbPY'''
    return self.IMDb_ID.replace('tt','');
  def set_item(self, key, item):
    '''Directly store the item with the given key.'''
    self.data[key] = item
  def update(self, new_data):
    '''Update the data dictionary with the new_data'''
    self.data.update( new_data );
  def __getitem__(self, key):
    '''Return the value for a given key.'''
    return self.data[key]
  def __contains__(self, input):
    '''Return true if self.data contains input.'''
    return input in self.data;
"""
