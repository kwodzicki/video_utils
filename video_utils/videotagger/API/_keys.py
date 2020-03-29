import os, time

from ...config import CONFIG

TVDbCACHE = os.path.join( os.path.expanduser('~'), '.tvdbToken' )                       # Set location of cache file for tvdbtoken
TIMEOUT   = 23 * 60 * 60                                                                # Set timeout for TVDb token to 23 hours

class Keys( object ):
  __TMDb_API_KEY    = os.environ.get('TMDB_API_KEY',   CONFIG.get('TMDB_API_KEY', None) )# Try to get TMDB_API_KEY from user environment; then try to get from CONFIG; then just use None
  __TMDb_API_TOKEN  = os.environ.get('TMDB_API_TOKEN', None)                             # Try to get TMDB_API_TOKEN from environment; then just use None
  __TVDb_API_KEY    = os.environ.get('TVDB_API_KEY',   CONFIG.get('TVDB_API_KEY', None) )# Try to get TVDB_API_KEY from user environment; then try to get from CONFIG; then just use None 
  __TVDb_API_TOKEN  = os.environ.get('TVDB_API_TOKEN', None)                             # Try to get TVDB_API_TOKEN from environment; then just use None
 
  __TVDb_USERNAME   = None
  __TVDb_USERKEY    = None
  __TVDb_TIME       = None

  def __init__(self):
    '''
    Method to initialize class
    '''
    if os.path.isfile( TVDbCACHE ):                                                     # If the TVDb cache file exists
      with open(TVDbCACHE, 'r') as fid:                                                 # Open for reading
        token, t = fid.read().split()                                                   # Read in the data; split on space to get token and time token was obtained
      t = float(t)                                                                      # Convert time to float
      if ( (time.time() - t) < TIMEOUT ):                                               # If current time minus token time is less than timeout
        self.__TVDb_API_TOKEN = token                                                   # Set token
        self.__TVDb_TIME      = t                                                       # Set token time
      else:                                                                             # Else
        self.__TVDb_API_TOKEN = None                                                    # Set token to None
        self.__TVDb_TIME      = None                                                    # Set token time to None

  ###############################################
  # The Movie Database
  @property
  def TMDb_API_KEY(self):
    return self.__TMDb_API_KEY
  @TMDb_API_KEY.setter
  def TMDb_API_KEY(self, val):
    self.__TMDb_API_KEY = val

  @property
  def TMDb_API_TOKEN(self):
    return self.__TMDb_API_TOKEN
  @TMDb_API_TOKEN.setter
  def TMDb_API_TOKEN(self, val):
    self.__TMDb_API_TOKEN = val

  #####################################################
  # The TV Database
  @property
  def TVDb_API_KEY(self):
    return self.__TVDb_API_KEY
  @TVDb_API_KEY.setter
  def TVDb_API_KEY(self, val):
    self.__TVDb_API_KEY = val

  @property
  def TVDb_API_TOKEN(self):
    if self.__TVDb_TIME:                                                # If time was set
      dt = time.time() - self.__TVDb_TIME                               # Compute token time
      if (dt < TIMEOUT):                                                # If less than timeout
        return self.__TVDb_API_TOKEN                                    # Return token
    return None                                                         # Return None
  @TVDb_API_TOKEN.setter
  def TVDb_API_TOKEN(self, val):
    if val:
      self.__TVDb_TIME = time.time()                                    # Set time of token
      with open(TVDbCACHE, 'w') as fid:
        fid.write( '{} {}'.format(val, self.__TVDb_TIME) )
    else:
      self.__TVDb_TIME = None
    self.__TVDb_API_TOKEN = val                                         # Set token

  @property
  def TVDb_USERNAME(self):
    return self.__TVDb_USERNAME
  @TVDb_USERNAME.setter
  def TVDb_USERNAME(self, val):
    self.__TVDb_USERNAME = val

  @property
  def TVDb_USERKEY(self):
    return self.__TVDb_USERKEY
  @TVDb_USERKEY.setter
  def TVDb_USERKEY(self, val):
    self.__TVDb_USERKEY = val
