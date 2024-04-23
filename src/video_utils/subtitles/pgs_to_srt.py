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
    Options,
    Pgs, PgsSubtitleItem,
    PgsToSrtRipper,
)

from .srt_utils import srt_cleanup

PGS_HEADER = 13

def rmfile( *args ):
    """
    Remove file(s) without errors

    Try to remove file(s); suppress errors

    Arguments:
        *args : Any number of files to remove

    Returns:
        None

    """

    for arg in args:
        try:
            os.remove( arg )
        except:
            pass

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

class PgsParser( ):
    """
    Parse information from PGS file

    """

    def __init__(self, pgs, lang):

        self.log = logging.getLogger(__name__)
        self.pgs = pgs
        self.media_path = MPath(pgs, lang)

    def gen_segments( self ):
        """Generate segments from PGS file"""

        self.log.debug('Generating PGS segments')
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

    def gen_display_sets( self ):
        """Generate DisplaySet(s) from PGS file"""

        self.log.debug('Generating display sets')
        index    = 0
        segments = []
        for seg in self.gen_segments():
            segments.append( seg )
            if seg.type == SegmentType.END:
                yield DisplaySet(index, segments)
                segments = []
                index += 1

    def gen_pgs_subtitle_items( self ):
        """Generate PgsSubtitleItem(s) from PGS file"""

        self.log.debug('Generating subtitle items')
        index = 0
        sets  = []
        for dis_set in self.gen_display_sets( ):
            if sets and dis_set.is_start():
                yield PgsSubtitleItem(index, self.media_path, sets )
                sets   = []
                index += 1
            sets.append( dis_set )

def pgs_to_srt( out_file, text_info, delete_source=False, **kwargs ):
    """
    Convert PGS (.sup) to SRT

    Arguments:
        File (path-like) : Location of source PGS
            file to convert to SRT
        lang (str) : 2-character code for subtitle 
            language.

    """

    log      = logging.getLogger( __name__ )
    sup_file = f"{out_file}{text_info['ext']}.sup"
    srt_file = f"{out_file}{text_info['ext']}.srt"

    if os.path.isfile( srt_file ):
        return 1, sup_file

    if not os.path.isfile( sup_file ):
        return 2, sup_file

    log.info( "Parsing PGS file : %s", sup_file )
    parse = PgsParser(sup_file, text_info.get('lang3', 'und'))
    opts  = Options()
    pgs   = Pgs(parse.media_path, opts, b'', '')
    pgs._items = list( parse.gen_pgs_subtitle_items( ) )
    if len(pgs._items) == 0:
        log.warning( "No subtitles found in PGS file, removing : %s", sup_file )
        rmfile( sup_file, srt_file )
        return 2, ''

    log.info( "Converting images to SRT" )
    srt = PgsToSrtRipper( pgs, opts ).rip( None )
    if len(srt) == 0:
        log.warning( "No subtitles converted to SRT : %s", sup_file )
        rmfile( srt_file )
        return 2, ''

    log.info( "Saving SRT data to file : %s", srt.path )
    srt.save()
    srt_cleanup( srt.path )

    if delete_source:
        log.info( "Deleting PGS file : %s", sup_file )
        os.remove( sup_file )

    return 0, srt.path
