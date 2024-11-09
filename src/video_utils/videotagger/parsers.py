"""
Parsers for metadata from TVDb and TMDb

"""

import logging
import re

from .api import IMAGE_KEYS
from .person import Person

# Dictionary for converting episode ordering (aired or DVD) to standard format
TVDbOrder = {
    'airedOrder': {
        'airedSeason': 'season_number',
        'airedEpisodeNumber': 'episode_number',
    },
    'dvdOrder': {
        'dvdSeason': 'season_number',
        'dvdEpisodeNumber': 'episode_number',
    },
}

TVDb2Stnd = {
    'episodeName': 'name',
    'firstAired': 'air_date',
    'seriesName': 'name',
}

TMDb2Stnd = {'first_air_date': 'air_date'}

# Pattern to find any (xxx) data at and of string
PARENTH = re.compile(r'(\s+\([^\)]+\))$')


def standardize(info, **kwargs):
    """
    Standardize TVDb and TMDb to internal tag convention; similar to TMDb

    Arguments:
      info (dict): Data from API request

    Keyword Arguments:
      **kwargs

    Returns:
      dict: Data from input, but converted to standardized tags

    """

    tvdb = kwargs.get('TVDb', False)

    # Set the keys dictionary based on tvdb
    keys = TVDb2Stnd if tvdb else TMDb2Stnd
    info_keys = list(info.keys())
    for key in info_keys:
        if key in keys:
            info[keys[key]] = info.pop(key)

    if tvdb:
        key = 'dvdOrder' if kwargs.get('dvdOrder', False) else 'airedOrder'
        keys = TVDbOrder[key]
        for key in info_keys:
            if key in keys:
                info[keys[key]] = info.pop(key)
        return tvdb2tmdb(info)

    return info


def tvdb2tmdb(info):
    """
    Convert TVDb data to TMDb for consistent parsing

    Arguments:
        info (dict): Data from API request

    Keyword arguments:
        None.

    Returns:
        dict: Keys modified from TVDb to TMDb

    """

    # Work on name key
    key = 'name'
    if info.get(key, None) is None:
        return None

    info['title'] = info[key]
    key = 'title'
    if isinstance(info[key], (tuple, list)):
        # Found case where list had None(s), so use try statement
        try:
            info[key] = ' - '.join(info[key])
        except:
            return None
    # info[key] = PARENTH.sub('', info[key])

    # Convert external IDs
    external_ids = {}
    for remote_id in info.pop('remoteIds', []):
        idx = remote_id.get('id')
        source = remote_id.get('sourceName', '')
        if source == 'IMDB':
            external_ids['imdb_id'] = idx
        elif source == 'TheMovieDB.com':
            external_ids['tmdb_id'] = idx
    info['external_ids'] = external_ids

    # Convert credits
    info = characters_to_credits(info)

    # Rename companines
    info['production_companies'] = info.pop('companies', [])

    # Rename aired date
    air_date = info.pop('firstAired', None)
    if air_date:
        info['air_date'] = air_date

    # Convert season/episode numbers
    info['season_number'] = info.pop('seasonNumber', None)
    info['episode_number'] = info.pop('number', None)

    keys = ['seriesId', 'season_number', 'episode_number']
    for key in keys:
        if key in info and isinstance(info[key], (tuple, list)):
            if not all(i == info[key][0] for i in info[key]):
                raise Exception(f'Not all values in {key} match!')
            info[key] = info[key][0]

    return info


def parse_credits(info, **kwargs):
    """
    Function to parse credits into Person objects

    Arguments:
        info (dict): Data from an API call

    Keyword argumetns:
        None.

    Returns:
        dict: Updated dictionary

    """

    log = logging.getLogger(__name__)
    credits_info = info.pop('credits', None)
    if credits_info is None:
        return info

    log.debug('Found credits to parse')
    for key, values in credits_info.items():
        if not isinstance(values, list):
            continue

        if len(values) == 0:
            log.debug('Empty  : %s', key)
            continue

        log.debug('Parsing: %s', key)
        for i, val in enumerate(values):
            values[i] = Person(data=val)
        if (key != 'crew') and ('order' in values[0]):
            info[key] = sorted(values, key=lambda x: x.order)
        else:
            info[key] = values

    return info


def parse_releases(info, **kwargs):
    """Parse release information from TMDb"""

    releases = info.pop('release_dates', None)
    if releases:
        results = releases.pop('results', None)
        if results:
            for result in results:
                releases[result['iso_3166_1']] = result['release_dates']
            info['release_dates'] = releases
        return info

    for rating in info.pop('contentRatings', []):
        rating = rating.get('name', '')
        if rating != '':
            info['rating'] = rating
            return info

    return info


def image_paths(info, **kwargs):
    """Build paths to poster/cover/banner/fanart images"""

    image_url = kwargs.get('imageURL', None)
    if image_url:
        for key, val in info.items():
            if any(image in key for image in IMAGE_KEYS):
                if isinstance(val, (list, tuple)):
                    val = val[0]
                if not isinstance(val, str) or not val.startswith('http'):
                    val = image_url.format(val)
                info[key] = val
    return info


def characters_to_credits(info: dict) -> dict:
    """
    Convert characters to credits dict

    TVDb v4 API uses the 'characters' tag to store information for all
    cast and crew for a series (or episode). This method acts to convert
    that into the 'credits' dict as expected from the v3 API and TMDb for
    consistency.

    """

    chars = info.pop('characters', None)
    if chars is None:
        return {**info, 'credits': {}}

    crew = []
    cast = []
    guests = []
    for char in chars:
        ptype = char.pop('peopleType', '').upper()
        name = char.pop('personName', '')
        if name == '':
            continue

        char['name'] = name
        if ptype == 'ACTOR':
            cast.append(char)
        elif ptype == 'GUEST STAR':
            guests.append(char)
        elif ptype == 'WRITER':
            crew.append({**char, 'job': 'Writer'})
        elif ptype == 'DIRECTOR':
            crew.append({**char, 'job': 'Director'})
        elif 'PRODUCER' in ptype:
            crew.append({**char, 'job': 'Producer'})

    info['credits'] = {
        'cast': cast,
        'crew': crew,
        'guest_stars': guests,
    }
    return info


def parse_info(info, **kwargs):
    """
    Wrapper function for parsing/standardizing data

    Arguments:
        info (dict): Data from API request

    Keyword arguments:
        **kwargs

    Returns:
        dict: Data from input, but parsed to standardized format

    """

    info = standardize(info, **kwargs)
    if info is not None:
        info = parse_credits(info, **kwargs)
        info = parse_releases(info, **kwargs)
        info = image_paths(info, **kwargs)
    return info
