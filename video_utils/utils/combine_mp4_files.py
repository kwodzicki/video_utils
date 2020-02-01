#!/usr/bin/env python
import logging;
import os;

from ..utils.subprocManager import SubprocManager

def combine_mp4_files(inFiles, outFile):
  '''
  Purpose:
    Function for combining multiple (2+) mp4 files into a single
    mp4 file. Needs the ffmpeg CLI
  Inputs
    inFiles : List of input file paths
    outFile : Output (combined) file path
  Outputs:
    Creates a new combined mp4 file
  Keywords:
    None.
  '''
  log = logging.getLogger( __name__ )
  if len(inFiles) < 2:                                                          # If there are less than 2 ipputs
    log.critical('Need at least two (2) input files!')
    return;                                                                     # Return from function
  manager = SubprocManager();                                                   # Initialize SubprocManager instance
  tmpFiles = [ '.'.join(f.split('.')[:-1])+'.ts' for f in inFiles];             # Iterate over inFiles list and create intermediate TS file paths

  cmdTS = ['ffmpeg', '-y', '-nostdin', 
    '-i',      '', 
    '-c',     'copy', 
    '-bsf:v', 'h264_mp4toannexb',
    '-f',     'mpegts', ''
  ];                                                                            # List with options for creating intermediate files
  cmdConcat = ['ffmpeg', '-nostdin', 
    '-i',     'concat:{}'.format( '|'.join(tmpFiles) ),
    '-c',     'copy', 
    '-bsf:a', 'aac_adtstoasc',
    outFile
  ];                                                                            # List with options for combining TS files back into MP4
  for i in range(len(inFiles)):                                                 # Iterate over all the input files
    cmdTS[3], cmdTS[-1] = inFiles[i], tmpFiles[i];                              # Set input/output files in the cmdTS list
    manager.addProc( cmdTS );                                                   # Add command to the process manager
  manager.run();                                                                # Run all the processes
  manager.addProc( cmdConcat );                                                 # Add the join command to process manager
  manger.run();                                                                 # Run the command

  for f in tmpFiles:                                                            # Iterate over the temporary files
    if os.path.isfile(f):                                                       # If the file exists
      os.remove(f);                                                             # Delete it

if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser(description="Simple python wrapper for FFmpeg to combine multiple mp4 files")
  parser.add_argument('inputs', nargs='+', help='input file(s) to combine')
  parser.add_argument('output', nargs=1,   help='Name of the output file')
  args = parser.parse_args()
  combine_mp4_files( args.inputs, args.output[0] );
