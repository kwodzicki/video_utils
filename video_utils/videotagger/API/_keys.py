import os, time

from ...config import CONFIG

TVDbCACHE = os.path.join( os.path.expanduser('~'), '.tvdbToken' )
TIMEOUT   = 23 * 60 * 60

class Keys( object ):
  __TMDb_API_KEY    = os.environ.get('TMDB_API_KEY',   CONFIG.get('TMDB_API_KEY', None) )
  __TMDb_API_TOKEN  = os.environ.get('TMDB_API_TOKEN', None)
  __TVDb_API_KEY    = os.environ.get('TVDB_API_KEY',   CONFIG.get('TVDD_API_KEY', None) )
  __TVDb_API_TOKEN  = os.environ.get('TVDB_API_TOKEN', None)
  __TVDb_USERNAME   = None
  __TVDb_USERKEY    = None
  __TVDb_TIME       = None
  def __init__(self):
    if os.path.isfile( TVDbCACHE ):
      with open(TVDbCACHE, 'r') as fid:
        token, t = fid.read().split()
      t        = float(t)
      if ( (time.time() - t) < TIMEOUT ):
        self.__TVDb_API_TOKEN = token
        self.__TVDb_TIME      = t

  #######
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

  ######
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
