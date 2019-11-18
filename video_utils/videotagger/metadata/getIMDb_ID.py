import logging;
import os, re;
from imdb import IMDb;

TVDb = None;                                                                    # Set tvdb to None
try:
  from video_utils.api_keys import tvdb as tvdb_key;                            # Attempt to import the API key from the api_keys module
except:
  tvdb_key = os.environ.get('TVDB_API_KEY', None);                              # On exception, try to get the API key from the TVDB_API_KEY environment variable

if tvdb_key:                                                                    # If the tvdb_key variable is valid
  import tvdbsimple as TVDb;                                                    # Import tvdbsimple as tvdb; this will make if tvdb: return True
  TVDb.KEYS.API_KEY = tvdb_key;                                                 # Set the API_KEY for the tvdbsimple
else:                                                                           # Else, get a logger and log an error
  logging.getLogger(__name__).warning( 
    "API key for TVDb could NOT be imported!"
  );

imdbFMT = 'tt{}';                                                               # Format string for IMDb id
yearPat = re.compile( r'\(([0-9]{4})\)' );                                      # Pattern for finding year in series name

def TVDb_Search(series_name, year, episode_title, season = None, episode = None):
  '''
  Name:
    TVDb_Search
  Purpose:
    To search TVDb to get the IMDb id
  Inputs:
    series_name   : Name of the series
    year          : Year series started
    episode_title : Title of the episode
  Keywords:
    season        : Integer for season number
    episode       : Integer for episode number  
  Outputs:
    Returns IMDb ID in format ttxxxxxxx
  '''
  if not TVDb: return None;                                                     # If the TVDb was NOT loaded, just return None;
  log = logging.getLogger(__name__)
  log.info( 'Attempting to get IMDb ID from TVDb' );               

  tvdb = TVDb.Search();                                                         # Initialize search for TVDb
  try:                                                                          # Try to
    res  = tvdb.series( series_name )                                           # Search for the series on the TVDb
  except:                                                                       # On exception
    pass;                                                                       # Do nothing
  else:                                                                         # If try was success
    log.debug( 'TVDb series search returned {} matches'.format( len(res) ) );   # Debugging information
    for r in res:                                                               # Iterate over all search results
      if r['firstAired'] and (str(year) in r['firstAired']):                    # If the local year is in the firstAird tag
        log.debug( 'Found series with same firstAired year' );                  # Debugging information
        if season:
          eps = TVDb.Series_Episodes( r['id'], airedSeason = season ).all()     # Get episodes for just the given season
        else:
          eps = TVDb.Series( r['id'] ).Episodes.all()                           # Get list of all episodes in series

        log.debug( 'TVDb returned {} episodes in the series'.format(len(eps)) );# Debugging information
        if episode:                                                             # If episode is set
          try:                                                                  # Try to
            ep = eps[episode-1]                                                 # Get episode directory from episode number
          except:                                                               # On excpetion
            log.info('Episode number out of episode range')                     # Log info
          else:                                                                 # Else
            return ep['imdbId'] if ep['imdbId'] else None                       # Return IMDb id

        for ep in eps:                                                          # If made here, iterate over all episodes
          if (ep['episodeName'].lower() in episode_title.lower()):              # If the episode name is in the local title and there is an imdbId in the ep
            log.debug( 'Found episode with same name' );
            if ('imdbId' in ep) and (ep['imdbId'] != ''):                       # If imdbId key exists AND imdbId value is NOT empty
              log.info( 'IMDb ID found from TVDb search' )
              return ep['imdbId'] if ep['imdbId'] else None                     # Return it

  log.warning( 'TVDb search failed' );
  return None 

def IMDb_Search(series_name, year, episode_title, season = None, episode = None):
  '''
  Name:
    IMDb_Search
  Purpose:
    To search IMDb to get the IMDb id
  Inputs:
    series_name   : Name of the series
    year          : Year series started
    episode_title : Title of the episode
  Keywords:
    season        : Integer for season number
    episode       : Integer for episode number  
  Outputs:
    Returns IMDb ID in format ttxxxxxxx
  '''
  log = logging.getLogger(__name__)
  log.info( 'Attempting to get IMDb ID from IMDb' );               
  imdb = IMDb();                                                                # Initialize IMDb instance
  res  = imdb.search_movie( series_name );                                      # Search for the episode title on IMDb
  log.debug( 'IMDb search returned {} matches'.format( len(res) ) );            # Debugging information
  for r in res:                                                                 # Iterate over all the results from IMDb
    if r['kind'].lower() == 'tv series':                                        # If object is a tv series 
      log.debug('Found series with matching name');
      if 'year' in r and year:                                                  # If the 'series year' key is in the result AND the local year is defined
        log.debug('Series has year information');
        if r['year'] != year: 
          log.debug('Series year did NOT match');
          continue;                                                             # If the result series year NOT match the local series year, skip series

      log.info('Getting list of episodes from IMDb.com')
      if season:                                                                # If season is set
        url    = imdb.urls['movie_main'] % r.movieID + 'episodes' 
        log.debug( 'Getting data from: {}'.format(url) )
        cont   = imdb._retrieve( url )                                          # Get content from episodes page; taken from imdb.parser.http.IMDbHTTPAccessSystem.get_movie_episodes
        data_d = imdb.mProxy.season_episodes_parser.parse( cont )               # Parse episodes information
        if (season in data_d['data']['_seasons']):
          url        = '{}?season={}'.format(url, season)
          log.debug( 'Getting data from: {}'.format(url) )
          other_cont = imdb._retrieve( url )
          other_data = imdb.mProxy.season_episodes_parser.parse(other_cont)
          episodes   = other_data['data']['episodes'][season]                   # Get dictionary of episodes for season
          if (episode in episodes):
            log.info( 'IMDb ID found from IMDb search')
            return imdbFMT.format( episodes[episode].getID() )
          else:
            for key, val in episodes.items():
              if val['title'].lower() in episode_title.lower():     # Check that the titles are the same
                log.info( 'IMDb ID found from IMDb search')
                return imdbFMT.format( val.getID() )     # Return the IMDb id
      else:
        imdb.update( r, 'episodes' )                                              # Get information for all episodes
        for s in r['episodes']:                                                 # Iterate over all the seasons in the episodes dictionary
          for e in r['episodes'][s]:                                            # Iterate over all the episodes in the season
            if r['episodes'][s][e]['title'].lower() in episode_title.lower():   # Check that the titles are the same
              log.info( 'IMDb ID found from IMDb search')
              return imdbFMT.format( r['episodes'][s][e].getID() );             # Return the IMDb id
             
  log.warning( 'IMDb search failed' )
  return None 

def getIMDb_ID( series_name, episode_title, season_ep = None ):
  '''
  Name:
    getIMDb_ID
  Purpose:
    A function that attempts to get the IMDb ID (i.e., tt0000000) based
    on the information from an input file path.

    This is designed to be used for Plex DVR TV Episode files, which
    have the file naming convention of:
      Series Name - S00E00 - Episode title.ts
  Inputs:
    in_file  : Full path to file to get IMDb ID for
  Outputs:
    Returns the IMDb ID if found, or None if not found.
  '''
  log = logging.getLogger(__name__);                                            # Initialize logger
  
  year = yearPat.findall( series_name );                                        # Try to find a year in the series name
  if len(year) == 1:                                                            # If found a year
    year   = int(year[0]);                                                      # Get year from list
    series_name = yearPat.sub('', series_name);                                 # Replace year in the series name with nothing
  else:                                                                         # Else
    year   = None;                                                              # Set year equal to None
  series_name = series_name.strip();                                            # Remove leading/trailing spaces
  log.debug(
    'Series: {}, Year: {}, Ep #: {}, Title: {}'.format(
      series_name, year, season_ep, episode_title)
  )

  try:
    season, episode = re.findall( r'[sS](\d{2,4})[eE](\d{2,4})', season_ep )[0]
  except:
    season = episode = None
  else:
    season  = int(season)
    episode = int(episode)

  imdbId = TVDb_Search(series_name, year, episode_title, season=season, episode=episode)    # Try to get id from TVDb
  if imdbId:                                                                                # If got id
    return imdbId                                                                           # Return ID
  return IMDb_Search(series_name, year, episode_title, season=season, episode=episode)      # Just return output from IMDb_Search
