import logging
import os, re
from .Person import Person


TVDb2Stnd = {'airedSeason'        : 'season_number',
             'airedEpisodeNumber' : 'episode_number',
             'episodeName'        : 'name',
             'firstAired'         : 'air_date',
             'seriesName'         : 'name'}

TMDb2Stnd = {'first_air_date'     : 'air_date'}

PARENTH   = re.compile( r'(\s+\([^\)]+\))$' )                           # Pattern to find any (xxx) data at and of string

def standardize( info, **kwargs ):
  tvdb = kwargs.get('TVDb', False)                                      # IF the TVDb keyword is set
  keys = TVDb2Stnd if tvdb else TMDb2Stnd                               # Set the keys dictionary based on tvdb
  for key in info.keys():                                               # Iterate over all keys in info
    if (key in keys):                                                   # If key is in keys
      info[ keys[key] ] = info.pop(key)                                 # Pop key from dict and re-add as new standard key
  if tvdb:                                                              # If tvdb then 
    return tvdb2tmdb( info )                                            # Convert TVDb info to match TMDb 
  return info

def tvdb2tmdb( info ):
  if info.get('name', None) is None:
    return None
  info['name'] = PARENTH.sub('', info['name'])

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

  return info

def parseCredits( info, **kwargs ):
  '''
  Purpose:
    Function to parse credits into Person objects
  Inputs:
    info   : Dictionary, or dictionary like, containing data from API call
  Keywords:
    None.
  Returns:
    Updated dictionary
  '''
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
      if any( image in key for image in imageKeys ):
        info[key] = imageURL.format( val )
  return info

def parseInfo( info, **kwargs ):
  info = standardize(   info, **kwargs )
  if info is not None:
    info = parseCredits(  info, **kwargs )
    info = parseReleases( info, **kwargs ) 
    info = imagePaths(    info, **kwargs )
  return info
