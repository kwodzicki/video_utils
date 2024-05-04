"""
Classes for movie information

"""

import logging
import os

from .base_item import BaseItem
from .parsers import parse_info
from .utils import replace_chars

EXTRA_LOOKUP = {
    'behindthescenes': 'Behind The Scenes',
    'deleted': 'Deleted Scenes',
    'featurette': 'Featurettes',
    'interview': 'Interviews',
    'scene': 'Scenes',
    'short': 'Shorts',
    'trailer': 'Trailers',
    'other': 'Other',
}


def get_basename(
    title: str,
    year: int | None = None,
    version: str = '',
    ID: str = '',
    isExtra: bool = False,
    **kwargs,
) -> str:
    """
    Helper function for getting basename

    This function is used for generating basenames from both TMDbMovie
    and TVDbMovie so that title can be truncated to 50 characters, version
    truncated to 20 characters, and invalid characters can be replaced.

    Arguments:
        title (str): Movie title

    Keyword arguments:
        year (int): Release year of movie
        version (str): Movie version; e.g., Extended Edition, Unrated
        ID (str): Movie ID
        isExtra (bool) If set, then the title is an extra feature
        **kwargs: Passed to the
            :meth:`video_utils.videotagger.utils.replace_chars` function

    Returns:
        str: Movie base name

    """

    log = logging.getLogger(__name__)
    log.info('Getting basename')

    if isExtra:
        return '-'.join(version.split('-')[:-1])

    title, version, ID = replace_chars(title, version, ID, **kwargs)
    if version != '':
        version = f"{{{version}}}"

    if year:
        return f'{title:.50} ({year}).{version}.{ID}'
    return f'{title:.50}.{version}.{ID}'


class BaseMovie(BaseItem):
    """
    Base object for movie information from TMDb or TVDb

    Provides methods that are used in both TMDbMovie and TVDbMovie
    objects for cleaner code

    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the class

        Arguments:
            *args:

        Keyword arguments:
            **kwargs:

        """

        super().__init__(*args, **kwargs)
        self._isMovie = True

    def __str__(self):
        try:
            return f'{self.title} ({self.release_date.year})'
        except:
            return self.title

    def __repr__(self):
        return f'<{self.__class__.__name__} ID: {self.id}; Title: {self}>'

    def get_basename(self, **kwargs):
        """
        Get file name in Plex convention

        This method returns file name in Plex convetion for given movie
        based on movie title and release year. The movie version and database
        ID from whichever database the metadata were obtained is incluced.

        Example:

            >>> movie = Movie.TMDbMovie(435)
            >>> print(movie.get_basename())
            'The Day After Tomorrow (2004)..tmdb435'

            >>> movie = Movie.TMDbMovie(435)
            >>> movie.setVersion('Extended Edition')
            >>> print(movie.get_basename())
            'The Day After Tomorrow (2004).Extended Edition.tmdb435'

        Arguments:
            None

        Keyword arguments:
            **kwargs: Passed to replace_chars() function

        Returns:
            str: File nam in Plex convention

        """

        title = self.title.replace('.', '_')
        try:
            year = self.release_date.year
        except:
            year = None
        return get_basename(
            title,
            year,
            version=self._version,
            ID=self.getIDPlex(),
            isExtra=self.isExtra,
            **kwargs,
        )

    def get_dirname(self, root=''):
        """
        Get directory structure in Plex convention

        This method returns directory structure in Plex convetion for
        given movie based on movie title and release year.

        Example:

            >>> movie = Movie.TMDbMovie(435)
            >>> print(movie.get_dirname())
            'Movies/The Day After Tomorrow (2004)'

        Arguments:
            None

        Keyword arguments:
            root (str): Root directory, is prepended to path

        Returns:
            str: Directory structure in Plex convention

        """

        mdir = replace_chars(str(self))
        mid = self.getIDPlex()
        if mid is not None:
            mdir = f"{mdir} {mid}"
        mdir = os.path.join(root, 'Movies', mdir)
        if self.isExtra:
            mdir = os.path.join(mdir, EXTRA_LOOKUP[self.extra_type])
        return mdir


class TMDbMovie(BaseMovie):
    """Object for movie information from TMDb"""

    EXTRA = ['external_ids', 'credits', 'content_ratings', 'release_dates']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tmdb = True

        if not self._data:
            if len(args) == 0:
                raise Exception("Must input movie ID or used 'data' keyword")
            movie_id = args[0]
            if isinstance(movie_id, str):
                if 'tmdb' in movie_id:
                    movie_id = movie_id.replace('tmdb', '')
            self.URL = self.TMDb_URLMovie.format(movie_id)
            json = self._get_json(self.URL, append_to_response=self.EXTRA)
            if json:
                info = parse_info(json, imageURL=self.TMDb_URLImage)
                if info is not None:
                    self._data.update(info)
        else:
            self.URL = self.TMDb_URLMovie.format(self.id)
            json = self.getExtra(*self.EXTRA)
            if json:
                info = parse_info(json, imageURL=self.TMDb_URLImage)
                if info is not None:
                    self._data.update(info)


class TVDbMovie(BaseMovie):
    """Object for movie information from TVDb"""

    EXTRA = ['external_ids', 'credits', 'content_ratings']

    def __init__(self, *args, **kwargs):
        """
        Initialize the class

        Arguments:
            movie_id (str,int): TVDb movie ID. Can include 'tvdb' or
                just integer
            *args: Arbitrary arguments

        Keyword arguments:
            data (dict): User-defined metadata; if None entered,
                will be downloaded
            **kwargs: Arbitrary arguments

        """

        super().__init__(*args, **kwargs)
        self._tmdb = False

        if not self._data:
            if len(args) == 0:
                raise Exception("Must input movie ID or used 'data' keyword")
            movie_id = args[0]
            if isinstance(movie_id, str):
                if 'tvdb' in movie_id:
                    movie_id = movie_id.replace('tvdb', '')
            self.URL = self.TVDb_URLMovie.format(movie_id)
            json = self._get_json(self.URL)
            if json:
                info = parse_info(json)
                if info is not None:
                    self._data.update(info)
        else:
            self.URL = self.TVDb_URLMovie.format(self.id)
            json = self.getExtra(*self.EXTRA)
            if json:
                info = parse_info(json)
                if info is not None:
                    self._data.update(info)
