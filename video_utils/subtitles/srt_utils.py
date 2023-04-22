"""
Utilities for working with SRT files

These tools can be used to clean up SRT files after converstion
from image based formats, or it interact/update existing SRT files.

"""

import logging
import os
import re
from datetime import datetime, timedelta

EIGHTH_NOTE       = '\xe2\x99\xaa'
LEFT_SINGLE_QUOTE = '\xe2\x80\x98'

class SRTsubs():
    """A python class to parse SRT subtitle files"""

    def __init__(self, fpath):
        """
        Initialize the class

        Arguments:
            fpath (str): Full path to srt file

        Keywords:
            None.

        Returns:
            Class object

        """

        self.log = logging.getLogger(__name__)
        if not os.path.isfile( fpath ):
            self.log.error( 'File does NOT exist!' )
            return
        if not fpath.endswith('.srt'):
            self.log.error( 'Not an SRT file!' )
            return
        self.fpath = fpath
        self.subs = []
        self.fmt  = '%H:%M:%S,%f'
        self.parse_subs()

    def parse_subs(self):
        """
        Parse subtitles from an SRT file into a list of dictionaries

        Arguments:
            None

        Keyword arguments:
            None

        Returns:
            None: Adds a list of dictionaries to the class

        """

        with open(self.fpath, mode='r', encoding='utf8') as fid:
            lines = fid.readlines()

        self.raw = ''.join(lines)
        lines = [line.rstrip() for line in lines]# Strip return characters
        nlines, i = len(lines), 0
        while i < nlines:
            if not lines[i].isdigit():
                i+=1
                continue

            # If made here, the line is a digit then begging of sub title
            # Line i+1 is the start and end time of the subtitle; split on space
            times = lines[i+1].split()

            # Append initial subtitle dictionary to subs list with subtitle
            # number, start/end times, and empty list for text
            self.subs.append(
                {
                    'sub_num' : int(lines[i]), 
                    'start'   : times[0],
                    'end'     : times[2], 
                    'text'    : [],
                }
            )
            # Increment i by tow (2) to skip start/stop time and get to first
            # line of subtitle text
            i += 2
            # While line[i] is not a digit, i.e., the next subtitle, iterate
            while not lines[i].isdigit():
                # Append the line to the list of subtitle text
                self.subs[-1]['text'].append( lines[i] )
                i += 1
                if i >= nlines:
                    break

    def adjust_timing( self, offset ):
        """
        Adjust timing of subtitles

        Arguments:
            offset (float): Change in time in seconds. Positive numbers
                shift to later time, negative to earlier.

        Keyword arguments:
            None

        Returns:
            None: Updates the self.subs array

        """

        # Set time offset based on input
        dlt   = timedelta(milliseconds = offset)
        # Get start time of first subtitle in datetime format
        start = datetime.strptime(self.subs[0]['start'], self.fmt)

        # If the year of the change to the first subtitle is less than 1900,
        # then the time would be negative, so much change time delta
        if (start + dlt).year < 1900:
            # Compute time delta so that start time of first subtitle is zero (0)
            dlt = datetime(1900, 1, 1, 0, 0, 0) - start
            self.log.warning(
                'Offset too large (start time < zero) changed to: %d',
                -dlt
            )
        # Iterate over every subtitle
        for i, sub in enumerate(self.subs):
            # Iterate over the start and end tags
            for j in ['start', 'end']:
                # Compute new timing
                time = datetime.strptime( sub[j], self.fmt) + dlt
                # Update timing in the dictionary of the subs array
                self.subs[i][j] = time.strftime( self.fmt )[:-3]

    def write_file(self, raw = False):
        """
        Write subtitle data to SRT file.

        Arguments:
            None

        Keyword arguments:
            raw   : Set to True to write raw data.

        Returns:
            None: Updates SRT file input

        """

        if len(self.subs) == 0:
            self.log.warning( 'Now subtitles read in!' )
            return

        with open(self.fpath, mode='w', encoding='utf8') as fid:
            if raw:
                fid.write( self.raw )
            else:
                for sub in self.subs:
                    fid.write( f"{sub['sub_num']}{os.linesep}" )
                    fid.write( f"{sub['start']} --> {sub['end']}{os.linesep}" )
                    fid.write( os.linesep.join( sub['text'] ) )
                    fid.write( os.linesep )

def srt_cleanup( fname, **kwargs ):
    """
    Fix some known bad characters in SRT file

    A python function to replace J' characters at the beginning or ending of 
    a subtitle line with a musical note character as this seems to be an issue 
    with the vobsub2srt program.

    Arguments:
        fname  : Path to a file. This file will be overwritten.

    Keyword arguments:
        verbose : Set to increase verbosity.

    Returns:
        int: Outputs a file to the same name as input, i.e., over writes the file.

    """

    log = logging.getLogger(__name__)
    out_file = fname + '.tmp'
    iid   = open(fname,    mode='r', encoding='utf8')
    oid   = open(out_file, mode='w', encoding='utf8')
    music = False
    for i, in_line in enumerate(iid):
        line = in_line.rstrip()
        if len(line) == 0:
            music = False
            os.write(line + os.linesep)
            continue

        # Checking for J' at beginning or end of line, likely music note
        if line[:4]  == f"J{LEFT_SINGLE_QUOTE}":
            log_msg = f"Line: {i} changed {line}"
            # Replace J' with the music note
            line = f"{EIGHTH_NOTE} {line[4:]}"
            # If the end of the line is J'
            if line[-4:] == f"J{LEFT_SINGLE_QUOTE}":
                line = f"{line[:-4]} {EIGHTH_NOTE}"
            log.debug( '%s ---> %s', log_msg, line )
            music = True
        # Else, if the J' is at the end of the line
        elif line[-4:] == f"J{LEFT_SINGLE_QUOTE}":
            log_msg = f"Line: {i} changed {line}"
            # Replace the J' with the music note
            line = f"{line[:-4]} {EIGHTH_NOTE}"
            log.debug( '%s ---> %s', log_msg, line )
            music = True
        # Check for ,' anywhere in line, Likely music note
        # If ,' is in the line
        elif f",{LEFT_SINGLE_QUOTE}" in line:
            # If the first characters are ,' and the last character is ;,
            # then last character should be music note
            if line[:4]  == f",{LEFT_SINGLE_QUOTE}" and line[-1] == ';':
                # Replace last character with a music note
                line = f"{line[:-1]} {EIGHTH_NOTE}"
            # Replace the ,' with a music note
            line = line.replace(f",{LEFT_SINGLE_QUOTE}", EIGHTH_NOTE+' ')
            music = True
        # If line begins and ends with capital J, then likely music notes
        elif line[0] == "J" and line[-1] == "J":
            # Replace the J's with music notes
            line = f"{EIGHTH_NOTE} {line[1:-2]} {EIGHTH_NOTE}"
            music = True
        elif line[:2] == 'J ':
            line = f"{EIGHTH_NOTE} {line[1:]}"
            music = True
        # If "J" is found followed by another capital letter, likely is a music note.
        elif re.match(re.compile(r'J[A-Z]{1}'), line):
            line = f"{EIGHTH_NOTE} {line[1:]}"
            music = True
        # If music is True, that means this line is a continuation of previous
        # line
        elif music is True:
            if line[-1] == ';':
                # If the last character is a semi colon, replace with music note
                line = f"{line[:-1]} {EIGHTH_NOTE}"
            elif line[-5:] == f", {LEFT_SINGLE_QUOTE}":
                # If the last characters are ", '" then replace with music note
                line = f"{line[:-5]} {EIGHTH_NOTE}"
            elif line[-4:] == f",{LEFT_SINGLE_QUOTE}":
                # If last characters are ",'" then replace with music note
                line = f"{line[:-4]} {EIGHTH_NOTE}"
            elif line[-4:] == '\xe2\x80\x99J':
                # If last characters are "'J" then replace with music note
                line = f"{line[:-4]} {EIGHTH_NOTE}"
            elif line[-4:] == f"J{LEFT_SINGLE_QUOTE}":
                # If the end of the line is J'
                line = f"{line[:-4]}{EIGHTH_NOTE}"
            elif line[-2:]  == ' J':
                # If last characters are " J" then replace with music note
                line = f"{line[:-2]} {EIGHTH_NOTE}"
            elif line[-1]  == 'J':
                # If last character is "J" then replace with music note
                line = f"{line[:-1]} {EIGHTH_NOTE}"
        oid.write(line + os.linesep)

    iid.close()
    oid.close()
    os.rename( out_file, fname )
    return 0
