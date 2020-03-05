import logging

from .BaseItem import BaseItem

class Person( BaseItem ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if not self._data: 
      if (len(args) == 0):
        raise Exception( "Must input person ID  or use 'data' keyword")

    self._isPerson = True

  def __repr__(self):
    return '<Person id: {}; name: {}>'.format(self.id, self.name)
  def __str__(self):
    return self.name
