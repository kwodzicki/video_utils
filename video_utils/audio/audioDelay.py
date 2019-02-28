#!/usr/bin/env python3

import soundfile as sf
import numpy as np
from scipy.signal import butter, lfilter, fftconvolve, correlate
from datetime import timedelta

################################################################################
def fft_xcorr(x, y):
	'''
	Function to compute scaled cross-correlation using ffts
	'''
	n      = len(x)
	start  = n//2;
	end    = start + n
	x      = np.pad( x, start, 'constant')
	y      = np.pad( y, start, 'constant')
	numer  = fftconvolve( x, y[::-1], 'same' )[start:end];
	denom1 = np.sum( (x - np.mean(x))**2 )
	denom2 = np.sum( (y - np.mean(y))**2 )
	return  numer / np.sqrt( denom1 * denom2 ) ;
################################################################################
def plotSignals(signal1, signal2, fs, delayM):
	'''
	Function to plot the signals to show the alignment.
	'''
	import matplotlib.pyplot as plt;                                              # Only import if we need to
	signal1 = signal1 / 2**16
	signal2 = signal2 / 2**16

	# Plot some graphs  
	skip = fs // 250;                                                             # Set skip for plot to reduce number of points
	time = np.arange(0, signal1.shape[0], skip) / fs;                             # Compute times, in seconds, for signal1
  
	plt.figure(1);                                                                # Initialize the a figure

	# Plots for orignal data  
	Left1,  Left2  = signal1[:,0], signal2[:,0];                                  # Set up Left  channels from signals 1 and 2
	Right1, Right2 = signal1[:,1], signal2[:,1];                                  # Set up Right channels from signals 1 and 2
	ax1 = plt.subplot(221);                                                             # Start a subplot
	plt.plot(time, Left1[::skip], 'r');                                           # Plot Left channel from signal1 as red
	plt.plot(time, Left2[::skip], 'b');                                           # Plot Left channel from signal2 as blue
	plt.grid(True);                                                               # Turn on the grid
	plt.ylabel('Left (amp.)');                                                    # Set y-axis label
	plt.title('Before Adjustment');                                               # Set plot title
	  
	ax2 = plt.subplot(223, sharex=ax1, sharey=ax1);                                                             # Start a subplot
	plt.plot(time, Right1[::skip], 'r', label='file 1');                          # Plot Right channel from signal1 as red
	plt.plot(time, Right2[::skip], 'b', label='file 2');                          # Plot Right channel from signal2 as blue
	plt.grid(True);                                                               # Turn on the grid
	plt.ylabel('Right (amp.)');                                                   # Set y-axis label
	plt.xlabel('Time (s)');                                                       # Set x-axis label
	plt.legend();                                                                 # Plot a legend
  
	# Plots for adjusted data  
	Left3  = np.roll(Left2,  delayM);                                             # Shift the left  channel from signal2 to match signal1
	Right3 = np.roll(Right2, delayM);                                             # Shift the right channel from signal2 to match signal1
	ax3 = plt.subplot(222, sharex=ax2, sharey=ax2);                               # Start a subplot
	plt.plot(time, Left1[::skip], 'r');                                           # Plot Left channel from signal1 as red
	plt.plot(time, Left3[::skip], 'b');                                           # Plot adjusted Left channel from signal2 as blue
	plt.grid(True);                                                               # Turn on the grid
	plt.title('After Adjustment');                                                # Set plot title
  
	ax4 = plt.subplot(224, sharex=ax3, sharey=ax3);                               # Start a subplot
	plt.plot(time, Right1[::skip], 'r', label='file 1');                          # Plot Right channel from signal1 as red
	plt.plot(time, Right3[::skip], 'b', label='file 2');                          # Plot adjusted Right channel from signal2 as blue
	plt.grid(True)                                                                # Turn on the grid
	plt.xlabel('Time (s)');                                                       # Set x-axis label
	plt.legend();                                                                 # Plot a legend
	plt.subplots_adjust(left=0.1, bottom=0.1, right=0.99, top=.9, 
    wspace=0.2, hspace=0.13); 
	plt.show();                                                                   # Display the plots
################################################################################
def audioDelay( file1, file2, showPlots = False, limit = None ):
	print( 'Determining delay between inputs...' );                               # Print a message
	signal1, fs1 = sf.read(file1, frames = 0, dtype=np.int16);                    # Get sample rate from the first file
	signal2, fs2 = sf.read(file2, frames = 0, dtype=np.int16);                    # Get sample rate from the second file

	if fs1 != fs2:                                                                # If the files have different sample rates
		print( 'Sampling frequencies are different!!!' );                           # Print warning message
		return None;                                                                # Return None

	if limit is None: limit = 60 * 1;                                             # Set default limit to one minute	
	limit = round( limit*fs1 );                                                   # Convert limit into samples
	signal1, fs1 = sf.read(file1, frames = limit, dtype=np.int16);                # Get data from the first file
	signal2, fs2 = sf.read(file2, frames = limit, dtype=np.int16);                # Get data from the second file

	diff = signal1.shape[0] - signal2.shape[0];                                   # Difference in the lengths of the singals
	if diff > 0:                                                                  # If diff is positive, that means signal2 is less than 'limit' in length
		signal2 = np.pad(signal2, ( (0, diff), (0, 0) ), 'constant');               # Pad signal2 because signal1 is longer
	elif diff < 0:                                                                # Else if, pad is negative
		signal1 = np.pad(signal1, ( (0, -diff), (0, 0) ), 'constant');              # Pad signal1 because signal2 is longer

	print( 'Applying low-pass filter' );                                          # Print some information
	cutoff = 400;                                                                 # Set cutoff for filter in Hz
	B, A = butter(4, cutoff / (fs1/2), btype='lowpass');                          # Get values for the filter
	signal1 = lfilter(B, A, signal1, axis=0);                                     # Apply the filter to signal1
	signal2 = lfilter(B, A, signal2, axis=0);                                     # Apply the filter to signal2

	# Cross-correlation of the two channels (same as convolution with one reversed)
	print( 'Computing cross correlation for left channels' );                     # Print some information
# 	corrL = fftconvolve(signal1[:, 0], signal2[::-1, 0], mode='same');            # Compute cross-correlation between left channels of signal1 and signal2
	corrL = fft_xcorr( signal1[:, 0], signal2[:, 0] );
	if max(corrL) < 0.9: 
		print( '  Correlation is low, alignment may be wrong!' );
	print( 'Computing cross correlation for right channels' );                    # Print some information
# 	corrR = fftconvolve(signal1[:, 1], signal2[::-1, 1], mode='same');            # Compute cross-correlation between right channels of signal1 and signal2
	corrR = fft_xcorr( signal1[:, 1], signal2[:, 1] )
	if max(corrR) < 0.9: 
		print( '  Correlation is low, alignment may be wrong!' );
	
	delayL = -( len(corrL)//2 - np.argmax(corrL) );                               # Get delay, in samples, between left channels
	delayR = -( len(corrR)//2 - np.argmax(corrR) );                               # Get delay, in samples, between left channels
	delayM = np.mean( [delayL, delayR] ).astype(np.int32);                        # Compute mean delay between channels
	print( 'L Delay:     {:010.4f} s'.format( delayL/fs1 ) );# Print some information
	print( 'R Delay:     {:010.4f} s'.format( delayR/fs1 ) );# Print some information
	print( 'Mean  Delay: {:010.4f} s'.format( delayM / fs1 ) );                   # Print some information

	if showPlots: plotSignals(signal1, signal2, fs1, delayM);                     # Generate plots if requested
		
	delay = str( timedelta(seconds = abs(delayM) / fs1) );                        # Generate timedelta based on absolute delay
	if delayM < 0: delay = '-' + delay;                                           # Add minus (-) sign to delay if necessary
	return (delayM/fs1, delay);                                                   # Return delay as float and string

################################################################################
if __name__ == "__main__":
	import argparse;                                                              # Import library for parsing
	parser = argparse.ArgumentParser(description="MKV Cron Converter");           # Set the description of the script to be printed in the help doc, i.e., ./script -h
	parser.add_argument("ref",    type=str, help="Referene file, new file will be offset to match this one."); 
	parser.add_argument("new",    type=str, help="New fil to be offset to match ref"); 
	parser.add_argument("-p", "--plot", action="store_true", help="Show plots of offset correction"); 
	args = parser.parse_args();                                                   # Parse the arguments

	delay = audioDelay( args.ref, args.new, showPlots = args.plot );