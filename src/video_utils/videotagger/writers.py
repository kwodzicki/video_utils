"""
To write metadata to MP4/MKV files

"""

import logging
import os
import sys
from xml.etree import ElementTree as ET
from subprocess import run, STDOUT, DEVNULL

from mutagen import mp4

from ..utils.check_cli import check_cli
from .utils import download_cover
from .tags import COMMON2MP4, COMMON2MKV

try:
    MKVPROPEDIT = check_cli( 'mkvpropedit' )
except:
    logging.getLogger(__name__).error('mkvpropedit NOT installed')
    MKVPROPEDIT = None

TVDB_ATTRIBUTION = (
    'TV and/or Movie information and images are provided by TheTVDB.com, '
    'but we are not endorsed or certified by TheTVDB.com or its affiliates. '
    'See website at https://thetvdb.com/.'
)
TMDB_ATTRIBUTION = (
    'TV and/or Movie information and images are provided by themoviedb.com (TMDb), '
    'but we are not endorsed or certified by TMDb or its affiliates. '
    'See website at https://themoviedb.org/.'
)

def get_version(metadata):
    """
    Extract version from meta data

    Arguments:
        metadata (dict) : Metadata for file

    Returns:
        str : The version of the file

    """

    version = metadata.pop('version', '').split('-')
    if (len(version) > 1) and (version[0] == 'edition'):
        return '-'.join(version[1:])
    return ''

def _update_comment( comment ):
    """
    Append TVDb and TMDb attribution information to comment

    Arguments:
        comment : str, list, or tuple containing comment from user

    Keyword arguments:
        None

    Returns:
        str: TVDb and TMDb attribution appended to input comment.

    """

    # If comment is tuple, convert to list
    if isinstance(comment, tuple):
        comment = list( comment )
    # If not list, convert to list
    elif not isinstance(comment, list):
        comment = [comment]

    # Iterate over TVDb and TMDb attributions
    for attrib in [ TVDB_ATTRIBUTION, TMDB_ATTRIBUTION ]:
        # If TVDb attribution not in comment, add it
        if not any( attrib in c for c in comment ):
            comment.append( attrib )

    # Join comment list on space and remove leading/trailing white space and return
    return ' '.join( comment ).strip()


########################################################################
def to_mp4( metadata ):
    """
    Convert internal tags to MP4 tags

    Arguments:
        metadata (dict): Metadata returned by a TVDb or TMDb movie or episde object

    Keyword arguments:
        None.

    Returns:
        dict: ictionary with valid MP4 tags as keys and correctly encoded values

    """

    # Get list of all keys currently in dictioanry
    keys = list( metadata.keys() )
    for key in keys:
        # Get value in key; poped off so no longer exists in dict
        val     = metadata.pop( key )
        # Get key_func value from MP4KEYS; default to None
        key_func = COMMON2MP4.get( key, None )
        if not key_func:
            continue

        # If key_func is a tuple
        if isinstance( key_func, tuple ):
            key = key_func[0]
            val = key_func[1]( val )
        else:
            key = key_func

        # Write encoded data under new key back into metadata
        metadata[key] = val

    return metadata

########################################################################
def to_mkv( metadata ):
    """
    Convert internal tags to MKV tags

    Arguments:
        metadata (dict): Metadata returned by a TVDb or TMDb movie or episde object

    Keyword arguments:
        None.

    Returns:
        dict: Dictionary with valid MKV tag level and tags as keys

    """

    # Get list of keys currently in dictionary
    keys = list( metadata.keys() )
    for key in keys:
        # Get value in key; popped off so no longer exists in dict
        val = metadata.pop(key)

        # If key exists in MKVKEYS,  Write data udner new key back into metadata
        if key in COMMON2MKV:
            metadata[ COMMON2MKV[key] ] = val

    return metadata

################################################################################
def mp4_tagger( fpath, metadata ):
    """
    Parse information from the IMDbPY API and write Tag data to MP4 files.

    Arguments:
        fpath (str): Full path of file to write metadata to.
        metadata (dict): Dictionary of meta data where keys are internal
            metadata keys and values are metadata values

    Keyword arguments:
        None

    Returns:
        int: Returns following values based on completion.
            -  0 : Completed successfully.
            -  1 : Input was NOT and MP4
            -  2 : IMDb ID was not valid
            -  3 : Failed to download information from IMDb AND themoviedb.org
            -  4 : Writing tags is NOT possible
            -  5 :  Failed when trying to remove tags from file.
            -  6 : Failed when trying to write tags to file.
            - 10 : IMDbPY not installed AND getTMDb_Info failed to import
            - 11 : File is too large

    """

    log = logging.getLogger(__name__)
    log.debug( 'Testing file is MP4' )

    # If the input file does NOT end in '.mp4'
    if not fpath.endswith('.mp4'):
        log.error('Input file is NOT an MP4!!!')
        return 1

    log.debug( 'Testing file too large' )
    # If the file size is larger than the supported maximum size
    if os.stat(fpath).st_size > sys.maxsize:
        log.error('Input file is too large!')
        return 11

    version = get_version( metadata )
    comment = _update_comment( metadata.get('comment',   '') )
    metadata.update( {'comment' : comment } )
    metadata  = to_mp4(metadata)
    if len(metadata) == 0:
        log.warning('No metadata, cannot write tags')
        return 3

    log.debug('Loading file using mutagen.mp4.MP4')
    # Initialize mutagen MP4 handler
    handle = mp4.MP4(fpath)

    log.debug('Attempting to add tag block to file')
    try:
        handle.add_tags()
    except mp4.error as error:
        # If the error is that the tag block already exists
        if 'already exists' not in str(error):
            log.error('Could NOT add tags to file!')
            return 4
        log.debug('MP4 tags already exist in file.')

    # Try to remove all old tags.
    try:
        handle.delete()
    except mp4.error as error:
        log.error( str(error) )
        return 5

    log.debug('Setting basic inforamtion')
    for key, val in metadata.items():
        if key == 'covr' and val != '':
            fmt  = (
                mp4.AtomDataType.PNG
                if val.endswith('png') else
                mp4.AtomDataType.JPEG
            )
            if os.path.isfile( val ):
                with open(val, 'rb') as fid:
                    data = fid.read()
            else:
                _, data = download_cover( fpath, val, text = version )

            if data is None:
                continue
            val = [ mp4.MP4Cover( data, fmt ) ]

        try:
            handle[key] = val
        except:
            log.warning( 'Failed to write metadata for: %s', key )

    log.debug('Saving tags to file')
    try:
        handle.save()
    except:
        log.error('Failed to save tags to file!')
        return 6
    return 0

def delete_attachments( fpath, nremove = 10 ):
    """
    Delete a bunch of attachments in an MKV file

    Arguments:
        fpath (str): Full path to file

    Keywords:
        nremove (int): Number of attachments to try to delete

    Returns:
        None

    """

    if not MKVPROPEDIT:
        return

    cmd  = [MKVPROPEDIT, fpath]
    for i in range(nremove):
        cmd += ['--delete-attachment', str(i)]
    _ = run( cmd, stdout=DEVNULL, stderr=STDOUT, check=False)

################################################################################
def add_target( ele, level ):
    """
    Add a target level to the XML file from MKV tagging

    Arguments:
        ele   : Element to add tag to
        level : Level of the tag

    Keyword arguments:
        None.

    Returns:
        An ElementTree SubElement instance

    """

    # Create subelement named Tag
    tags = ET.SubElement(ele, 'Tag')
    # Add subelement named Targets to Tag element
    targ = ET.SubElement(tags, 'Targets')
    # Set the TargetTypeValue text
    ET.SubElement(targ, 'TargetTypeValue').text = str(level)
    return tags

################################################################################
def add_tag( ele, key, val ):
    """
    Add a tag to XML element for MKV tagging 

    Arguments:
        ele   : Element to add tag to
        key   : Tag name to add
        val   : Value of the tag

    Keyword arguments:
        None.

    Returns:
        None

    """

    # If val is an iterable type, convert to comma seperated string
    if isinstance(val, (list,tuple,)):
        val = ','.join(map(str, val))
    # Else, if not a str instance, convert to string
    elif not isinstance(val, str):
        val = str(val)

    # Add a new subelement to ele
    simple = ET.SubElement(ele, 'Simple')
    ET.SubElement(simple, 'Name').text   = key# Set element Name to key
    ET.SubElement(simple, 'String').text = val# Set element string to val

def mkv_tagger( fpath, metadata ):
    """
    Parse information from the IMDbPY API and write Tag data to MP4 files.

    Arguments:
        fpath (str): Full path of file to write metadata to.
        metadata (dict): Meta data where keys are internal metadata keys
            and values are metadata values

    Keyword arguments:
        None.

    Returns:
        int: Returns following values based on completion.
            -  0 : Completed successfully.
            -  1 : Input was NOT and MKV
            -  2 : IMDb ID was not valid
            -  3 : Failed to download information from IMDb AND themoviedb.org
            -  4 : Writing tags is NOT possible
            -  5 :    Failed when trying to remove tags from file.
            -  6 : Failed when trying to write tags to file.
            - 10 : IMDbPY not installed AND getTMDb_Info failed to import
            - 11 : File is too large.

    """

    log = logging.getLogger(__name__)
    if not MKVPROPEDIT:
        log.warning( 'mkvpropedit not installed' )
        return 4

    log.debug( 'Testing file is MKV' )
    # If the input file does NOT end in '.mp4'
    if not fpath.endswith('.mkv'):
        log.error('Input file is NOT an MKV!!!')
        return 1

    log.debug( 'Testing file too large' )
    # If the file size is larger than the supported maximum size
    if os.stat(fpath).st_size > sys.maxsize:
        log.error('Input file is too large!')
        return 11

    version = get_version( metadata )
    comment = _update_comment( metadata.get('comment',   '') )
    metadata.update( {'comment' : comment } )
    metadata  = to_mkv( metadata )

    if len(metadata) == 0:
        log.warning('No metadata, cannot write tags')
        return 3

    # Get the directory and baseanem of the file
    file_dir, _ = os.path.split( fpath )
    xml_file    = os.path.join( file_dir, 'tags.xml' )

    log.debug('Setting basic inforamtion')
    # Top-level of XML tree and dict for storing XML elements
    top, tags = ET.Element('Tags'), {}

    cover_file = None
    # Iterate over all key/value pairs in metadata dictionary
    for key, val in metadata.items():
        if key == 'covr':
            if os.path.isfile( val ):
                cover_file = val
            else:
                cover_file, _ = download_cover( fpath, val, text = version )
            continue

        # Get TargetTypeValue and tag from the key tuple
        target_type_value, tag = key
        if target_type_value not in tags:
            # Add it using the add_target function
            tags[target_type_value] = add_target( top, target_type_value )
        # Add the tag/value to the target
        add_tag( tags[target_type_value], tag, val )

    # Write xml data to file
    ET.ElementTree(top).write( xml_file )

    cmd = [MKVPROPEDIT, fpath, '-t', f'all:{xml_file}']

    # If the 'full-size cover url' is in the metadata
    if cover_file and os.path.isfile( cover_file ):
        # Delete any existing attachments
        delete_attachments( fpath )
        cmd.extend(
            ['--attachment-name', 'Poster', '--add-attachment',  cover_file]
        )

    log.debug('Saving tags to file')

    proc = run(cmd, stdout = DEVNULL, stderr = STDOUT, check=False)

    try:
        os.remove( xml_file )
    except:
        pass

    if proc.returncode != 0:
        log.error('Failed to save tags to file!')
        return 6

    return 0

########################################################################
def write_tags( fpath, metadata, **kwargs ):
    """
    Wrapper for mp4_tagger and mkv_tagger

    Arguments:
        fpath (str): Full path of file to write tags to
        metadata (dict): Dictionary with tag/values to write

    Keyword argumetns:
        **kwargs : Silently ignored

    Returns:
        bool: True if tags written, False otherwise

    """

    log = logging.getLogger(__name__)

    if fpath.endswith('.mp4'):
        return mp4_tagger( fpath, metadata = metadata )
    if fpath.endswith('.mkv'):
        return mkv_tagger( fpath, metadata = metadata )

    log.error('Unsupported file type : %s', fpath)
    return False
