#!/usr/bin/env python3
"""
Replace audio stream(s) in video file

Given two video files, replace the audio streams
in one with the streams from another. Audio from
the second file is time aligned to the first file
to reduce/eliminate audio/video sync issues.

"""

import logging

import os
import re
import subprocess

from threading import Thread
from datetime import timedelta

import psutil

from ..mediainfo import MediaInfo

from .audio_delay import audio_delay
from .dolby_downmix  import dolby_downmix

################################################################################
def extract_audio( info, infile, outdir, result, time = None ):
    """
    A function to extract an audio stream from a video file

    Arguments:
        info   : Information about the audio strem to extract
        infile : Full path to the file to extract the stream from

    Keyword arguments:
        time (timedelta): How long the extracted stream should be.
        lossless (bool): Set to True to extract into a FLAC file.
                   Only valid when stream is > 2 channels.

    Returns:
        str: Path to the extracted audio stream

    """

    log = logging.getLogger(__name__)
    log.info( 'Extracting audio for alignment: %s', infile )
    outfile = os.path.splitext( os.path.basename(infile) )[0] + '.ogg'
    outfile = os.path.join(outdir, outfile)

    log.info( 'Output file: %s', outfile )

    if info['Channel_s_'] <= 2:
        cmd = [
            'ffmpeg', 
            '-y',
            '-nostdin',
            '-v', 'quiet',
            '-stats',
            '-i', infile,
            '-vn',
        ]
        if time is not None:
            cmd.extend( ['-t', str(time)] )
        cmd.append( outfile )
        proc = subprocess.run( cmd, check=False )
        if proc.returncode != 0:
            log.error('There was an error')
            if os.path.isfile( outfile ):
                os.remove( outfile )
            return
    else:
        outfile = dolby_downmix( infile, outdir=outdir, time=time )

    result[0] = outfile

def file_name_info( infile, info=None ):
    """
    A function to get information for naming a file

    Arguments:
        infile (str): Full path to the file to get information for

    Keyword arguments:
        None

    Returns:
        list: List with file information

    """

    minfo = MediaInfo(infile) if info is None else info
    if minfo['Video'][0]['Height'] <= 480:
        info = ['480p']
    elif minfo['Video'][0]['Height'] <= 720:
        info = ['720p']
    elif minfo['Video'][0]['Height'] <= 1080:
        info = ['1080p']
    elif minfo['Video'][0]['Height'] <= 2160:
        info = ['2160p']
    try:
        info.append( minfo['Video'][0]['Encoded_Library_Name'] )
    except:
        info.append( minfo['Video'][0]['Writing_library/String'].split()[0] )
    for track in minfo['Audio']:
        fmt   = track.get('Format', '')
        lang2 = track.get('Language/String2', '')
        lang2 = lang2.upper()+'_' if lang2 != '' else 'EN_'
        info.append( lang2 + fmt )
    return info

################################################################################
def compute_offset(in1, in2, info1, info2, outdir):
    """Function to get offset between files."""

    log     = logging.getLogger(__name__)
    # Set size to third of total memory
    mem_size = psutil.virtual_memory().total // 4

    # Length in seconds is the total memory divided by
    # (48kHz sample rate, times 2 bytes per sample, times 2 channels)
    a_length = mem_size / (48000 * 2 * 2) / 2
    a_length = timedelta( seconds = a_length)

    in1_audio, in2_audio = [None], [None]
    args1   = (info1['Audio'][0], in1, outdir, in1_audio, a_length, )
    args2   = (info2['Audio'][0], in2, outdir, in2_audio, a_length, )
    threads = [
        Thread(target=extract_audio, args=args1),
        Thread(target=extract_audio, args=args2),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if in1_audio[0] is None or in2_audio[0] is None:
        log.error('Failed to extract audio from one of the files')
        return None

    in1_audio = in1_audio[0]
    in2_audio = in2_audio[0]
    delay = audio_delay(in1_audio, in2_audio)
    if os.path.isfile(in1_audio):
        os.remove(in1_audio)
    if os.path.isfile(in2_audio):
        os.remove(in2_audio)
    return delay

################################################################################
def replace_audio_streams( in1, in2, outdir = None, replace = False):
    """
    Replace audio streams in one file with those from another.

    This function will replace all audio streams in in1 with those
    in in2. If all audio streams in in2 are surround (i.e., > 2 channels),
    one downmixed stream will also be placed in in1.

    """

    log = logging.getLogger(__name__)
    if outdir is None:
        outdir = os.path.dirname(in1)
    out         = os.path.join(outdir, 'test.mp4')
    base        = ['ffmpeg', '-nostdin', '-v', 'quiet', '-stats']
    inputs      = []
    codecs      = ['-c:v', 'copy']
    opts        = ['-movflags', 'disable_chpl', '-hide_banner']
    audio_codec = '-c:a:{} aac -b:a:{} 192k'

    info1   = MediaInfo( in1 )
    info2   = MediaInfo( in2 )

    if len(info1['Video']) != 1:
        log.error('Input one (1) must have only one (1) video stream!')
        return False

    if len(info2['Audio']) == 0:
        log.error('Input two (2) must have at least one (1) audio stream!')
        return False

    # Dictionary to hold information about new merged file
    new_info = {
        'Video' : info1['Video'],
        'Audio' : [],
    }
    # Set mapping to map video stream from input one
    mapping = ['-map', '0:' + str(info1['Video'][0]['StreamOrder'])]

    test_time = None#str( timedelta( seconds = 300 ) )

    # Search for any two channel audio streams in second input
    any2ch = any( i['Channel_s_'] <=2 for i in info2['Audio'] )
    audio_stream_id = 0
    # If there are no audio streams in the second file with 2 or fewer tracks
    if not any2ch:
        # Append the information for the first audio stream of input2
        # to the newInfo list; copy ensures is own instance of dict
        new_info['Audio'].append( info2['Audio'][0].copy() )
        new_info['Audio'][-1]['Format'] = 'AAC'
        audio_stream_id += 1

    # Mapping for the second input file
    for i in range( len(info2['Audio']) ):
        # Get information for the ith audio stream of input 2
        info = info2['Audio'][i]
        # Append the information to the newInfo dictionary
        new_info['Audio'].append( info )
        stream_num = info['StreamOrder'] if 'StreamOrder' in info else 0
        mapping.extend( ['-map', f"1:{stream_num}"] )
        if info['Channel_s_'] <= 2:
            codecs.extend( audio_codec.format(i, i).split() )
        else:
            codecs.extend( [f"-c:a:{audio_stream_id}", 'copy'] )
        audio_stream_id += 1

    # Set up output file name
    info  = file_name_info( out, new_info )
    fbase = os.path.basename(in1)
    fname = fbase.split('.')
    if re.match(r'S\d{2,}E\d{2,}', fbase):
        fname = '.'.join( [fname[0]] + info + fname[-2:] )
    else:
        fname = '.'.join( fname[:3] + info + fname[-2:] )
    out = os.path.join(outdir, fname)
    log.info( 'Output: %s', out )
    if out == in1:
        log.warning( 'Output matches input one!' )
        return False

    # If the output file exits and replace is NOT set
    if os.path.isfile(out) and not replace:
        log.error( 'Output file already exits!' )
        log.error( 'Set replace key to overwrite' )
        return False

    # If the file exits, delete it; replace MUST be set
    if os.path.isfile(out):
        os.remove(out)

    delay = compute_offset(in1, in2, info1, info2, outdir)
    if delay is None:
        return False

    # If there are not any 2 channel audio streams in file2
    if not any2ch:
        log.info( 'Downmixing surround stream to stereo AAC' )
        audio_in = dolby_downmix( in2, aac=True, outdir=outdir, time=test_time)
        if audio_in is None:
            log.error('Reorder during Dolby Downmix, returning!')
            return False
        # Get information from the first audio stream
        info   = info2['Audio'][0]
        # Append down-mixed file path to inputs list
        inputs = ['-itsoffset', delay[1], '-i', audio_in]
        # Add mapping for the file
        mapping.extend( ['-map', '2:0'] )
        opts  += [
            '-metadata:s:a:0', 'title=Dolby Pro Logic II', 
            '-metadata:s:a:0', 'language='+info['Language/String2'],
        ]

    # Set up input files with offset for audio
    inputs = ['-i', in1, '-itsoffset', delay[1], '-i', in2] + inputs
    # Generate the command by combining by adding inputs, mapping, codecs, and extra options
    cmd    = base + inputs + mapping + codecs + opts
    if test_time is not None:
        cmd.extend( ['-t', test_time] )

    cmd.append( out )
    log.info('Combining files')
    _ = subprocess.run( cmd, check=False )
    if audio_in is None:
        return False

    if os.path.isfile(audio_in):
        os.remove(audio_in)                             # If the file exists, remove it

    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Utility to replace audio streams one file with audio streams from another"
    )
    parser.add_argument(
        "orig",
        type = str,
        help = "Original file; will replace audio",
    )
    parser.add_argument(
        "new",
        type = str,
        help = "New file with surround stream(s); new audio",
    )
    parser.add_argument(
        "-o", "--output",
        type = str,
        help = "Output directory.",
    )
    parser.add_argument(
        "-r", "--replace",
        action = "store_true",
        help   = "Set to replace existing output file.",
    )

    args = parser.parse_args()
    _ = replace_audio_streams(
        args.orig,
        args.new,
        args.output,
        args.replace,
    )
