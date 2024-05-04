"""
Class for metadata about person

"""

from .base_item import BaseItem


class Person(BaseItem):
    """
    Class for person metadata

    Used for actors, directors, etc.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self._data:
            if len(args) == 0:
                raise Exception("Must input person ID  or use 'data' keyword")

        self._isPerson = True

    def __repr__(self):
        return f'<Person id: {self.id}; name: {self.name}>'

    def __str__(self):
        return self.name
