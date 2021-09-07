import logging

from datetime import datetime

from .API import BaseAPI
from .writers import writeTags

class BaseItem( BaseAPI ):
  """Extends the BaseAPI class for use in Episdode, Movie, Person, etc classes"""

  def __init__(self, *args, data = None, version = None, **kwargs):
    """
    Initialize the class

    Arguments:
      *args: Various, none used; passed to super()

    Keyword arguments:
      data (dict): Metadata to initialize class with
      version (str): Release version such as 'Extended Edition'; only relevant for movies
      **kwargs: arbitrary arguments

    """

    super().__init__(*args, **kwargs)                                                   # Initialize parent class(es)
    self.__log      = logging.getLogger(__name__)
    self._data      = data if isinstance(data, dict) else {}
    self._version   = version if isinstance(version, str) else ''
    self._isMovie   = False
    self._isSeries  = False
    self._isEpisode = False
    self._isPerson  = False
    self._tmdb      = False                                                             # Flag specifying if data from TMDb or TVDb
    self.URL        = None

  @property
  def isMovie(self):
    """bool: Identifies object as movie"""

    return self._isMovie

  @property
  def isSeries(self):
    """bool: Identifies object as TV series"""

    return self._isSeries

  @property
  def isEpisode(self):
    """bool: Identifies object as episode"""

    return self._isEpisode

  @property
  def isPerson(self):
    """bool: Identifies object as person"""

    return self._isPerson

  def __contains__(self, key):
    return key in self._data
  def __setitem__(self, key, item):
    self._data[key] = item
  def __getitem__(self, key):
    return self._data.get(key, None)
  def __getattr__(self, key):
    return self._data.get(key, None)

  def pop(self, key, *args):
    return self._data.pop(key, *args)
  def keys(self):
    return self._data.keys()
  def get(self, *args):
    return self._data.get(*args)

  def addComment(self, text):
    """
    Add a user comment to metadata information

    Arguments:
      text (str): Comment to add

    Keyword arguments:
      None

    Returns:
      None

    """

    self._data['comment'] = text

  def setVersion(self, version):
    """
    Set version of file (i.e., Extended Edition); only valid for movies.

    Arguments:
      version (str): Movie version

    Keyword arguments:
      None

    Returns:
      None

    """

    self._version = version

  def getExtra(self, *args):
    """
    Method to get extra information from an api 

    Arguments:
      *args (list): Keys for API call

    Keyword arguments:
      None

    Returns:
      dict: Extra information

    """

    if self.URL:                                                                        # If URL is defined
      extra = {}                                                                        # Initialize extra as empty dictionary
      for key in args:                                                                  # Iterate over each key
        if (key not in self._data):                                                     # If the key does NOT already exist in object
          URL  = '{}/{}'.format(self.URL, key)                                          # Build URL
          json = self._getJSON(URL)                                                     # Get JSON data
          if json:                                                                      # If data is valid
            extra[key] = json                                                           # Place data under key in extra
      return extra                                                                      # Return extra
    return None

  def _findExternalID( self, external ):
    """Find external tag"""

    tag = 'external_ids'                                                                # Tag of interest in the data
    if (tag in self._data):                                                             # If external_ids in the _data dictionary
      for key, item in self._data[tag].items():                                         # Iterate over key/value pairs in the external_ids dictionary
        if external in key:                                                             # If the requested external tag is in the key; e.g., 'imdb' is the tag of interest, but the actual tag is 'imdb_id', this will be True
          return item                                                                   # Return the item
    self.__log.debug('No external ID found for : {}!'.format(external) )                # Log some debug information
    return None
 
  def getID(self, external = None, **kwargs):
    """
    Method to get ID of object, or external ID of object

    Arguments:
      None

    Keyword arguments:
      external (str): Set to external ID key. Will return None if not found
      **kwargs: Various accepted, none used

    Returns:
      Return the item ID or None if not found

    """

    if external:                                                                        # If external keyword set
      fmt = '{}{{}}'.format( external )                                                 # Set up format for ID
      ID  = self._findExternalID( external )                                            # Try to get the ID
    else:                                                                               # Else, no external tag requested
      fmt = 'tmdb{}' if self._tmdb else 'tvdb{}'                                        # Set format base on _tmdb attribute
      ID  = self._data.get('id', None)                                                  # Get id from data or None if no id

    if ID:                                                                              # If ID
      return fmt.format( ID )                                                           # Return formatted id
    return ID                                                                           # Return ID

  def getIDPlex( self, **kwargs ):
    """
    Method to get ID of object or external ID of object in Plex standard format

    The Plex format for the ID is "{source-ID}" where source is tmdb, tvdb, or
    imdb and ID is the ID; imdb IDs begin with tt.

    Arguments:
      None

    Keyword arguments:
      **kwargs: All keywords accepted by getID()

    Returns:
      Return the item ID or None if not found

    """

    pid = self.getID( **kwargs )
    if pid is not None:
      return '{' + pid[:4] + '-' + pid[4:] + '}'

  def _getDirectors(self):
    """
    Method to get list of director(s)

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      List of srings containing director(s)

    """

    if self.crew is not None:
      return [i['name'] for i in self.crew if i.job == 'Director']
    return ['']

  def _getWriters(self):
    """
    Method to get list of writer(s)

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      List of srings containing writer(s)

    """

    if self.crew is not None:
      persons = []
      for person in self.crew:
        if person.job in ['Writer', 'Story', 'Screenplay']:
          persons.append( '{} ({})'.format( person.name, person.job ) )
      return persons
    return ['']

  def _getCast(self):
    """
    Method to get list of cast members

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      List of srings containing cast members

    """

    if self.cast is not None:
      return [i.name for i in self.cast]
    return ['']

  def _getRating( self, **kwargs ):
    """
    Method to iterate over release dates to extract rating

    Arguments:
      None

    Keyword arguments:
      country (str): The country of release to get rating from. Default is US.
      **kwargs: Other arguments are accepted but ignored for compatability
    Returns:
      String containing rating

    """

    rating = ''                                                                         # Default rating is emtpy string
    country = kwargs.get('country', 'US')                                               # Get country from kwargs, default to US
    if 'release_dates' in self:                                                         # If 'release_dates' key in self
      releases = self.release_dates.get(country, [])                                    # Try to get releases for country; return empty list on no key
      for release in releases:                                                          # Iterate over all releases
        if release['type'] <= 3 and release['certification'] != '':                     # If the release meets these criteria
          return release['certification']
          #rating = release['certification']                                             # Set the rating
    elif self.isEpisode:                                                                # Else, if object is episode
      return self.Series.rating                                                       # Get rating from series
      #rating = self.Series.rating                                                       # Get rating from series
    return rating                                                                       # Return rating

  def _getGenre(self):
    """
    Method to get list of genre(s) 

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      List of strings containing genre(s)

    """

    if self.genres is not None:
      return [i['name'] for i in self.genres]
    return ['']

  def _getProdCompanies(self, **kwargs):
    """
    Method to get list of production company(s) 

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      List of strings containing production company(s)

    """

    if self.production_companies is not None:
      return [i['name'] for i in self.production_companies]
    return ['']

  def _getPlot(self, **kwargs):
    """
    Get short and long plots 

    Arguments:
      None

    Keyword arguments:
      None

    Returns:
      tuple: Short (less than 240 characters) and long plots

    """

    sPlot = lPlot = ''
    if self.overview is not None:
      if len(self.overview) < 240:
        sPlot = self.overview
      else:
        lPlot = self.overview
    return sPlot, lPlot 

  def _getCover( self, **kwargs ):
    """
    Method to get URL of poster

    Arguments:
      None

    Keyword arguments:
      **kwargs

    Returns:
      URL to poster if exists, else empty string

    """

    if self.filename is not None:
      return self.filename
    elif self.poster_path is not None:
      return self.poster_path
    return ''

  def _episodeData(self, **kwargs):
    plots = self._getPlot()
    year  = str( self.air_date.year ) if isinstance(self.air_date, datetime) else ''
    data  = {'year'       : year,
             'title'      : self.title,
             'seriesName' : self.Series.title,
             'seasonNum'  : self.season_number, 
             'episodeNum' : self.episode_number,
             'sPlot'      : plots[0],
             'lPlot'      : plots[1],
             'cast'       : self._getCast(),
             'prod'       : self._getProdCompanies(), 
             'dir'        : self._getDirectors(), 
             'wri'        : self._getWriters(),
             'genre'      : self._getGenre(), 
             'rating'     : self._getRating( **kwargs ),
             'kind'       : 'episode',
             'cover'      : self._getCover(),
             'comment'    : self._data.get('comment', ''),
             'version'    : self._version
    }
    return data

  def _movieData(self, **kwargs):
    title = '{} - {}'.format(self.title, self._version) if self._version else self.title
    plots = self._getPlot()
    year  = str( self.release_date.year ) if isinstance(self.release_date, datetime) else ''
    data  = {'year'    : year, 
             'title'   : title,
             'sPlot'   : plots[0],
             'lPlot'   : plots[1],
             'cast'    : self._getCast(),
             'prod'    : self._getProdCompanies(), 
             'dir'     : self._getDirectors(), 
             'wri'     : self._getWriters(),
             'genre'   : self._getGenre(),
             'rating'  : self._getRating( **kwargs ),
             'kind'    : 'movie',
             'cover'   : self._getCover(),
             'comment' : self._data.get('comment', ''),
             'version' : self._version
    }
    return data

  def metadata(self, **kwargs):
    """
    Method to get metadata in internal, standard format

    Arguments:
      None

    Keyword arguments:
      **kwargs

    Returns:
      dict: Metadata in internal, standard format

    """

    if self.isEpisode:
      return self._episodeData(**kwargs)
    elif self.isMovie:
      return self._movieData(**kwargs)
    return None

  def writeTags( self, file, **kwargs ):
    """"
    Method to write metadata to file

    Arguments:
      file (str): Path to video file to write metadata to

    Keyword arguments:
      **kwargs

    Returns:
      bool: True if tags written, False otherwise

    """

    data = self.metadata( **kwargs )
    if data:
      return writeTags( file, data, **kwargs )      
    self.__log.error('Failed to get metadata')
    return False
