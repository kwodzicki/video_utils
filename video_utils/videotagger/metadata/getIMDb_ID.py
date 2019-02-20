import logging;
import os, re;
from imdb import IMDb;

TVDb = None;                                                                    # Set tvdb to None
try:
  from video_utils.api_keys import tvdb as tvdb_key;                            # Attempt to import the API key from the api_keys module
except:
  tvdb_key = os.environ.get('TVDB_API_KEY', None);                              # On exception, try to get the API key from the TVDB_API_KEY environment variable

if tvdb_key:                                                                    # If the tvdb_key variable is valid
  import tvdbsimple as TVDb;                                                    # Import tvdbsimple as tvdb; this will make if tvdb: return True
  TVDb.KEYS.API_KEY = tvdb_key;                                                 # Set the API_KEY for the tvdbsimple
else:                                                                           # Else, get a logger and log an error
  logging.getLogger(__name__).error( 
    "API key for TVDb could NOT be imported!"
  );

imdbFMT = 'tt{}';                                                               # Format string for IMDb id
yearPat = re.compile( r'\(([0-9]{4})\)' );                                      # Pattern for finding year in series name

def getIMDb_ID( in_file ):
  '''
  Name:
    getIMDb_ID
  Purpose:
    A function that attempts to get the IMDb ID (i.e., tt0000000) based
    on the information from an input file path.

    This is designed to be used for Plex DVR TV Episode files, which
    have the file naming convention of:
      Series Name - S00E00 - Episode title.ts
  Inputs:
    in_file  : Full path to file to get IMDb ID for
  Outputs:
    Returns the IMDb ID if found, or None if not found.
  '''
  log = logging.getLogger(__name__);                                            # Initialize logger

  log.debug('Extracting information from file name');
  fileBase          = os.path.basename( in_file );                              # Get base name of input file
  series, se, title = fileBase.split(' - ');                                    # Split the file name on ' - '; not header information of function

  year              = yearPat.findall( series );                                # Try to find a year in the series name
  if len(year) == 1:                                                            # If found a year
    year   = int(year[0]);                                                      # Get year from list
    series = yearPat.sub('', series);                                           # Replace year in the series name with nothing
  else:                                                                         # Else
    year   = None;                                                              # Set year equal to None

  title             = title.split('.');                                         # Split the title on period; this is to get file extension
  ext               = title[-1];                                                # Get the file extension; last element of list
  title             = '.'.join(title[:-1]);                                     # Join all but last element of title list using period; will rebuild title

  ###############
  ### IMDb serach
  log.info( 'Attempting to get IMDb ID from IMDb' );               
  imdb = IMDb();                                                                # Initialize IMDb instance
  res  = imdb.search_episode( title );                                          # Search for the episode title on IMDb

  for r in res:                                                                 # Iterate over all the results from IMDb
    if r['episode of'].lower() in series.lower():                               # If the series name from IMDb is in the series name from the file
      log.debug('Found series with matching name');
      if 'series year' in r and year:                                           # If the 'series year' key is in the result AND the local year is defined
        log.debug('Series has year information');
        if r['series year'] != year: 
          log.debug('Series year did NOT match');
          continue;                                                             # If the result series year NOT match the local series year, skip series
      log.info( 'IMDb ID found from IMDb search')
      return imdbFMT.format( r.getID() );                                       # Return the IMDb id
  
  log.warning( 'IMDb search failed' )
  
  ###############
  ### TVDb serach
  if not TVDb: return None;                                                     # If the TVDb was NOT loaded, just return None;
  log.info( 'Attempting to get IMDb ID from TVDb' );               

  tvdb = TVDb.Search();                                                         # Initialize search for TVDb
  res  = tvdb.series( series );                                                 # Search for the series on the TVDb
  for r in res:                                                                 # Iterate over all search results
    if str(year) in r['firstAired']:                                            # If the local year is in the firstAird tag
      log.debug( 'Found series with same firstAird year' );
      eps = TVDb.Series( r['id'] ).Episodes.all();                              # Get list of all episodes in series
      for ep in eps:                                                            # Iterate over all episodes
        if (ep['episodeName'].lower() in title.lower()) and ('imdbId' in ep):   # If the episode name is in the local title and there is an imdbId in the ep
          log.debug( 'Found episode with same name' );
          if ep['imdbId'] != '':                                                # If the imdbId tag is NOT empty
            log.info( 'IMDb ID found from TVDb search' )
            return ep['imdbId'];                                                # Return it

  log.warning( 'TVDb search failed' );
  return None;