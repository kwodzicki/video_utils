'''
Name:
	test_dependencies
Purpose:
	A function to test if all dependencies are present for the 
	library. Depending on the importance of a given python module 
	or command line utility the main program will be stopped with
	error message, or message will be displayed stating what
	features will not work correctly.
Inputs:
	None.
Outputs:
	If minimum number of  dependencies are found to run, returns a list
	of missing command line tools
Keywords:
	None.
Author and History:
	Kyle R. Wodzicki     Created 12 Jan. 2017
'''
import logging
log = logging.getLogger(__name__);
import os

try:
	from .. import config
except:
  from videoconverter import config

cpulimit = True;                                                                # Set cpulimit to None
vobsub   = True;                                                                # Set vobsub to False
srt      = True;                                                                # Set srt to False
MP4Tags  = True;                                                                # Set enableMP4Tags to False


def _local_import(module):
	'''
	Function to import packages.
	'''
	module_obj   = __import__( module );                                          # Import the module
	module_split = module.split(".");                                             # Split the module string on period
	for sub_obj in module_split[1:]: module_obj = getattr(module_obj, sub_obj);   # Iterate over the sub-modules and import them to replace the previous module
	globals()[module_split[-1]] = module_obj;                                     # Set the lowest-level module name to the full module import

def runCheck():
	############################################################################
	# Check for required python packages
	python_req_miss, python_opt_miss = [], [];
	cli_req_miss, cli_opt_miss = [], [];

	for i in config.python_req:
		try:
			_local_import( i );
		except:
			python_req_miss.append( i );		
	if len( python_req_miss ) > 0:
		msg = "The following required Python modules could NOT be imported:"
		log.critical( msg );
		for i in python_req_miss: log.critical( "    "+i );
		exit(1);
	if 'subprocess' in python_req_miss:
		msg = ["Cannont check for command line utilites until the",
					 "'subprocess' module is installed!"]
		for i in msg: log.critical( i );
		exit(1);

	############################################################################
	# Check for required command line utilities
	for i in config.cli_req:
		with open(os.devnull, 'w') as null:
			status = subprocess.call(['which', i], stdout = null, stderr = null );
		if status != 0: cli_req_miss.append( i );
	if len( cli_req_miss ) > 0:
		msg = ["The following required command line utility(s) were NOT found!",
					 "  If they are installed, be sure that they are in you PATH:"]
		for i in msg: log.critical( i );
		for i in cli_req_miss: log.critical( "    " + i );
	if (len( python_req_miss ) > 0) or (len( cli_req_miss ) > 0): exit(1);        # If any of the python modules could NOT be loaded, or any of the required CLIs were not found, exit
	############################################################################
	# Check for optional python packages
	for i in config.python_opt:
		try:
			_local_import( i );
		except:
			python_opt_miss.append( i );		
	if len( python_opt_miss ) > 0:
		msg = "The following optional Python modules could NOT be imported:"
		log.warning( msg );
		for i in python_opt_miss:
			if 'getMetaData' in i:                                                      # If the mp4tags command was NOT found
				log.warning( "    "+i+": MP4 tagging is disabled!" );
				MP4Tags = None;                                                           # Set enableMP4Tags to False
			else:
				log.warning( "    "+i );

	############################################################################
	# Check for optional command line utilities
	for i in config.cli_opt:
		with open(os.devnull, 'w') as null:
			status = subprocess.call(['which', i], stdout = null, stderr = null);
		if status != 0:
			cli_opt_miss.append( i );
			# Turn off any options that will NOT work
			if i == 'cpulimit':                                                         # If the cpulimit command was NOT found
				cpulimit = None;                                                          # Set cpulimit to None
				log.warning( 'CPU limiting is disabled!' );                               # Print a warning
			elif i == 'mkvextract':                                                     # If the mkvextract command was NOT found
				vobsub = None;                                                            # Set vobsub to False
				log.warning( 'VobSub extraction is disabled!' );                          # Print a warning
			elif i == 'vobsub2srt':                                                     # If the vobsub2srt command was NOT found
				srt = None;                                                               # Set srt to False
				log.warning( 'VobSub conversion to SRT is disabled!' );                   # Print a warning
	if len( cli_opt_miss ) > 0:
		msg = ["The following optional command line utility(s) were NOT found!",
					 "  The program will still run, but some features, such as VobSub",
					 "  extraction and CPU limiting may be disabled. If the utilities",
					 "  are installed, be sure that they are in your PATH:"]
		for i in msg: log.warning( i );
		for i in cli_opt_miss: log.warning( "      " + i );
runCheck();