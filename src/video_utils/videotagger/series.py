"""
Classes for Series objects

"""

from .base_item import BaseItem
from .parsers import parse_info


class BaseSeries(BaseItem):
    """
    Base class for TMDb and TVDb Series

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._isSeries = True

    def __repr__(self):
        return f'<{self.__class__.__name__} ID: {self.id}; Title: {self}>'

    def __str__(self):
        try:
            out = f'{self.title} ({self.air_date.year})'
        except:
            out = self.title

        pid = self.getIDPlex()
        if pid is not None:
            return f'{out} {pid}'
        return out


class TMDbSeries(BaseSeries):
    """
    For TMDb Series objects

    """

    EXTRA = ['external_ids', 'content_ratings']

    def __init__(self, *args, **kwargs):
        """
        Arguments:
            seriesID: The series ID from themoviedb.com,
                not need if data keyword is used

        Keyword arguments:
            data: Series data returned by a search

        """

        super().__init__(*args, **kwargs)
        self._tmdb = True

        if self._data:
            self.URL = self.TMDb_URLSeries.format(self.id)
            json = self.getExtra(*self.EXTRA)
            if json:
                self._data.update(json)
            return

        if len(args) == 0:
            raise Exception("Must input series ID or use 'data' keyword")
        seriesID = args[0]
        if isinstance(seriesID, str):
            if not seriesID.startswith('tmdb'):
                raise Exception("TMDb series ID must start with 'tmdb'")
            seriesID = seriesID.replace('tmdb', '')
        self.URL = self.TMDb_URLSeries.format(seriesID)
        json = self._get_json(self.URL, append_to_response=self.EXTRA)
        if not json:
            return

        info = parse_info(json, imageURL=self.TMDb_URLImage)
        if info is not None:
            self._data.update(info)


class TVDbSeries(BaseSeries):
    """
    For TVDb Series objects

    """

    def __init__(self, *args, **kwargs):
        """
        Arguments:
            seriesID : The series ID from themoviedb.com,
                not need if data keyword is used

        Keyword arguments:
            data: Series data returned by a search

        """

        super().__init__(*args, **kwargs)
        self._tmdb = False
        self.KWARGS = {'TVDb': True, 'imageURL': self.TVDb_URLImage}

        if len(self._data) != 0:
            return

        if len(args) == 0:
            raise Exception("Must input series ID or use 'data' keyword")

        seriesID = args[0]
        if isinstance(seriesID, str):
            if not seriesID.startswith('tvdb'):
                raise Exception("TVDb series ID must start with 'tvdb'")
            seriesID = seriesID.replace('tvdb', '')

        self.URL = self.TVDb_URLSeries.format(seriesID)
        json = self._get_json(f"{self.URL}/extended", short=False)
        if not isinstance(json, dict):
            return

        info = parse_info(json, **self.KWARGS)
        if info is None:
            return

        self._data.update(
            self.sort_series(info)
        )

    @staticmethod
    def sort_series(info: dict, key: str = 'seasons') -> dict:

        if key not in info:
            return info

        nseasons = 0
        seasons = {}
        for ss in info[key]:
            ss_type = ss.get('type', {}).get('name', '')
            if ss_type not in seasons:
                seasons[ss_type] = [ss]
            else:
                seasons[ss_type].append(ss)

        for ss in seasons.values():
            if len(ss) > nseasons:
                nseasons = len(ss)

        seasons['max'] = nseasons
        info[key] = seasons

        return info
