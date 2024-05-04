"""
Base API class for TVDb and TMDb

"""

import logging
import json

import requests

from .keys import Keys
from .utils import convert_date

# Timeout for requests; in seconds
KEYS = Keys()


class BaseAPI:
    """BaseAPI class for interacting with TMDb and TVDb APIs"""

    TMDb_URLBase = 'https://api.themoviedb.org/3'
    TMDb_URLSearch = f'{TMDb_URLBase}/search/multi'
    TMDb_URLFind = f'{TMDb_URLBase}/find/{{}}'
    TMDb_URLMovie = f'{TMDb_URLBase}/movie/{{}}'
    TMDb_URLSeries = f'{TMDb_URLBase}/tv/{{}}'
    TMDb_URLSeason = f'{TMDb_URLSeries}/season/{{}}'
    TMDb_URLEpisode = f'{TMDb_URLSeason}/episode/{{}}'
    TMDb_URLPerson = f'{TMDb_URLBase}/person/{{}}'
    TMDb_URLImage = 'https://image.tmdb.org/t/p/original/{}'

    TVDb_URLBase = 'https://api.thetvdb.com'
    TVDb_URLLogin = f'{TVDb_URLBase}/login'
    TVDb_URLSearch = f'{TVDb_URLBase}/search/series'
    TVDb_URLMovie = f'{TVDb_URLBase}/movies/{{}}'
    TVDb_URLSeries = f'{TVDb_URLBase}/series/{{}}'
    TVDb_URLEpisode = '{}/episodes/{}'
    TVDb_URLImage = 'https://artworks.thetvdb.com/banners/{}'
    __TVDb_Headers = {'Content-Type': 'application/json'}

    TIMEOUT = 600.0

    def __init__(self, *args, **kwargs):
        """
        Arguments:
          *args: Various, None used

        Keywords arguments:
          **kwargs: Various, None used

        """

        self.__log = logging.getLogger(__name__)

    @property
    def TVDb_Headers(self):
        """Return TVDb headers"""

        self._tvdb_login()
        return self.__TVDb_Headers

    def _tvdb_login(self):
        """
        Method to login to (get api token) from TVDb

        Arguments:
          None

        Keyword arguements:
          None

        Returns:
          None: Sets attributes and creates token file in user home dir

        """

        # If api token is valid
        if KEYS.TVDb_API_TOKEN:
            self.__log.log(5, 'Using existing TVDb token')
            self.__TVDb_Headers['Authorization'] = (
                f'Bearer {KEYS.TVDb_API_TOKEN}'
            )
            return True

        self.__TVDb_Headers.pop('Authorization', None)
        KEYS.TVDb_API_TOKEN = None
        if KEYS.TVDb_API_KEY:
            self.__log.log(5, 'Getting new TVDb token')
            data = {"apikey": KEYS.TVDb_API_KEY}
            # If the username and userkey are set (not recommended)
            if KEYS.TVDb_USERNAME and KEYS.TVDb_USERKEY:
                data.update(
                    {
                        "username": KEYS.TVDb_USERNAME,
                        "userkey": KEYS.TVDb_USERKEY,
                    }
                )

            resp = requests.post(
                self.TVDb_URLLogin,
                data=json.dumps(data),
                headers=self.__TVDb_Headers,
                timeout=self.TIMEOUT,
            )

            if resp.status_code == 200:
                KEYS.TVDb_API_TOKEN = resp.json()['token']
                self.__TVDb_Headers['Authorization'] = (
                    f'Bearer {KEYS.TVDb_API_TOKEN}'
                )
                return True

            self.__log.error('Error getting TVDb login token!')
        else:
            raise Exception('No TVDb API key defined!')

        return False

    def _get_request(self, url, **params):
        """
        Method to issue requests.get()

        Arguments:
            url (str): URL for request

        Keyword arguments:
            **kwargs: All keywords are sent to params keyword of requests.get()

        Returns:
            requests Response object

        """

        resp = None
        kwargs = {'params': params}
        if self.TMDb_URLBase in url:
            if 'api_key' not in kwargs['params']:
                if KEYS.TMDb_API_KEY:
                    kwargs['params']['api_key'] = KEYS.TMDb_API_KEY
                else:
                    raise Exception('TMDb API Key is not set!')
        elif self.TVDb_URLBase in url:
            kwargs['headers'] = self.TVDb_Headers
        else:
            raise Exception('Invalid URL!')

        try:
            resp = requests.get(url, timeout=self.TIMEOUT, **kwargs)
        except Exception as error:
            self.__log.warning('Request failed: %s', error)
        else:
            if not resp.ok:
                kwargs.pop('headers', None)
                self.__log.warning(
                    'Request is not okay: %s; %s; %s',
                    url,
                    kwargs,
                    resp,
                )
                resp = self._close_request(resp)

        return resp

    def _close_request(self, resp):
        """
        Method to close Response object

        Arguments:
            resp   : Response object

        Keyword arguments:
            None

        Returns:
            None

        """

        try:
            resp.close()
        except:
            pass

    def _get_json(self, url, **kwargs):
        """
        Method to try to get JSON data from request

        Arguments:
            url (str): URL for request

        Keyword arguments:
            **kwargs: All accepted by requests.get()

        Returns:
            JSON data if success, else, None

        """

        json_data = None
        # Key to check
        key = 'append_to_response'
        if key in kwargs:
            # If value under key is tuple or list, join using comma
            if isinstance(kwargs[key], (list, tuple)):
                kwargs[key] = ','.join(kwargs[key])

        resp = self._get_request(url, **kwargs)
        if resp:
            try:
                json_data = resp.json()
            except Exception as error:
                self.__log.error('Failed to get JSON data : %s', error)
            resp = self._close_request(resp)
        return convert_date(json_data)
