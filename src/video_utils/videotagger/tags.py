"""
Lookup tables for tag names

Provides lookup tables for converting from MP4/MKV tags to the
conventions used internally in the package. Also provides
inverted lookup tables for converting from internal convention
to MP4/MKV tags.

"""


def freeform(tag):
    """
    Generate MP4 freeform tag

    Note from the mutagen package:
        The freeform ‘----‘ frames use a key in the format ‘----:mean:name’
        where ‘mean’ is usually ‘com.apple.iTunes’ and ‘name’ is a unique
        identifier for this frame. The value is a str, but is probably text
        that can be decoded as UTF-8. Multiple values per key are supported.

    """

    return f'----:com.apple.iTunes:{tag}'


def encoder(val):
    """Convert val to correct type for writting tags"""

    if isinstance(val, (tuple, list,)):
        return [i.encode() for i in val]
    if isinstance(val, str):
        return val.encode()
    return val


# A dictionary where keys are the starndard internal tags and values are
# MP4 tags. If a value is a tuple, then the first element is the tag and
# the seoncd is the encoder function required to get the value to the
# correct format
COMMON2MP4 = {
    'year': '\xa9day',
    'title': '\xa9nam',
    'seriesName': 'tvsh',
    'seasonNum': ('tvsn', lambda x: [x]),
    'episodeNum': ('tves', lambda x: [x]),
    'genre': '\xa9gen',
    'kind': ('stik', lambda x: [9] if x == 'movie' else [10]),
    'sPlot': 'desc',
    'lPlot': (freeform('LongDescription'), encoder,),
    'rating': (freeform('ContentRating'), encoder,),
    'prod': (freeform('Production Studio'), encoder,),
    'cast': (freeform('Actor'), encoder,),
    'dir': (freeform('Director'), encoder,),
    'wri': (freeform('Writer'), encoder,),
    'comment': '\xa9cmt',
    'cover': 'covr'
}

MP42COMMON = {
    val[0] if isinstance(val, tuple) else val: key
    for key, val in COMMON2MP4.items()
}

# A dictionary where keys are the standard internal tags and values are
# MKV tags. The first value of each tuple is the level of the tag and the
# second is the tag name
# See: https://matroska.org/technical/specs/tagging/index.html
COMMON2MKV = {
    'year': (50, 'DATE_RELEASED'),
    'title': (50, 'TITLE'),
    'seriesName': (70, 'TITLE'),
    'seasonNum': (60, 'PART_NUMBER'),
    'episodeNum': (50, 'PART_NUMBER'),
    'genre': (50, 'GENRE'),
    'kind': (50, 'CONTENT_TYPE'),
    'sPlot': (50, 'SUMMARY'),
    'lPlot': (50, 'SYNOPSIS'),
    'rating': (50, 'LAW_RATING'),
    'prod': (50, 'PRODUCION_STUDIO'),
    'cast': (50, 'ACTOR'),
    'dir': (50, 'DIRECTOR'),
    'wri': (50, 'WRITTEN_BY'),
    'comment': (50, 'COMMENT'),
    'cover': 'covr'
}

MKV2COMMON = {
    val: key for key, val in COMMON2MKV.items()
}
