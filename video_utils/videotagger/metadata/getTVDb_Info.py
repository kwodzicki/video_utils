import logging

try:
	from video_utils.api_keys import tvdb as tvdb_key;       # Attempt to import the API key from the api_keys module
except:
  tvdb_key = os.environ.get('TVDB_API_KEY', None);         # On exception, try to get the API key from the TVDB_API_KEY environment variable

if not tvdb_key:
	raise Exception("API key for TVDb could NOT be imported!");

try:
	import tvdbsimple as tvdb;
except:
	raise Exception("Failed to import 'tvdbsimple'!")
tvdb.KEYS.API_KEY = tvdb_key;

# def download_TVDb(Info, imdbId, maxAttempt = 3, logLevel = None): 
# 	attempt = 1;
# 	while attempt < maxAttempt+1:                                               # While not at the maximum attempts
# 		try:                                                                      # Try to...
# 			tvdbInfo = search.series( imdbId = imdbId );                            # Search the TV Database for the show
# 		except:                                                                   # On exception...
# 			tvdbInfo = None;                                                        # Set tvdbInfo to None
# 			log.debug('Attempt {} of {} Failed!'.format(attempt, maxAttempt));      # Debugging information
# 			attempt += 1;                                                           # Increment the attempt counter
# 		else:                                                                     # Else when try is successful
# 			break;                                                                  # Break the while loop
# 	if attempt == maxAttempt or tvdbInfo is None:                               # If reached the maximum attempts or failed to download
# 		log.warning('Search by IMDb ID Failed!');                                 # Log a warning
# 		return None;                                                              # Return None
# 	log.debug('Search by IMDb ID successful');                                  # Some debugging information
# 	if len(tvdbInfo) == 1:                                                      # If found only one (1) matching series
# 		log.info('Information downloaded from thetvdb.com!');                     # Some debugging information		
# 		return tvdbInfo[0];                                                       # Return the information


def getTVDb_Info( Info = None, imdbId = None, maxAttempt = 3, logLevel = None ):
	'''
	Name:
		getTVDb_Info
	Purpose:
		A python function to download tv show informaiton from thetvdb.com
	Inputs:
		Info   : A dictionary containing the series name and first
		         air data; this information is intended to be from
		         themoviedb.org (i.e., getTMDb_Info). Dictionary
		         should be of form:
		         Info = {'seriesName'     : 'Name of Series', 
		                 'first_air_data' : 'YYYY-MM-DD'}
		imdbId : The IMDb index for the series.
		ONLY ONE OF THESE IS REQUIRED AT A TIME!!!
	Outputs:
		Returns the dictionary of information downloaded from thetvdb.com
		about the series.
	'''
	log = logging.getLogger(__name__);                                            # Initialize logger
	if Info is None and imdbId is None: return None;                              # If series name and imdbId NOT input, return None

	log.debug('Setting up a search instance');                                    # Debugging information
	attempt = 1;                                                                  # Initialize attempt to one (1)
	while attempt < maxAttempt+1:                                                 # While not at the maximum attempts
		try:                                                                        # Try to...
			search = tvdb.Search();                                                   # Set up a search instance of tvdbsimple
		except:                                                                     # On exception...
			log.debug('Attempt {} of {} Failed!'.format(attempt, maxAttempt));        # Debugging information
			attempt += 1;                                                             # Increment the attempt counter
		else:                                                                       # Else when try is successful
			break;                                                                    # Break the while loop
	if attempt == maxAttempt:                                                     # If reached the maximum attempts 
		log.warning('Failed to set up Search instance!');                           # Log a warning
		return None;                                                                # Return None
	log.debug('Successfully set up search instance');                             # Some debugging information


	seriesName = None;
	if Info is not None:                                                          # If information was input (i.e., Info not None)
		if 'seriesName' in Info and 'first_air_date' in Info:                       # If NO first_air_date tag in Info
			seriesName = Info['seriesName']                                           # If NO 'seriesName' tag in Info
	if imdbId is not None:                                                        # Else, if imdbId is not None
		if type(imdbId) is not str: imdbId = str(imdbId);                           # Ensure imdbId is a string
		if imdbId[:2] != 'tt': imdbId = 'tt' + str(imdbId);                         # Ensure the imdbId string begins with 'tt'
	if seriesName is not None and imdbId is not None: seriesName = None;          # If both seriesName and imdbID are not None, set seriesName to None

	attempt = 1;                                                                  # Initialize attempt to one (1)
	log.info( 'Attempting to get information from thetvdb.com...' );
	while attempt < maxAttempt+1:                                                 # While not at the maximum attempts
		try:                                                                        # Try to...
			tvdbInfo = search.series( name = seriesName, imdbId = imdbId );           # Search the TV Database for the show
		except:                                                                     # On exception...
			tvdbInfo = None;                                                          # Set tvdbInfo to None
			log.debug('Attempt {} of {} Failed!'.format(attempt, maxAttempt));        # Debugging information
			attempt += 1;                                                             # Increment the attempt counter
		else:                                                                       # Else when try is successful
			break;                                                                    # Break the while loop
	if attempt == maxAttempt or tvdbInfo is None:                                 # If reached the maximum attempts or failed to download
		log.warning('TVDb search Failed!');                                         # Log a warning
		return None;                                                                # Return None
	log.debug('TVDb search successful');                                          # Some debugging information
	if Info:
		for i in tvdbInfo:                                                          # Iterate over all series returned
			if i['firstAired'] == Info['first_air_date']:                             # If the first aired date from the tv database matches that of the movie database
				log.info('Information downloaded from thetvdb.com!');                   # Some debugging information		
				return i;                                                               # Return the information
	elif len(tvdbInfo) == 1:                                                      # If found only one (1) matching series
		log.info('Information downloaded from thetvdb.com!');                       # Some debugging information		
		return tvdbInfo[0];                                                         # Return the information
	log.warning('Failed to get information from thetvdb.com!');                   # Some debugging information		
	return None;

# 	if Info is not None:                                                          # If information was input (i.e., Info not None)
# 		if 'seriesName' not in Info:                                                # If NO 'seriesName' tag in Info
# 			log.warning('No series name in Info dictionary, returning');              # Log a warning
# 			return None;                                                              # Return None
# 		if 'first_air_date' not in Info:                                            # If NO first_air_date tag in Info
# 			log.warning('No first_air_date in Info dictionary, returning');           # Log a warning
# 			return None;                                                              # Return None
# 		log.debug('Attempting search for series based on name');                    # Debugging informaiton
# 		while attempt < maxAttempt+1:                                               # While not at the maximum attempts
# 			try:                                                                      # Try to...
# 				tvdbInfo = search.series( Info['seriesName'] );                         # Search the TV Database for the show
# 			except:                                                                   # On exception...
# 				tvdbInfo = None;                                                        # Set tvdbInfo to None
# 				log.debug('Attempt {} of {} Failed!'.format(attempt, maxAttempt));      # Debugging information
# 				attempt += 1;                                                           # Increment the attempt counter
# 			else:                                                                     # Else when try is successful
# 				break;                                                                  # Break the while loop
# 		if attempt == maxAttempt or tvdbInfo is None:                               # If reached the maximum attempts or failed to download
# 			log.warning('Search by name Failed!');                                    # Log a warning
# 			return None;                                                              # Return None
# 		log.debug('Search by name successful');                                     # Some debugging information
# 		for i in tvdbInfo:                                                          # Iterate over all series returned
# 			if i['firstAired'] == Info['first_air_date']:                             # If the first aired date from the tv database matches that of the movie database
# 				log.info('Information downloaded from thetvdb.com!');                   # Some debugging information		
# 				return i;                                                               # Return the information
# 	elif imdbId is not None:                                                      # Else, if imdbId is not None
# 		if type(imdbId) is not str: imdbId = str(imdbId);                           # Ensure imdbId is a string
# 		if imdbId[:2] != 'tt': imdbId = 'tt' + str(imdbId);                         # Ensure the imdbId string begins with 'tt'
# 		log.debug('Attempting search for series based on IMDb ID');                 # Debugging informaiton
# 		while attempt < maxAttempt+1:                                               # While not at the maximum attempts
# 			try:                                                                      # Try to...
# 				tvdbInfo = search.series( imdbId = imdbId );                            # Search the TV Database for the show
# 			except:                                                                   # On exception...
# 				tvdbInfo = None;                                                        # Set tvdbInfo to None
# 				log.debug('Attempt {} of {} Failed!'.format(attempt, maxAttempt));      # Debugging information
# 				attempt += 1;                                                           # Increment the attempt counter
# 			else:                                                                     # Else when try is successful
# 				break;                                                                  # Break the while loop
# 		if attempt == maxAttempt or tvdbInfo is None:                               # If reached the maximum attempts or failed to download
# 			log.warning('Search by IMDb ID Failed!');                                 # Log a warning
# 			return None;                                                              # Return None
# 		log.debug('Search by IMDb ID successful');                                  # Some debugging information
# 		if len(tvdbInfo) == 1:                                                      # If found only one (1) matching series
# 			log.info('Information downloaded from thetvdb.com!');                     # Some debugging information		
# 			return tvdbInfo[0];                                                       # Return the information
# 	log.warning('Failed to get information from thetvdb.com!');                   # Some debugging information		
# 	return None;                                                                  # If got to this point, information was NOT found for requested series
