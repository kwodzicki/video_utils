import logging;
import os, sys, re;
from urllib.request import urlopen;
from subprocess import Popen, STDOUT, DEVNULL

from xml.etree import ElementTree as ET

from video_utils.utils.checkCLI import checkCLI

try:                                                                        # Try to...
    from video_utils.videotagger.metadata.getMetaData import getMetaData;   # Import getMetaData function from makemkv_to_mp4
except:                                                                     # On exception...
    getMetaData = None
 
try:
  checkCLI( 'mkvpropedit' )
except:
  logging.getLogger(__name__).error('mkvpropedit NOT installed')
  raise

################################################################################
def downloadCover( outDir, metaData ):
    '''
    Name:
        downloadCover
    Purpose:
        Function to download cover art image
    Inputs:
        outDir   : Output directory for the covert art file
        metaData : Dictionary containing metaData; idealy from getMetaData
                    function
    Keywords:
        None.
    Outputs:
        Creates outDir/cover[.png, .jpeg] if cover art data downloaded
    '''
    log = logging.getLogger(__name__)
    if ('full-size cover url' in metaData):                                         # If the 'full-size cover url' is in the metaData
        log.debug('Attempting to get coverart');                                    # Debugging information
        url = metaData['full-size cover url'];                                      # Get image url
        if url.endswith('png'):
            coverFile = os.path.join( outDir, 'cover.png' )
        else:
            coverFile = os.path.join( outDir, 'cover.jpeg' )
    
        log.info('Downloading cover art');                                          # Log some information
        try:                                                                        # Try to...
            data = urlopen( url ).read();                                             # Download the image data
        except:                                                                     # On exception...
            log.warning( 'Could NOT download cover art!' );                           # log a warning
        else:                                                                       # Else, try was successful 
            log.info('Download successful!');                                         # Log some information
            with open(coverFile, 'wb') as fid:
                fid.write( data )
            return coverFile
    return None

################################################################################
def encode( input ):
    '''Function to encode data to correct type'''
    if isinstance(input, (list,tuple,)):                                            # If the input is type list
        try:                                                                        # Try to...
            return ', '.join( [ i['name'] for i in input ] )                        # Convert to binary strings taking the 'name' of every element of i
        except:                                                                     # On exception
            return ', '.join( input )                                               # Convert each element to binary string
    else:                                                                           # Else, not a list
        return input                                                                # Just get binary string

################################################################################
def getPlot( metaData, short = False ):
    '''Function to parse plot information'''
    for tag in ["plot outline", "plot"]:                                          # Iterate over the two tags
        if tag in metaData:                                                         # If the tag is in metaData dictionary
            tmp = metaData[tag];                                                      # Set tmp to metaData[tag]
            if type(tmp) is not list: tmp = [ tmp ];                                  # If tmp is NOT a list, make it a list
            for i in tmp:                                                             # Iterate over every element of tmp
                if short:                                                               # If the short keyword is set, try to return the short (<240 characters) plot
                    if len(i) < 240: return i;                                            # If the length of i is less than 240 characters, return i
                else:                                                                   # Else, short is NOT set so attempt to return long plot
                    if len(i) > 240: return i;                                            # If the length of i is greater than 240 characters, return the plot
    return None;                                                                  # If made it here, nothing matched criteria so return None.

################################################################################
def addTarget( ele, level ):
  tags = ET.SubElement(ele, 'Tag')
  targ = ET.SubElement(tags, 'Targets')
  ET.SubElement(targ, 'TargetTypeValue').text = str(level)
  return tags

################################################################################
def addTag( ele, key, val ):
    simple = ET.SubElement(ele, 'Simple')
    ET.SubElement(simple, 'Name').text   = key
    ET.SubElement(simple, 'String').text = str(val)

################################################################################
def mkvTags( file, IMDbid=None, metaData = None ):
    '''
    Name:
        mkvTags
    Purpose:
        A function to parse information from the IMDbPY API and
        write Tag data to MP4 files.
    Inputs:
        file   : Full path of file to write metadata to.
    Outputs:
        Returns following values based on completion.
             0 : Completed successfully.
             1 : Input was NOT and MKV
             2 : IMDb ID was not valid
             3 : Failed to download information from IMDb AND themoviedb.org
             4 : Writing tags is NOT possible
             5 :    Failed when trying to remove tags from file.
             6 : Failed when trying to write tags to file.
            10 : IMDbPY not installed AND getTMDb_Info failed to import
            11 : File is too large
    Keywords:
        IMDbid    : Set to the IMDb id to use for file.
                                 Default tries to get from file name.
        metaData : Set to result of previous call to
                                 imdb.IMDb().get_movie(). Default is to 
                                 download the data.
    Dependencies:
        mkvpropedit
    Author and History: 
        Kyle R. Wodzicki     Created 18 Feb. 2018
    '''
    log = logging.getLogger(__name__);                                              # Set up a logger
    log.debug( 'Testing file is MKV' );                                             # Debugging information
    if not file.endswith('.mkv'):                                                   # If the input file does NOT end in '.mp4'
        log.error('Input file is NOT an MKV!!!'); return 1;                         # Print message and return code one (1)

    log.debug( 'Testing file too large' );                                          # Debugging information
    if os.stat(file).st_size > sys.maxsize:                                         # If the file size is larger than the supported maximum size
        log.error('Input file is too large!'); return 11;                           # Print message and return code eleven (11)
        
    if metaData is None:                                                            # IF the metaData key is NOT set
        log.debug( 'No metadata input, attempting to download' );                   # Debugging information
        if IMDbid is None:                                                          # If no IMDbid was input
            log.debug( 'No IMDb ID input, extracting from file name' );             # Debugging information
            try:                                                                    # Try to...
                IMDbid = file.split('.')[-2];                                       # Get IMDbid from file name (using makemkv_to_mp4 file naming convention)
            except:                                                                 # On exception
                log.warning( 'Could NOT get IMDb ID from file!' );                  # Warning information information
                return 2;                                                           # Return 2
            if IMDbid[:2] != 'tt':                                                  # If the first to characters of the IMDb ID are NOT 'tt'
                log.warning( 'IMDb ID not vaild!' );                                # Warning information information
                return 2;                                                           # Return 2
        if (getMetaData is None):
            log.error('IMDbPY and API key(s) NOT installed!');                      # Log an error
            return 10;                                                              # Return from function
        else:                                                                       # If import successfull
            metaData = getMetaData( IMDbid );                                       # Get the metaData from imdb.com and themoviedb.org
    if len(metaData.keys()) < 2:                                                    # If less than two (2) tags in dictionary
        log.warning('Failed to download metaData! Tag(s) NOT written!');            # Log a warning that the metaData failed to download
        return 3;                                                                   # Return code 3
    if IMDbid is None: IMDbid = 'tt' + metaData.getID();                            # Get IMDb ID if it is NOT set
    filedir, filebase = os.path.dirname( file ), os.path.basename( file );          # Get the directory and baseanem of the file
    re_test = re.match(re.compile(r's\d{2}e\d{2} - '), filebase);                   # Test for if the file name starts with a specific pattern, then it is an episode
    se_test = 'series title' in metaData and 'season' in metaData and 'episode' in metaData;  # Test for if there is a season AND episode tag in the imdb information

    log.debug('Setting up title information base on episode/movie');              # Debugging information
    prefix, qualifier = '', '';                                                   # Initialize a prefix and qualifier for the video title
    if se_test and not re_test:                                                   # If the se test is True, but the re_test is false
        prefix = 's{:02d}e{:02d} - '.format(metaData['season'],metaData['episode']);# Set up season prefix
    if not se_test and not re_test:                                               # If both the se and re tests are False
        qualifier = filebase.split('.')[1];                                         # Set the qualifier
        if qualifier != '': qualifier = ' - ' + qualifier;                          # Update the qualifier

    log.debug('Setting basic inforamtion');                                       # Debugging information
    top = ET.Element('Tags')

    if (se_test or re_test):
        # Work on collection level data, i.e., data for the show
        tags = addTarget( top, '70')
        if 'seriesName' in metaData: 
            addTag(tags, 'TITLE', metaData['seriesName'])                                    # Append TV show name to the mp4cmd
        elif 'series title' in metaData:                               
            addTag(tags, 'TITLE', metaData['series title'])                                    # Append TV show name to the mp4cmd
    
        # Work on edition/issue/volume/opus level data, i.e., data for the season
        tags = addTarget( top, '60')
        if 'season'  in metaData: addTag( tags, 'PART_NUMBER',  metaData['season'] ); # Set the season number
        if 'first_air_date' in metaData:                                                    # If the air_date key is present
            addTag( tags, 'DATE_RELEASED', metaData['first_air_date'] )                         # Set the air date
            
    # Work on edition/issue/volume/opus level data, i.e., data for the season
    tags = addTarget( top, '50')
    if 'episode'  in metaData: addTag( tags, 'PART_NUMBER',  metaData['episdoe'] ); # Set the season number
    if 'title' in metaData:
        addTag(tags, 'TITLE', prefix + metaData['title'])
        if (qualifier != ''): addTag(tags, 'SUBTITLE', qualifier)                 # Set the movie/show title
    if 'genre'   in metaData:        
        addTag(tags, 'GENRE', ','.join( [ i['name'] for i in metaData['genre'] ] ) )
    if 'air_date' in metaData:                                                    # If the air_date key is present
        addTag( tags, 'DATE_RELEASED', metaData['air_date'] )                         # Set the air date
    elif 'year' in metaData:    
        addTag( tags, 'DATE_RELEASED', metaData['year'] )                         # Set the air date

    if (se_test or re_test):
        addTag(tags, 'CONTENT_TYPE', 'episode')
    else:
        addTag(tags, 'CONTENT_TYPE', 'movie')
  
    if 'mpaa' in metaData:
        addTag(tags, 'LAW_RATING', encode( metaData['mpaa'].split(' ') ) )                      # Split the rating information on spaces
    
    if 'production companies' in metaData: 
        addTag( tags, 'PRODUCTION_STUDIO', encode( metaData['production companies'] ) )                 # Set the metadata

    if 'cast' in metaData:        
        addTag( tags, 'ACTOR', encode( metaData['cast'] ) );                                 # Set the metadata

    if 'director' in metaData:
        addTag( tags, 'DIRECTOR', encode( metaData['director'] ) );                             # Set the metadata

    if 'writer' in metaData:
        addTag( tags, 'WRITTEN_BY', encode( metaData['writer'] ) );                               # Set the metadata

    log.debug('Setting plot inforamtion');                                        # Debugging information
    shortPlot = getPlot(metaData, True);                                          # Get short plot description
    longPlot  = getPlot(metaData);                                                # Get long plot description
    if shortPlot: addTag(tags, 'SUMMARY',  shortPlot)                             # If short plot available, write it to the file
    if longPlot:  addTag(tags, 'SYNOPSIS', encode( longPlot ) )                   # If long plot available, write it to the file


    fileDir   = os.path.dirname( file )
    xmlFile   = os.path.join( fileDir, 'tags.xml' )

    ET.ElementTree(top).write( xmlFile ) 

    cmd = ['mkvpropedit', file, '-t', 'all:{}'.format(xmlFile)]

    coverFile = downloadCover( fileDir, metaData )
    if coverFile:                                         # If the 'full-size cover url' is in the metaData
        cmd += ['--attachment-name', 'Cover art']
        cmd += ['--add-attachment',   coverFile] 

    log.debug('Saving tags to file');                                             # Debugging information
   
    proc = Popen(cmd, stdout = DEVNULL, stderr = STDOUT)
    proc.wait()
  
    try:
        os.remove( xmlFile )
    except:
        pass

    try:
        os.remove( coverFile )
    except:
        pass
  
    if (proc.returncode != 0): 
        log.error('Failed to save tags to file!');                                  # Log an error
        return 6
 
    return 0;
