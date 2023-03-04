"""
Parser/converter for PGS (.sup) files

Makes use of pgsrip package to make a
'simplified' converter for PGS files

"""

import logging
import os

from pgsrip.media_path import MediaPath, Language 
from pgsrip.pgs import (
    SEGMENT_TYPE, SegmentType, 
    DisplaySet, from_hex,
)
from pgsrip.ripper import (
    SubRipFile,
    Options,
    Pgs, PgsSubtitleItem,
    PgsToSrtRipper,
)

PGS_HEADER = 13

class MPath( MediaPath ):
    """
    Overrides some of MediaPath functionality

    Wanted to be able to explicitly set the 
    language and have the string representation
    be a bit different

    """

    def __init__(self, path, lang: str = 'und'):

        super().__init__(path)

        self.base_path, _ = os.path.splitext(path) 
        self.language = (
            lang 
            if (lang == 'und') else 
            Language.fromcleanit(lang)
        )

    def __str__(self):

        return f"{self.base_path}.{self.extension}"

class PgsParser( object ):
    """
    Parse information from PGS file

    """

    def __init__(self, pgs, lang):

        self.pgs = pgs
        self.media_path = MPath(pgs, lang)

    def genSegments( self ):
        """Generate segments from PGS file"""
    
        with open(self.pgs, 'rb') as iid:
            info = iid.read(PGS_HEADER)
            while info:
                if info[:2] != b'PG':
                    break
                if len(info) < PGS_HEADER: 
                    break
                
                segment_type = SEGMENT_TYPE[ SegmentType(info[10] ) ]
                size = from_hex( info[-2:] )
                yield segment_type( info+iid.read(size) )
                info = iid.read(PGS_HEADER)
    
    def genDisplaySets( self ):
        """Generate DisplaySet(s) from PGS file"""
    
        index    = 0
        segments = []
        for s in self.genSegments():
            segments.append( s )
            if s.type == SegmentType.END:
                yield DisplaySet(index, segments)
                segments = []
                index += 1
    
    def genPgsSubtitleItems( self ):
        """Generate PgsSubtitleItem(s) from PGS file"""

        index = 0
        sets  = []
        for ds in self.genDisplaySets( ):
            if sets and ds.is_start():
                yield PgsSubtitleItem(index, self.media_path, sets )
                sets   = []
                index += 1
            sets.append( ds )

def pgs_to_srt( pgsFile, lang ):
    """
    Convert PGS (.sup) to SRT

    Arguments:
        pgsFile (path-like) : Location of source PGS
            file to convert to SRT
        lang (str) : 2-character code for subtitle 
            language.

    """

    log        = logging.getLogger( __name__ )
    parse      = PgsParser( pgsFile, lang )
    opts       = Options()
    pgs        = Pgs(parse.media_path, opts, b'', '')
    pgs._items = list( parse.genPgsSubtitleItems( ) )

    srt = PgsToSrtRipper( pgs, opts ).rip( None )
    if len(srt) == 0:
        log.warning( f"No subtitles found for {pgsFile}" ) 
        return

    srt.save()
