import logging
try:
  from ...api_keys import tvdb as tvdb_key       # Attempt to import the API key from the api_keys module
except:
  tvdb_key = os.environ.get('TVDB_API_KEY', None)         # On exception, try to get the API key from the TVDB_API_KEY environment variable

if not tvdb_key:
  msg = "API key for TVDb could NOT be imported!"
  logging.getLogger(__name__).error( msg )
  raise Exception( msg )

import time

import tvdbsimple as TVDb 
TVDb.KEYS.API_KEY = tvdb_key;

########################################################################################
def tvdbSeriesSearch( title = None, IMDbID = None):
  '''
  Purpose:
    Function to query tvdb.com for  series
  Inputs:
    None.
  Keywords:
    title   : Title of series to look for
    IMDbID  : IMDb ID of series to search for. 
               If both keys used, this key takes priority.
               If search success with IMDb, then returns
               results, else tries with title
  Output:
    Returns list containing search results, or empty list
    if no results
  '''
  log = logging.getLogger(__name__)
  if IMDbID:
    if (IMDbID[:2] != 'tt'):
      IMDbID = 'tt{}'.format( IMDbID )
    log.debug( 'Search TVDb using IMDb ID' )
    try:
      resp = TVDb.Search().series( imdbId = IMDbID )                                  # Set up a search instance of tvdbsimple
    except:
      log.warning( 'TVDb search failed using IMDb' )
    else:
      return resp

  if title:
    log.debug( 'Search TVDb using series title' )
    try:
      resp = TVDb.Search().series( name = title )                                     # Set up a search instance of tvdbsimple
    except:
      log.warning( 'TVDb search failed using series title' )
    else:
      return resp
   
  return [] 


########################################################################################
def episodeBySeasonEp(series, episode, seasonEp):
  '''
  Purpose:
    Function to get episode information based on
    episode and season number. This function only
    get information for episodes in given season to
    reduce pinging TVDb. If search files to find
    episode with given number, will try to find
    based on name
  Inputs:
    series   : Dictionary of series inforamtion
    episode  : Name of the episode to get
    seasonEp : Tuple or list containing season and episode numbers
  '''
  log = logging.getLogger(__name__)
  log.debug( 'Searching TVDb by season/episode number' )
  kwargs = {'airedSeason' : seasonEp[0], 'airedEpisode' : seasonEp[1]}                  # Set keyword arguments f
  try:
    eps = TVDb.Series_Episodes( series['id'], **kwargs  ).all()                         # Get episodes for just t
  except Exception as err:
    log.debug('TVDb Series/Episodes search failed: {}'.format(err))
    eps = None

  if not eps:
    try:
      series_eps = TVDb.Series( series['id'] ).Episodes                                 # Get list of all episo
    except Exception as err:
      log.debug('TVDb failed to grab all episodes: {}'.format(err))
    else:
      info   = series_eps.summary()
      season = str(seasonEp[0])
      if (season in info['airedSeasons']): 
        eps = series_eps.all()

  if eps:
    log.debug( 'TVDb returned {} episodes in the series'.format(len(eps)) )             # Debugging information
    for ep in eps:
      if (ep['airedSeason'] == seasonEp[0]) and (ep['airedEpisodeNumber'] == seasonEp[1]):
        return ep

    return episodeByTitle( series, episode, eps = eps )

  log.warning( 'TVDb search failed' )
  return {}

########################################################################################
def episodeByTitle( series, episode, eps = None ):
  '''
  Purpose:
    Function to get episode information for given episode
    based on episode title
  Inputs:
    series  : idmbpy Movie object of series information
    episode : Name of the episode to get
  Keywords:
    eps     : List of episodes to search; intended for when
               calling funtion from episodeBySeasonEp, which
               already downloaded all episode information
               if it is calling this function.
  '''
  log = logging.getLogger(__name__)
  log.debug( 'Searching TVDb by episode title' )
  if episode:
    if not eps:                                                                           # If eps not defined, then we will download all episode data
      try:
        eps = TVDb.Series( series['id'] ).Episodes.all()                                  # Get list of all episo
      except Exception as err:
        log.debug('TVDb failed to grab all episodes: {}'.format(err))

    if eps:
      for ep in eps:                                                                      # If made here, iterate
        if (ep['episodeName'].lower() in episode.lower()):                                # If the episode name i
          log.debug( 'Found episode with same name' )
          return ep                                                                       # Return it

  log.warning( 'TVDb search failed' )
  return {}

########################################################################################
def getTVDb_Info( episode,
    title    = None,
    seasonEp = None,
    year     = None,
    IMDbID   = None,
    tmdbInfo = None):
  '''
  Name:
    getTVDb_Info
  Purpose:
    A python function to download tv show informaiton from thetvdb.com
  Inputs:
    episode  : Name of episode to search for.
  Keywords:
    title    : Name of series to search for.
    IMDbID   : The IMDb ID for the TV series
    seasonEp : Tuple or list containing season and episode numbers
    year     : Year of movie or series; required for movie search
  Outputs:
    Returns the dictionary of information downloaded from thetvdb.com
    about the series.
  '''
  log = logging.getLogger(__name__)                                                     # Initialize logger

  if (not title) and (not IMDbID):
    raise Exception('Must input series name OR series IMDb ID' )

  resp = tvdbSeriesSearch(title = title, IMDbID = IMDbID)
  log.debug( 'TVDb series search returned {} matche(s)'.format( len(resp) ) )
  for r in resp:                                                                        # Iterate over all search
    time.sleep(0.1)                                                                     # Sleep to reduce hammeri
    if year and r['firstAired']:
      if (str(year) in r['firstAired']):                                                # If year is denfined and firestAired is defined and years match
        log.debug( 'Found series with same firstAired year' )                           # Debugging information
      else:
        continue                                                                        # Else, skip series

    if seasonEp:
      ep = episodeBySeasonEp( r, episode, seasonEp )
    else:
      ep = episodeByTitle( r, episode )

    if ep:
      ep['first_air_date'] = r['firstAired']
      ep['seriesName']     = r['seriesName']
      return ep
  
  return None
