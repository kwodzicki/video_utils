import logging
import requests, json
from datetime import datetime

from ._keys import Keys

KEYS    = Keys()
DATEFMT = '%Y-%m-%d'

def convertDate( info ):
  if isinstance(info, (list,tuple,)):
    return [ convertDate(i) for i in info ]
  elif isinstance(info, dict):
    for key, val in info.items():
      if isinstance(val, (list,tuple,dict,)):
        info[key] = convertDate( val )
      elif ('date' in key) or ('Aired' in key):
        try:
          info[key] = datetime.strptime(val, DATEFMT)
        except:
          info[key] = None
  return info



####################################################################################
class BaseAPI( object ):
  TMDb_URLBase    = 'https://api.themoviedb.org/3'
  TMDb_URLSearch  = '{}/search/multi'.format( TMDb_URLBase )
  TMDb_URLMovie   = '{}/movie/{}'.format(     TMDb_URLBase,   '{}' )
  TMDb_URLSeries  = '{}/tv/{}'.format(        TMDb_URLBase,   '{}' )
  TMDb_URLSeason  = '{}/season/{}'.format(    TMDb_URLSeries, '{}' )
  TMDb_URLEpisode = '{}/episode/{}'.format(   TMDb_URLSeason, '{}' )
  TMDb_URLPerson  = '{}/person/{}'.format(    TMDb_URLBase,   '{}' )
  TMDb_URLImage   = 'http://image.tmdb.org/t/p/original/{}'

  TVDb_URLBase    = 'https://api.thetvdb.com'
  TVDb_URLLogin   = '{}/login'.format( TVDb_URLBase )
  TVDb_URLSearch  = '{}/search/series'.format( TVDb_URLBase )
  TVDb_URLMovie   = '{}/movies/{}'.format(     TVDb_URLBase,   '{}' )
  TVDb_URLSeries  = '{}/series/{}'.format(     TVDb_URLBase,   '{}' )
  TVDb_URLEpisode = '{}/episodes/{}'
  TVDb_URLImage   = 'https://artworks.thetvdb.com/banners/{}' 
  __TVDb_Headers  = {'Content-Type': 'application/json'} 

  def __init__(self, *args, **kwargs):
    self.__log = logging.getLogger(__name__)

  @property
  def TVDb_Headers(self):
    self._tvdbLogin()
    return self.__TVDb_Headers

  def _tvdbLogin(self):
    if KEYS.TVDb_API_TOKEN:
      self.__log.debug( 'Using existing TVDb token' )
      self.__TVDb_Headers['Authorization'] = 'Bearer {}'.format(KEYS.TVDb_API_TOKEN)
    else:
      self.__TVDb_Headers.pop('Authorization', None)
      KEYS.TVDb_API_TOKEN = None
      if KEYS.TVDb_API_KEY:
        self.__log.debug( 'Getting new TVDb token' )
        data = {"apikey": KEYS.TVDb_API_KEY}
        if KEYS.TVDb_USERNAME and KEYS.TVDb_USERKEY:
          data.update( {"username": KEYS.TVDb_USERNAME, "userkey": KEYS.TVDb_USER} )

        resp = requests.post( self.TVDb_URLLogin, data=json.dumps(data), headers=self.__TVDb_Headers )

        if (resp.status_code == 200):
          KEYS.TVDb_API_TOKEN = resp.json()['token']
          self.__TVDb_Headers['Authorization'] = 'Bearer {}'.format(KEYS.TVDb_API_TOKEN)
          return True
        else:
          self.__log.error( 'Error getting TVDb login token!' )
      else:
        raise Exception( 'No TVDb API key defined!' )


  #################################
  def _getRequest(self, url, **params):
    '''
    Purpose:
      Method to issue requests.get()
    Inputs:
      All accepted by requests.get()
    Keywords:
      All keywords are sent to params keyword of requests.get
    Outputs:
      requests Response object
    '''
    resp   = None
    kwargs = {'params' : params}
    if (self.TMDb_URLBase in url):
      if ('api_key' not in kwargs['params']):
        if KEYS.TMDb_API_KEY:
          kwargs['params']['api_key'] = KEYS.TMDb_API_KEY
        else:
          raise Exception( 'TMDb API Key is not set!' )
    elif (self.TVDb_URLBase in url):
      kwargs['headers'] = self.TVDb_Headers
    else:
      raise Exception( 'Invalid URL!' )

    try:
      resp  = requests.get( url, **kwargs )
    except Exception as err:
      self.__log.error( 'Request failed: {}'.format(err) )
    else:
      if not resp.ok:
        self.__log.error( 'Request is not okay' )
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
  def _getJSON(self, url, **kwargs):
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
    key  = 'append_to_response'                                                     # Key to check 
    if (key in kwargs):                                                             # If key is present
      if isinstance(kwargs[key], (list, tuple,) ):                                  # If value under key is tuple or list
        kwargs[key] = ','.join( kwargs[key] )                                       # Join using comma
    resp = self._getRequest(url, **kwargs)
    if resp:
      try:
        json = resp.json()
      except Exception as err:
        self.__log.error('Failed to get JSON data')
      resp = self._closeRequest( resp )
    return convertDate( json )
