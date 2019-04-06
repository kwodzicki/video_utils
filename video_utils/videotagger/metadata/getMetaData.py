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

if not getIMDb_Info and not getTMDb_Info and not getTVDb_Info:
  raise Exception('Could not import IMDb OR TMDb  OR TVDb!');

def getMetaData( IMDb_ID, attempts = None ):
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
    IMDb_ID  : The IMDb id for the video
  Outputs:
    Returns a dictionary, which may be empty, of metadata for the IMDb id input
  Keywords:
    attempts: Maximum attempts for download retries
  '''
  log = logging.getLogger(__name__);                                            # Initialize logger

  log.info( 'Getting metadata for file' );
  IMDb = TMDb = TVDb = None;                                                    # Set all variables to None
  if getIMDb_Info:                                                              # If getIMDb_Info imported correctly
    IMDb = getIMDb_Info( IMDb_ID, attempts = attempts );                        # Get information from imdb.com
    if IMDb:                                                                    # If valid data returned from IMDb.com
      if ('episode of' in IMDb) and getTVDb_Info:                               # If the data is for an episode and getTVDb_Info imported correclty
        try:                                                                    # Try to...
          imdbId = IMDb['episode of'].getID();                                  # Get the imdbID for the series
        except:                                                                 # If there is an error getting to ID for the series...
          log.warning('Could NOT get series id from imdb.com, info incomplete!!!');# Log a warning message
        else:                                                                   # If the try is a success
          TVDb = getTVDb_Info( imdbId = imdbId );                               # Get information from TVDb based on imdbId if TVDb is available
        if TVDb:                                                                # If information is downloaded
          if 'seriesName' in TVDb:                                              # If there is a seriesName tag in the info
            IMDb['seriesName'] = TVDb['seriesName'];                            # Redefine the series name

  if getTMDb_Info:                                                              # If getTMDb_Info imported correctly
    TMDb = getTMDb_Info( IMDb_ID, attempts = attempts );                        # If TMDb is True, get information from themoviedatabase.org
    if TMDb:                                                                    # If TMDb is valid
      if TMDb['is_episode'] and getTVDb_Info:                                   # If the data if for an episode and getTVDb_Info imported correlcty
        if not TVDb:                                                            # If information from thetvdb.com as not yet been downloaded
          TVDb = getTVDb_Info( Info = TMDb );                                   # Get information from TVDb
        if TVDb:                                                                # If information is downloaded
          if 'seriesName' in TVDb:                                              # If there is a seriesName tag in the info
            TMDb.set_item('seriesName', TVDb['seriesName']);                    # Redefine the series name

  if (not TMDb) and (not IMDb):                                                 # If both are not valid
    return {};                                                                  # Return empty dictionary
  elif TMDb and (not IMDb):                                                     # Else, if TMBd is valid AND IMDb is not...
    return TMDb;                                                                # Return TMBd
  elif (not TMDb) and IMDb:                                                     # Else, if IMBd is not valid AND TMDb is...
    return IMDb;                                                                # Return IMBd
  else:                                                                         # Else, both must valid
    for key in IMDb.keys():                                                     # Iterate over all keys in IMDb
      if not TMDb.has_key(key):                                                 # If TMDb does NOT have the key
        try:                                                                    # Try to
          info = IMDb[key];                                                     # Get info from IMDb using; in try because has broken before
        except:                                                                 # If failed to get key
          log.debug( 'Failed to get IMDb key: {}'.format(key) );
        else:                                                                   # If was success
          TMDb.set_item( key, info );                                           # Add the key from IMDb to TMDb
    return TMDb;                                                                # Return TMDb object