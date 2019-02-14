import logging;
try:
	import imdb;
except:
	raise Exception('IMDbPY failed to import!');
imdbLog = logging.getLogger('imdbpy');                                          # Get the imdbpy logger
while len(imdbLog.handlers) > 0:                                                # While there are handlers in the imdbpy logger
	for handler in imdbLog.handlers:                                              # Iterate over the handlers in the logger
		handler.close();                                                            # Close the handler
		imdbLog.removeHandler(handler);                                             # Remove all handler

def getIMDb_Info( IMDbID, attempts = None ):
	'''
	Name:
	   getIMDb_Info
	Purpose:
	   A python functio that attempts to download information
	   from imdb.com using the IMDbPY python package.
	Inputs:
	   IMDbID : The id from the URL of a movie on imdb.com.
	             Ex. For the movie 'Push', the URL is:
	             http://www.imdb.com/title/tt0465580/
	             Making the imdb id tt0465580
	Outputs:
	   Returns and instance of the imdb.IMDb().get_movie
	   function
	Keywords:
	   attempts : Maximum number of times to try to get
	               data from imdb.com.
	               DEFAULT is 250.
	Author and History:
	   Kyle R. Wodicki     Created 16 Sep. 2017
	'''
	log = logging.getLogger(__name__);                                            # Initialize a logger
	IMDb = imdb.IMDb();                                                           # Initialize IMDb instance
	log.info('Attempting to get information from imdb.com...')
	attempts = 250 if attempts is None else attempts;                             # Set maximum attempts to try to get data from IMDb
	attempt  = 0;                                                                 # Set attempt to zero (0)
	while attempt < attempts:                                                     # While attempt is less than max attempt
		try:		                                                                    # Try to...
			IMDb_info = IMDb.get_movie( IMDbID.replace('tt','') );                    # Get information about the Movie/TV Show from the IMDb Python API
		except:                                                                     # Except and catch exception
			attempt += 1;                                                             # Increment attempt
		else:                                                                       # Else, try was successful and data downloaded
			if not IMDb_info.has_key('title'):                                        # If the IMDb_info object does NOT have the 'title' key
				attempt += 1;                                                           # Increment attempt
			elif IMDb_info['title'] == 'How Did You Get Here?':                       # If the title is 'How Did You Get Here?'
				attempt+=1;                                                             # Increment attempt
			else:                                                                     # Else
				log.info('Information downloaded from imdb.com!');                      # Print log information
				break;                                                                  # Break the while loop
	if attempt == attempts:                                                       # If reached the maximum attempts
		log.warning('Failed to get information from imdb.com!');                    # Log a waring
		return {};		                                                              # Return and empty dictionary
	return IMDb_info;		                                                          # Return the IMDb information