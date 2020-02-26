import logging

from .API import BaseAPI
from .writers import mp4Tags, mkvTags

'''
A note from the mutagen package:
The freeform ‘----‘ frames use a key in the format ‘----:mean:name’ where ‘mean’
is usually ‘com.apple.iTunes’ and ‘name’ is a unique identifier for this frame.
The value is a str, but is probably text that can be decoded as UTF-8. Multiple
values per key are supported.
'''
freeform = lambda x: '----:com.apple.iTunes:{}'.format( x );                                # Functio

MP4KEYS = {
  'year'       : '\xa9day',
  'title'      : '\xa9nam',
  'seriesName' : 'tvsh',
  'seasonNum'  : 'tvsn',
  'episodeNum' : 'tves',
  'genre'      : '\xa9gen',
  'kind'       : 'stik',
  'sPlot'      : 'desc',
  'lPlot'      : freeform('LongDescription'),
  'rating'     : freeform('ContentRating'),
  'prod'       : freeform('Production Studio'),
  'cast'       : freeform('Actor'),
  'dir'        : freeform('Director'),
  'wri'        : freeform('Writer'),
  'cover'      : 'covr'
}

MKVKEYS = {
  'year'       : (50, 'DATE_RELEASED'),
  'title'      : (50, 'TITLE'),
  'seriesName' : (70, 'TITLE'),
  'seasonNum'  : (60, 'PART_NUMBER'),
  'episodeNum' : (50, 'PART_NUMBER'),
  'genre'      : (50, 'GENRE'),
  'kind'       : (50, 'CONTENT_TYPE'),
  'sPlot'      : (50, 'SUMMARY'),
  'lPlot'      : (50, 'SYNOPSIS'),
  'rating'     : (50, 'LAW_RATING'), 
  'prod'       : (50, 'PRODUCION_STUDIO'),
  'cast'       : (50, 'ACTOR'),
  'dir'        : (50, 'DIRECTOR'),
  'wri'        : (50, 'WRITTEN_BY'),
  'cover'      : 'covr'
}

class BaseItem( BaseAPI ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
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
    return [i['name'].encode() for i in self.crew if i.job == 'Director']

  def _getWriters(self):
    persons = []
    for person in self.crew:
      if person.job in ['Writer', 'Story', 'Screenplay']:
        persons.append( '{} ({})'.format( person.name, person.job ) )
    return [p.encode() for p in persons]

  def _getRating( self, **kwargs ):
    rating = ''
    country = kwargs.get('country', 'US')
    if 'release_dates' in self:
      for release in self.release_dates[country]:
        if release['type'] <= 3 and release['certification'] != '':
          rating = release['certification']
    elif self.isEpisode:
      rating = self.Series.rating
    return rating.encode()

  def _getProdCompanies(self, **kwargs):
    if 'production_companies' in self:
      return [i['name'].encode() for i in self.production_companies]
    return ''

  def _getPlot(self, **kwargs):
    sPlot = lPlot = ''
    if 'overview' in self:
      if len(self.overview) < 240:
        sPlot = self.overview
      else:
        lPlot = self.overview
    return sPlot, lPlot 

  def _getCover( self, **kwargs ):
    if 'filename' in self:
      return self.filename
    elif 'poster_path' in self:
      return self.poster_path
    return ''

  def _episodeData(self, **kwargs):
    plots = self._getPlot()
    data  = {'year'       : str( self.air_date.year ),
             'title'      : self.title,
             'seriesName' : self.Series.title,
             'seasonNum'  : [self.season_number], 
             'episodeNum' : [self.episode_number],
             'sPlot'      : plots[0],
             'lPlot'      : plots[1],
             'cast'       : [i.name.encode() for i in self.cast],
             'prod'       : self._getProdCompanies(), 
             'dir'        : self._getDirectors(), 
             'wri'        : self._getWriters(),
             'genre'      : [i for i in self.Series.genre],
             'rating'     : self._getRating( **kwargs ),
             'kind'       : 'episode' if kwargs.get('MKV', False) else [10],
             'cover'      : self._getCover()
    }
    return data

  def _movieData(self, qualifier=None, **kwargs):
    title = '{} - {}'.format(self.title, qualifier) if qualifier else self.title
    plots = self._getPlot()
    data  = {'year'   : str( self.release_date.year ),
             'title'  : title,
             'sPlot'  : plots[0],
             'lPlot'  : plots[1],
             'cast'   : [i.name.encode() for i in self.cast],
             'prod'   : self._getProdCompanies(), 
             'dir'    : self._getDirectors(), 
             'wri'    : self._getWriters(),
             'genre'  : [i['name'].encode() for i in self.genres],
             'rating' : self._getRating( **kwargs ),
             'kind'   : 'movie' if kwargs.get('MKV', False) else [9],
             'cover'  : self._getCover()
    }
    return data

  def _metadata(self, **kwargs):
    if self.isEpisode:
      return self._episodeData(**kwargs)
    elif self.isMovie:
      return self._movieData(**kwargs)
    return None

  def writeTags( self, file, **kwargs ):
    if file.endswith('.mp4'):
      data = self._metadata(**kwargs)
      if data:
        keys = list( data.keys() )
        for key in keys:
          data[ MP4KEYS[key] ] = data.pop(key)
        return mp4Tags( file, metaData = data )
      return None
    elif file.endswith('.mkv'):
      kwargs['MKV'] = True
      data = self._metadata(**kwargs)
      if data:
        keys = list( data.keys() )
        for key in keys:
          data[ MKVKEYS[key] ] = data.pop(key)
        return mkvTags( file, metaData = data )
      return None
    else:
      self.log.error('Unsupported file type!')
      return False

  def toMKV(self, **kwargs):
    kwargs['MKV'] = True
    data = self._metadata(**kwargs)
    if data:
      keys = list( data.keys() )
      for key in keys:
        data[ MKVKEYS[key] ] = data.pop(key)
      return data 
    return None

  def toMP4(self, **kwargs):
    data = self._metadata(**kwargs)
    if data:
      keys = list( data.keys() )
      for key in keys:
        data[ MP4KEYS[key] ] = data.pop(key)
      return data 
    return None
