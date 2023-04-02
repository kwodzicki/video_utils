"""
Downmixing of surround audio

"""

import os
from subprocess import run, STDOUT, DEVNULL

# Panning settings for Dolby Pro Logic and Dolby Pro Logic II
_panning = {
    'PLII' : {
        'L' : 'FL + 0.707*FC - 0.8165*BL - 0.5774*BR',
        'R' : 'FR + 0.707*FC + 0.5774*BL + 0.8165*BR',
    },
    'PL'  : {
        'L' : 'FL + 0.707*FC - 0.707*BL - 0.707*BR',
        'R' : 'FR + 0.707*FC + 0.707*BL + 0.707*BR',
    },
}


################################################################################
def get_downmix_filter( pro_logic_2 = True ):
    """
    Get format string for downmix filter

    Function to return an filter string for FFmpeg audio filter
    to downmix surround audio channels to Dolby Pro Logic or Dolby Pro Logic II

    Arguments:
        None

    Keyword arguments:
        pro_logic_2 : Set to use Dolby Pro Logic II downmix. This is the default

    Returns:
        str: Format string for filter

    """

    fmt = 'PLII' if pro_logic_2 else 'PL'
    left, right = _panning[fmt]['L'], _panning[fmt]['R']
    return '|'.join( [ "pan=stereo", f"FL<{left}", f"FR<{right}" ] )

################################################################################
def dolby_downmix( infile, outdir=None, pro_logic_2=True, aac=False, flac=False, time=None ):
    """
    Downmix surround sound channels (5.1+) in a video file to Dolby Pro Logic II

    A function that downmixes surround sound channels (5.1+) in
    a video file to Dolby Pro Logic II.

    Information can be found starting in section 7.8 on page 91 of
    http://www.atsc.org/wp-content/uploads/2015/03/A52-201212-17.pdf
    and at: http://forum.doom9.org/showthread.php?s=&threadid=27936

    Arguments:
        infile (str): Full path to the file that should be downmixed

    Keyword arguments:
        pro_logic_2 (bool): Set to downmix to Dolby Pro Logic II.
            This is the default. Setting to False will downmix in Dolby Pro Logic.
        flac (bool): Set to output as FLAC encoded file. Default is OGG.
        aac (bool): Set to output as AAC encoded file. Default is OGG.
        time (str): String in format HH:MM:SS.0 specifing the
            length of the downmix. Default is complete stream.

    Returns:
        None: A stereo downmix of audio tracks in infile with the same name as input.
            Only first audio stream is downmixed

    """

    infile  = os.path.abspath( infile )
    base = ['ffmpeg','-y', '-nostdin', '-v', 'quiet', '-stats', '-i',infile]
    opts = ['-vn', '-ac', '2', '-b:a', '192k']

    if outdir is None:
        outdir = os.path.dirname( infile )
    outfile = os.path.splitext( os.path.basename(infile) )[0]
    outfile = os.path.join(outdir, outfile)
    if flac:
        outfile += '.flac'
        opts.extend( ['-c:a','flac'] )
    elif aac:
        outfile += '.m4a'
        opts.extend( ['-c:a','aac'] )
    else:
        outfile += '.ogg'
        opts.extend( ['-c:a','libvorbis'] )
    opts.extend( ['-af', get_downmix_filter(pro_logic_2) ] )
    cmd = base + opts
    if time is not None:
        cmd.extend( ['-t', str(time)] )
    cmd.append( outfile )

    proc = run( cmd, stdout=DEVNULL, stderr=STDOUT, check=False )
    if proc.returncode == 0:
        return outfile
    if os.path.isfile( outfile ):
        os.remove( outfile )
    return None
