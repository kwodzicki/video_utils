import logging;
import os;
from datetime import timedelta;
from subprocess import call, Popen, STDOUT, DEVNULL;

if call(['which', 'comskip'], stdout = DEVNULL, stderr = STDOUT ) != 0:         # If cannot find the ccextractor CLI
  msg = "comskip is NOT installed or not in your PATH!";
  logging.getLogger(__name__).error(msg);
  raise Exception( msg );                 # Raise an exception

from video_utils.utils.subprocManager import subprocManager

# Following code may be useful for fixing issues with audio in
# video files that cut out
# ffmpeg -copyts -i "concat:in1.ts|in2.ts" -muxpreload 0 -muxdelay 0 -c copy joint.ts

class comremove( subprocManager ):
  # _comskip = ['comskip', '--hwassist', '--cuvid', '--vdpau'];
  _comskip = ['comskip'];
  _comcut  = ['ffmpeg', '-nostdin', '-y', '-i'];
  _comjoin = ['ffmpeg', '-nostdin', '-y', '-i'];
  def __init__(self, ini = None, threads = None, cpulimit = None, verbose = None):
    super().__init__();
    self.log      = logging.getLogger(__name__);
    self.ini      = ini if ini else os.environ.get('COMSKIP_INI', None);        # If the ini input value is NOT None, then use it, else, try to get the COMSKIP_INI environment variable
    self.threads  = threads;
    self.cpulimit = cpulimit;
    self.verbose  = verbose;
    self.outDir   = None;
    self.fileExt  = None;
  ########################################################
  def process(self, in_file ):
    self.outDir  = os.path.dirname( in_file );                                  # Store input file directory in attribute
    self.fileExt = in_file.split('.')[-1];                                      # Store Input file extension in attrubute
    edl_file     = None;
    tmp_Files    = None;                                                        # Set the status to True by default
    cut_File     = None;

    edl_file     = self.comskip( in_file );                                     # Attempt to run comskip and get edl file path
    if edl_file:                                                                # If eld file path returned
      tmp_Files  = self.comcut( in_file, edl_file );                            # Run the comcut method to extract just show segments; NOT comercials

    if tmp_Files:                                                               # If status is True
      cut_File   = self.comjoin( tmp_Files );                                   # Attempt to join the files and update status using return code from comjoin

    if cut_File:                                                                 # If status is True
      self.check_size( in_file, cut_File );

    self.outDir  = None;                                                        # Reset attribute
    self.fileExt = None;                                                        # Reset attribute

    return True;                                                              # Return the status 
  ########################################################
  def comskip(self, in_file):
    '''
    Purpose:
      Method to run the comskip CLI to locate commerical breaks
      in the input file
    Inputs:
      in_file : Full path of file to run comskip on
    Outputs:
      Returns path to .edl file produced by comskip IF the 
      comskip runs successfully. If comskip does not run
      successfully, then None is returned.
    '''
    self.log.info( 'Running comskip to locate commercial breaks')
    cmd = self._comskip;
    if self.threads:
      cmd.append( '--threads={}'.format(self.threads) );
    if self.ini:
      cmd.append( '--ini={}'.format(self.ini) );
    
    tmp_file  = '.'.join( in_file.split('.')[:-1] );                            # Get file path with no extension
    edl_file  = '{}.edl'.format(      tmp_file );                               # Path to .edl file
    txt_file  = '{}.txt'.format(      tmp_file );                               # Path to .txt file
    logo_file = '{}.logo.txt'.format( tmp_file );                               # Path to .logo.txt file
    
    cmd.append( '--output={}'.format(self.outDir) );
    cmd.extend( [in_file, self.outDir] );
    self.log.debug( 'comskip command: {}'.format(' '.join(cmd)) );              # Debugging information
    if self.verbose:
      self.addProc(cmd, stdout = log, stderr = err);
    else:
      self.addProc(cmd);
    self.run();

    if sum(self.returncodes) == 0:
      self.log.info('comskip ran successfully');
      try:
        os.remove( txt_file );
      except:
        pass
      return edl_file;
    else:
      self.log.warning('There was an error with comskip')
      return None;
  ########################################################
  def comcut(self, in_file, edl_file):
    '''
    Purpose:
      Method to create intermediate files that do NOT 
      contain comercials.
    Inputs:
      in_file  : Full path of file to run comskip on
      edl_file : Full path of .edl file produced by
    Outputs:
      Returns list of file paths for the intermediate 
      files created if successful. Else, returns None.
    '''
    cmdBase  = self._comcut + [in_file];                                        # Base command for splitting up files
    tmpFiles = [];                                                              # List for all temporary files
    fnum     = 0;                                                               # Set file number to zero
    segStart = timedelta( seconds = 0.0 );                                      # Initial start time of the show segment; i.e., the beginning of the recording
    fid      = open(edl_file, 'r');                                             # Open edl_file for reading
    info     = fid.readline();                                                  # Read first line from the edl file
    while info:                                                                 # While the line is NOT empty
      comStart, comEnd = info.split()[:2];                                      # Get the start and ending times of the commercial
      comStart   = timedelta( seconds = float(comStart) );                      # Get start time of commercial as a time delta
      comEnd     = timedelta( seconds = float(comEnd) );                        # Get the end time of the commercial as a time delta
      segDura    = comStart - segStart;                                         # Get segment duration as time between current commerical start and last commercial end
      outFile  = 'tmp_{:03d}.{}'.format(fnum, self.fileExt);                    # Set output file name
      outFile  = os.path.join(self.outDir, outFile);                            # Get file name for temporary file                           
      tmpFiles.append( outFile );                                               # Append temporary output file path to tmpFiles list
      cmd      = cmdBase + ['-ss', str(segStart), '-t', str(segDura)];          # Append start time and duration to cmdBase to start cuting command;
      cmd     += ['-c', 'copy', '-map', '0', outFile];                          # Append more options to the command
      self.addProc( cmd, single = True );                                       # Add the command to the subprocManager queue
      segStart = comEnd;                                                        # The start of the next segment of the show is the end time of the current commerical break 
      info     = fid.readline();                                                # Read next line from edl file
      fnum    += 1;                                                             # Increment the file number
    fid.close();                                                                # Close the edl file
    self.run();                                                                 # Run all the subprocess
    if sum( self.returncodes ) != 0:
      self.log.critical( 'There was an error cutting out commericals!' );
      tmpFiles = None;                                                          # Set the tmpFiles variable to None

    if tmpFiles:                                                                # Check the tmpFiles variable
      self.log.debug('Removing the edl_file');                                  # Debugging information
      os.remove( edl_file );                                                    # Delete the edl file
    return tmpFiles;
  ########################################################
  def comjoin(self, tmpFiles):
    '''
    Purpose:
      Method to join intermediate files that do NOT 
      contain comercials into one file.
    Inputs:
      tmpFiles : List containing full paths of 
                 intermediate files to join
    Outputs:
      Returns path to continous file created by joining
      intermediate files if joining is successful. Else
      returns None.
    '''
    self.log.info( 'Joining video segments into one file')
    inFiles = '|'.join( tmpFiles );
    inFiles = 'concat:{}'.format( inFiles );
    outFile = 'tmp_nocom.{}'.format(self.fileExt);                              # Output file name for joined file
    outFile = os.path.join(self.outDir, outFile);                               # Output file path for joined file
    cmd     = self._comjoin + [inFiles, '-c', 'copy', '-map', '0', outFile];    # Command for joining files
    self.addProc( cmd );                                                        # Run the command
    self.run();
    for file in tmpFiles:                                                       # Iterate over the input files
      self.log.debug('Deleting temporary file: {}'.format(file));               # Debugging information 
      os.remove( file );                                                        # Delete the temporary file
    if sum(self.returncodes) == 0:
      return outFile;
    else:
      try:
        os.remove( outFile );
      except:
        pass;
      return None;
  ########################################################
  def check_size(self, in_file, cut_file):
    '''
    Purpose:
      To check that the file with no commercials
      is a reasonable size; i.e., check if too much
      has been removed. If the file size is sane,
      then just replace the input file with the 
      cut file (one with no commercials). If the
      file size is NOT sane, then the cut file is
      removed and the original input file is saved
    Inputs:
      in_file  : Full path of file to run comskip on
      cut_file : Full path of file with NO commercials
    Authors:
      Barrowed from https://github.com/ekim1337/PlexComskip
    '''
    self.log.debug( "Running file size check to make sure too much wasn't removed");
    in_file_size  = os.path.getsize( in_file  );
    cut_file_size = os.path.getsize( cut_file );
    replace       = False
    if 1.1 > float(cut_file_size) / float(in_file_size) > 0.5:
      msg     = 'Output file size looked sane, replacing the original: {} -> {}'
      replace = True;
    elif 1.01 > float(cut_file_size) / float(in_file_size) > 0.99:
      msg = 'Output file size was too similar; keeping original: {} -> {}'
    else:
      msg = 'Output file size looked odd (too big/too small); keeping original: {} -> {}'
    self.log.info( 
      msg.format(
        self.__size_fmt(in_file_size), self.__size_fmt(cut_file_size)
      )
    );
    if replace:
      os.rename( cut_file, in_file );
    else:
      os.remove( cut_file );
  ########################################################
  def __size_fmt(self, num, suffix='B'):
    '''
    Purpose:
      Private method for determining the size of 
      a file in a human readable format
    Inputs:
      num  : An integer number file size
    Authors:
      Barrowed from https://github.com/ekim1337/PlexComskip
    '''
    for unit in ['','K','M','G','T','P','E','Z']:
      if abs(num) < 1024.0:
        return "{:3.1f}{}{}".format(num, unit, suffix)
      num /= 1024.0
    return "{:.1f}{}{}".format(num, 'Y', suffix);
