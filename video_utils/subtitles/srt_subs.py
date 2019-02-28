import logging;
import os;
from datetime import datetime, timedelta;

class srt_subs():
  def __init__(self, file):
    '''
    Name:
       srt_subs_parser
    Purpose:
       A python class to parse SRT subtitle files
    Inputs:
       file : Full path to srt file
    Outputs:
       None.
    Keywords:
       None.
    Author and History:
       Kyle R. Wodzicki     Created 16 Sep. 2017

    '''
    self.log = logging.getLogger(__name__)
    if not os.path.isfile( file ):
      self.log.error( 'File does NOT exist!' )
      return;
    elif not file.endswith('.srt'):
      self.log.error( 'Not an SRT file!' )
      return;
    self.file = file;
    self.subs = [];                                                             # Initialize subs attribute as list
    self.fmt  = '%H:%M:%S,%f'; # Time format
    self.parse_subs();
  ##############################################################################
  def parse_subs(self):
    '''
    Name:
       parse_subs
    Purpose:
       A python function to parse subtitles from an SRT
       file into a list of dictionaries
    Inputs:
       None.
    Outputs:
       Adds a list of dictionaries to the class
    Keywords:
       None.
    Author and History:
       Kyle R. Wodzicki     Created 16 Sep. 2017
    '''
    with open(self.file, 'r') as f: lines = f.readlines();                      # Open input file for reading
    self.raw = ''.join(lines);
    lines = [line.rstrip() for line in lines];                                  # Strip return characters
    nLines, i = len(lines), 0;                                                  # Get number of lines and set i counter to zero (0)
    while i < nLines:                                                           # Iterate while i less than number of lines
      if lines[i].isdigit():                                                    # If the line is a digit then begging of sub title
        times = lines[i+1].split();                                             # Line i+1 is the start and end time of the subtitle; split on space
        self.subs.append(
          {'sub_num' : int(lines[i]), 
           'start'   : times[0],
           'end'     : times[2], 
           'text'    : []});                                                    # Append initial subtitle dictionary to subs list with subtitle number, start/end times, and empty list for text
        i += 2;                                                                 # Increment i by tow (2) to skip start/stop time and get to first line of subtitle text
        while not lines[i].isdigit():                                           # While line[i] is not a digit, i.e., the next subtitle, iterate
          self.subs[-1]['text'].append( lines[i] );                             # Append the line to the list of subtitle text
          i += 1;                                                               # Increment i by one (1)
          if i >= nLines: break;                                                # If i is greater equal number of lines, then break while loop
  ##############################################################################
  def adjust_timing( self, offset ):
    '''
    Name:
       adjust_timing
    Purpose:
       A python function to adjust timing of subtitles
    Inputs:
       offset : Change in time in seconds. Positive numbers
                 shift to later time, negative to earlier.
    Outputs:
       Updates the self.subs array
    Keywords:
       None.
    Author and History:
       Kyle R. Wodzicki     Created 16 Sep. 2017
    '''
    dlt   = timedelta(milliseconds = offset);                                   # Set time offset based on input
    start = datetime.strptime(self.subs[0]['start'], self.fmt);                 # Get start time of first subtitle in datetime format
    if (start + dlt).year < 1900:                                               # If the year of the change to the first subtitle is less than 1900, then the time would be negative, so much change time delta
      dlt = datetime(1900, 1, 1, 0, 0, 0) - start;                              # Compute time delta so that start time of first subtitle is zero (0)
      self.log.warning( 
        'Offset too large (start time < zero) changed to: {}'.format( -dlt )
      );                                                                        # Log message that the time delta has been changed
    for i in range( len(self.subs) ):                                           # Iterate over every subtitle
      for j in ['start', 'end']:                                                # Iterate over the start and end tags
        time = datetime.strptime( self.subs[i][j], self.fmt) + dlt;             # Compute new timing
        self.subs[i][j] = time.strftime( fmt )[:-3];                            # Update timing in the dictionary of the subs array
  ##############################################################################
  def write_file(self, raw = False):
    '''
    Name:
       write_file
    Purpose:
       A python function to write subtitle data to SRT file.
    Inputs:
       None.
    Outputs:
       Updates SRT file input
    Keywords:
       raw   : Set to True to write raw data.
    Author and History:
       Kyle R. Wodzicki     Created 16 Sep. 2017
    '''
    if len(self.subs) == 0:                                                     # If there are NO subtitles in the subs attribute
      self.log.warning( 'No subtitles read in!' );                              # Log message that no subtitles were read in
      return;                                                                   # Return
    else:                                                                       # Else, there are subtitles
      with open(self.file, 'w') as f:                                           # Open file for writing
        if raw:
          f.write( self.raw );
        else:
          for i in self.subs:                                                   # Iterate over subtitles
            f.write( str(i['sub_num']) + '\n' );                                # Write the subtitle number
            f.write( ' --> '.join( [i['start'], i['end'] ] ) + '\n' );          # Write subtitle timing
            f.write( '\n'.join( i['text'] ) + '\n' );                           # Write subtitle text