#!/usr/bin/env python3
"""
Determine audio delay between files

Using the audio_delay() function, the delay between
audio files can be determined. This is done using
the cross-correlation between the two files and
using the lag/lead at which the correlation is the
largest.

There is also a function that can be used to
visualize the delay between the two files, and
the accuracy of this method at aligning them.

"""

import logging

from datetime import timedelta
import numpy as np
from scipy.signal import butter, lfilter, fftconvolve

import soundfile as sf

try:
    import matplotlib.pyplot as plt
except:
    plt = None

def audio_delay( file1, file2, show_plots=False, limit=None ):
    """
    Compute delay between audio in different video files

    Motivation behind this function was to add surround
    sound tracks to videos that only contined stereo
    downmixes, but were higher video resolution (say 720p)
    than the source of the surround tracks (say 480p from DVD). 

    Arguments:
        file1 (str) : Path to file to align to
        file2 (str) : Path to file to align

    Keyword arguments:
        show_plots (bool) : If true, try to display plots
            of alignment
        limit (int) : Length of audio file (in minutes) to use
            to align

    Returns:
        tuple : Delay (in seconds) as float and as formatted string

    """

    log = logging.getLogger(__name__)
    log.info( 'Determining delay between inputs' )
    # Get sample rate from the files
    _, fs1 = sf.read(file1, frames = 0, dtype=np.int16)
    _, fs2 = sf.read(file2, frames = 0, dtype=np.int16)

    if fs1 != fs2:
        log.error( 'Sampling frequencies are different!!!' )
        return None

    # Set default limit to one minute
    if limit is None:
        limit = 60 * 1

    # Convert limit into samples
    limit = round( limit*fs1 )

    # Get data from the first file
    signal1, fs1 = sf.read(file1, frames=limit, dtype=np.int16)
    signal2, fs2 = sf.read(file2, frames=limit, dtype=np.int16)

    # Difference in the lengths of the singals
    diff = signal1.shape[0] - signal2.shape[0]

    # Pad signals to ensure are same length
    if diff > 0:
        signal2 = np.pad(signal2, ( (0, diff), (0, 0) ), 'constant')
    elif diff < 0:
        signal1 = np.pad(signal1, ( (0, -diff), (0, 0) ), 'constant')

    log.info( 'Applying low-pass filter' )

    # Set cutoff for filter in Hz
    cutoff = 400

    # Get values for the filter and apply to signals
    const_b, const_a = butter(4, cutoff / (fs1/2), btype='lowpass')
    signal1 = lfilter(const_b, const_a, signal1, axis=0)
    signal2 = lfilter(const_b, const_a, signal2, axis=0)

    # Cross-correlation of the two channels (same as convolution with one reversed)
    log.info( 'Computing cross correlation for left channels' )
    corr_left = fft_xcorr( signal1[:, 0], signal2[:, 0] )
    if max(corr_left) < 0.9:
        log.warning( 'Correlation for left channel is low, alignment may be wrong!' )
    log.info( 'Computing cross correlation for right channels' )
    corr_right = fft_xcorr( signal1[:, 1], signal2[:, 1] )
    if max(corr_right) < 0.9:
        log.warning( 'Correlation for right channel is low, alignment may be wrong!' )

    # Get delay, in samples, between left and right channels
    delay_left  = -( len(corr_left )//2 - np.argmax(corr_left) )
    delay_right = -( len(corr_right)//2 - np.argmax(corr_right) )
    # Compute mean delay between channels
    delay_mean  = np.mean( [delay_left, delay_right] ).astype(np.int32)
    log.info( "L Delay:     %010.4f s", delay_left  / fs1 )
    log.info( "R Delay:     %010.4f s", delay_right / fs1 )
    log.info( "Mean Delay:  %010.4f s", delay_mean  / fs1 )

    if show_plots and plt is not None:
        plot_signals(signal1, signal2, fs1, delay_mean)

    # Generate timedelta based on absolute delay
    delay_str = str( timedelta(seconds = abs(delay_mean) / fs1) )
    if delay_mean < 0:
        delay_str = '-' + delay_str
    # Return delay as float and string
    return (delay_mean/fs1, delay_str)

def fft_xcorr(samples1, samples2):
    """
    Compute scaled cross-correlation using ffts

    Compute the cross-correlation between two audio 
    files to determine time delay

    Arguments:
        samples1 (numpy.ndarray) : Samples from first audio file
        samples2 (numpy.ndarray) : Samples from second audio file

    """

    nsamp    = len(samples1)
    start    = nsamp // 2
    end      = start + nsamp
    samples1 = np.pad( samples1, start, 'constant')
    samples2 = np.pad( samples2, start, 'constant')
    numer    = fftconvolve( samples1, samples2[::-1], 'same' )[start:end]
    denom1   = np.sum( (samples1 - np.mean(samples1))**2 )
    denom2   = np.sum( (samples2 - np.mean(samples2))**2 )
    return  numer / np.sqrt( denom1 * denom2 )

def plot_signals(signal1, signal2, fs, delay_mean):
    """Function to plot the signals to show the alignment."""

    log = logging.getLogger(__name__)
    if plt is None:
        log.error('matplotlib NOT installed. Cannot plot!')
        return

    signal1 = signal1 / 2**16
    signal2 = signal2 / 2**16

    # Plot some graphs
    skip = fs // 250
    time = np.arange(0, signal1.shape[0], skip) / fs

    plt.figure(1)

    # Plots for orignal data
    left1,  left2  = signal1[:,0], signal2[:,0]
    right1, right2 = signal1[:,1], signal2[:,1]
    ax1 = plt.subplot(221)
    plt.plot(time, left1[::skip], 'r')
    plt.plot(time, left2[::skip], 'b')
    plt.grid(True)
    plt.ylabel('Left (amp.)')
    plt.title('Before Adjustment')

    ax2 = plt.subplot(223, sharex=ax1, sharey=ax1)
    plt.plot(time, right1[::skip], 'r', label='file 1')
    plt.plot(time, right2[::skip], 'b', label='file 2')
    plt.grid(True)
    plt.ylabel('right (amp.)')
    plt.xlabel('Time (s)')
    plt.legend()

    # Plots for adjusted data
    left3  = np.roll(left2,  delay_mean)
    right3 = np.roll(right2, delay_mean)
    ax3 = plt.subplot(222, sharex=ax2, sharey=ax2)
    plt.plot(time, left1[::skip], 'r')
    plt.plot(time, left3[::skip], 'b')
    plt.grid(True)
    plt.title('After Adjustment')

    # Start a subplot
    ax4 = plt.subplot(224, sharex=ax3, sharey=ax3)
    plt.plot(time, right1[::skip], 'r', label='file 1')
    plt.plot(time, right3[::skip], 'b', label='file 2')
    plt.grid(True)
    plt.xlabel('Time (s)')
    plt.legend()

    plt.subplots_adjust(
        left   = 0.1,
        bottom = 0.1,
        right  = 0.99,
        top    = 0.9,
        wspace = 0.2,
        hspace = 0.13,
    )
    plt.show()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Utility to determine the delay, in seconds, between audio streams in two files"
    )
    parser.add_argument(
        "ref",
        type = str,
        help = "Referene file, new file will be offset to match this one.",
    )
    parser.add_argument(
        "new",
        type = str,
        help = "New file to be offset to match ref",
    )
    parser.add_argument(
        "-p",
        "--plot",
        action = "store_true",
        help   = "Show plots of offset correction",
    )
    args = parser.parse_args()

    delay = audio_delay( args.ref, args.new, show_plots = args.plot )
