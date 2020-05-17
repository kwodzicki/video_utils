import logging
import os, re
from .Person import Person

# Dictionary for converting episode ordering (aired or DVD) to standard format
TVDbOrder = {'airedOrder' : {
                     'airedSeason'        : 'season_number',
                     'airedEpisodeNumber' : 'episode_number'},
             'dvdOrder'   : {
                     'dvdSeason'          : 'season_number',
                     'dvdEpisodeNumber'   : 'episode_number'}}

TVDb2Stnd = {'episodeName'        : 'name',
             'firstAired'         : 'air_date',
             'seriesName'         : 'name'}

TMDb2Stnd = {'first_air_date'     : 'air_date'}

PARENTH   = re.compile( r'(\s+\([^\)]+\))$' )                                           # Pattern to find any (xxx) data at and of string

def standardize( info, **kwargs ):
  tvdb     = kwargs.get('TVDb', False)                                                  # IF the TVDb keyword is set
  keys     = TVDb2Stnd if tvdb else TMDb2Stnd                                           # Set the keys dictionary based on tvdb
  infoKeys = list( info.keys() ) 
  for key in infoKeys:                                                                  # Iterate over all keys in info
    if (key in keys):                                                                   # If key is in keys
      info[ keys[key] ] = info.pop(key)                                                 # Pop key from dict and re-add as new standard key
  if tvdb:                                                                              # If tvdb then 
    key  = 'airedOrder' if kwargs.get('airedOrder', False) else 'dvdOrder'              # Set key to 'airedOrder' or 'dvdOrder' based on airedOrder keyword; 'dvdOrder' by default
    keys = TVDbOrder[key]                                                               # Get keys for converting ordering to internal format
    for key in infoKeys:                                                                # Iterate over keys in infoKeys
      if key in keys:                                                                   # If the key is in the keys dictionary
        info[ keys[key] ] = info.pop(key)                                               # Convert the key 
    return tvdb2tmdb( info )                                                            # Convert TVDb info to match TMDb 
  return info                                                                           # Return info; if got here then tvdb was False

def tvdb2tmdb( info ):
  # Work on name key
  key = 'name'                                                                          # Set key for next section; makes updating key easier as used a lot in next few lines
  if info.get(key, None) is None:                                                       # Try to get key from dictionary; check if None
    return None                                                                         # If None, return None
  if isinstance(info[key], (tuple,list)):                                               # If the value is iterable
    info[key] = ' - '.join(info[key])                                                   # Join value
  info[key] = PARENTH.sub('', info[key])

  if ('imdbId' in info):
    info[ 'external_ids' ] = {'imdb_id' : info.pop('imdbId') }

  credits = info.pop( 'credits', {} ) 
  crew    = [] 
  job     = 'Director'
  if ('director' in info):
    name = info.pop('director')
    crew.append( {'name' : name, 'job' : job } )
  elif ('directors' in info):
    for name in info.pop('directors'):
      crew.append( {'name' : name, 'job' : job } )

  job = 'Writer'
  if ('writers' in info):
    for name in info.pop('writers'):
      crew.append( {'name' : name, 'job' : job } )

  if crew:
    credits['crew'] = crew
    
  guests = info.pop('guestStars', None)
  if guests:
    for i in range( len(guests) ):
      guests[i] = {'name' : guests[i]}
    credits['guest_stars'] = guests 

  if credits:
    info['credits'] = credits

  keys = ['seriesId', 'airedSeasonID', 'season', 'season_number', 'episode_number']     # List of keys that need to be checked for matching
  for key in keys:                                                                      # Iterate over all keys
    if key in info and isinstance(info[key], (tuple, list)):                            # If the key is in info dictionary, and the value of the key is an iterable
      if not all( [i == info[key][0] for i in info[key]] ):                             # If not all the values match
        raise Exception('Not all values in {} match!'.format(key))                      # Raise exception
      info[key] = info[key][0]                                                          # Set info[key] value to the first element of the iterable

  return info

def parseCredits( info, **kwargs ):
  """
  Function to parse credits into Person objects

  Arguments:
    info (dict): Data from an API call

  Keyword argumetns:
    None.

  Returns:
    dict: Updated dictionary
  """

  log     = logging.getLogger(__name__)
  credits = info.pop('credits', None)
  if credits:
    log.debug('Found credits to parse')
    for key, val in credits.items():
      if isinstance(val, list):
        if len(val)== 0:
          log.debug( 'Empty  : {}'.format(key) )
        else:
          log.debug( 'Parsing: {}'.format(key) )
          for i in range( len(val) ):
            val[i] = Person( data = val[i] )
          if (key != 'crew') and ('order' in val[0]):
            info[key] = sorted(val, key=lambda x: x.order)
          else:
            info[key] = val
  return info

def parseReleases( info, **kwargs ):
  releases = info.pop( 'release_dates', None )
  if releases:
    results = releases.pop('results', None )
    if results:
      for result in results:
        releases[result['iso_3166_1']] = result['release_dates']
      info['release_dates'] = releases
  return info

def imagePaths( info, **kwargs ):
  imageURL = kwargs.get('imageURL', None)
  if imageURL:
    imageKeys = ['_path', 'poster', 'banner', 'fanart', 'filename']
    for key, val in info.items():
      if any( [image in key for image in imageKeys] ):
        if isinstance(val, (list,tuple)): val = val[0]                                  # If is an iterable, take first value
        info[key] = imageURL.format( val )
  return info

def parseInfo( info, **kwargs ):
  info = standardize(   info, **kwargs )
  if info is not None:
    info = parseCredits(  info, **kwargs )
    info = parseReleases( info, **kwargs ) 
    info = imagePaths(    info, **kwargs )
  return info
