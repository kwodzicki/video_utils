import logging
import requests, json
from datetime import datetime

from ._keys import Keys

KEYS    = Keys()
DATEFMT = '%Y-%m-%d'

def convertDate( info ):
  '''
  Purpose:
    Function to convert any date information into a datetime object
  Inputs:
    info  : Dictionary containing JSON response data
  Keywords:
    None.
  Returns:
    Updated info dictionary where date strings have been converted to
    datetime objects
  '''
  log = logging.getLogger(__name__)
  if isinstance(info, (list,tuple,)):                                                   # If info is a list or tuple
    return [ convertDate(i) for i in info ]                                             # Return recursive call to convertDate on each element
  elif isinstance(info, dict):                                                          # Else, if is dictionary
    for key, val in info.items():                                                       # Iterate over key/value pairs
      if isinstance(val, (list,tuple,dict,)):                                           # If value is list,tuple,dict
        info[key] = convertDate( val )                                                  # Set value of info[key] to result of recursive call
      elif ('date' in key) or ('Aired' in key):                                         # Else, if 'date' or 'Aired' in key
        try:                                                                            # Try to convert date string into datetime object
          info[key] = datetime.strptime(val, DATEFMT)
        except:
          info[key] = None
  return info



####################################################################################
class BaseAPI( object ):
  TMDb_URLBase    = 'https://api.themoviedb.org/3'
  TMDb_URLSearch  = '{}/search/multi'.format( TMDb_URLBase )
  TMDb_URLFind    = '{}/find/{}'.format(      TMDb_URLBase,   '{}' )
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
    '''
    Purpose:
      Method to login to (get api token) from TVDb
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      None. Sets attributes and creates token file in user home dir
    '''
    if KEYS.TVDb_API_TOKEN:                                                             # If api token is valid
      self.__log.log( 5, 'Using existing TVDb token' )                                   # Log info
      self.__TVDb_Headers['Authorization'] = 'Bearer {}'.format(KEYS.TVDb_API_TOKEN)    # Set TVDb headers
      return True
    else:                                                                               # Else
      self.__TVDb_Headers.pop('Authorization', None)                                    # Pop off Authorization
      KEYS.TVDb_API_TOKEN = None                                                        # Set token to None
      if KEYS.TVDb_API_KEY:                                                             # If the api key is set
        self.__log.log( 5, 'Getting new TVDb token' )                                    # Log info
        data = {"apikey": KEYS.TVDb_API_KEY}                                            # Data for requesting in api token
        if KEYS.TVDb_USERNAME and KEYS.TVDb_USERKEY:                                    # If the username and userkey are set (not recommended)
          data.update( {"username": KEYS.TVDb_USERNAME, "userkey": KEYS.TVDb_USER} )    # Add to the data dict

        resp = requests.post( self.TVDb_URLLogin, data=json.dumps(data), headers=self.__TVDb_Headers )# Request the new token

        if (resp.status_code == 200):                                                   # If request is good
          KEYS.TVDb_API_TOKEN = resp.json()['token']                                    # Get the token
          self.__TVDb_Headers['Authorization'] = 'Bearer {}'.format(KEYS.TVDb_API_TOKEN)# Set new Authorization
          return True                                                                   # Return True
        else:
          self.__log.error( 'Error getting TVDb login token!' )
      else:
        raise Exception( 'No TVDb API key defined!' )
    return False

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
      self.__log.warning( 'Request failed: {}'.format(err) )
    else:
      if not resp.ok:
        kwargs.pop('Authorization', None)                                               # Try to pop off authorization for logging; don't want to store this in logs
        self.__log.warning( 'Request is not okay: {}; {}; {}'.format(url, kwargs, resp) )
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
