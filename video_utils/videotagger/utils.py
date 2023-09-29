"""
Utilities for video tagging

"""

import logging
import os
import re
from urllib.request import urlopen
from io import BytesIO

from PIL import Image, ImageFont, ImageDraw

from .. import DATADIR


TTF      = os.path.join(DATADIR, 'Anton-Regular.ttf')
RED      = (255,   0,   0)
WHITE    = (240, 240, 240)
BSCALE   = 0.05
TSCALE   = 0.85
SPACE    = ' '

# Characters that are not allowed in file paths
#BADCHARS = re.compile( '[#%{}\\\<\>\*\?/\$\!\:\@]' )
BADCHARS = re.compile( r'[#%\\\<\>\*\?/\$\!\:\@]' )

def _replace( string, repl, **kwargs ):
    """
    'Private' function for replace characters in string

    Arguments:
        string (str): String to have characters replaced
        repl (str): String to replace bad characters with

    Keyword arguments:
        **kwargs: Any, none used currently

    Returns:
        str: String with bad values repaced by repl value

    """

    return BADCHARS.sub( repl, string ).replace('&', 'and').strip()

def replace_chars( *args, repl = ' ', **kwargs ):
    """
    Replace invalid path characters; '&' replaced with 'and'

    Arguments:
        *args (str): String(s) to replace characters in

    Keyword arguments:
        repl (str): String to replace bad characters with; default is space (' ')
        **kwargs

    Returns:
        String, or list, with bad values replaced by repl value

    """

    if len(args) == 1:
        return _replace( args[0], repl, **kwargs )
    return [ _replace( arg, repl, **kwargs ) for arg in args ]

def is_id(db_id):
    """Check to ensure the db_id is valid db_id"""

    # If tvdb or tmdb in the first
    return db_id[:4] == 'tvdb' or db_id[:4] == 'tmdb'

def download(url):
    """
    Download data from URL

    Arguments:
      url (str): Full URL of data to download

    Keyword arguments:
      None.

    Returns:
      bytes: Data downloaded from file; None if failed

    """

    log  = logging.getLogger(__name__)
    data = None
    log.debug('Attempting to open URL: %s', url)
    try:
        resp = urlopen( url )
    except Exception as error:
        log.warning( 'Failed to open URL: %s', error )
        return data

    log.debug('Attempting to download data')
    try:
        data = resp.read()
    except Exception as error:
        log.warning( 'Failed to download data: %s', error )

    try:
        resp.close()
    except Exception as error:
        log.debug('Failed to close URL: %s', error )

    return data

def get_font( text, bbox ):
    """
    Determine font size for movie version

    This function determines the font size to use when adding movie version
    information to a poster. The font size is determined by iteratively 
    increasing the font size until the text will no longer fit inside the
    specified box. The font size is the decremented slightly to ensure it
    fits. Space is also added between letters to ensure that the text
    spans most of the box horizontally.

    Arguments:
        text (str): Text to add to the movie poster
        bbox (iterable): Dimensions of the box (width,height) to write text in

    Keyword arguments:
        None

    Returns:
        tuple: Input text (may be updated with extra space between characters)
            and a pillow ImageFont font object.

    """

    bbox      = list(bbox)
    bbox[0]  *= TSCALE
    bbox[1]  *= TSCALE
    fontsize  = 1
    font      = ImageFont.truetype(TTF, size = fontsize)
    text_size = font.getsize( text )

    # While the text fits within the box
    while text_size[0] < bbox[0] and text_size[1] < bbox[1]:
        fontsize += 1
        font      = ImageFont.truetype(TTF, size = fontsize)
        text_size = font.getsize( text )

    # Decrement font size by 2 to ensure will fit
    fontsize -= 2
    font      = ImageFont.truetype(TTF, size = fontsize)

    text_size = font.getsize( text )
    text_list = list(text)

    # Set number of added spaces to zero
    nspace    = 0

    # While width of text fits within bbox
    while text_size[0] < bbox[0]:
        nspace += 1
        # Join text list using nspaces
        text      = (SPACE * nspace).join( text_list )
        # Get new text size
        text_size = font.getsize( text )

    # Decement number of spaces as too wide at first
    nspace -= 1
    text    = (SPACE * nspace).join( text_list )

    return text, font

def add_text( fpath_data, text ):
    """
    Add text to image object

    This function adds a text string to a pillow Image object

    Arguments:
        fpath_data (file, bytes): Path to a file to read in or bytes of file
        text (str): String to add to image

    Keyword arguments:
        None

    Returns:
        bytes: Image data

    """

    # If input is a bytes instance
    if isinstance(fpath_data, bytes):
        file_obj = BytesIO()
        file_obj.write( fpath_data )
        file_obj.seek(0)
    else:
        file_obj = fpath_data

    # Open the image
    image = Image.open( file_obj )
    # Initialize a drawer
    draw  = ImageDraw.Draw( image )
    # Width and height of box to draw text in
    bbox  = (image.width, image.height * BSCALE)

    # Get text (may add spaces) and font to use
    text, font = get_font( text, bbox )

    text_size = font.getsize( text )
    # Compute x offset to center text
    xoffset  = int( bbox[0] - text_size[0] ) // 2
    yoffset  = 0

    # Draw red box at top of cover
    draw.rectangle( (0, bbox[1], bbox[0], 0), fill = RED )
    # Write text in box
    draw.text( (xoffset, yoffset), text, font = font, fill = WHITE )

    data  = BytesIO()# Initialize BytesIO
    image.save( data, format = image.format )# Save data to BytesIO object
    data.seek(0)# Seek to beginning of data
    return data.read()# Return bytes

def download_cover( video_path, url, text = None ):
    """
    Wrapper function to download artwork and add version text

    Arguments:
        video_path (str): Path to video file artwork is for
        url (str): URL of artwork to download

    Keyword arguments:
        text (str): Text to add to artwork; typically is movie version

    Returns:
        tuple: Path to downloaded image on local disc, and bytes for image data

    """

    data = download( url )
    if data is None:
        return None, None

    # If text is string instance and NOT empty, add text to the image
    if isinstance(text, str) and text != '':
        data = add_text( data, text )

    image_ext  = os.path.splitext( url        )[1]
    image_path = os.path.splitext( video_path )[0] + image_ext

    with open( image_path, 'wb' ) as fid:
        fid.write( data )

    return image_path, data
