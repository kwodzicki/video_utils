import logging
import os

from .BaseItem import BaseItem
from .parsers import parseInfo
from .Series    import TMDbSeries, TVDbSeries

class BaseEpisode( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._isEpisode = True

  def __repr__(self):
    return '<{} ID: {}; Title: S{:02d}E{:02d} - {}>'.format(
      self.__class__.__name__, self.id, self.season_number, self.episode_number, self.title
    )

  def __str__(self):
    return 'S{:02d}E{:02d} - {}'.format(
      self.season_number, self.episode_number, self.title
    )

  def getBasename(self):
    if isinstance(self, TMDbEpisode):
      fmt = 'tmdb{}'
    else:
      fmt = 'tvdb{}'
    return 'S{:02d}E{:02d} - {}.{}'.format(
      self.season_number, self.episode_number, self.title, fmt.format(self.Series.id)
    )

  def getDirname(self, root = ''):
    '''
    Keywords:
      root    : Root directory
    '''
    return os.path.join( root, 'TV Shows', 
      str( self.Series ), 'Season {:02d}'.format(self.season_number) )

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
        self._data.update( parseInfo(json, imageURL = self.TMDb_URLImage) )
    else:
      self.URL = self.TMDb_URLEpisode.format( self.Series.id, self.season_number, self.episode_number )
      json = self.getExtra( *self.EXTRA )
      if json:
        self._data.update( parseInfo(json, imageURL = self.TMDb_URLImage) )
  
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
      if json and ('data' in json):
        if isinstance( json['data'], dict ):
          json = json['data']
        else:
          json = json['data'][0]

        actors = self._getJSON( self.Series.URL + '/actors' )
        if ('errors' not in actors):
          json['credits'] = {'cast' : actors['data']}
        self._data.update( parseInfo(json, **self.KWARGS) )

    #else:
    #  self.URL = self.TVDb_URLEpisode.format( self.Series.id, self.airedSeason, self.airedEpisodeNumber )
    #  json = self.getExtra( *self.EXTRA )
    #  if json:
    #    self._data.update( parseInfo(json, imageURL = self.TVDb_URLImage) )
  
    self._data['title'] = self.name
