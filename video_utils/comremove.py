import logging;
import os;
from datetime import timedelta;
from subprocess import Popen, STDOUT, DEVNULL;

try:
  from .utils.limitCPUusage import limitCPUusage;
except:
  limitCPUusage = None;



class comremove( object ):
  # _comskip = ['comskip', '--hwassist', '--cuvid', '--vdpau'];
  _comskip = ['comskip'];
  _comcut  = ['ffmpeg', '-nostdin', '-y', '-i'];
  _comjoin = ['ffmpeg', '-nostdin', '-y', '-i'];
  log      = logging.getLogger( __name__ );
  log.setLevel( logging.DEBUG );
  def __init__(self, ini = None, threads = None, cpulimit = None, verbose = None):
    self.ini      = ini if ini else os.environ.get('COMSKIP_INI', None);        # If the ini input value is NOT None, then use it, else, try to get the COMSKIP_INI environment variable
    self.threads  = threads;
    self.cpulimit = cpulimit;
    self.outDir   = None;
    self.fileExt  = None;
  ########################################################
  def run(self, in_file ):
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
  def check_size(self, in_file, cut_file):
    def size_fmt(num, suffix='B'):
      for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
          return "{3.1f}{}{}".format(num, unit, suffix)
        num /= 1024.0
      return "{.1f}{}{}".format(num, 'Y', suffix);

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
        size_fmt(in_file_size), size_fmt(cut_file_size)
      )
    );
    if replace:
      os.rename( cut_file, in_file );
    else:
      os.remove( cut_file );
  ########################################################
  def comjoin(self, tmpFiles):
    inFiles = '|'.join( tmpFiles );
    inFiles = 'concat:{}'.format( inFiles );
    outFile = 'tmp_nocom.{}'.format(self.fileExt);                              # Output file name for joined file
    outFile = os.path.join(self.outDir, outFile);                               # Output file path for joined file
    cmd     = self._comjoin + [inFiles, '-c', 'copy', '-map', '0', outFile];    # Command for joining files
    proc    = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );                  # Run the command
    proc.communicate();                                                         # Wait for command to finish
    for file in tmpFiles:                                                       # Iterate over the input files
      self.log.debug('Deleting temporary file: {}'.format(file));               # Debugging information 
      os.remove( file );                                                        # Delete the temporary file
    if proc.returncode == 0:
      return outFile;
    else:
      try:
        os.remove( outFile );
      except:
        pass;
      return None;
  ########################################################
  def comcut(self, in_file, edl_file):
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
      proc     = Popen( cmd, stdout = DEVNULL, stderr = STDOUT);                # Start ffmpeg command
      proc.communicate();                                                       # Wait for to finish
      if proc.returncode != 0:
        self.log.critical( 'There was an error cutting out commericals!' )
        tmpFiles = None;                                                        # Set the tmpFiles variable to None
        break;                                                                  # Break the while loop
      segStart = comEnd;                                                        # The start of the next segment of the show is the end time of the current commerical break 
      info     = fid.readline();                                                # Read next line from edl file
      fnum    += 1;                                                             # Increment the file number
    fid.close();                                                                # Close the edl file
    if tmpFiles:                                                                # Check the tmpFiles variable
      self.log.debug('Removing the edl_file');                                  # Debugging information
      os.remove( edl_file );                                                    # Delete the edl file
    return tmpFiles;
  ########################################################
  def comskip(self, in_file):
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

    with open(os.path.join(self.outDir, 'comskip.log'), 'w') as log:
      with open(os.path.join(self.outDir, 'comskip.err'), 'w') as err:
        proc = Popen(cmd, stdout = log, stderr = err);
    if limitCPUusage and self.cpulimit:
      CPU_id = limitCPUusage(proc.pid, self.cpulimit, self.threads);            # Run cpu limit command
    proc.communicate();                                                         # Wait for self.handbrake to finish completely

    try:                                                                        # Try to...
      CPU_id.communicate();                                                     # Communicate with CPU_id to wait for it to exit cleanly
    except:                                                                     # On exception
      pass;
    if proc.returncode == 0:
      self.log.info('comskip ran successfully');
      try:
        os.remove( txt_file );
      except:
        pass
      return edl_file;
    else:
      self.log.warning('There was an error with comskip')
      return None;
