import logging

from .BaseItem import BaseItem
from .parsers import parseInfo

class BaseSeries( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._isSeries = True

  def __repr__(self):
    return '<{} ID: {}; Title: {}>'.format(self.__class__.__name__, self.id, self)

  def __str__(self):
    try:
      return '{} ({})'.format(self.title, self.air_date.year)
    except:
      return '{}'.format(self.title)

class TMDbSeries( BaseSeries ):
  EXTRA = ['external_ids', 'content_ratings']
  def __init__(self, *args, **kwargs):
    '''
    Inputs:
      seriesID  : The series ID from themoviedb.com, not need if data keyword is used
    Keywords:
      data      : Series data returned by a search
    '''
    super().__init__(*args, **kwargs)
    if not self._data:
      if (len(args) == 0):
        raise Exception( "Must input series ID or use 'data' keyword" )
      self.URL = self.TMDb_URLSeries.format( args[0] )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json:
        self._data.update( parseInfo( json, imageURL = self.TMDb_URLImage ) )
    else:
      self.URL = self.TMDb_URLSeries.format( self.id )
      json = self.getExtra( *self.EXTRA )
      if json:
        self._data.update( json )

    self._data['title'] = self.name


class TVDbSeries( BaseSeries ):
  def __init__(self, *args, **kwargs):
    '''
    Inputs:
      seriesID  : The series ID from themoviedb.com, not need if data keyword is used
    Keywords:
      data      : Series data returned by a search
    '''
    super().__init__(*args, **kwargs)
    self.KWARGS =  {'TVDb' : True, 'imageURL' : self.TVDb_URLImage}
    if not self._data:
      if (len(args) == 0):
        raise Exception( "Must input series ID or use 'data' keyword" )
      self.URL = self.TVDb_URLSeries.format( args[0] )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json and ('data' in json):
        self._data.update( parseInfo( json['data'], **self.KWARGS) )
    #else:
    #  self.URL = self.TVDb_URLSeries.format( self.id )
    #  json = self.getExtra( *self.EXTRA )
    #  if json:
    #    self._data.update( json )

    self._data['title'] = self.name
