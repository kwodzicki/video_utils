"""
Classes for episode information

"""

import logging
import os

from .base_item import BaseItem
from .series    import TMDbSeries, TVDbSeries
from .parsers import parse_info
from .utils import replace_chars

SEFMT = 'S{:02d}E{:02d} - {}'

def get_basename(seasonNum, episodeNum, title, ID = '', **kwargs):
    """
    Helper function for getting basename

    This function is used for generating basenames from both TMDbEpisode
    and TVDbEpisode so that names can be truncated to 50 characters
    and invalid characters can be replaced

    Arguments:
        seasonNum (int): Episode season number
        episodeNum (int): Episode number
        title (str): Episode title

    Keyword arguments:
        ID (str): Series ID
        **kwargs: Passed to the :meth:`video_utils.videotagger.utils.replace_chars` function

    Returns:
        str: Episode base name

    """

    basename = SEFMT.format(seasonNum, episodeNum, title)
    basename, ID = replace_chars( basename, ID, **kwargs )
    return f'{basename:.50}.{ID}'

def to_list( arg ):
    """
    Convert variable to a list

    Arguments:
        arg (?) : convert argument to a list

    """

    if isinstance(arg, tuple):
        return list(arg)
    if not isinstance(arg, list):
        return [arg]
    return arg

class BaseEpisode( BaseItem ):
    """
    Base object for episode information from TMDb or TVDb

    Provides methods that are used in both TMDbEpisode and TVDbEpisode
    objects for cleaner code.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._isEpisode = True

    def __str__(self):
        return SEFMT.format( self.season_number, self.episode_number, self.title )

    def __repr__(self):
        return f'<{self.__class__.__name__} ID: {self.id}; Title: {self}>'

    def get_basename(self, **kwargs):
        """
        Get file name in semi-Plex convention

        This method returns file name in semi-Plex convention for
        the given episode based on season/episode number and name.
        The series ID from whichever database the metadata were
        obtained is included.
        Note that the series name is NOT included.

        Example:

            >>> ep = Episode.TVDbEpisode(269782, 1, 1)
            >>> print( ep.get_basename() )
            'S01E01 - Pilot.tvdb269782'

        Arguments:
            None

        Keyword arguments:
            **kwargs: Any accepted, all ignored

        Returns:
            str: File name in semi-Plex convention

        """

        ID    = self.Series.getIDPlex()
        title = self.title.replace('.', '_')
        return get_basename(
            self.season_number,
            self.episode_number,
            title,
            ID,
            **kwargs,
        )

    def get_dirname(self, root = ''):
        """
        Get directory structure in Plex convention

        This method returns directory structure in the Plex convention for
        the given episode based on series name and season.

        Example:

            >>> ep = Episode.TVDbEpisode(269782, 1, 1)
            >>> print( ep.get_dirname() )
            'TV Shows/Friends with Better Lives (2014)/Season 01'

        Arguments:
            None

        Keyword arguments:
            root (str): Root directory, is prepended to path

        Returns:
            str: Directory structure in Plex convention

        """

        series = replace_chars( str(self.Series) )
        season = f'Season {self.season_number:02d}'
        return os.path.join( root, 'TV Shows', series, season )

class TMDbEpisode( BaseEpisode ):
    """Object for episode information from TMDb"""

    EXTRA = ['external_ids', 'credits']
    def __init__(self, *args, **kwargs):
        """
        Arguments:
            seriesID (int, TMDbSeries): The series ID from themoviedb.com, OR a Series object. 
            seasonNum (int): Season number of episode
            episodeNum (int): Episode number of episode
 
        Keyword arguments:
            **kwargs: Various, none used

        """

        super().__init__(*args, **kwargs)

        if not self._data:
            if len(args) < 3:
                raise Exception( "Must input series ID or object and season and episode number" )
            if isinstance( args[0], TMDbSeries):
                self.Series = args[0]
            else:
                self.Series = TMDbSeries( args[0] )

            self.URL = self.TMDb_URLEpisode.format( self.Series.id, *args[1:3] )
            json     = self._get_json( self.URL, append_to_response = self.EXTRA )
            if json:
                info = parse_info(json, imageURL = self.TMDb_URLImage)
                if info is not None:
                    self._data.update( info )
        else:
            self.URL = self.TMDb_URLEpisode.format(
                self.Series.id,
                self.season_number,
                self.episode_number,
            )
            json = self.getExtra( *self.EXTRA )
            if json:
                info = parse_info(json, imageURL = self.TMDb_URLImage)
                if info is not None:
                    self._data.update( info )

class TVDbEpisode( BaseEpisode ):
    """Object for episode information from TVDb"""

    def __init__(self, *args, **kwargs):
        """
        Arguments:
            seriesID (int, TVDbSeries): The series ID from themoviedb.com, OR a Series object. 
            seasonNum (int): Season number of episode
            episodeNum (int): Episode number of episode
 
        Keyword arguments:
            dvdOrder (bool): Set to use dvdOrder from TVDb; default is airedOrder
            **kwargs: Various, none used

        """

        super().__init__(*args, **kwargs)
        self.__log  = logging.getLogger(__name__)
        extra_kws = {
            'TVDb'     : True,
            'imageURL' : self.TVDb_URLImage,
        }

        if self._data:
            return

        if len(args) < 3:
            raise Exception( "Must input series ID or object and season and episode number" )

        self.Series = (
            args[0]
            if isinstance( args[0], TVDbSeries) else
            TVDbSeries( args[0] )
        )

        dvdOrder = kwargs.get('dvdOrder', False)
        self.URL = self.TVDb_URLEpisode.format( self.Series.URL, 'query' )
        json     = None
        if dvdOrder:
            # Search using supplied season/episode as dvd season/episode
            json = self._get_json( self.URL, dvdSeason=args[1], dvdEpisode=args[2] )
            if json is None:
                self.__log.warning(
                    'TVDb search based on DVD order failed, falling back to aired order'
                )

        if json is None:
            dvdOrder = False
            json     = self._get_json(self.URL, airedSeason=args[1], airedEpisode=args[2])

        if (json is None) or ('data' not in json):
            return

        # Set ref to first element of data list
        ref = json['data'][0]
        # If more than one result in data list
        if len(json['data']) > 1:
            ref = {key : to_list(val) for key, val in ref.items()}

            for extra in json['data'][1:]:
                for key in ref.keys():
                    extra_val = extra.get(key, None)
                    if extra_val is None:
                        continue
                    ref[key] += to_list( extra_val )
        json = ref

        actors = self._get_json( self.Series.URL + '/actors' )
        if actors is not None and 'errors' not in actors:
            json['credits'] = {'cast' : actors['data']}
        info = parse_info(json, dvdOrder = dvdOrder, **extra_kws)
        if info is not None:
            self._data.update( info )
