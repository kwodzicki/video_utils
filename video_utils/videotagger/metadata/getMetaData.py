import logging
  
try:
  from .getIMDb_Info import getIMDb_Info;
except:
  getIMDb_Info = None;

try:
  from .getTMDb_Info import getTMDb_Info;
except:
  getTMDb_Info = None;

try:
  from .getTVDb_Info import getTVDb_Info;
except:
  getTVDb_Info = None;

getTMDb_Info = None
getTVDb_Info = None

if not getIMDb_Info and not getTMDb_Info and not getTVDb_Info:
  raise Exception('Could not import IMDb OR TMDb  OR TVDb!');

def getMetaData( **kwargs ):
  '''
  Purpose:
    A function that attempts to get data from imdb.com, thetvdb.com, and 
    themoviedb.org. thetvdb.com is ONLY used if the video is determined to
    be an episode of a TV show and the only information used is the 
    series name. If data from from IMDb and TMDb are returned, any information
    from IMDb that is NOT in the information from TMDb is add to TMDb
    information. If only one of the websites returns information, only
    that informaiton is returned from this function. If neither site
    returns informaiton, then an empty dictionary is returned.
  Inputs:
    None
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
    Returns a dictionary, which may be empty, of metadata for the IMDb id input
  '''
  log = logging.getLogger(__name__);                                            # Initialize logger

  log.info( 'Getting metadata for file' );
  IMDb = TMDb = TVDb = None;                                                    # Set all variables to None
  if getIMDb_Info:                                                              # If getIMDb_Info imported correctly
    IMDb = getIMDb_Info( **kwargs )                                             # Get information from imdb.com
    if IMDb:                                                                    # If valid data returned from IMDb.com
      if ('episode of' in IMDb) and getTVDb_Info:                               # If the data is for an episode and getTVDb_Info imported correclty
        episode     = kwargs.get( 'episode', IMDb['title'] )                    # Get episode name for kwargs; use IMDb as fall back
        seasonEp    = kwargs.get('seasonEp', (IMDb['season'], IMDb['episode'])) # Add seasonEp to keywords
        TVDb_kwargs = {'IMDbID'   : IMDb['episode of'].getID(),
                       'seasonEp' : seasonEp}                                   # Initialize keyword args for TVDb
        TVDb        = getTVDb_Info( episode, **TVDb_kwargs )                    # Get information from TVDb based on imdbId if TVDb is available
        if TVDb:                                                                # If information is downloaded
          if ('seriesName' in TVDb):                                            # If there is a seriesName tag in the info
            IMDb['seriesName'] = TVDb['seriesName'];                            # Redefine the series name

  if getTMDb_Info:                                                              # If getTMDb_Info imported correctly
    TMDb = getTMDb_Info( **kwargs )                                             # If TMDb is True, get information from themoviedatabase.org
    if TMDb:                                                                    # If TMDb is valid
      if TMDb.is_episode and getTVDb_Info:                                      # If the data if for an episode and getTVDb_Info imported correlcty
        if (not TVDb):                                                          # If information from thetvdb.com as not yet been downloaded
          episode     = kwargs.get( 'episode', IMDb['title'] )                    # Get episode name for kwargs; use IMDb as fall back
          seasonEp    = kwargs.get('seasonEp', (IMDb['season'], IMDb['episode'])) # Add seasonEp to keywords
          IMDbID      = TMDb['show_external_ids'].get('imdb_id', None) 
          TVDb_kwargs = {'IMDbID'   : IMDbID, 'seasonEp' : seasonEp}                                   # Initialize keyword args for TVDb
          TVDb        = getTVDb_Info( episode, **TVDb_kwargs )                    # Get information from TVDb based on imdbId if TVDb is available
        if TVDb:                                                                # If information is downloaded
          if ('seriesName' in TVDb):                                            # If there is a seriesName tag in the info
            TMDb.set_item('seriesName', TVDb['seriesName']);                    # Redefine the series name

  if (not TMDb) and (not IMDb):                                                 # If both are not valid
    return {};                                                                  # Return empty dictionary
  elif TMDb and (not IMDb):                                                     # Else, if TMBd is valid AND IMDb is not...
    return TMDb;                                                                # Return TMBd
  elif (not TMDb) and IMDb:                                                     # Else, if IMBd is not valid AND TMDb is...
    return IMDb;                                                                # Return IMBd
  else:                                                                         # Else, both must valid
    TMDb.IMDbID = IMDb.getID()                                                  # Set IMDbID attribute of TMDb
    for key in IMDb.keys():                                                     # Iterate over all keys in IMDb
      if not TMDb.has_key(key):                                                 # If TMDb does NOT have the key
        try:                                                                    # Try to
          info = IMDb[key];                                                     # Get info from IMDb using; in try because has broken before
        except:                                                                 # If failed to get key
          log.debug( 'Failed to get IMDb key: {}'.format(key) );
        else:                                                                   # If was success
          TMDb.set_item( key, info );                                           # Add the key from IMDb to TMDb
    return TMDb;                                                                # Return TMDb object
