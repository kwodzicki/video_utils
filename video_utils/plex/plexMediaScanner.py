import logging
import os 

from plexapi.server import PlexServer

from .utils import getToken

################################################################################
def plexMediaScanner( sectionName, path=None ):
  """
  A python function that scans library through API call
  
  Arguments:
    sectionName (str) : Name of the library section to scan

  Keyword arguments:
    path (str) : Path to scan for new files; use to only scan 
        part of section

  Returns:
    bool : True if success, False otherwise

  """

  log = logging.getLogger(__name__);

  token = getToken()
  if token is None:
    log.error( 'Failed to get Plex token for API call!' )
    return False

  try:
    plex = PlexServer( **token )
  except Exception as err:
    log.error( f"Failed to create PlexServer object : {err}" )
    return False

  try:
    section = plex.library.section( sectionName )
  except Exception as err:
    log.error( f"Failed to find section '{sectionName}' on server" )
    return False

  if path is not None:
    if not os.path.isdir(path):
      log.warning( f"No such directory '{path}'; scanning entire library section" )
      path = None

  section.update( path )

  return True
