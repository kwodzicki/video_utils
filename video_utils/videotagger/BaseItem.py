import logging

from datetime import datetime

from .API import BaseAPI
from .writers import mp4Tagger, mkvTagger

'''
A note from the mutagen package:
The freeform ‘----‘ frames use a key in the format ‘----:mean:name’ where ‘mean’
is usually ‘com.apple.iTunes’ and ‘name’ is a unique identifier for this frame.
The value is a str, but is probably text that can be decoded as UTF-8. Multiple
values per key are supported.
'''

class BaseItem( BaseAPI ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__log      = logging.getLogger(__name__)
    self._data      = kwargs.get('data', {})
    self._version   = kwargs.get('version', '')
    self._isMovie   = False
    self._isSeries  = False
    self._isEpisode = False
    self._isPerson  = False
    self.URL        = None
 
  @property
  def isMovie(self):
    return self._isMovie
  @property
  def isSeries(self):
    return self._isSeries
  @property
  def isEpisode(self):
    return self._isEpisode
  @property
  def isPerson(self):
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
    self._data['comment'] = text

  def setVersion(self, version):
    self._version = version

  def getExtra(self, *keys):
    '''
    Purpose:
      Method to get extra information from an api 
    Inputs:
      List of keys for API call
    Keywords:
      None.
    Returns:
      Dictionary of extra information
    '''
    if self.URL:                                                                        # If URL is defined
      extra = {}                                                                        # Initialize extra as empty dictionary
      for key in keys:                                                                  # Iterate over each key
        if (key not in self._data):                                                     # If the key does NOT already exist in object
          URL  = '{}/{}'.format(self.URL, key)                                          # Build URL
          json = self._getJSON(URL)                                                     # Get JSON data
          if json:                                                                      # If data is valid
            extra[key] = json                                                           # Place data under key in extra
      return extra                                                                      # Return extra
    return None

  def getID(self, external = None):
    '''
    Purpose:
      Method to get ID of object, or external ID of object
    Inputs:
      None.
    Keywords:
      external : Set to external ID key. Will return None if
                  not found
    Returns:
      Return the item ID or None if not found
    '''
    if external:
      if ('external_ids' in self._data):
        return self._data['external_ids'].get(external, None)
      else:
        self.__log.debug('No external IDs found!')
      pass

    return self._data.get('id', None)

  def _getDirectors(self):
    '''
    Purpose:
      Method to get list of director(s)
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      List of srings containing director(s)
    '''
    if self.crew is not None:
      return [i['name'] for i in self.crew if i.job == 'Director']
    return ['']

  def _getWriters(self):
    '''
    Purpose:
      Method to get list of writer(s)
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      List of srings containing writer(s)
    '''
    if self.crew is not None:
      persons = []
      for person in self.crew:
        if person.job in ['Writer', 'Story', 'Screenplay']:
          persons.append( '{} ({})'.format( person.name, person.job ) )
      return persons
    return ['']

  def _getCast(self):
    '''
    Purpose:
      Method to get list of cast members
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      List of srings containing cast members
    '''
    if self.cast is not None:
      return [i.name for i in self.cast]
    return ['']

  def _getRating( self, **kwargs ):
    '''
    Purpose:
      Method to iterate over release dates to extract rating
    Inputs:
      None.
    Keywords:
      country  : The country of release to get rating from.
                  Default is US
    Returns:
      String containing rating
    '''
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
    '''
    Purpose:
      Method to get list of genre(s) 
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      List of strings containing genre(s)
    '''
    if self.genres is not None:
      return [i['name'] for i in self.genres]
    return ['']

  def _getProdCompanies(self, **kwargs):
    '''
    Purpose:
      Method to get list of production company(s) 
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      List of strings containing production company(s)
    '''
    if self.production_companies is not None:
      return [i['name'] for i in self.production_companies]
    return ['']

  def _getPlot(self, **kwargs):
    '''
    Purpose:
      Method to get short and long plots 
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      Tuple containg short (less than 240 characters) and long plots
    '''
    sPlot = lPlot = ''
    if self.overview is not None:
      if len(self.overview) < 240:
        sPlot = self.overview
      else:
        lPlot = self.overview
    return sPlot, lPlot 

  def _getCover( self, **kwargs ):
    '''
    Purpose:
      Method to get URL of poster
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      URL to poster if exists, else empty string
    '''
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
    '''
    Purpose:
      Method to get metadata in internal, standard format
    Inputs:
      None.
    Keywords:
      Various.
    Returns:
      Dictionary of metadata in internal, standard format
    '''
    if self.isEpisode:
      return self._episodeData(**kwargs)
    elif self.isMovie:
      return self._movieData(**kwargs)
    return None

  def writeTags( self, file, **kwargs ):
    '''
    Purpose:
      Method to write metadata to file
    Inputs:
      file   : Path to video file to write metadata to
    Keywords:
      Various.
    Returns:
      True if tags written, False otherwise
    '''
    data = self.metadata( **kwargs )
    if data:
      if file.endswith('.mp4'):
        return mp4Tagger( file, metaData = data )
      elif file.endswith('.mkv'):
        return mkvTagger( file, metaData = data )
      else:
        self.__log.error('Unsupported file type : {}'.format(file))
        return False
    self.__log.error('Failed to get metadata')
    return False
