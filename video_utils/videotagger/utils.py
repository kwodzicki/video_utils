import logging
import os, re
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
#BADCHARS = re.compile( '[#%{}\\\<\>\*\?/\$\!\:\@]' )                                   # Characters that are not allowed in file paths
BADCHARS = re.compile( '[#%\\\<\>\*\?/\$\!\:\@]' )                                   # Characters that are not allowed in file paths

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

def replaceChars( *args, repl = ' ', **kwargs ):
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

  if len(args) == 1:                                                                    # If one input argument
    return _replace( args[0], repl, **kwargs )                                          # Return single value
  return [ _replace( arg, repl, **kwargs ) for arg in args ]                            # Iterate over all input arguments, returning list
 
def download(URL):
  """
  Download data from URL

  Arguments:
    URL (str): Full URL of data to download

  Keyword arguments:
    None.

  Returns:
    bytes: Data downloaded from file; None if failed

  """

  log  = logging.getLogger(__name__)
  data = None
  log.debug('Attempting to open URL: {}'.format(URL))
  try:
    resp = urlopen( URL )
  except Exception as err:
    log.warning( 'Failed to open URL: {}'.format(err) )
    return data

  log.debug('Attempting to download data')
  try:
    data = resp.read()
  except Exception as err:
    log.warning( 'Failed to download data' )

  try:
    resp.close()
  except Exception as err:
    log.debug('Failed to close URL: {}'.format( err ) )

  return data

def getFont( text, bbox ):
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
    tuple: Input text (may be updated with extra space between characters) and a
      pillow ImageFont font object.

  """

  bbox      = list(bbox)                                                        # Convert bbox to list
  bbox[0]  *= TSCALE                                                            # Scale the box height by TSCALE
  bbox[1]  *= TSCALE                                                            # Scale the box height by TSCALE
  fontsize  = 1                                                                 # Set font to 1
  font      = ImageFont.truetype(TTF, size = fontsize)                          # Load font
  textSize  = font.getsize( text )                                              # Get size of text
  while textSize[0] < bbox[0] and textSize[1] < bbox[1]:                        # While the text fits within the box
    fontsize += 1                                                               # Increment fontsize by one
    font      = ImageFont.truetype(TTF, size = fontsize)                        # Load font with new fontsize
    textSize  = font.getsize( text )                                            # Get size of text
  fontsize -= 2                                                                 # Decrement font size by 2 to ensure will fit
  font      = ImageFont.truetype(TTF, size = fontsize)                          # Load font with fontsize

  textSize  = font.getsize( text )                                              # Get size of text
  textList  = list(text)                                                        # Convert text to  list
  nspace    = 0                                                                 # Set number of added spaces to zero
  while textSize[0] < bbox[0]:                                                  # While width of text fits within bbox
    nspace += 1                                                                 # Increment number of spaces
    text    = (SPACE * nspace).join( textList )                                 # Join text list using nspaces
    textSize  = font.getsize( text )                                            # Get new text size
  nspace -= 1                                                                   # Decement number of spaces as too wide at first
  text    = (SPACE * nspace).join( textList )                                   # Set text

  return text, font                                                             # Return text and font

def addText( fp, text ):
  """
  Add text to image object

  This function adds a text string to a pillow Image object

  Arguments:
    fp (file, bytes): Path to a file to read in or bytes of file
    text (str): String to add to image

  Keyword arguments:
    None

  Returns:
    bytes: Image data

  """

  if isinstance(fp, bytes):                                                     # If input is a bytes instance
    fileObj = BytesIO()                                                         # Create bytes IO object
    fileObj.write( fp )                                                         # Write bytes
    fileObj.seek(0)                                                             # Seek back to beginning
  else:                                                                         # Else
    fileObj = fp                                                                # Set fileObj to input

  image = Image.open( fileObj )                                                 # Open the image
  draw  = ImageDraw.Draw( image )                                               # Initialize a drawer
  bbox  = (image.width, image.height * BSCALE)                                  # Width and height of box to draw text in

  text, font = getFont( text, bbox )                                            # Get text (may add spaces) and font to use

  textSize = font.getsize( text )                                               # Get text size
  xoffset  = int( bbox[0] - textSize[0] ) // 2                                  # Compute x offset to center text
  yoffset  = 0                                                                  # Set yoffset to zero

  draw.rectangle( (0, bbox[1], bbox[0], 0), fill = RED )                        # Draw red box at top of cover
  draw.text( (xoffset, yoffset), text, font = font, fill = WHITE )              # Write text in box

  data  = BytesIO()                                                             # Initialize BytesIO
  image.save( data, format = image.format )                                     # Save data to BytesIO object
  data.seek(0)                                                                  # Seek to beginning of data
  return data.read()                                                            # Return bytes

def downloadCover( videoPath, URL, text = None ):
  """
  Wrapper function to download artwork and add version text

  Arguments:
    videoPath (str): Path to video file artwork is for
    URL (str): URL of artwork to download

  Keyword arguments:
    text (str): Text to add to artwork; typically is movie version

  Returns:
    tuple: Path to downloaded image on local disc, and bytes for image data

  """

  imagePath = None                                                                      # Initialize imagePath to None
  data      = download( URL )                                                           # Download data from URL
  if data is not None:                                                                  # If data is NOT None
    if isinstance(text, str) and text != '':                                            # If text is string instance and NOT empty
      data = addText( data, text )                                                      # Add text to image data

    imageExt  = os.path.splitext( URL       )[1]                                        # Get image extension
    imagePath = os.path.splitext( videoPath )[0] + imageExt                             # Set image path
    
    with open( imagePath, 'wb' ) as fid:                                                # Open imagePath in binary write mode
      fid.write( data )                                                                 # Write data to file

  return imagePath, data                                                                # Return path to file and image bytes
