#!/usr/bin/env python3
import sys, os;
from subprocess import Popen, STDOUT, DEVNULL;

# Panning settings for Dolby Pro Logic and Dolby Pro Logic II
_panning = {
  'PLII' : {
    'L' : 'FL + 0.707*FC - 0.8165*BL - 0.5774*BR',
    'R' : 'FR + 0.707*FC + 0.5774*BL + 0.8165*BR'
  },
  'PL'  : {
    'L' : 'FL + 0.707*FC - 0.707*BL - 0.707*BR',
    'R' : 'FR + 0.707*FC + 0.707*BL + 0.707*BR'
  }
}


################################################################################
def getDownmixFilter( PLII = True ):
  '''
  Name:
    getDownmixFilter
  Purpose:
    A python function to return an filter string for FFmpeg audio filter
    to downmix surround audio channels to Dolby Pro Logic or Dolby Pro Logic II
  Inputs:
    None.
  Outputs:
    Returns filter string
  Keywords:
    PLII    : Set to use Dolby Pro Logic II downmix. This is the default
  '''
  if PLII:                                                                      # If PLII is True
    L, R = _panning['PLII']['L'], _panning['PLII']['R'];                        # Panning for right channel in PLII downmix
  else:                                                                         # Else
    L, R = _panning['PL']['L'], _panning['PL']['R'];                            # Panning for right channel in ProLogic downmix
  return '|'.join( [ "pan=stereo", 'FL<{}'.format(L), 'FR<{}'.format(R) ] );    # Create string for filter option

################################################################################
def DolbyDownmix( inFile, outDir = None, PLII = True, AAC = False, FLAC = False, time = None ):
	'''
	Name:
	   DolbyDownmix
	Purpose:
	   A function that downmixes surround sound channels (5.1+) in
	   a video file to Dolby Pro Logic II.
	   Information can be found starting in section 7.8 on page 91 of
	   http://www.atsc.org/wp-content/uploads/2015/03/A52-201212-17.pdf
	   and at:
	   http://forum.doom9.org/showthread.php?s=&threadid=27936
	Inputs:
	   inFile : Full path to the file that should be downmixed
	Outputs:
	   A stereo downmix of audio tracks in inFile with the
	   same name as input.
	   Only first audio stream is downmixed....
	Keywords:
	   PLII     : Set to downmix to Dolby Pro Logic II.
	               This is the default. Setting to Fasle
	               will downmix in Dolby Pro Logic.
	   AAC      : Set to output as AAC encoded file. Default
	               is OGG.
	   time     : String in format HH:MM:SS.0 specifing the
	               lenght of the downmix. Default is complete
	               stream.
	Author and History:
	   Kyle R. Wodzicki     Created 01 Feb. 2018
	'''
	inFile  = os.path.abspath( inFile );                                          # Make sure we have the absolute path
	base = ['ffmpeg','-y', '-nostdin', '-v', 'quiet', '-stats', '-i',inFile];     # Set up command base
	opts = ['-vn', '-ac', '2', '-b:a', '192k'];                                   # Set up command options

	if outDir is None: outDir = os.path.dirname( inFile );
	outFile = '.'.join( os.path.basename(inFile).split('.')[:-1] )
	outFile = os.path.join(outDir, outFile);                                      # Set outFile if it is NOT set
	if FLAC:
		outFile += 'flac';                                                          # Append file extension to outFile
		opts.extend( ['-c:a','flac'] );                                             # Set audio codec
	elif AAC:                                                                     # If AAC is True, use aac codec
		outFile += '.m4a';                                                          # Append file extension to outFile
		opts.extend( ['-c:a','aac'] );                                              # Set audio codec
	else:                                                                         # Else, use libvorbis codec
		outFile += '.ogg';                                                          # Append file extension to outFile
		opts.extend( ['-c:a','libvorbis'] );                                        # Set audio codec
	# Channel summing based on LoRo option, see text referenced above
# 	if LoRo:
# 		clev = 0.707;
# 		slev = 0.500;
# 		L = 'FL+{:05.3f}*FC+{:05.3f}*BL'.foramt(clev, slev);
# 		R = 'FR+{:05.3f}*FC+{:05.3f}*BR'.foramt(clev, slev);
	opts.extend( ['-af', getDownmixFilter(PLII) ] );                              # Append panning options to opts list
	cmd = base + opts;                                                            # Join base and opts into command
	if time is not None:                                                          # If time is set
		cmd.extend( ['-t', str(time)] );                                            # Append time to command
	cmd.append( outFile );                                                        # Append outFile to command

	proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );                       # Run the command
	proc.communicate();                                                           # Wait for command to finish
	if proc.returncode == 0:                                                      # If no errors
		return outFile;                                                             # Return outFile path
	else:                                                                         # Else, there was an error
		if os.path.isfile( outFile ): os.remove( outFile );                         # If the file exists, remove it because it's bad
		return None;                                                                # Return None;
		
if __name__ == "__main__":
	import sys
	if len(sys.argv) != 2:
		print( 'Incorrect number of inputs!' );
	dolbyPLII( sys.argv[1] );
	exit(1);
