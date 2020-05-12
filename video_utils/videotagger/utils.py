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
BADCHARS = re.compile( '[#%{}\\\<\>\*\?/\$\!\:\@]' )                                   # Characters that are not allowed in file paths

def replaceChars( string, repl = ' ', **kwargs ):
  return BADCHARS.sub( repl, string ).replace('&', 'and')
 
def download(URL):
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
  data = download( URL )
  if data is None:
    return False

  if isinstance(text, str) and text != '':
    data = addText( data, text )

  imageExt  = os.path.splitext( URL       )[1]
  imagePath = os.path.splitext( videoPath )[0] + imageExt
  
  with open( imagePath, 'wb' ) as fid:
    fid.write( data )
  return imagePath, data
