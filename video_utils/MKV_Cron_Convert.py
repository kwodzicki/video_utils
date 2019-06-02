import os, sys, setproctitle, time;
sys.path = sys.path[1:];                                                        # Remove parent directory of this file from sys_path so that makemkv_to_mp4 imports correctly

from threading import Thread;
from datetime import datetime;
from subprocess import Popen, PIPE;

from video_utils.version import __version__
from video_utils.videoconverter import videoconverter;

class MKV_Cron_Convert( videoconverter ):
  def __init__(self, in_dir, **kwargs):
    '''
    Keywords:
      Accepts all keywords accepted by videoconveter class
    '''
    self.in_dir        = in_dir;                                                # Set input directory attribute
    self.__out_dir     = kwargs.pop('out_dir', None);
    self.__log_dir     = kwargs.pop('log_dir', None);
    super().__init__( **kwargs );

    self.status        = 0; 
    self.home          = os.path.expanduser("~");                               # Get users home directory path
    self.pid_Name      = 'MakeMKV_Cron';
    self.pid_lock_file = '/tmp/' + self.pid_Name + '.pid';                      # Set up the pid_lock_file name
    self.halt          = False;
    self.logFile       = os.path.join(self.home, 'MKV_Convert.log');            # Path to the log directory
    self.logID         = None;                                                  # File id for the log file

  ##############################################################################
  def run(self):
    '''Function to iterate over files in a directory and convert them.'''
    if os.path.isfile( self.pid_lock_file ):                                    # Check if the pid_lock file exists
      with open(self.pid_lock_file, 'r') as f: pid = f.readline( );             # Write the pid to the file
      ps = Popen( ['ps', '-o', 'comm=', '-p', pid], stdout=PIPE );              # Run a ps command to determine the name of the process running under the PID of the previous call the MKV_Cron_Convert
      ps_output = ps.stdout.read(); ps.stdout.close(); ps.wait();               # Get the output from the command, close the pipe, and wait for the subprocess to finish cleanly
      if self.pid_Name in str(ps_output):                                       # If there is an instance of this script running, then exit the script
        if self._printlog( 'Instance already running' ): return;                # Print message that an instance is running
        self.status = 1; return;                                                # Set status to one (1) and return

    # If the script makes it to here that means either the pid_lock file did NOT
    # exist OR the name of the process running under the PID in the file did NOT
    # match that of this script
    with open(self.pid_lock_file, 'w') as f: f.write( str( os.getpid() ) );     # Write the pid to the file
    setproctitle.setproctitle( self.pid_Name );                                 # Set the process name to pid_Name
    if self._printlog( 'Started' ): return;                                     # Write date of the conversion start to the log file file_num = 1;      
    
    fmt = "{:4d} of {:4d}: {}";                                                 # Set up a formatting string, file number being worked on, and a halt variable
    allFiles     = 0;                                                           # Total number of files processed in all directories
    allStartTime = datetime.now();                                              # Start time for all directories
    for dir in self.in_dir:                                                     # Iterate over all input directories
      if self._printlog( 'Looking for files in: {}'.format( dir ) ): return;    # Print a logging message
      self.out_dir = dir if self.__out_dir is None else self.__out_dir;         # Set output directory to current input directory if the private output directory was NOT set else, use private output directory
      if self.__log_dir is None:                                                # if the private log directory is None
        self.log_dir = os.path.join(self.out_dir, 'logs');                      # Set log directory to current output directory with 'log' appended
      else:                                                                     # Else, the private log directory was set
        self.log_dir = self.__log_dir;                                          # Use the private log directory
      
      file_list = self.get_file_list(dir);                                      # Generate a list of all files in the input directory with a mkv extension
      while len(file_list) > 0 and self.halt is False:                          # While there are files in the file_list and the halt variable is False
        startTime = datetime.now();                                             # Get start time of directory run
        file_num, totFiles = 0, 0;                                              # Initialize file number to zero (0) and totFiles in the directory that have been processed to zero
        for file_path in file_list:                                             # Iterate over each file in file_list variable
          file_base = os.path.basename( file_path );                            # Get base name of the file
          file_num += 1;                                                        # Increment the file number
          file = os.path.basename( file_path );                                 # Get the base name from the file path
          if not os.path.isfile( file_path ):                                   # If the file does NOT exist
            if self._printlog('File not exist: ' + file_base): return;          # Print message that the file does NOT exist
            continue;                                                           # Skip to the next file
          info1 = os.stat( file_path );                                         # Get information about the file,
          time.sleep(10);                                                       # Sleep for 10 seconds
          info2 = os.stat( file_path );                                         # Get information again
          if info1.st_size != info2.st_size:                                    # If the file sizes do NOT match
            msg = 'File size changed (still transferring?): ' + file_base;      # Message to be printed to the log
            if self._printlog( msg ): return;                                   # Print message that the file may be still transferring to the directory
            continue;                                                           # Skip to the next file 
          if self._printlog( fmt.format(file_num, len(file_list), file_base) ): # Write basic information about the file being transcoded to the log file
            return;                                                             # Return
          log_file = os.path.join(self.log_dir, file[:-4] + '.log');            # Set log file based on log_dir and file name
          self._init_logger(log_file);                                          # Initialize the logger
          self.transcode(file_path);                                            # Transcode the file
          if self.transcode_status != 0 and \
             self.transcode_status is not None:                                 # If the transcode_status is NOT zero (0)
            if self._printlog('      There was an error during the transcode!'):# Write error message to log
              return;                                                           # Return
            self.halt = True; break;                                            # Set halt to true and break out of the for loop
          elif self.transcode_status is None:                                   # If the transcode status is None, then output file exists already
            if self._printlog('      Output file exists, skipping!'): return;   # Log a message
          else:                                                                 # Else, the transcode was a success!
            totFiles += 1;                                                      # Increment the total number of files processed in the directory by one
            allFiles += 1;                                                      # Increment the total number of files processed in all directories by one         
          if self.halt:                                                         # If transcode finished but halt has been changed to True
            msg = ['User halted excecution!!!',
                   'Remaining {} file(s) will be transcoded on next run!'];     # List containing messages to log
            msg[-1] = msg[-1].format( len(file_list) - file_num );              # Add number of files into message
            if self._printlog( msg ): return;                                   # Write error message to log
            break;                                                              # Break the while loop

        exTime = datetime.now() - startTime;                                    # Compute execution time
        msg = [ 'Execution time: {}'.format( exTime ) ];                        # Initialize list containing message to print
        if totFiles > 0:                                                        # If at least one (1) file has been processed
          msg.append( 'Averge time per file: {}'.format(exTime / totFiles) );   # Append average execution time per file to message
        msg.append( 'Processed {} file(s) in: {}'.format(file_num, dir) );      # Append more information to message
        if self._printlog( msg ): return;                                       # If message fails to write to file, return
        if not self.halt:                                                       # If halt as not been set to True
          if self._printlog( 'Scanning for new files in: {}'.format( dir ) ):   # Write message that directory is being rescanned;      
            return;
          file_list = self.get_file_list(dir) if self.remove else [];           # Regenerate a list of all files in the input directory with a mkv extension IF the remove key IS set, else, do NOT regenerate file list

      if self.halt: break;                                                      # If halt is True, then break the for loop
    self.halt = True;                                                           # Set halt attribute to True when finishing
    exTime = datetime.now() - allStartTime;                                     # Compute execution time
    msg = [ 'Total execution time: {}'.format( exTime ) ];
    if allFiles > 0: 
      msg += ['Average time per file: {}'.format(exTime / allFiles)];
    msg += [ 'Finished' ];                                                      # List containing messages to log
    if self._printlog( msg ): return;                                           # If the logging fails, return
    try:                                                                        # Try to
      os.remove( self.pid_lock_file );                                          # Delete the pid lock file
    except:                                                                     # On exception
      pass;                                                                     # Do nothing

  ##############################################################################
  def get_file_list(self, dir):
    ''' Function to get files from all input directories'''
    file_list = [];                                                             # Initialize all_files variable as a list
    if not os.path.isdir( dir ):                                                # If the input directory is NOT a directory
      msg = [ 'Requested input directory does NOT exist!', dir ];               # Message to print
      if self._printlog( msg ): return;                                         # Print a message
    else:                                                                       # If the input directory IS a directory
      for file in os.listdir( dir ):                                            # Iterate over file list from given input directory
        if file.endswith('.mkv'):                                               # If the file ends with '.mkv' extension
          file_list.append( os.path.join( dir, file ) );                        # Append the full file path to the file_list variable
      file_list.sort( key = lambda str: str.lower() );                          # Sort the file_list
    return file_list;                                                           # Return the all_files

  ##############################################################################
  def _printlog(self, text):
    '''
    Function to print to a log file. If the leaveOpen
    key is set to True, file is NOT closed when
    function returns
    '''
    stopConvert = False;                                                        # variable to determine if should be stopped
    if type(text) is not list: text = [text];                                   # Make sure text is of type list
    try:                                                                        # Try to...
      self.logID = open(self.logFile, 'a');                                     # Open the log file
    except:                                                                     # On exception...
      self.logID = None;                                                        # Force logID to None;
      print( '\nFailed to open log file for writing! Halting program!' );       # Print message to screen
      print( 'Below is information to be logged:' );                            # Print message to screen
      self.status = 2;                                                          # Set status to 2
      stopConvert = True;                                                       # Set stop convert to True
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S');                        # Get current date
    for i in text:                                                              # Iterate over all strings in text list
      msg  = '{} - {}'.format( date, i );                                       # Message to be printed
      try:                                                                      # Try to...
        self.logID.write( msg + '\n' );                                         # Write information to the log file
      except:                                                                   # On exception...
        print( msg );                                                           # Print message to the screen
        self.status = 2;                                                        # Set status to 2
        stopConvert = True;                                                     # Set stop convert to True
    try:                                                                        # Try to...
      self.logID.close();                                                       # Close the file
    except:                                                                     # On exception...
      print( '\nFailed to close log file, halting!' );                          # Print a message
      self.status = 2;                                                          # Set status to 2
      stopConvert = True;                                                       # Set stopConvert to True
    return stopConvert;                                                         # Return the stop message

