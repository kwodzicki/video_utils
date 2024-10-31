"""
Base API class for TVDb and TMDb

"""

import logging
import json
from urllib.parse import urlencode

import requests
import tvdb_v4_official as tvdb_api

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

    TVDb_URLBase = tvdb_api.Url().base_url.rstrip('/')
    TVDb_URLSearch = f'{TVDb_URLBase}/search'
    TVDb_URLMovie = f'{TVDb_URLBase}/movies/{{}}'
    TVDb_URLSeries = f'{TVDb_URLBase}/series/{{}}'
    TVDb_URLEpisode = '{}/episodes/{}'
    TVDb_URLImage = f'{TVDb_URLBase}/artwork/{{}}'

    TIMEOUT = 600.0

    def __init__(self, *args, **kwargs):
        """
        Arguments:
          *args: Various, None used

        Keywords arguments:
          **kwargs: Various, None used

        """

        self.__log = logging.getLogger(__name__)
        self._tvdb = None

    @property
    def tvdb(self):
        if self._tvdb is not None:
            return self._tvdb

        try:
            self._tvdb = tvdb_api.TVDB(
                getattr(KEYS, 'TVDb_API_KEY', ''),
                pin=getattr(KEYS, 'TVDb_API_PIN', ''),
            )
        except Exception as err:
            self.__log.error("Failed to log into TVDb: %s", err)
            return None

        return self._tvdb

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

        if self.TMDb_URLBase in url:
            return self._get_request_tmdb(url, params)

        if self.TVDb_URLBase in url:
            return self._get_request_tvdb(url, params)

        raise Exception('Invalid URL!')

    def _get_request_tmdb(self, url, params):

        kwargs = {'params': params}
        if 'api_key' not in kwargs['params']:
            if not KEYS.TMDb_API_KEY:
                raise Exception('TMDb API Key is not set!')
            kwargs['params']['api_key'] = KEYS.TMDb_API_KEY

        try:
            resp = requests.get(url, timeout=self.TIMEOUT, **kwargs)
        except Exception as error:
            self.__log.warning('Request failed: %s', error)
            return None

        if resp.ok:
            return resp

        kwargs.pop('headers', None)
        self.__log.warning(
            'Request is not okay: %s; %s; %s',
            url,
            kwargs,
            resp,
        )
        return self._close_request(resp)

    def _get_request_tvdb(self, url, params):

        url = url + "?" + urlencode(params)
        return self.tvdb.request.make_request(url)

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

        # Key to check
        key = 'append_to_response'
        if key in kwargs:
            # If value under key is tuple or list, join using comma
            if isinstance(kwargs[key], (list, tuple)):
                kwargs[key] = ','.join(kwargs[key])

        resp = self._get_request(url, **kwargs)
        if resp is None:
            return None

        if isinstance(resp, (list, dict)):
            json_data = resp
        else:
            try:
                json_data = resp.json()
            except Exception as error:
                self.__log.error('Failed to get JSON data : %s', error)
                return None
            finally:
                resp = self._close_request(resp)

        return convert_date(json_data)
