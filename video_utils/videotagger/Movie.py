import logging
import os

from .BaseItem import BaseItem
from .parsers import parseInfo
from .utils import replaceChars

class BaseMovie( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._isMovie = True

  def __str__(self):
    try:
      return '{} ({})'.format(self.title, self.release_date.year)
    except:
      return '{}'.format(self.title)

  def __repr__(self):
    return '<{} ID: {}; Title: {}>'.format( self.__class__.__name__, self.id, self )

  def getBasename(self, modifier = '', **kwargs):
    '''
    Purpose:
      Method to get base name for standardized file naming.
    Inputs:
      None.
    Keywords:
      modifier : Set to modifier string such as 'Director's Cut'
    Returns:
      Returns string of 'Title (year).Modifier.ID'
    '''
    fmt      = '{}.{}.tmdb{}' if isinstance(self, TMDbMovie) else '{}.{}.tvdb{}'
    basename = fmt.format(self, modifier, self.id)
    return replaceChars( basename, **kwargs )

  def getDirname(self, root = ''):
    mdir = replaceChars( str(self) )
    return os.path.join( root, 'Movies', mdir )

class TMDbMovie( BaseMovie ):
  EXTRA = ['external_ids', 'credits', 'content_ratings', 'release_dates']
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    
    if not self._data:
      if (len(args) == 0):
        raise Exception( "Must input movie ID or used 'data' keyword" )
      self.URL = self.TMDb_URLMovie.format( args[0] )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json:
        self._data.update( parseInfo( json, imageURL = self.TMDb_URLImage ) )      
    else:
      self.URL = self.TMDb_URLMovie.format( self.id )
      json = self.getExtra( *self.EXTRA )
      if json:
        self._data.update( parseInfo( json, imageURL = self.TMDb_URLImage ) )      

class TVDbMovie( BaseMovie ):
  EXTRA = ['external_ids', 'credits', 'content_ratings']
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    
    if not self._data:
      if (len(args) == 0):
        raise Exception( "Must input movie ID or used 'data' keyword" )
      self.URL = self.TVDb_URLMovie.format( args[0] )
      json     = self._getJSON( self.URL, append_to_response = self.EXTRA )
      if json:
        self._data.update( parseCredits( json ) )      
    else:
      self.URL = self.TVDb_URLMovie.format( self.id )
      json = self.getExtra( *self.EXTRA )
      if json:
        self._data.update( parseCredits( json ) )      
