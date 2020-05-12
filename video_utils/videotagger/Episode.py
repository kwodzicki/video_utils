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
    series = replaceChars( str(self.Series) )
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
    self.__log  = logging.getLogger(__name__)
    self.KWARGS = {'TVDb' : True, 'imageURL' : self.TVDb_URLImage}
    if not self._data:
      if (len(args) < 3):
        raise Exception( "Must input series ID or object and season and episode number" )
      if isinstance( args[0], TVDbSeries):
        self.Series = args[0]
      else:
        self.Series = TVDbSeries( args[0] )
      airedOrder = kwargs.get('airedOrder', False)                                      # Get aireOrder keyword; False is default

      self.URL = self.TVDb_URLEpisode.format( self.Series.URL, 'query' )                # Build base URL for getting episode information
      json     = None                                                                   # Default json to None
      if airedOrder is False:                                                           # If airedOrder is False
        json = self._getJSON( self.URL, dvdSeason=args[1], dvdEpisode=args[2] )         # Search using supplied season/episode as dvd season/episode
        if json is None:                                                                # If json is None, something broke
          self.__log.warning('TVDb search based on DVD order failed, falling back to aired order')
     
      if json is None:                                                                  # If JSON is None here, then either airedOrder was set OR dvdOrder search failed
        airedOrder = True
        json       = self._getJSON(self.URL, airedSeason=args[1], airedEpisode=args[2]) # Search using supplied season/episode as aired season/episode

      if json is not None and ('data' in json):                                         # If returned json is valid and has data key
        ref = json['data'][0]                                                           # Set ref to first element of data list
        if len(json['data']) > 1:                                                       # If more than one result in data list
          for key, val in ref.items():                                                  # Iterate over key/value pairs in reference dictionary
            if isinstance(val, tuple):                                                  # If the value is a tuple instance
              ref[key] = list(val)                                                      # Convert to list
            elif not isinstance(val, list):                                             # Else, if it is not a list
              ref[key] = [val]                                                          # Convert to list
          for extra in json['data'][1:]:                                                # Iterate over elements 1 to end of the result list
            for key in ref.keys():                                                      # Iterate over the keys in the reference dictionary
              extraVal = extra.get(key, None)                                           # Try to get value of key in the extra dictionary; return None as default
              if extraVal is not None:                                                  # If the extra value is NOT None
                if isinstance(extraVal, tuple):                                         # If value is tuple
                  extraVal = list(extraVal)                                             # Convert to list
                elif not isinstance(extraVal, list):                                    # Else, if not list
                  extraVal = [extraVal]                                                 # Convert to list
                ref[key] += extraVal                                                    # Add the extra value to the value in the reference dictionary
        json = ref                                                                      # Set json to reference dictionary
 
        actors = self._getJSON( self.Series.URL + '/actors' )
        if actors is not None and 'errors' not in actors:
          json['credits'] = {'cast' : actors['data']}
        info = parseInfo(json, airedOrder=airedOrder, **self.KWARGS)
        if info is not None: 
          self._data.update( info )

    #else:
    #  self.URL = self.TVDb_URLEpisode.format( self.Series.id, self.airedSeason, self.airedEpisodeNumber )
    #  json = self.getExtra( *self.EXTRA )
    #  if json:
    #    self._data.update( parseInfo(json, imageURL = self.TVDb_URLImage) )
  
    self._data['title'] = self.name
