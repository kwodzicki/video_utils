import logging
import os

from .BaseItem import BaseItem
from .parsers import parseInfo
from .utils import replaceChars

def getBasename(title, year=None, version='', ID='', **kwargs):
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
    **kwargs: Passed to the :meth:`video_utils.videotagger.utils.replaceChars` function

  Returns:
    str: Movie base name

  """

  title, version, ID = replaceChars( title, version, ID, **kwargs )
  if year:                                                                              # If year is valid
    return '{:.50} ({}).{:.20}.{}'.format( title, year, version, ID )               # Generate base name
  return '{:.50}.{:.20}.{}'.format( title, version, ID )                          # Generate base name without year

class BaseMovie( BaseItem ):
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

    super().__init__(*args, **kwargs)                                                   # Initialize parent class(es)
    self._isMovie = True                                                                # Set _isMovie flag to True

  def __str__(self):
    try:
      return '{} ({})'.format(self.title, self.release_date.year)
    except:
      return '{}'.format(self.title)

  def __repr__(self):
    return '<{} ID: {}; Title: {}>'.format( self.__class__.__name__, self.id, self )

  def getBasename(self, **kwargs):
    """
    Get file name in Plex convention

    This method returns file name in Plex convetion for given movie
    based on movie title and release year. The movie version and database
    ID from whichever database the metadata were obtained is incluced.

    Example:

        >>> movie = Movie.TMDbMovie(435)
        >>> print( movie.getBasename() )
        'The Day After Tomorrow (2004)..tmdb435'

        >>> movie = Movie.TMDbMovie(435)
        >>> movie.setVersion( 'Extended Edition' )
        >>> print( movie.getBasename() )
        'The Day After Tomorrow (2004).Extended Edition.tmdb435'

    Arguments:
      None

    Keyword arguments:
      **kwargs: Passed to replaceChars() function

    Returns:
      str: File nam in Plex convention

    """

    title = self.title.replace('.', '_')
    try:
      year = self.release_date.year
    except:
      year = None
    return getBasename( title, year, self._version, self.getIDPlex(), **kwargs )

  def getDirname(self, root = ''):
    """
    Get directory structure in Plex convention

    This method returns directory structure in Plex convetion for given movie
    based on movie title and release year.

    Example:

        >>> movie = Movie.TMDbMovie(435)
        >>> print( movie.getDirname() )
        'Movies/The Day After Tomorrow (2004)' 

    Arguments:
      None

    Keyword arguments:
      root (str): Root directory, is prepended to path

    Returns:
      str: Directory structure in Plex convention

    """
    mdir = replaceChars( str(self) )
    mid  = self.getIDPlex()
    if mid is not None:
      mdir = '{} {}'.format( mdir, mid )
    return os.path.join( root, 'Movies', mdir )

class TMDbMovie( BaseMovie ):
  """Object for movie information from TMDb"""

  EXTRA = ['external_ids', 'credits', 'content_ratings', 'release_dates']
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._tmdb = True

    if not self._data:                                                                  # If data is empty
      if (len(args) == 0):
        raise Exception( "Must input movie ID or used 'data' keyword" )
      movieID = args[0]
      if isinstance(movieID, str):
        if 'tmdb' in movieID:
          movieID = movieID.replace('tmdb', '')
      self.URL = self.TMDb_URLMovie.format( movieID )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json:
        info = parseInfo( json, imageURL = self.TMDb_URLImage )
        if info is not None: 
          self._data.update( info )      
    else:
      self.URL = self.TMDb_URLMovie.format( self.id )
      json = self.getExtra( *self.EXTRA )
      if json:
        info = parseInfo( json, imageURL = self.TMDb_URLImage )
        if info is not None: 
          self._data.update( info )      

class TVDbMovie( BaseMovie ):
  """Object for movie information from TVDb"""

  EXTRA = ['external_ids', 'credits', 'content_ratings']
  def __init__(self, *args, **kwargs):
    """
    Initialize the class

    Arguments:
      movieID (str,int): TVDb movie ID. Can include 'tvdb' or just integer
      *args: Arbitrary arguments

    Keyword arguments:
      data (dict): User-defined metadata; if None entered, will be downloaded
      **kwargs: Arbitrary arguments

    """

    super().__init__(*args, **kwargs)                                                   # Initialize parent class(es)
    self._tmdb = False                                                                  # Set _tmdb flag to False as this is TVDb

    if not self._data:                                                                  # If no _data
      if (len(args) == 0):
        raise Exception( "Must input movie ID or used 'data' keyword" )
      movieID = args[0]
      if isinstance(movieID, str):
        if 'tvdb' in movieID:
          movieID = movieID.replace('tvdb', '')
      self.URL = self.TVDb_URLMovie.format( movieID )
      json     = self._getJSON( self.URL )
      if json:
        info = parseInfo( json )
        if info is not None: 
          self._data.update( info )      
    else:
      self.URL = self.TVDb_URLMovie.format( self.id )
      json = self.getExtra( *self.EXTRA )
      if json:
        info = parseInfo( json )
        if info is not None: 
          self._data.update( info )      
