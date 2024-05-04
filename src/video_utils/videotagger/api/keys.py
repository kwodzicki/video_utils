"""
API Key handler for TMDb and TVDb

"""

import os
import time

from ...config import CONFIG

# Set location of cache file for tvdbtoken
TVDbCACHE = os.path.join(os.path.expanduser('~'), '.tvdbToken')
# Set timeout for TVDb token to 23 hours
TIMEOUT = 23 * 60 * 60


class Keys:
    """
    Class to store API key info for TVDb and TMDb

    """

    # Try to get TMDB_API_KEY from user environment;
    # then try to get from CONFIG; then just use None
    __TMDb_API_KEY = os.environ.get(
        'TMDB_API_KEY',
        CONFIG.get('TMDB_API_KEY', None),
    )

    # Try to get TMDB_API_TOKEN from environment; then just use None
    __TMDb_API_TOKEN = os.environ.get('TMDB_API_TOKEN', None)

    # Try to get TVDB_API_KEY from user environment;
    # then try to get from CONFIG; then just use None
    __TVDb_API_KEY = os.environ.get(
        'TVDB_API_KEY',
        CONFIG.get('TVDB_API_KEY', None),
    )

    # Try to get TVDB_API_TOKEN from environment; then just use None
    __TVDb_API_TOKEN = os.environ.get('TVDB_API_TOKEN', None)

    __TVDb_USERNAME = None
    __TVDb_USERKEY = None
    __TVDb_TIME = None

    def __init__(self):
        """Initialize class"""

        # If the TVDb cache file exists
        if not os.path.isfile(TVDbCACHE):
            return

        # Open for reading
        with open(TVDbCACHE, mode='r', encoding='utf8') as fid:
            # Read in the data; split on space to get token and
            # time token was obtained
            token, token_time = fid.read().split()
        token_time = float(token_time)

        # If current time minus token time is less than timeout
        if (time.time() - token_time) < TIMEOUT:
            self.__TVDb_API_TOKEN = token
            self.__TVDb_TIME = token_time
        else:
            self.__TVDb_API_TOKEN = None
            self.__TVDb_TIME = None

    ###############################################
    # The Movie Database
    @property
    def TMDb_API_KEY(self):
        """Return API key for TMDb"""
        return self.__TMDb_API_KEY

    @TMDb_API_KEY.setter
    def TMDb_API_KEY(self, val):
        """Set API key for TMDb"""
        self.__TMDb_API_KEY = val

    @property
    def TMDb_API_TOKEN(self):
        """Return API token for TMDb"""
        return self.__TMDb_API_TOKEN

    @TMDb_API_TOKEN.setter
    def TMDb_API_TOKEN(self, val):
        """Set API token for TMDb"""
        self.__TMDb_API_TOKEN = val

    #####################################################
    # The TV Database
    @property
    def TVDb_API_KEY(self):
        """Return API key for TVDb"""
        return self.__TVDb_API_KEY

    @TVDb_API_KEY.setter
    def TVDb_API_KEY(self, val):
        """Set API key for TVDb"""
        self.__TVDb_API_KEY = val

    @property
    def TVDb_API_TOKEN(self):
        """Return API token for TVDb"""
        # If time was set
        if self.__TVDb_TIME:
            # If less than timeout
            if (time.time() - self.__TVDb_TIME) < TIMEOUT:
                return self.__TVDb_API_TOKEN
        return None

    @TVDb_API_TOKEN.setter
    def TVDb_API_TOKEN(self, val):
        """Set API token for TVDb"""
        if val:
            self.__TVDb_TIME = time.time()
            with open(TVDbCACHE, mode='w', encoding='utf8') as fid:
                fid.write(f'{val} {self.__TVDb_TIME}')
        else:
            self.__TVDb_TIME = None
        self.__TVDb_API_TOKEN = val

    @property
    def TVDb_USERNAME(self):
        """Return username for TVDb"""
        return self.__TVDb_USERNAME

    @TVDb_USERNAME.setter
    def TVDb_USERNAME(self, val):
        """Set username for TVDb"""
        self.__TVDb_USERNAME = val

    @property
    def TVDb_USERKEY(self):
        """Return userkey for TVDb"""
        return self.__TVDb_USERKEY

    @TVDb_USERKEY.setter
    def TVDb_USERKEY(self, val):
        """Set userkey for TVDb"""
        self.__TVDb_USERKEY = val
