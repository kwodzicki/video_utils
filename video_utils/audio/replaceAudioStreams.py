#!/usr/bin/env python3

import os, shutil, re, subprocess, psutil
from threading import Thread
from datetime import timedelta
from time import sleep

from ..mediainfo import MediaInfo

from .audioDelay import audioDelay
from .DolbyDownmix  import DolbyDownmix

################################################################################
def extractAudio( info, inFile, outDir, result, time = None ):
  '''
  Name:
     extractAudio
  Purpose:
     A function to extract an audio stream from a video file
  Inputs:
     info   : Information about the audio strem to extract
     inFile : Full path to the file to extract the stream from
  Outputs:
     Returns the path to the extracted audio stream
  Keywords:
     time     : How long the extracted stream should be.
                 time is a timedelta object.
     lossless : Set to True to extract into a FLAC file.
                 Only valid when stream is > 2 channels.
  '''
  print('Extracting audio for alignment'.format(inFile));                       # Print some inforamtion
  outFile = '.'.join( os.path.basename(inFile).split('.')[:-1] )
  outFile = os.path.join(outDir, outFile);
  outFile += '.ogg'                                                             # Append '.ogg' to outFile
  print( 'outFile: {}'.format(outFile) );
  if info['Channel_s_'] <= 2:                                                   # If the number of audio channels is <= 2
    cmd = ['ffmpeg','-y','-nostdin', '-v', 'quiet', '-stats', '-i',inFile, '-vn'];# Initialize command list
    if time is not None: cmd.extend( ['-t', str(time)] );                       # Append time if it is NOT None
    cmd.append( outFile );                                                      # Append outfile to command
#     with open(os.devnull, 'w') as devnull:                                      # Open /dev/null for writing
#       proc = subprocess.Popen( cmd, stdout=devnull, stderr=subprocess.STDOUT ); # Call the command
    proc = subprocess.Popen( cmd );
    proc.communicate();                                                         # Wait for command to finish
    if proc.returncode != 0:                                                    # If the return code is NOT zero (0)
      print('There was an error');                                              # Print message
      if os.path.isfile( outFile ): os.remove( outFile );                       # Remove the output file
  else:                                                                         # Else, it is a surround stream
    outFile = DolbyDownmix( inFile, outDir = outDir, time = time );             # Downmix the stream to setero
  result[0] = outFile;

################################################################################
def fileNameInfo( inFile, info = None ):
  '''
  Name:
     fileNameInfo
  Purpose:
     A function to get information for naming a file
  Inputs:
     inFile : Full path to the file to get information for
  Outputs:
     Returns list with file information
  Keywords:
     None.
  '''
  m = MediaInfo(inFile) if info is None else info;                              # Get information about the file
  if m['Video'][0]['Height'] <= 480:                                            # If image size if <= 480
    info = ['480p'];                                                            # Set resolution to 480p
  elif m['Video'][0]['Height'] <= 720:                                          # Else, if image size is <= 720
    info = ['720p'];                                                            # Set resolution to 720p
  elif m['Video'][0]['Height'] <= 1080:                                         # Else, if image size is <= 1080
    info = ['1080p'];                                                           # Set resolution to 1080p
  elif m['Video'][0]['Height'] <= 2160:                                         # Else, if image size is <= 2160
    info = ['2160p'];                                                           # Set resolution to 2160p
  try:
    info.append( m['Video'][0]['Encoded_Library_Name'] );                       # Append the encoding library name to info
  except:
    info.append( m['Video'][0]['Writing_library/String'].split()[0] );
  for track in m['Audio']:                                                      # Iterate over all audio tracks in the file
    fmt   = track['Format']           if 'Format'           in track else '';   # Set audio track format
    lang2 = track['Language/String2'] if 'Language/String2' in track else '';   # Set audio track language
    lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_';                        # Set default language to English
    info.append( lang2 + fmt );                                                 # Append audio track information
  return info;                                                                  # Return list of information

################################################################################
def computeOffset(in1, in2, info1, info2, outDir):
  '''Function to get offset between files.'''
  memSize = psutil.virtual_memory().total // 4;                                 # Set size to third of total memory
  aLength = memSize / (48000 * 2 * 2) / 2;                                      # Length in seconds is the total memory divided by (48kHz sample rate, times 2 bytes per sample, times 2 channels)
  aLength = timedelta( seconds = aLength);
  in1_audio, in2_audio = [None], [None];                                        # Set up in1_audio and in2_audio as lists with None; used to get output from threads
  args1   = (info1['Audio'][0], in1, outDir, in1_audio, aLength, );             # Set up arguments for in1 thread
  args2   = (info2['Audio'][0], in2, outDir, in2_audio, aLength, );             # Set up arguments for in2 thread
  threads = [];                                                                 # Set up list for threads
  threads.append( Thread(target=extractAudio, args=args1) );                    # Initialize thread1 and append handle to threads list
  threads.append( Thread(target=extractAudio, args=args2) );                    # Initialize thread2 and append handle to threads list
  for thread in threads: thread.start();                                        # Iterate over threads and start each
  while all( [thread.is_alive() for thread in threads] ): sleep(0.01);     # While all the process are alive, leep for a little
  for thread in threads:                                                        # One of the process is no longer alive so iterate to find the dead one
    if not thread.is_alive():                                                   # If the process is not alive
      thread.join();                                                            # Join the process
      threads.remove( thread );                                                 # Remove it from the list
      break;                                                                    # Break the for loop
  threads[0].join();                                                            # Join remaining thread to completion
    
  if in1_audio[0] is None or in2_audio[0] is None: 
    print('Failed to extract audio from one of the files')
    return None;
  in1_audio = in1_audio[0]
  in2_audio = in2_audio[0]
  delay = audioDelay(in1_audio, in2_audio); 
  if in1_audio is not None:
    if os.path.isfile(in1_audio): os.remove(in1_audio);
  if in2_audio is not None:
    if os.path.isfile(in2_audio): os.remove(in2_audio);
  return delay;
  
################################################################################
def replaceAudioStreams( in1, in2, outDir = None, replace = False):
  '''
  This function will replace all audio streams in in1 with those
  in in2. If all audio streams in in2 are surround (i.e., > 2 channels),
  one downmixed stream will also be placed in in1.
  '''
  if outDir is None: outDir = os.path.dirname(in1)
  out    = os.path.join(outDir, 'test.mp4');
  base   = ['ffmpeg', '-nostdin', '-v', 'quiet', '-stats']
  inputs = [];
  codecs = ['-c:v', 'copy'];                                                    # Codec options (copy audio and video)
  opts   = ['-movflags', 'disable_chpl', '-hide_banner'];                       # Extra options; removes weird extra movie chaptes
  aCodec = '-c:a:{} aac -b:a:{} 192k';                                          # String formatter for audio transcoding
  
  info1   = MediaInfo( in1 );                                                   # get information for input one
  info2   = MediaInfo( in2 );                                                   # get information for input two

  if len(info1['Video']) != 1:                                                  # If there is not one (1) video stream in input one
    print('Input one (1) must have only one (1) video stream!')
    return 1;
  if len(info2['Audio']) == 0:                                                  # If there is not one (1) audio stream in input two
    print('Input two (2) must have at least one (1) audio stream!');
    return 2;
  newInfo = {'Video' : info1['Video'], 'Audio' : []};                           # Dictionary to hold information about new merged file
  mapping = ['-map', '0:' + str(info1['Video'][0]['StreamOrder'])];             # Set mapping to map video stream from input one

  testTime = None;#str( timedelta( seconds = 300 ) )

  any2ch = any( [ i['Channel_s_'] <=2 for i in info2['Audio'] ] );              # Search for any two channel audio streams in second input
  aCh    = 0;                                                                   # Audio stream number in output file
  if not any2ch:                                                                # If there are no audio streams in the second file with 2 or fewer tracks
    newInfo['Audio'].append( info2['Audio'][0].copy() );                        # Append the information for the first audio stream of input2 to the newInfo list; copy ensures is own instance of dict
    newInfo['Audio'][-1]['Format'] = 'AAC';                                     # Set the format (i.e., encoder) of the stream to AAC, as this is what it will be
    aCh += 1;                                                                   # Increment aCh counter 
  # Mapping for the second input file
  for i in range( len(info2['Audio']) ):                                        # Iterate over the audio in input two
    info = info2['Audio'][i];                                                   # Get information for the ith audio stream of input 2
    newInfo['Audio'].append( info );                                            # Append the information to the newInfo dictionary
    sn = str(info['StreamOrder']) if 'StreamOrder' in info else '0';            # Set stream order based on audio stream order or to zero by default
    mapping.extend( ['-map', '1:'+ sn] );                                       # Add the mapping for the file
    if info['Channel_s_'] <= 2:                                                 # If the audio stream has less than or equal to two (2) channels
      codecs.extend( aCodec.format(i, i).split() );                             # Set encoding for the stream; i.e., stream re-encoded
    else:                                                                       # Else
      codecs.extend( ['-c:a:'+str(aCh), 'copy'] );                              # Set stream codec to copy
    aCh += 1;                                                                   # Increment aCh

  # Set up output file name
  info     = fileNameInfo( out, newInfo );                                      # Get file naming information
  fBase    = os.path.basename(in1)
  fname    = fBase.split('.');                                                # Get basename of input and split on period
  if re.match('S\d{2,}E\d{2,}', fBase):
    fname = '.'.join( [fname[0]] + info + fname[-2:] );                         # Set the output file name
  else:                                                                         # Else, must be a movie
    fname = '.'.join( fname[:3] + info + fname[-2:] );                          # Set the output file name
  out = os.path.join(outDir, fname);                                            # Set new file path
  print( 'Output: {}'.format(out) );
  if out == in1:                                                                # If the output file name matches the first input
    print( 'Output matches input one!' );                                       # Print message
    return;                                                                     # Return
  elif os.path.isfile(out):                                                     # Else, if the output file already exists
    if replace:                                                                 # If replace is set
      print( 'Replacing old output file' );
      if os.path.isfile(out): os.remove(out);                                   # If out file still exists, delete it
    else:                                                                       # Else, out does match and replace not True
      print( 'Output file already exits!' );                                    # Print some information
      print( 'Set replace key to overwrite' );                                  # Print some information
      return;                                                                   # Return

  delay = computeOffset(in1, in2, info1, info2, outDir);                        # Compute delay between files
  if delay is None: return;                                                     # If delay is None, return from function
  if not any2ch:                                                                # If there are not any 2 channel audio streams in file2
    print( 'Downmixing surround stream to stereo AAC' );                        # Print some information
    audioIn = DolbyDownmix( in2, AAC=True, outDir = outDir, time = testTime);   # Downmix the stream
    if audioIn is None:                                                         # If a file path was returned
      print('Reorder during Dolby Downmix, returning!');                        # Print some information
      return;                                                                   # Return
    else:                                                                       # Else
      info = info2['Audio'][0];                                                 # Get information from the first audio stream
      inputs = ['-itsoffset', delay[1], '-i', audioIn];                         # Append down-mixed file path to inputs list
      mapping.extend( ['-map', '2:0'] );                                        # Add mapping for the file
      opts  += ['-metadata:s:a:0', 'title=Dolby Pro Logic II', 
                '-metadata:s:a:0', 'language='+info['Language/String2']];       # Add some metadata options for the stream
  inputs = ['-i', in1, '-itsoffset', delay[1], '-i', in2] + inputs;             # Compute offsets for inputs
  cmd    = base + inputs + mapping + codecs + opts;                             # Generate the command by combining by adding inputs, mapping, codecs, and extra options
  if testTime is not None: cmd.extend( ['-t', testTime] );                      # Append testTime if not None

  cmd.append( out );                                                            # Add output name
  print('Combining files');                                                     # Print information
  proc = subprocess.Popen( cmd );                                               # Initialize merger
  proc.communicate();                                                           # Wait for merge to finish
  if audioIn is not None:                                                       # If down-mixed audio file path is not None
    if os.path.isfile(audioIn): os.remove(audioIn);                             # If the file exists, remove it
  #print('Writing tags');
  #status = mp4Tags(out, metaData = metaData);                                   # Write metadata

################################################################################
if __name__ == "__main__":
  import argparse;                                                              # Import library for parsing
  parser = argparse.ArgumentParser(description="Utility to replace audio streams one file with audio streams from another");           # Set the description of the script to be printed in the help doc, i.e., ./script -h
  parser.add_argument("orig",    type=str, help="Original file; will replace audio"); 
  parser.add_argument("new",     type=str, help="New file with surround stream(s); new audio"); 
  parser.add_argument("-o", "--output",   type=str, help="Output directory."); 
  parser.add_argument("-r", "--replace",   action="store_true", help="Set to replace existing output file.");
  args = parser.parse_args();                                                   # Parse the arguments
  status = replaceAudioStreams( args.orig, args.new, 
    args.outDir, args.replace ); 
  exit( status )
