import logging;
try:
  from imdb import IMDb
except:
  raise Exception('IMDbPY failed to import!');

imdb   = IMDb()                                                                     # Initialize IMDb instanc

########################################################################################
def updateSeriesInfo( series, episode ):
  '''
  Purpose:
    To update series information in the episode object
  Inputs:
    series  : imdbpy Movie object containing information about series
    episode : imdbpy Movie object containing information about episode
  Keywords:
    None.
  Returns:
    Update episode object
  '''
  if ('year' in series):
    episode['first_air_date'] = series['year']
  return episode

########################################################################################
def episodeByID( episode ):
  '''
  Purpose:
    Function to get series information for given episode if
    IMDb ID was used to get episode.
  Inputs:
    episode : imdbpy Movie object returned by .get_movie()
  '''
  log = logging.getLogger(__name__)

  try:                                                                          # Try to
    seriesID = episode['episode of'].getID()                                       # Get series ID
  except:
    log.warning( 'Failed to get IMDb ID for series' )                           # Log warning
  else:
    try:
      series = imdb.get_movie( seriesID )                                         # Get series information
    except:
      log.warning( 'Failed to get series information from IMDb' )
    else:
      episode = updateSeriesInfo( series, episode )  
  return episode

########################################################################################
def episodeBySeasonEp( series, episode, seasonEp ):
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
  log.debug('Searching for episode based on season/episode number')
  url    = imdb.urls['movie_main'] % series.movieID + 'episodes'
  log.debug( 'Getting data from: {}'.format(url) )
  cont   = imdb._retrieve( url )                                                        # Get content from episod
  data_d = imdb.mProxy.season_episodes_parser.parse( cont )                             # Parse episodes informat
  if (seasonEp[0] in data_d['data']['_seasons']):
    url        = '{}?season={}'.format(url, seasonEp[0])
    log.debug( 'Getting data from: {}'.format(url) )
    other_cont = imdb._retrieve( url )
    other_data = imdb.mProxy.season_episodes_parser.parse(other_cont)
    episodes   = other_data['data']['episodes'][seasonEp[0]]                            # Get dictionary of episo
    if (seasonEp[1] in episodes):
      log.debug( 'IMDb information found based on season/episode number' )
      epID = episodes[ seasonEp[1] ].getID()
      return imdb.get_movie( epID )
    else:
      log.debug( 'Falling back to matching by episode name' )
      for key, val in episodes.items():
        if val['title'].lower() in episode.lower():                                     # Check that the titles are the same
          epID = val.getID()
          return imdb.get_movie( epID )
  return None

########################################################################################
def episodeByTitle( series, episode ):
  '''
  Purpose:
    Function to get episode information for given episode
    based on episode title
  Inputs:
    series  : idmbpy Movie object of series information
    episode : Name of the episode to get
  '''
  log = logging.getLogger(__name__)
  log.debug('Searching for episode based on episode title')
  imdb.update( series, 'episodes' )                                             # Get information for a
  for s in series['episodes']:                                                  # Iterate over all the se
    for e in series['episodes'][s]:                                             # Iterate over all the ep
      if series['episodes'][s][e]['title'].lower() in episode.lower():          # Check that the titles a
        log.info( 'IMDb information found')
        epID = series['episodes'][s][e].getID()
        return imdb.get_movie( epID )
 
########################################################################################
def getEpisode( title, episode, seasonEp = None, year = None ):
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
  Outputs:
    Returns imdbpy Movie object if found; empty dictionary if not found
  '''
  log = logging.getLogger(__name__)
  seriesSearch  = imdb.search_movie( title )                                            # Search for the episode
  log.debug( 'IMDb search returned {} matches'.format( len(seriesSearch) ) )            # Debugging information
  for series in seriesSearch:                                                           # Iterate over all the re
    if (series['kind'].lower() != 'tv series'): continue                                # If object is NOT tv series, skip it
    log.debug('Found series with matching name')

    if ('year' in series) and year:                                                     # If the 'series year' ke
      log.debug('Series has year information')
      if (series['year'] != year):
        log.debug('Series year did NOT match')
        continue                                                                        # If the result series ye

    if seasonEp:                                                                        # If seasonEp is set
      ep = episodeBySeasonEp( series, episode, seasonEp )                               # Get episode information
    else:
      ep = episodeByTitle( series, episode )
  
    if ep and ('year' in series):
      ep['first_air_date'] = series['year']
      ep['seriesName']     = '{} ({})'.format(series['title'], series['year'])

    return ep
  return {}
 
########################################################################################
def getIMDb_Info( 
    IMDbID     = None, 
    title      = None,
    episode    = None, 
    seasonEp   = None, 
    year       = None):
  '''
  Name:
    getIMDb_Info
  Purpose:
    A python functio that attempts to download information
    from imdb.com using the IMDbPY python package.
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
  Outputs:
    Returns and instance of the imdb.IMDb().get_movie
    function
  Author and History:
    Kyle R. Wodicki     Created 16 Sep. 2017
  '''

  log       = logging.getLogger(__name__)                                           # Initialize a logger

  log.info('Attempting to get information from imdb.com...')
  epInfo = None
  if IMDbID:                                                                        # If ID is input, use that
    resp = imdb.get_movie( IMDbID.replace('tt','') )                                # Get movie (or episode) from IMDb based on the ID
    if ('episode of' not in resp):                                                  # If 'episode of' NOT in the response, assume is movie
      return resp
    else:                                                                           # Else, assume episode
      return episodeByID( resp )                                                    # Try to get some series information 
  elif title and (not episode):                                                     # If title is set and year is not; assume we want a movie
    log.info( 'Assuming movie search based on keywords' )
    if year:                                                                        # If the year is also set, then we will try to find the movie
      resp = imdb.search_movie( title )                                             # Search for the movie
      for r in resp:                                                                # Iterate over responses
        if (r['year'] == year):                                                     # If year matches
          return r                                                                  # Return the movie information
      log.warning( 'Failed to find movie' )                                         # If got here, then did not return yet
    else:
      log.error( 'Must input year for movie search!' )
    return {}                                                                       # Return nothing from this section
  elif title and episode:                                                           # If title and episode are set, assume we want an episode
    return getEpisode( title, episode, seasonEp = seasonEp, year = year )

  return None
