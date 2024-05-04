"""
Parsers for metadata from TVDb and TMDb

"""

import logging
import re
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

    if 'imdbId' in info:
        info['external_ids'] = {'imdb_id': info.pop('imdbId')}

    # work on credits
    credits_info = info.pop('credits', {})
    crew = []
    job = 'Director'
    key = 'director'
    if key in info:
        crew.append(
            {'name': info.pop(key), 'job': job}
        )

    key = 'directors'
    for name in info.pop(key, []):
        crew.append(
            {'name': name, 'job': job}
        )

    job = 'Writer'
    key = 'writers'
    for name in info.pop(key, []):
        crew.append(
            {'name': name, 'job': job}
        )

    if crew:
        credits_info['crew'] = crew

    guests = info.pop('guestStars', None)
    if guests:
        credits_info['guest_stars'] = [
            {'name': guest} for guest in guests
        ]

    if credits_info:
        info['credits'] = credits_info

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


def image_paths(info, **kwargs):
    """Build paths to poster/cover/banner/fanart images"""

    image_url = kwargs.get('imageURL', None)
    if image_url:
        image_keys = ['_path', 'poster', 'banner', 'fanart', 'filename']
        for key, val in info.items():
            if any(image in key for image in image_keys):
                if isinstance(val, (list, tuple)):
                    val = val[0]
                info[key] = image_url.format(val)
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
