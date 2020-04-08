import logging
import os

from .BaseItem import BaseItem
from .parsers import parseInfo
from .utils import replaceChars

def getBasename(title, year=None, version='', ID='', **kwargs):
  if year:
    basename = '{:.50} ({}).{:.20}.{}'.format( title, year, version, ID )
  else:
    basename = '{:.50}.{:.20}.{}'.format( title, version, ID )
  return replaceChars( basename, **kwargs )

class BaseMovie( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._isMovie = True
    self.version  = kwargs.get('version', '')

  def __str__(self):
    try:
      return '{} ({})'.format(self.title, self.release_date.year)
    except:
      return '{}'.format(self.title)

  def __repr__(self):
    return '<{} ID: {}; Title: {}>'.format( self.__class__.__name__, self.id, self )

  def getBasename(self, **kwargs):
    '''
    Purpose:
      Method to get base name for standardized file naming.
    Inputs:
      None.
    Keywords:
      Passed to replaceChars function
    Returns:
      Returns string of 'Title (year).Modifier.ID'
    '''
    title = self.title.replace('.', '_')
    try:
      year = self.release_date.year
    except:
      year = None
    return getBasename( title, year, self.version, self.getID(), **kwargs )

  def getDirname(self, root = ''):
    mdir = replaceChars( str(self) )
    return os.path.join( root, 'Movies', mdir )

  def getID(self, **kwargs):
    ID = super().getID( **kwargs ) 
    if kwargs.get('external', None) is None:
      if isinstance(self, TMDbMovie):
        return 'tmdb{}'.format( ID )
      else:
        return 'tvdb{}'.format( ID )
    return ID
 
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
  EXTRA = ['external_ids', 'credits', 'content_ratings']
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    
    if not self._data:
      if (len(args) == 0):
        raise Exception( "Must input movie ID or used 'data' keyword" )
      self.URL = self.TVDb_URLMovie.format( args[0] )
      json     = self._getJSON( self.URL )#, append_to_response = self.EXTRA )
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
