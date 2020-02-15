import logging
import os, re
from datetime import timedelta
from subprocess import Popen, PIPE, STDOUT, DEVNULL

from .utils.checkCLI import checkCLI

try:
  COMSKIP = checkCLI( 'comskip' )
except:
  logging.getLogger(__name__).error( "comskip is NOT installed or not in your PATH!" )
  COMSKIP = None

from . import POPENPOOL

#from .utils.subprocManager import SubprocManager;

# Following code may be useful for fixing issues with audio in
# video files that cut out
# ffmpeg -copyts -i "concat:in1.ts|in2.ts" -muxpreload 0 -muxdelay 0 -c copy joint.ts

class ComRemove( object ):
  # _comskip = ['comskip', '--hwassist', '--cuvid', '--vdpau'];
  _comskip = ['comskip'];
  _comcut  = ['ffmpeg', '-nostdin', '-y', '-i'];
  _comjoin = ['ffmpeg', '-nostdin', '-y', '-i'];

  ########################################################
  def __init__(self, **kwargs):
    '''
    Keywords:
      ini      : Path to comskip.ini file for comskip settings
      threads  : Number of threads comskip is allowed to use
      cpulimit : Set limit of cpu usage per thread
      verbose  : Depricated
    ''' 
    super().__init__( **kwargs );
    self.__log      = logging.getLogger(__name__);
    if ('ini' in kwargs):
      self.ini = kwargs['ini']
    else:
      self.ini = os.environ.get('COMSKIP_INI', None)
    self.threads  = kwargs.get('threads',  POPENPOOL.threads)
    self.cpulimit = kwargs.get('cpulimit', None)
    self.verbose  = kwargs.get('verbose',  None)
    self.__outDir   = None;
    self.__fileExt  = None;

  ########################################################
  def removeCommercials(self, in_file, chapters = False ):
    '''
    Purpose:
      Main method for commercial identification and removal.
    Inputs:
      in_file  : Full path of file to run commercial removal on
    Outputs:
      boolean
    Kewords:
      chapters : Set for non-destructive commercial 'removal'.
                  If set, will generate .chap file containing
                  Show segment and commercial break chapter info
                  for FFmpeg.
    '''
    self.__outDir  = os.path.dirname( in_file )                                     # Store input file directory in attribute
    self.__fileExt = in_file.split('.')[-1]                                         # Store Input file extension in attrubute
    edl_file     = None
    tmp_Files    = None                                                             # Set the status to True by default
    cut_File     = None
    status       = False
    edl_file     = self.comskip( in_file )                                          # Attempt to run comskip and get edl file path
    if edl_file:                                                                    # If eld file path returned
      if chapters:                                                                  # If chapters keyword set
        status = self.comchapter( in_file, edl_file )                               # Generate .chap file
        os.remove(edl_file)                                                         # Delete to edl file
      else:                                                                         # Else, actually cut up file to remove commercials
        tmp_Files  = self.comcut( in_file, edl_file )                               # Run the comcut method to extract just show segments; NOT comercials
        if tmp_Files:                                                               # If list of tmp_Files returned; None on failure
          cut_File   = self.comjoin( tmp_Files )                                    # Attempt to join the files and update status using return code from comjoin
        if cut_File:                                                                # If path to output file returned; None on failure
          self.check_size( in_file, cut_File )                                      # Check size to see that not too much removed
          status = True                                                             # Set status to True

    self.__outDir  = None                                                           # Reset attribute
    self.__fileExt = None                                                           # Reset attribute

    return status                                                                   # Return the status 

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
    if not COMSKIP:
      self.__log.info('comskip utility NOT found!')
      return None 

    self.__log.info( 'Running comskip to locate commercial breaks')
    if (self.__outDir  is None): self.__outDir  = os.path.dirname( in_file );                                  # Store input file directory in attribute
    if (self.__fileExt is None): self.__fileExt = in_file.split('.')[-1];                                      # Store Input file extension in attrubute
    
    cmd = self._comskip.copy();
    cmd.append( '--threads={}'.format(self.threads) );
    
    tmp_file  = os.path.splitext( in_file )[0];                            # Get file path with no extension
    edl_file  = '{}.edl'.format(      tmp_file );                               # Path to .edl file
    txt_file  = '{}.txt'.format(      tmp_file );                               # Path to .txt file
    logo_file = '{}.logo.txt'.format( tmp_file );                               # Path to .logo.txt file
    
    cmd.append( '--output={}'.format(self.__outDir) );
    cmd.extend( [in_file, self.__outDir] );
    
    self.__log.debug( 'comskip command: {}'.format(' '.join(cmd)) );              # Debugging information
    proc = POPENPOOL.Popen_async(cmd, threads = self.threads)
#    if self.verbose:
#      self.addProc(cmd, stdout = log, stderr = err);
#    else:
#      self.addProc(cmd);
    if not proc.wait( timeout = 8 * 3600 ):                                     # Wait for 8 hours for comskip to finish; this should be more than enough time
      self.__log.error('comskip NOT finished after 8 hours; killing')
      proc.kill()
      
    if proc.returncode == 0:
      self.__log.info('comskip ran successfully');
      if not os.path.isfile( edl_file ):
        self.__log.warning('No EDL file was created; trying to convert TXT file')
        edl_file = self.convertTXT( txt_file, edl_file )
      for file in [txt_file, logo_file]:
        try:
          os.remove( file );
        except:
          pass
      return edl_file;
      
    self.__log.warning('There was an error with comskip')
    for file in [txt_file, edl_file, logo_file]:
      try:
        os.remove(file)
      except:
        pass

    return None;

  ########################################################
  def comchapter(self, in_file, edl_file):
    '''
    Purpose:
      Method to create an ffmpeg metadata file that
      contains chatper information marking commercials.
      These metadata will be written to in_file
    Inputs:
      in_file  : Full path of file to run comskip on
      edl_file : Full path of .edl file produced by
    Outputs:
      Boolean, True if success, False if failed
    '''
    self.__log.info('Generating metadata file')
    chpFMT      = '[CHAPTER]\nTIMEBASE=1/1000\nSTART={}\nEND={}\ntitle={}\n'

    fDir, fBase = os.path.split( in_file )                                              # Split file path to get directory path and file name
    fName, fExt = os.path.splitext( fBase )                                             # Split file name and extension
    metaFile    = os.path.join( fDir, '{}.chap'.format(fName) )                 # Generate file name for chapter metadata

    fileLength  = self.getVideoLength(in_file)
    segment     = 1
    commercial  = 1

    mid         = open(metaFile, 'w')                                                   # Open metadata file for writing
    mid.write( ';FFMETADATA1\n' )                                                       # Write header to file

    segStart    = timedelta( seconds = 0.0 );                                      # Initial start time of the show segment; i.e., the beginning of the recording
    with open(edl_file, 'r') as fid:                                             # Open edl_file for reading
      info        = fid.readline();                                                  # Read first line from the edl file
      while info:                                                                 # While the line is NOT empty
        comStart, comEnd = info.split()[:2];                                      # Get the start and ending times of the commercial
        comStart   = timedelta( seconds = float(comStart) );                      # Get start time of commercial as a time delta
        comEnd     = timedelta( seconds = float(comEnd) );                        # Get the end time of the commercial as a time delta
        if comStart.total_seconds() > 1.0:                                        # If the start of the commercial is NOT near the very beginning of the file
          # From segStart to comStart is NOT commercial
          sTime    = int(segStart.total_seconds() * 1000)
          eTime    = int(comStart.total_seconds() * 1000)
          mid.write( chpFMT.format(sTime, eTime, 'Show Segment \#{}'.format(segment)) )
          self.__log.debug( 'Show segment {} - {} to {} micros'.format(segment, sTime, eTime) ) 
          # From comStart to comEnd is commercail
          sTime    = eTime
          eTime    = int(comEnd.total_seconds() * 1000)
          mid.write(chpFMT.format(sTime, eTime, 'Commercial Break \#{}'.format(commercial)) )
          self.__log.debug( 'Commercial {} - {} to {} micros'.format(commercial, sTime, eTime) ) 
          # Increment counters
          segment    += 1
          commercial += 1
        segStart = comEnd;                                                        # The start of the next segment of the show is the end time of the current commerical break 
        info     = fid.readline();                                                # Read next line from edl file

    dt = (fileLength - segStart).total_seconds()                                    # Time difference, in seconds, between segment start and end of file
    if (dt >= 5.0):                                                                 # If the time differences is greater than a few seconds
      sTime = int(segStart.total_seconds()   * 1000)
      eTime = int(fileLength.total_seconds() * 1000) 
      mid.write( chpFMT.format(sTime, eTime, 'Show Segment \#{}'.format(segment)) )
 
    mid.close()
    return True 

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
    self.__log.info('Cutting out commercials')
    cmdBase  = self._comcut + [in_file];                                        # Base command for splitting up files
    tmpFiles = [];                                                              # List for all temporary files
    fnum     = 0;                                                               # Set file number to zero
    segStart = timedelta( seconds = 0.0 );                                      # Initial start time of the show segment; i.e., the beginning of the recording
    fid      = open(edl_file, 'r');                                             # Open edl_file for reading
    info     = fid.readline();                                                  # Read first line from the edl file
    procs    = []
    while info:                                                                 # While the line is NOT empty
      comStart, comEnd = info.split()[:2];                                      # Get the start and ending times of the commercial
      comStart   = timedelta( seconds = float(comStart) );                      # Get start time of commercial as a time delta
      comEnd     = timedelta( seconds = float(comEnd) );                        # Get the end time of the commercial as a time delta
      if comStart.total_seconds() > 1.0:                                        # If the start of the commercial is NOT near the very beginning of the file
        segDura  = comStart - segStart;                                         # Get segment duration as time between current commerical start and last commercial end
        outFile  = 'tmp_{:03d}.{}'.format(fnum, self.__fileExt);                  # Set output file name
        outFile  = os.path.join(self.__outDir, outFile);                          # Get file name for temporary file                           
        cmd      = cmdBase + ['-ss', str(segStart), '-t', str(segDura)];        # Append start time and duration to cmdBase to start cuting command;
        cmd     += ['-c', 'copy', outFile];                                     # Append more options to the command
        tmpFiles.append( outFile );                                             # Append temporary output file path to tmpFiles list
        procs.append( POPENPOOL.Popen_async( cmd, threads=1 ) )                 # Add the command to the SubprocManager queue
      segStart = comEnd;                                                        # The start of the next segment of the show is the end time of the current commerical break 
      info     = fid.readline();                                                # Read next line from edl file
      fnum    += 1;                                                             # Increment the file number
    fid.close();                                                                # Close the edl file
    POPENPOOL.wait()
    if sum( [p.returncode for p in procs] ) != 0:                               # If one or more of the process failed
      self.__log.critical( 'There was an error cutting out commericals!' );
      for tmp in tmpFiles:                                                      # Iterate over list of temporary files
        if os.path.isfile( tmp ):                                               # If the file exists
          try:                                                                  # Try to 
            os.remove( tmp );                                                   # Delete the file
          except:                                                               # On exception
            self.__log.warning( 'Error removing file: {}'.format(tmp) );          # Log a warning
      tmpFiles = None;                                                          # Set the tmpFiles variable to None

    self.__log.debug('Removing the edl_file');                                    # Debugging information
    os.remove( edl_file );                                                      # Delete the edl file
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
    self.__log.info( 'Joining video segments into one file')
    inFiles = '|'.join( tmpFiles );
    inFiles = 'concat:{}'.format( inFiles );
    outFile = 'tmp_nocom.{}'.format(self.__fileExt);                              # Output file name for joined file
    outFile = os.path.join(self.__outDir, outFile);                               # Output file path for joined file
    cmd     = self._comjoin + [inFiles, '-c', 'copy', '-map', '0', outFile];    # Command for joining files
    proc    = POPENPOOL( cmd )                                                        # Run the command
    proc.wait()
    for file in tmpFiles:                                                       # Iterate over the input files
      self.__log.debug('Deleting temporary file: {}'.format(file));               # Debugging information 
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
    self.__log.debug( "Running file size check to make sure too much wasn't removed");
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
    self.__log.info( 
      msg.format(
        self.__size_fmt(in_file_size), self.__size_fmt(cut_file_size)
      )
    );
    if replace:
      os.rename( cut_file, in_file );
    else:
      os.remove( cut_file );

  ########################################################
  def convertTXT( self, txt_file, edl_file ):
    if not os.path.isfile(txt_file):
      self.__log.error('TXT file does NOT exist!')
      return None
    elif os.stat(txt_file).st_size == 0:
      self.__log.warning('TXT file is empty!');
      return None;    

    with open(txt_file, 'r') as txt:
      with open(edl_file, 'w') as edl:
        line = txt.readline();
        rate = int(line.split()[-1])/100.0;
        line = txt.readline();                                                  # Read past a line
        line = txt.readline();                                                  # Read line
        while line != '':                                                       # While the line from the txt file is NOT emtpy
          start, end = [float(i)/rate for i in line.rstrip().split()];          # Strip of return, split line on space, convert each value to float and divide by frame rate
          edl.write( '{:0.2f} {:0.2f} 0\n'.format( start, end ) );              # Write out information to edl file
          line = txt.readline();                                                # Read next line
    return edl_file;                                                            # Return edl_file path

  ########################################################
  def getVideoLength(self, in_file):
    proc = Popen( ['ffmpeg', '-i', in_file], stdout=PIPE, stderr=STDOUT)
    info = proc.stdout.read().decode()
    dur  = re.findall( r'Duration: ([^,]*)', info )
    if (len(dur) == 1):
      hh, mm, ss = [float(i) for i in dur[0].split(':')]
      dur = hh*3600.0 + mm*60.0 + ss
    else:
      dur = 86400.0
    return timedelta( seconds = dur )

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
