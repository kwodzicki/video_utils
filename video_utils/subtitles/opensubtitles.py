#!/usr/bin/env python
# To get subtitle SRT files from opensubtitles.org

import logging;
import os, time;
import socket;
from base64 import standard_b64decode;
from zlib import decompress;
from xmlrpc.client import ServerProxy;

from ..config import opensubtitles as opensubs_config
  
ext = ('.avi', '.m4v', '.mp4', '.mkv', '.mpeg', '.mov', '.wmv');                # List of some common video extensions

class opensubtitles( ServerProxy ):
  '''
  A python class to download SRT subtitles for opensubtitles.org.
  '''
  api_url     = opensubs_config['url'];                                  # Set the URL
  user_agent  = opensubs_config['user_agent'];                           # Set the user agent for testing
  title       = None
  IMDb        = None
  lang        = ['eng']
  verbose     = False
  nSubs       = 1
  sort        = 'score'
  track_num   = None
  get_forced  = False

  server_lang = 'en';                                                    # Set up the server
  attempts    = 10;
  def __init__( self, username = '', userpass = '', verbose = False):
    '''
    Name:
       __init__
    Purpose:
       A pyhton function to initialize the opensubtitles class.
    Inputs:
       None.
    Outputs:
       Save an SRT subtitle file with same convetion as movie
       file IF a subtitle is found.
    Keywords:
      username   : User name for opensubtitles.org.
      userpass   : Password for opensubtitles.org. Recommend that
                    this be the md5 hash of the password and not
                    the plain text of the password for slightly
                    better security
    Example:
      To download the top 5 subtiles for foreign language parts and full movie
      based on score in english, the call word look like:
        subs = opensubtitles().getSubtitles('/path/to/file', nSubs=5)
      as the default for sorting is score and english is the
      default language.
      
      To download the 5 newest subtitles in Russian for foreign 
      language parts and full movie the call word look like:
        subs = opensubtitles('/path/to/file', lang='rus', nSubs=5, sort='date')
    Author and history:
       Kyle R. Wodzicki     Created 12 Sep. 2017
         Modified 21 Sep. 2017 by Kyle R. Wodzicki
           - Added 0.3 second sleeps in search function so that 
             40 requests per 10 second limit is never reached.
           - Added the username and userpass keywords for so
              users can login using their accounts if they like. 
        
         Some code borrowed from
           https://github.com/chripede/opensubtitle-downloader
    '''
    super().__init__( opensubs_config['url'], verbose=False )

    self.log         = logging.getLogger(__name__);
  
    self.username    = '' if username is None else username;                     # Set username attribute 
    self.userpass    = '' if userpass is None else userpass;                     # Set userpass attribute
    self.verbose     = verbose;
    self.subs        = None;
    
    self.login_token = None;                                                    # Set the login token

  ##############################################################################        
  def _parseKwargs(self, **kwargs):
    '''
    Purpose:
      Method to parse keyword arguments into class attributes
    '''
    self.title      = kwargs.get('title',      None)
    self.IMDb       = kwargs.get('IMDb',       None)
    self.lang       = kwargs.get('lang',       None)
    self.verbose    = kwargs.get('verbose',    False)
    self.nSubs      = kwargs.get('nSubs',      1)
    self.sort       = kwargs.get('sort',       'score').lower()
    self.track_num  = kwargs.get('track_num',  None)
    self.get_forced = kwargs.get('get_forced', False)

    if self.track_num: self.track_num = int( self.track_num )
    if not isinstance(self.lang, (tuple, list,)):                               # Make sure lang attribute is iterable
      self.lang = [self.lang]
    if (len(self.lang) == 0):
      self.lang = ['eng']

  ##############################################################################        
  def getSubtitles(self, file, **kwargs):
    '''
    Attempt to log-in to, download from, and log-out of the server.
    No user interaction requried.
    Inputs:
       file : Full path to the movie file to download SRT file for.
    Outputs:
       Save an SRT subtitle file with same convetion as movie
       file IF a subtitle is found.
    Keywords:
       title   : Set to title of movie to search for. Default is to use
                  title from file.
       imdb    : Set to IMDb id of moive to search for. Default is to
                  try to get IMDb id from file name.
       lang    : String of list of strings to language to download
                  subtitle in using ISO 639-2 code. Default is english (eng).
       verbose : Set to True to increase verbosity. Default: False
       nSubs   : Set to the number of files subtitles to download
                  for each file. Default is one (1).
       sort    : Set the sorting method used for downloading.
                  Options are:
                    score     : Sort based on score
                    downloads : Sort based on number of times downloaded
                    date      : Sort based on upload date
                  All of the sorting is done in descending order.
                  Default is score.
      track_num  : Set to specific 'track' number for labeling.
                     Default is to start at zero.
      get_forced : Set to True to get only forced subtitles.
                     Default is to get full.
    '''
    self._parseKwargs( **kwargs )
    self.login();
    self.searchSubs(file = file);
    files = self.saveSRT( file = file );
    self.logout()
    return files

  ##############################################################################        
  def searchSubs(self, **kwargs):
    '''
    A python function to search for, download, and save subtitles.
    '''
    if self.login_token is None: return;
    self.log.info("Searching for subtitles...");

    search  = {'sublanguageid' : ','.join( kwargs.get('lang', self.lang) )};    # Initialize search attribute with language(s) set; keyword input overrides class attribute lang
    if ('IMDb' in kwargs) or self.IMDb:                                         # If IMDb is input
      search['imdbid'] = kwargs.get('IMDb', self.IMDb).replace('tt','');        # Use imdb if it is set
    elif ('title' in kwargs) or self.title:                                     # Else if a title is input
      search['movie name'] = kwargs.get('title', self.title);                   # Use it
    elif ('file' in kwargs):                                                    # Else, if file is set use information from the file name
      file = kwargs.get('file')
      tmp  = os.path.basename(file).split('.');                                 # Split file basename on period
      id   = -2 if file.lower().endswith( ext ) else -1;                        # Index of where IMDb id is supposed to be based on whether there is a file extension or not
      if len(tmp) > 1:                                                          # If there is more than one element in the list after split on period
        if len(tmp[id]) > 2:                                                    # If the length of the value where the IMDb id should be is greater than two (2)
          if tmp[id][:2] == 'tt':                                               # If the first two (2) letters of the second last string are tt
            search['imdbid'] = tmp[id][2:];                                     # Assume it is the IMDb ID
      if 'imdbid' not in search:                                                # If imdbid is NOT defined
        search['movie name'] = tmp[0];                                          # Take first string as the title
        
    if ('imdbid' in search) or ('movie name') in search:
      for i in range(self.attempts):                                            # Try n times to log in
        try:                                                                    # Try to...
          resp = self.SearchSubtitles(self.login_token, [ search ]);            # Search for movies
        except:                                                                 # On exception...
          time.sleep(1);                                                        # Sleep for one (1) second
        else:                                                                   # If the try is successful...
          if self.check_status( resp ):                                         # Get server status
            time.sleep(0.3);                                                    # Sleep 0.3 seconds so that request limit is NOT reached
            if resp['data'] == False:                                           # If the data tag in the response is False
              self.log.info("No subtitles found"); return;                      # Print log and return
            elif len(resp['data']) == 0:                                        # Else, if the data tag has a length of zero (0)
              self.log.info("No subtitles found"); return;                      # Print log and return
            self.sortSubs( resp['data'] );                                      # Sort the subtitles
            return;                                                             # Return from the function
    return

  ##############################################################################        
  def sortSubs( self, sub_data ):
    '''
    A function for sorting the subtitles by score, download count, and date.
    '''
    self.subs = {};                                                             # Set subs to empty dictionary
    keys = ( ('Score', 'score'), ('SubDownloadsCnt', 'downloads'), ('SubAddDate', 'date') );
    for lang in self.lang:                                                      # Iterate over all languages
      self.subs[lang] = {'score' : None, 'downloads' : None, 'date' : None};    # Initialize dictionary to store sorted subtitle information
      subs = []
      for sub in sub_data:
        if type(sub) is str: sub = sub_data[sub];                               # If sub is type string, then assume sub_data is a dictionary and set sub to information for key 'sub'
        test = int(sub['SubBad'])  != 1      and \
               sub['SubFormat']     == 'srt' and \
               sub['SubLanguageID'] == lang
        if test:
          if self.get_forced:
            if int( sub['SubForeignPartsOnly'] ) == 1:
              subs.append( sub );
          elif int( sub['SubForeignPartsOnly'] ) == 0:
            subs.append( sub );
      for sub in subs:
        if len(sub) == 0:
          self.subs[lang] = None;
        else:                                                                   # Work on sub titles will all movie text if any were found
          for key in keys:                                                      # Iterate over the keys
            self.subs[lang][key[1]] = [];                                       # Set the value for the dictionary key to an empty list
            vals  = [ i[ key[0] ] for i in subs ];                              # Get values to sort
            index = sorted( range(len(vals)), key=vals.__getitem__, reverse=True);# Get indices, in reverse order, for sorting
            for i in index: self.subs[lang][key[1]].append( subs[i] );          # Append the dictionaries to the subs_all attribute in descending order

  ##############################################################################        
  def saveSRT( self, file = '' ):
    '''
    A python function to save the SRT subtitle data.
    '''
    files = []                                                                  # List of all downloaded files
    if self.subs is None: return;
    track = -1 if self.track_num is None else self.track_num - 1;
    if file.lower().endswith( ext ):                                       # If the file name has any of these extensions
      srt_base = '.'.join(file.split('.')[:-1]);                           # Remove the extension
    else:                                                                       # Else, assumes there is NO extension
      srt_base = file;                                                     # Use input file path

    for lang in self.lang:
      self.log.info('Language: {:}, forced: {:}'.format(lang,self.get_forced));
      subs = self.subs[lang][self.sort]
      if subs is None:
        self.log.info('  No subtitle(s) found');
        continue;

      for i in range( self.nSubs ):                                             # Iterate over number of subtitle files to grab
        if i >= len(subs): break;                                               # Break the loop if i is too large
        track += 1;                                                             # Increment the track counter

        srt = '{}.{:d}.{:}'.format(srt_base, track, lang);                      # Add the subtitle track number and language code to the file name
        if self.get_forced: srt = '{}.forced'.format(srt)                       # Append forced if forced flag set
        srt = '{}.srt'.format(srt)

        if os.path.isfile( srt ):
          self.log.info('  File already exists...Skipping!');
          files.append( srt )
          continue;

        dir = os.path.dirname( srt );
        if not os.path.isdir( dir ): os.makedirs( dir );                        # Create output directory if it does NOT exist
        data = self.download( subs[i] );                                        # Download and decompress the data
        if data is not None:
          with open(srt, 'wb') as f: f.write( data );                           # Write the data
          files.append( srt )
    return files

  ##############################################################################        
  def download( self, sub ):
    '''
    A function to download subtitle file and return the decompressed data.
    '''
    self.log.info('  Downloading subtitle...');                                 # Print to log
    for i in range(self.attempts):                                              # Try n times to download
      try:                                                                      # Try to ...
        resp = self.DownloadSubtitles(self.login_token, 
          [ sub['IDSubtitleFile'] ] );                                          # Download the subtitle
      except:                                                                   # On exception...
        time.sleep(0.5);                                                        # Sleep for half (0.5) a second
      else:                                                                     # If download was successful
        if self.check_status(resp):                                             # If the response is Okay
          tmp = resp['data'][0]['data'].encode('ascii');                        # Encode the data to ascii
          if type(tmp) is str:                                                  # If the type of tmp is string
            decoded = standard_b64decode(tmp);                                  # Decode the data
          else:                                                                 # Else.
            decoded = standard_b64decode(resp['data'][0]['data']);              # Decode the data
          return decompress(decoded, 15 + 32);                                  # Return decompressed data
    self.log.error('  Failed to download subtitle!');                           # Log error
    return None;                                                                # If reached here, the data did NOT download correctly

  ##############################################################################
  # Login / Logout / Check_status
  def login(self):
    '''Log in to OpenSubtitles'''
    self.log.info("Login to opensubtitles.org...");                             # Print log for logging in
    for i in range(self.attempts):                                              # Try n times to log in
      try:                                                                      # Try to...
        resp = self.LogIn(self.username, self.userpass, 
          self.server_lang, self.user_agent);                                   # login to opensubtitles.org
      except:                                                                   # On exception...
        time.sleep(1);                                                          # Sleep for one (1) second
      else:                                                                     # If try is successful...
        if self.check_status( resp ):                                           # If the response is Okay
          self.login_token = resp['token'];                                     # Set the login token
          return;                                                               # Return from function
    # If get to here, login failed
    self.log.error( "Failed to login!" );                                       # Print log
    self.login_token = None;                                                    # Set the login token to None
  def logout(self):
    '''Log out from OpenSubtitles'''
    if self.login_token is None: return;                                        # If the login token is None, then NOT logged in and just return
    self.log.info("Logout of opensubtitles.org...");                            # Print log for logging out
    for i in range(self.attempts):                                              # Try n times to log in
      try:                                                                      # Try to...
        resp = self.LogOut(self.login_token);                            # Logout of opensubtitles.org
      except:                                                                   # On exception...
        time.sleep(1);                                                          # Sleep for one (1) second
      else:                                                                     # If try is successful...
        if self.check_status( resp ):                                           # Check logout status
          self.login_token = None;                                              # Reset login token to None.
          return;                                                               # Return from function
    # If get to here, logout failed
    self.log.error( "Failed to logout!" );                                      # Print error to log
    self.login_token = None;                                                    # Reset login token to None.
  def check_status(self, resp):
    '''Check the return status of the request.
    Anything other than "200 OK" raises a UserWarning
    '''
    try:
      if resp['status'].upper() != '200 OK':
        self.log.error( "Response error from " + self.api_url );
        self.log.error( "Response status was: " + resp['status'] );
        return False;
      return True;
    except:
      self.log.error( "No response from API!" );
      return False;

################################################################################
# Set up command line arguments for the function
if __name__ == "__main__":
  import argparse;                                                              # Import library for parsing
  parser = argparse.ArgumentParser(description="OpenSubtitles");                # Set the description of the script to be printed in the help doc, i.e., ./script -h
  parser.add_argument("file",   type=str, help="Path to file subtitles are for."); 
  parser.add_argument("--imdb", type=str, help="IMDb id starting with tt."); 
  args = parser.parse_args();                                                   # Parse the arguments

  logger = logging.getLogger('__main__');                                       # Load logger on command line run
  logger.setLevel(logging.INFO);                                               # Set log level to debug
  sh = logging.StreamHandler();                                                 # Load a stream handler
  logger.addHandler(sh);                                                        # Add the stream handler to the logger
  
  files = opensubtitles().getSubtitles( args.file, IMDb = args.imdb )
#   exit( x );
