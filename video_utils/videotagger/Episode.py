import logging
import os

from .BaseItem import BaseItem
from .Series    import TMDbSeries, TVDbSeries
from .parsers import parseInfo
from .utils import replaceChars

SEFMT = 'S{:02d}E{:02d} - {}' 

def getBasename(seasonNum, episodeNum, title, ID = '', **kwargs):
  basename = SEFMT.format(seasonNum, episodeNum, title)
  basename = '{:.50}.{}'.format( basename, ID )
  return replaceChars( basename, **kwargs )

class BaseEpisode( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._isEpisode = True

  def __str__(self):
    return SEFMT.format( self.season_number, self.episode_number, self.title )

  def __repr__(self):
    return '<{} ID: {}; Title: {}>'.format( self.__class__.__name__, self.id, self )

  def getBasename(self, **kwargs):
    ID    = self.Series.getID()
    title = self.title.replace('.', '_')
    return getBasename( self.season_number, self.episode_number, title, ID, **kwargs )  

  def getDirname(self, root = ''):
    '''
    Keywords:
      root    : Root directory
    '''
    series = replaceChars( str(self.Series) ).replace('.', '_')
    season = 'Season {:02d}'.format( self.season_number ) 
    return os.path.join( root, 'TV Shows', series, season )

  def getID(self, **kwargs):
    ID = super().getID( **kwargs )
    if kwargs.get('external', None) is None:
      if isinstance(self, TMDbEpisode):
        return 'tmdb{}'.format( ID )
      else:
        return 'tvdb{}'.format( ID )
    return ID

class TMDbEpisode( BaseEpisode ):
  EXTRA = ['external_ids', 'credits']
  def __init__(self, *args, **kwargs):
    '''
    Inputs:
      series    : The series ID from themoviedb.com, OR a Series object. 
    Keywords:
      None.
    '''
    super().__init__(*args, **kwargs)
    if not self._data:
      if (len(args) < 3):
        raise Exception( "Must input series ID or object and season and episode number" )
      if isinstance( args[0], TMDbSeries):
        self.Series = args[0]
      else:
        self.Series = TMDbSeries( args[0] )

      self.URL = self.TMDb_URLEpisode.format( self.Series.id, *args[1:3] )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json:
        info = parseInfo(json, imageURL = self.TMDb_URLImage)
        if info is not None:
          self._data.update( info )
    else:
      self.URL = self.TMDb_URLEpisode.format( self.Series.id, self.season_number, self.episode_number )
      json = self.getExtra( *self.EXTRA )
      if json:
        info = parseInfo(json, imageURL = self.TMDb_URLImage) 
        if info is not None:
          self._data.update( info )
  
    self._data['title'] = self.name

class TVDbEpisode( BaseEpisode ):
  def __init__(self, *args, **kwargs):
    '''
    Inputs:
      series    : The series ID from themoviedb.com, OR a Series object. 
    Keywords:
      None.
    '''
    super().__init__(*args, **kwargs)
    self.KWARGS = {'TVDb' : True, 'imageURL' : self.TVDb_URLImage}
    if not self._data:
      if (len(args) < 3):
        raise Exception( "Must input series ID or object and season and episode number" )
      if isinstance( args[0], TVDbSeries):
        self.Series = args[0]
      else:
        self.Series = TVDbSeries( args[0] )

      self.URL = self.TVDb_URLEpisode.format( self.Series.URL, 'query' )
      json     = self._getJSON( self.URL, airedSeason=args[1], airedEpisode=args[2] )
      if json is not None and ('data' in json):
        if isinstance( json['data'], dict ):
          json = json['data']
        else:
          json = json['data'][0]

        actors = self._getJSON( self.Series.URL + '/actors' )
        if actors is not None and 'errors' not in actors:
          json['credits'] = {'cast' : actors['data']}
        info = parseInfo(json, **self.KWARGS)
        if info is not None: 
          self._data.update( info )

    #else:
    #  self.URL = self.TVDb_URLEpisode.format( self.Series.id, self.airedSeason, self.airedEpisodeNumber )
    #  json = self.getExtra( *self.EXTRA )
    #  if json:
    #    self._data.update( parseInfo(json, imageURL = self.TVDb_URLImage) )
  
    self._data['title'] = self.name
