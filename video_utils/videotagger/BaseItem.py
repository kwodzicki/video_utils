import logging

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

  def getExtra(self, *keys):
    if self.URL:
      extra = {}
      for key in keys:
        if (key not in self._data):
          URL  = '{}/{}'.format(self.URL, key)
          json = self._getJSON(URL)
          if json:
            extra[key] = json
      return extra
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
    if self.crew is not None:
      return [i['name'] for i in self.crew if i.job == 'Director']
    return ['']

  def _getWriters(self):
    if self.crew is not None:
      persons = []
      for person in self.crew:
        if person.job in ['Writer', 'Story', 'Screenplay']:
          persons.append( '{} ({})'.format( person.name, person.job ) )
      return persons
    return ['']

  def _getCast(self):
    if self.cast is not None:
      return [i.name for i in self.cast]
    return ['']

  def _getRating( self, **kwargs ):
    rating = ''
    country = kwargs.get('country', 'US')
    if 'release_dates' in self:
      for release in self.release_dates[country]:
        if release['type'] <= 3 and release['certification'] != '':
          rating = release['certification']
    elif self.isEpisode:
      rating = self.Series.rating
    return rating

  def _getGenre(self):
    if self.genres is not None:
      return [i['name'] for i in self.genres]
    return ['']

  def _getProdCompanies(self, **kwargs):
    if self.production_companies is not None:
      return [i['name'] for i in self.production_companies]
    return ['']

  def _getPlot(self, **kwargs):
    sPlot = lPlot = ''
    if self.overview is not None:
      if len(self.overview) < 240:
        sPlot = self.overview
      else:
        lPlot = self.overview
    return sPlot, lPlot 

  def _getCover( self, **kwargs ):
    if self.filename is not None:
      return self.filename
    elif self.poster_path is not None:
      return self.poster_path
    return ''

  def _episodeData(self, **kwargs):
    plots = self._getPlot()
    data  = {'year'       : str( self.air_date.year ),
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
             'cover'      : self._getCover()
    }
    return data

  def _movieData(self, **kwargs):
    title = '{} - {}'.format(self.title, self.version) if self.version else self.title
    plots = self._getPlot()
    data  = {'year'   : str( self.release_date.year ),
             'title'  : title,
             'sPlot'  : plots[0],
             'lPlot'  : plots[1],
             'cast'   : self._getCast(),
             'prod'   : self._getProdCompanies(), 
             'dir'    : self._getDirectors(), 
             'wri'    : self._getWriters(),
             'genre'  : self._getGenre(),
             'rating' : self._getRating( **kwargs ),
             'kind'   : 'movie',
             'cover'  : self._getCover()
    }
    return data

  def metadata(self, **kwargs):
    if self.isEpisode:
      return self._episodeData(**kwargs)
    elif self.isMovie:
      return self._movieData(**kwargs)
    return None

  def writeTags( self, file, **kwargs ):
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
