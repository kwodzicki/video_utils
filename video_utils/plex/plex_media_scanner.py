"""
Wrapper utils for calling Plex media scanner

"""

import logging
import os

from plexapi.server import PlexServer

from .utils import get_token

################################################################################
def plex_media_scanner( section_name, path=None ):
    """
    A python function that scans library through API call
    
    Arguments:
        section_name (str) : Name of the library section to scan

    Keyword arguments:
        path (str) : Path to scan for new files use to only scan 
            part of section

    Returns:
        bool : True if success, False otherwise

    """

    log = logging.getLogger(__name__)

    token = get_token()
    if token is None:
        log.error( 'Failed to get Plex token for API call!' )
        return False

    try:
        plex = PlexServer( **token )
    except Exception as err:
        log.error( "Failed to create PlexServer object : %s", err )
        return False

    try:
        section = plex.library.section( section_name )
    except:
        log.error( "Failed to find section '%s' on server", section_name )
        return False

    if path is not None:
        if not os.path.isdir(path):
            log.warning(
                "No such directory '%s'; scanning entire library section",
                path,
            )
            path = None

    log.info(
        'Running Plex Media Scanner on section "%s", path "%s"',
        section_name,
        path,
    ) 
    section.update( path )

    return True
