import logging
	
# Try python3 import, else try python2 import
IMDb = True;
try:
	from .getIMDb_Info import getIMDb_Info;
except:
	try:
		from getIMDb_Info import getIMDb_Info;
	except:
		IMDb = False;

TMDb = True;
try:
	from .getTMDb_Info import getTMDb_Info;
except:
	try:
		from getTMDb_Info import getTMDb_Info;
	except:
		TMDb = False;

TVDb = True;
try:
	from .getTVDb_Info import getTVDb_Info;
except:
	try:
		from getTVDb_Info import getTVDb_Info;
	except:
		TVDb = False;

if not IMDb and not TMDb:
	raise Exception('Could not import IMDb and TMDb APIs!');

def getMetaData( IMDb_ID, attempts = None, TMDb=TMDb, IMDb=IMDb, TVDb=TVDb ):
	'''
	A function that attempts to get data from imdb.com and themoviedb.org.
	If data from both are returned, any information from imdb.com that
	is NOT in the information from themoviedb.org is add to themoviedb.org
	information. If only one of the websites returns information, only
	that informaiton is returned from this function. If neither site
	returns informaiton, then an empty dictionary is returned.
	'''
	log = logging.getLogger(__name__);                                            # Initialize logger

	log.info( 'Getting metadata for file' );
	tvdbInfo = None;                                                              # Initialize tvdbInfo to None
	if IMDb: IMDb = getIMDb_Info( IMDb_ID, attempts = attempts );                 # If IMDb is True, get information from imdb.com
	if type(IMDb) is not bool:                                                    # If TMDb is NOT a boolean type
		if 'episode of' in IMDb and TVDb:                                           # If the data if for an episode and TVDb is True
			try:                                                                      # Try to...
				imdbId = IMDb['episode of'].getID();                                    # Get the imdbID for the series
			except:                                                                   # If there is an error getting to ID for the series...
				log.warning('Could NOT get series id from imdb.com, info incomplete!!!');# Log a warning message
			else:                                                                     # If the try is a success
				if TVDb: tvdbInfo = getTVDb_Info( imdbId = imdbId );                    # Get information from TVDb based on imdbId if TVDb is available
			if tvdbInfo is not None:                                                  # If information is downloaded
				if 'seriesName' in tvdbInfo:                                            # If there is a seriesName tag in the info
					IMDb['seriesName'] = tvdbInfo['seriesName'];                          # Redefine the series name

	if TMDb: TMDb = getTMDb_Info( IMDb_ID, attempts = attempts );                 # If TMDb is True, get information from themoviedatabase.org
	if type(TMDb) is not bool:                                                    # If TMDb is NOT a boolean type
		if TMDb['is_episode'] and TVDb:                                             # If the data if for an episode and TVDb is True
			if tvdbInfo is None and TVDb:                                             # If information from thetvdb.com as not yet been downloaded
				tvdbInfo = getTVDb_Info( Info = TMDb );                    	            # Get information from TVDb
			if tvdbInfo is not None:                                                  # If information is downloaded
				if 'seriesName' in tvdbInfo:                                            # If there is a seriesName tag in the info
					TMDb.set_item('seriesName', tvdbInfo['seriesName']);                  # Redefine the series name

	if type(TMDb) is bool and type(IMDb) is bool:                                 # If both are still boolean type
		return {};                                                                  # Return empty dictionary
	elif type(TMDb) is not bool and type(IMDb) is bool:                           # Else, if TMBd is not a boolean AND IMDb is...
		return TMDb;                                                                # Return TMBd
	elif type(TMDb) is bool and type(IMDb) is not bool:                           # Else, if IMBd is not a boolean AND TMDb is...
		return IMDb;                                                                # Return IMBd
	else:                                                                         # Else, both must NOT be booleans
		for key in IMDb.keys():                                                     # Iterate over all keys in IMDb
			if not TMDb.has_key(key):                                                 # If TMDb does NOT have the key
				TMDb.set_item( key, IMDb[key] );                                        # Add the key from IMDb to TMDb
		return TMDb;                                                                # Return TMDb object