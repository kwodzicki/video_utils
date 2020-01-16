import logging

try:
  from ...api_keys import tmdb as tmdb_key                  # Attempt to import the API key from the api_keys module
except:
  tmdb_key = os.environ.get('TMDB_API_KEY', None)         # On exception, try to get the API key from the TMDB_API_KEY environment variable

if not tmdb_key:
  msg = "API key for TMDb could NOT be imported!";
  logging.getLogger(__name__).error( msg );
  raise Exception( msg );

import requests
import time
from ...config import TMDb as TMDb_config

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
  director, writer = [], []                                                     # Initialize director and writer as lists
  for person in crew:                                                           # Iterate over everyone in crew
    if person['job'] == 'Director':                                             # If person is a director
      director.append( person )                                                 # Append to director list
    elif person['job'] == 'Writer':                                             # If person is a writer
      writer.append( person )                                                   # Append to writer list   
  info = {}
  if (len(director) > 0):
    info['director'] = director
  if (len(writer) > 0):
    info['writer'] = writer
  return info                                                                   # Return director and writer lists

###
def sortCast( cast ):
  return sorted(cast, key=lambda x: x['order'])[:30];

def parseCredits( credits ):
  info = {}
  if ('crew' in credits):
    info.update( parseCrew( credits['crew'] ) )
  if ('cast' in credits):
    info['cast'] = sortCast( credits['cast'] )
  return info 

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

def downloadInfo( url, **kwargs ):
  '''Function to download and parse json data from the API'''
  log     = logging.getLogger(__name__)
  retries = kwargs.pop('retries', 3)
  attempt = 0                                                                   # Initialize attempt to zero (0)
  json    = None
  if ('api_key' not in kwargs): kwargs['api_key'] = tmdb_key
  if ('append_to_response' in kwargs):
    if not isinstance( kwargs['append_to_response'], str):
      kwargs['append_to_response'] = ','.join( kwargs['append_to_response'] )   # If not string instance, then join using coma

  while attempt < retries:                                                      # While attempt is less than retries 
    try:                                                                        # Try;
      response = requests.get( url, params=kwargs)                               # Get the JSON response from the URL
    except:                                                                     # On exceptiong
      attempt += 1                                                              # Increment attempt
      time.sleep( 0.01 )
    else:                                                                       # If try was successful
      break;                                                                    # Break the while loop if the line above did NOT raise exception
  if attempt == retries:                                                        # If the attempt is equal to the maximum number of retries 
    log.warning('Failed to access themoviedb.org API!!!');                      # Log a warning
    return None;                                                                # Return None
  else:
    try:
      json = response.json()
    except:
      log.warning('Failed to get JSON from API')
    try:
      response.close()
    except:
      pass
  return json                                                                   # Parse the response and return it

#########################################################################################
def parseSeriesInfo( info ):
  '''
  Purpose:
    Function to parse information about series
    from JSON data returned by TMDb API to
    keys that match the imdbpy package
  Inputs:
    info : Dictionary of JSON data returned by call to API
  Keywords:
    None.
  Returns:
    Dictionary with keys matching those of imdbpy;
    extra keys are copied as well
  '''
  log = logging.getLogger(__name__)
  if ('show_id' not in info):
    info['show_id'] = info.pop('id', None)

  info['show_external_ids'] = info.pop('external_ids', {} )

  if ('name'   in info):
    info['seriesName'] = info.pop('name')                                                   # Add series name to output dictionary
  if ('genres' in info):
    info['genre']      = info.pop('genres')                                                 # Set the genres
  if ('production_companies' in info):                                                      # If 'production companies' in info
    info['production companies'] = info.pop('production_companies')                         # Set the production companies tag to list of the names of the production companies

  # Work on rating information
  if ('content_ratings' not in info):
    log.warning('Failed to get rating information!');
  else:
    rating = parseRating( info['content_ratings'] )                                         # Parse the rating information
    if rating: info['mpaa'] = ' ' + rating                                                  # Prepend space to the rating and add to output dictionary

  if ('seriesName' not in info):
    return None                                                                             # If the 'seriesName' tag is NOT in the dictionary by now, just return

  return info 

#########################################################################################
def parseEpisodeInfo( info, retries = 3 ):
  '''
  Purpose:
    Function to parse information about episodes
    from JSON data returned by TMDb API to
    keys that match the imdbpy package
  Inputs:
    info : Dictionary of JSON data returned by call to API
  Keywords:
    None.
  Returns:
    Dictionary with keys matching those of imdbpy;
    extra keys are copied as well
  '''
  # Work on some episode specific information
  log = logging.getLogger(__name__)
  if ('name'       in info):
    info['title'] = info.pop('name')              # Set episode name in output
  if ('overview'   in info):
    info['plot']  = [info.pop('overview')]        # Set episode plot in output
  if ('still_path' in info) and  isinstance( info['still_path'], str):                                    # If still_path is type string
    info['full-size cover url'] = TMDb_config['urlImage'] + info['still_path']          # Set poster path
  if ('credits' in info):                                                       # if the crew tag is NOT in the episode dictionary
    info.update( parseCredits( info['credits'] ) )
  else:
    log.warning('No credits information...');                     # Log an error

  return info 

###################################################################
def parseMovieInfo( info ):
  '''
  Purpose:
    Function to parse information about Movies
    from JSON data returned by TMDb API to
    keys that match the imdbpy package
  Inputs:
    info : Dictionary of JSON data returned by call to API
  Keywords:
    None.
  Returns:
    Dictionary with keys matching those of imdbpy;
    extra keys are copied as well
  '''
  log = logging.getLogger(__name__);
  if ('overview'    in info):
    info['plot']  = [data['overview']];
  if ('genres'      in info):
    info['genre'] = info['genres'];
  if ('poster_path' in info):
    if isinstance(info['poster_path'], str):                                                # If poster_path is type string
      info['full-size cover url']  = TMDb_config['urlImage'] + info['poster_path']          # Set post url
  if ('production_companies' in info): 
    info['production companies'] = info['production_companies']

  # Work on movie credit information
  if ('credits' not in info):                                                               # If None is returned from downloadInfo
    log.warning('Failed to get movie credit information')                                   # Log a warning
  else:                                                                                     # Else, something must have downloaded
    info.update( parseCredits( info['credits'] ) )
  
  # Work on movie release information
  if ('release_dates' not in info):                                                         # If None is returned from downloadInfo
    log.warning('Failed to get movie release information')                                  # Log a warning
  else:
    year, mpaa = parseRelease( info['release_dates'] )                                      # Parse the year and rating data based on release information
    if year is not None: info['year'] = year                                                # If year is NOT None, add to the output dictionary
    if mpaa is not None: info['mpaa'] = mpaa                                                # If mpaa is NOT None, add to the output dictionary

  return info                                                                               # Return the data

#########################################################################################
def getMovieInfo( movie_id ):
  '''
  Purpose:
    To get/parse json data from the api for a given movie
  Inputs:
    movie_id  : TMDb movie id to get information for
  Keywords:
    None.
  Returns:
    dictionary of information if data retrieved, else None
  '''
  url  = TMDb_config['urlMovie'].format( movie_id )                                         # Set URL for movie
  info = downloadInfo( url, append_to_response=['credits','release_dates','external_ids'] )                                              # Get the movie data
  if info:
    return parseMovieInfo( info )                                                           # Parse the movie data
  return None

#########################################################################################
def getEpisodeInfo( show_id, season, episode ):
  '''
  Purpose:
    To get/parse json data from the api for a given episode
  Inputs:
    show_id  : TMDb show id to get information for
    season   : Season number of episode to get data for
    episode  : Episode number of episode to get data for
  Keywords:
    None.
  Returns:
    dictionary of information if data retrieved, else None
  '''
  url  = TMDb_config['urlEpisode'].format( show_id, season, episode )
  info = downloadInfo( url, append_to_response=['credits','external_ids'] )
  if info:
    return parseEpisodeInfo( info )
  return None

#########################################################################################
def getSeriesInfo( show_id ):
  '''
  Purpose:
    To get/parse json data from the api for a given series
  Inputs:
    show_id  : TMDb show id to get information for
  Keywords:
    None.
  Returns:
    dictionary of information if data retrieved, else None
  '''
  url  = TMDb_config['urlSeries'].format( show_id )                                         # Set series info URL
  info = downloadInfo( url, append_to_response=['external_ids','content_ratings','genres']) # Get full series info
  if info:
    return parseSeriesInfo( info )

  return None
 
#########################################################################################
def searchByIMDbID( IMDbID ):
  '''
  Purpose:
    Function to serach for movie/episode given an
    IMDb ID
  Inputs:
    IMDbID   : IMDb ID to search for
  '''
  log  = logging.getLogger(__name__)                                                        # Initialize a logger
  movie, tv = False, False                                                                  # Initialize movie and tv variables to False

  log.info('Attempting to get information from themoviedb.org...')                          # Log some information
  info = downloadInfo( TMDb_config['urlFind'].format(IMDbID), 
      external_source='imdb_id')                                                                             # Search themoviedb.org using the IMDb ID
  if info is None:                                                                          # If no information was return, then there was an issue
    log.warning('Failed to find matching content on themoviedb.org!')                       # Log a warning message
  elif ('movie_results' in info) and ('tv_episode_results' in info):                        # Else, if the two keys are in the dictionary
    if len(info['movie_results']) == 1:                                                     # If the length of movie results is one (1)
      movie = getMovieInfo( info['movie_results'][0]['id'] )                                # Parse the movie data
    if len(info['tv_episode_results']) == 1:                                                # Else, if the length of tv/episode results is one (1)
      ep       = info['tv_episode_results'][0] 
      seasonEp = ( ep['season_number'], ep['episode_number'], ) 
      tv       = episodeBySeasonEp( ep['show_id'], ep['name'], seasonEp )                   # Parse the episode data
    if (movie and tv) or tv:                                                                # If both movie and TV data returned OR just TV data returned, assume TV
      tv['is_episode'] = True                                                               # Set is episod to Ture
      return tv                                                                             # Update the tmdb.data with the TV information
    elif movie:                                                                             # Else, only movie data was returned
      return movie                                                                          # Update the tmdb.data with the movie information
    else:                                                                                   # Else, something went wrong
      log.warning('Failed to get information from themoviedb.org!')                         # Log a warning
      log.warning('More than one movie or TV show returned?')                               # Log a warning
  else:                                                                                     # Else, tags may have changed in the API
    log.warning('Something went wrong with the API...Tag changes in JSON?')                 # Log a warning
  return {}                                                                                 # Return the TMDb class instance

#########################################################################################
def episodeByTitle( show_id, episode ):
  '''
  Purpose:
    Function to get episode information for given episode
    based on episode title
  Inputs:
    series  : idmbpy Movie object of series information
    episode : Name of the episode to get
  '''
  log = logging.getLogger(__name__)
  log.debug( 'Searching for episode base on episode title' )
  series = getSeriesInfo( show_id )                                                         # Get full series info
  if not series:
    return None
  log.debug( 'Iterating over all season/episodes' ) 

  for season in series['seasons']:                                                          # Iterate over all seasons
    url    = TMDb_config['urlSeason'].format( series['show_id'], season['season_number'] )
    season = downloadInfo( url )
    if not season:
      continue     
    for ep in season['episodes']:
      if (ep['name'].lower() in episode.lower()):
        info = getEpisodeInfo( series['show_id'], season['season_number'], ep['episode_number'] )
        info.update( series )
        log.info( 'Found episode based on episode name search' )
        return info

  log.info( 'Search by episode name returned no results' ) 
  return None
 
#########################################################################################
def episodeBySeasonEp( show_id, episode, seasonEp ):
  '''
  Purpose:
    Function to get episode information based on
    episode and season number. This function only
    get information for episodes in given season to
    reduce pinging IMDb. If search files to find
    episode with given number, will try to find
    based on name
  Inputs:
    series   : idmbpy Movie object of series information
    episode  : Name of the episode to get
    seasonEp : Tuple or list containing season and episode numbers
  '''
  log = logging.getLogger(__name__)
  log.debug( 'Searching for episode base on season/episode number' )
  info = getEpisodeInfo( show_id, *seasonEp ) 
  if info:
    series = getSeriesInfo( show_id )
    if series:
      info.update( series )
    log.info( 'Found episode based on season/episode number' )
    return info

  log.info( 'Search by season/episode number returned no results, trying by name...' )
  return episodeByTitle( series, episode )

#########################################################################################
def getEpisode( title, episode, seasonEp = None, year = None, depth = 5 ):
  '''
  Purpose:
    Function to get series information for given episode if
    IMDb ID was used to get episode.
  Inputs:
    title   : Series title to search for
    episode : Episode title to search for
  Keywords:
    seasonEp  : Tuple or list containing season and episode numbers
    year      : Year of series; speeds thing us and helps make sure
                  series is grabbed.
    depth     : How many series to check before giving up
  Outputs:
    Returns dictionary if found; None if not found
  '''

  log    = logging.getLogger(__name__)
  kwargs = {'query' : title}
  if year: kwargs['year'] = year

  seriesSearch = downloadInfo( TMDb_config['tvSearch'], **kwargs )  
  for idx, series in enumerate( seriesSearch['results'] ):
    log.info( 'Checking series: {} for match'.format( series['name'] ) )
    if seasonEp:
      ep = episodeBySeasonEp( series['id'], episode, seasonEp )
    else:
      ep = episodeByTitle( series['id'], episode )

    if ep:
      return ep

    if (idx == (depth-1)):
      log.warning( 'Checked {} series and found no match'.format(depth) )                   # If depth is zero, then checked as deep as we want to go
      break

  return None
      
###################################################################
def getTMDb_Info(
    IMDbID   = None, 
    title    = None,
    episode  = None,
    seasonEp = None,
    year     = None,
    depth    = 5,
    retries  = 3):
  '''
  Name:
    getTMDb_Info
  Purpose:
    A python functio that attempts to download information
    from tmdb.com.
  Inputs:
    None.
  Keywords:
    IMDbID   : The id from the URL of a movie on imdb.com.
                 Ex. For the movie 'Push', the URL is:
                 http://www.imdb.com/title/tt0465580/
                 Making the imdb id tt0465580
    title    : Name of movie or series to search for.
                 If searching for movie, must include year
                 If seraching for episode, must include episode
    episode  : Name of episode to search for.
    seasonEp : Tuple or list containing season and episode numbers
    year     : Year of movie or series; required for movie search
    depth    : How deep to go into search results to find match
  Outputs:
    Returns TMDb instance; very loosely based on IMDb() object
  Author and History:
    Kyle R. Wodicki     Created 16 Sep. 2017
  '''
  log  = logging.getLogger(__name__)                                                        # Initialize a logger
  tmdb = TMDb( )                                                                            # Initialize instance of the TMDb class
  info = {}

  if IMDbID:
    info = searchByIMDbID( IMDbID )
  elif title and (not episode):
    log.info( 'Assuming movie search based on keywords' )
    if not year:
      log.error( 'Must input year for movie search!' )
    else:
      info = downloadInfo( TMDb_config['movieSearch'], query=title, year=year )
      if info and (info['total_results'] == 1):
        info = getMovieInfo( info['results'][0]['id'] )                                    # Parse the movie data
  elif title and episode:
    info = getEpisode( title, episode, seasonEp = seasonEp, year = year, depth = depth)

  if info:
    tmdb.update( info )

  return tmdb

###################################################################
class TMDb( object ):
  def __init__(self):
    self.IMDbID = None
    self.data   = {'is_episode' : False};

  @property
  def is_episode(self):
    return self.data['is_episode']
  @is_episode.setter
  def is_episode(self, val):
    self.data['is_episode'] = val

  def getID(self, external = None):
    if self.IMDbID:
      return self.IMDbID.replace('tt', '')
    elif external:
      try:
        return self.data['external_ids'].get( external, None )
      except:
        return None
    else:
      return self.data['id']
 
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
