import logging

from .API import BaseAPI

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
