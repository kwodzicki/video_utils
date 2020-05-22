import logging
import os, re
from datetime import timedelta

from . import config
from .utils.checkCLI import checkCLI
from .utils.ffmpeg_utils import getVideoLength, FFMetaData
from .utils.handlers import RotatingFile

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
    """
    Initialize the COmRemove class

    Keyword arguments:
      iniDir (str): Path to directory containing .ini files for
                   comskip settigs. If set, will try to find
                   .ini file with same name as TV show series,
                   falling back to comskip.ini if not found.
                   Default is to use .ini included in pacakge.
      threads (int): Number of threads comskip is allowed to use
      cpulimit (int): Set limit of cpu usage per thread
      verbose  (bool): Depricated

    """

    super().__init__( **kwargs );
    self.__log = logging.getLogger(__name__);

    threads    = kwargs.get('threads',  None)                                           # Set number of threads process will use
    if not isinstance(threads, int):                                                    # If threads is not integer type, use number of threads in POPENPOOL
      threads = POPENPOOL.threads

    iniDir     = kwargs.get('iniDir', None)                                             # Get iniDir from kwargs, returning None if it does not exist
    if iniDir is None:                                                                  # If iniDir is None
      iniDir = os.environ.get('COMSKIP_INI_DIR', None)                                  # Try to get from environment; return None if not exist
      if iniDir is None:                                                                # If iniDir is still None
        iniDir = config.CONFIG.get('COMSKIP_INI_DIR', None)                             # Try to get from CONFIG; return None if not exist
    if iniDir is not None:                                                              # If iniDir is not None
      if not os.path.isdir( iniDir ):                                                   # If path does not exist
        iniDir = None                                                                   # Set iniDir to None

    comskip_log      = kwargs.get('comskip_log', None)
    if comskip_log is None:
      comskip_log = config.getComskipLog( self.__class__.__name__ )
    self.iniDir      = iniDir                                                              # Set attribute 
    self.threads     = threads                                                             # Set number of threads process will use; default is number of threads in POPENPOOL
    self.comskip_log = comskip_log 
    self.cpulimit    = kwargs.get('cpulimit',    None)
    self.verbose     = kwargs.get('verbose',     None)
    self.__outDir    = None
    self.__fileExt   = None

  ########################################################
  def removeCommercials(self, in_file, chapters = False, name = '' ):
    """
    Main method for commercial identification and removal.

    Arguments:
      in_file (str): Full path of file to run commercial removal on

    Keyword arguments:
      chapters (bool): Set for non-destructive commercial 'removal'.
        If set, will generate .chap file containing show segment and
        commercial break chapter info for FFmpeg.
      name (str): Name of series or movie (Plex convention). Required
        if trying to use specific comskip.ini file

    Returns:
      If chapters is True, returns string to ffmpeg metadata file on
      success, False otherwise.
      if Chapters is False, returns True on success, False otherwise

    """

    self.__outDir  = os.path.dirname( in_file )                                     # Store input file directory in attribute
    self.__fileExt = in_file.split('.')[-1]                                         # Store Input file extension in attrubute
    edl_file     = None
    tmp_Files    = None                                                             # Set the status to True by default
    cut_File     = None
    status       = False
    edl_file     = self.comskip( in_file, name = name )                             # Attempt to run comskip and get edl file path
    if edl_file:                                                                    # If eld file path returned
      if os.path.getsize( edl_file ) == 0:                                          # If edl_file size is zero (0)
        status = True                                                               # Set status True
        os.remove(edl_file)                                                         # Delete to edl file
      elif chapters:                                                                # If chapters keyword set
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
  def comskip(self, in_file, name = ''):
    """
    Method to run the comskip CLI to locate commerical breaks in the input file

    Arguments:
      in_file (str): Full path of file to run comskip on

    Keyword arguments:
      name (str): Name of series or movie (Plex convention). Required
        if trying to use specific comskip.ini file

    Returns:
      Path to .edl file produced by comskip IF the 
      comskip runs successfully. If comskip does not run
      successfully, then None is returned.

    """

    if not COMSKIP:
      self.__log.info('comskip utility NOT found!')
      return None 

    self.__log.info( 'Running comskip to locate commercial breaks')
    if (self.__outDir  is None): self.__outDir  = os.path.dirname( in_file );                                  # Store input file directory in attribute
    if (self.__fileExt is None): self.__fileExt = in_file.split('.')[-1];                                      # Store Input file extension in attrubute
    
    cmd = self._comskip.copy();
    cmd.append( '--threads={}'.format(self.threads) )
    cmd.append( '--ini={}'.format( self._getIni(name=name) ) )

    tmp_file  = os.path.splitext( in_file )[0];                            # Get file path with no extension
    edl_file  = '{}.edl'.format(      tmp_file );                               # Path to .edl file
    txt_file  = '{}.txt'.format(      tmp_file );                               # Path to .txt file
    logo_file = '{}.logo.txt'.format( tmp_file );                               # Path to .logo.txt file
    
    cmd.append( '--output={}'.format(self.__outDir) );
    cmd.extend( [in_file, self.__outDir] );
    self.__log.debug( 'comskip command: {}'.format(' '.join(cmd)) );              # Debugging information

    if self.comskip_log:
      kwargs = {'stdout'             : RotatingFile( self.comskip_log ),
                'universal_newlines' : True}
    else:
      kwargs = {}
    proc = POPENPOOL.Popen_async(cmd, threads = self.threads, **kwargs)

    if not proc.wait( timeout = 8 * 3600 ):                                     # Wait for 8 hours for comskip to finish; this should be more than enough time
      self.__log.error('comskip NOT finished after 8 hours; killing')
      proc.kill()
    if proc.returncode == 0 or proc.returncode == 1:
      self.__log.info('comskip ran successfully')
      if proc.returncode == 1:
        self.__log.info('No commericals detected!')
      elif not os.path.isfile( edl_file ):
        self.__log.warning('No EDL file was created; trying to convert TXT file')
        edl_file = self.convertTXT( txt_file, edl_file )
      for file in [txt_file, logo_file]:
        try:
          os.remove( file )
        except:
          pass
      return edl_file
      
    self.__log.warning('There was an error with comskip')
    for file in [txt_file, edl_file, logo_file]:
      try:
        os.remove(file)
      except:
        pass

    return None

  ########################################################
  def comchapter(self, in_file, edl_file):
    """
    Create an ffmpeg metadata file containing chatper information for commercials.

    The edl file created by comskip is parsed into an FFMETADATA file. This
    file can then be passed to ffmpeg to create chapters in the output file
    marking show and commercial segments.

    Arguments:
      in_file (str): Full path of file to run comskip on
      edl_file (str): Full path of .edl file produced by

    Returns:
      str: Path to ffmpeg metadata file

    """

    self.__log.info('Generating metadata file')

    showSeg     = 'Show Segment \#{}'
    comSeg      = 'Commercial Break \#{}'
    segment     = 1
    commercial  = 1
    segStart    = 0.0                                                                   # Initial start time of the show segment; i.e., the beginning of the recording

    fDir, fBase = os.path.split( in_file )                                              # Split file path to get directory path and file name
    fName, fExt = os.path.splitext( fBase )                                             # Split file name and extension
    metaFile    = os.path.join( fDir, '{}.chap'.format(fName) )                         # Generate file name for chapter metadata

    fileLength  = getVideoLength(in_file)

    ffmeta      = FFMetaData()
    with open(edl_file, 'r') as fid:                                                    # Open edl_file for reading
      info = fid.readline();                                                            # Read first line from the edl file
      while info:                                                                       # While the line is NOT empty
        comStart, comEnd = map(float, info.split()[:2])                                 # Get the start and ending times of the commercial as float
        if comStart > 1.0:                                                              # If the start of the commercial is NOT near the very beginning of the file
          # From segStart to comStart is NOT commercial
          title = showSeg.format(segment)
          ffmeta.addChapter( segStart, comStart, title ) 
          self.__log.debug( '{} - {:0.2f} to {:0.2f} s'.format(title, segStart, comStart) ) 
          # From comStart to comEnd is commercial
          title = comSeg.format(commercial)
          ffmeta.addChapter( comStart, comEnd, title )
          self.__log.debug( '{} - {:0.2f} to {:0.2f} s'.format(title, comStart, comEnd) ) 
          # Increment counters
          segment    += 1
          commercial += 1
        segStart = comEnd                                                               # The start of the next segment of the show is the end time of the current commerical break 
        info     = fid.readline()                                                       # Read next line from edl file

    if (fileLength - segStart) >= 5.0:                                                                 # If the time differences is greater than a few seconds
      ffmeta.addChapter( segStart, fileLength, showSeg.format(segment) )
 
    ffmeta.save( metaFile )

    return metaFile 

  ########################################################
  def comcut(self, in_file, edl_file):
    """
    Method to create intermediate files that do NOT contain comercials.

    Arguments:
      in_file (str): Full path of file to run comskip on
      edl_file (str): Full path of .edl file produced by

    Returns:
      list: File paths for the intermediate files created if successful. Else, returns None.

    """

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
    """
    Method to join intermediate files that do NOT contain comercials into one file.

    Arguments:
      tmpFiles (list): Full paths of intermediate files to join

    Returns:
      Returns path to continous file created by joining
      intermediate files if joining is successful. Else
      returns None.

    """

    self.__log.info( 'Joining video segments into one file')
    inFiles = '|'.join( tmpFiles );
    inFiles = 'concat:{}'.format( inFiles );
    outFile = 'tmp_nocom.{}'.format(self.__fileExt);                                    # Output file name for joined file
    outFile = os.path.join(self.__outDir, outFile);                                     # Output file path for joined file
    cmd     = self._comjoin + [inFiles, '-c', 'copy', '-map', '0', outFile];            # Command for joining files
    proc    = POPENPOOL.Popen_async( cmd )                                              # Run the command
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
    """
    Check that the file with no commercials is a reasonable size

    A check to see if too much has been removed. If the file size is sane,
    then just replace the input file with the cut file (one with no commercials).
    If the file size is NOT sane, then the cut file is removed and the original 
    input file is saved.
    Borrowed from https://github.com/ekim1337/PlexComskip

    Arguments:
      in_file (str): Full path of file to run comskip on
      cut_file (str): Full path of file with NO commercials

    Returns:
      None

    """

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
    """
    Convert txt file created by comskip to edl_file

    Arguments:
      txt_file (str): Path to txt_file
      edl_file (str): Path to edl_file

    Keyword arguments:
      None

    Returns:
      str: Path to edl file

    """

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
  def _getIni( self, name = '' ):
    """
    Method to get name of .ini file to use for commercial removal

    Arguments:
      None.

    Keyword arguments:
      name (str): Plex formatted TV series or Movie name.

    Returns:
      str: Path to Comskip INI file to use for commercial removal

    """

    if self.iniDir:                                                                     # If the iniDir is defined
      if name != '':                                                                    # If name not empty
        ini = os.path.join( self.iniDir, '{}.ini'.format(name) )                        # Define path
        if os.path.isfile( ini ):                                                       # If file exists
          return ini                                                                    # Return path
      ini  = os.path.join( self.iniDir, 'comskip.ini' )                                 # Set path default for user defined directory
      if os.path.isfile( ini ):                                                         # If the file exists
        return ini                                                                      # Return path
    return config.COMSKIPINI                                                            # Return default file

  ########################################################
  def __size_fmt(self, num, suffix='B'):
    """
    Private method for determining the size of a file in a human readable format
      
    Borrowed from https://github.com/ekim1337/PlexComskip

    Arguments:
      num (int) : File size

    """

    for unit in ['','K','M','G','T','P','E','Z']:
      if abs(num) < 1024.0:
        return "{:3.1f}{}{}".format(num, unit, suffix)
      num /= 1024.0
    return "{:.1f}{}{}".format(num, 'Y', suffix);
