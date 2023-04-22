"""
Widgets for videotagging GUI

"""
import logging

import os
import shutil

from PyQt5.QtWidgets import QMainWindow, QWidget, QFileDialog
from PyQt5.QtWidgets import QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QAction
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from ..config import CACHEDIR
from . import movie as _movie, episode as _episode
from .utils import download_cover
from .writers import write_tags
from .readers import mp4_reader, mkv_reader

HOME                = os.path.expanduser('~')
HOME                = '/mnt/Media_6TB/testing'

EXT_FILTER          = "Videos (*.mp4 *.mkv)"

# The following are placeholder text for search boxes
SEARCH_ID_TEXT      = 'Series or Movie ID'
SEARCH_SEASON_TEXT  = 'Season # (optional)'
SEARCH_EPISODE_TEXT = 'Episode # (optional)'

# The following define lables and placeholder text for metadata entry boxes
TITLE               = ('Title',        'Movie or Episode title')
SERIES              = ('Series',       'TV series title')
SEASON              = ('Season',       'Season number')
EPISODE             = ('Episode',      'Episode number')
YEAR                = ('Year',         'Year of release/airing' )
RATING              = ('Rating',       'Content rating' )
SPLOT               = ('Synopsis',     'Short synopsis of movie/episode')
COMMENT             = ('Comments',     'User comments')
LPLOT               = ('Summary',      'Longer summary of movie/episode')
GENRE               = ('Genre',        'Comma separated list of genres' )
CURFILE             = ('Current File', 'No file currently loaded' )

# Ensure cache directory exists
os.makedirs(CACHEDIR, exist_ok = True)

class SearchWidget( QWidget ):
    """
    Widget for searching for video

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log    = logging.getLogger(__name__)
        layout      = QHBoxLayout()

        self.combo_box = QComboBox()
        self.combo_box.addItem('')
        self.combo_box.addItem('TMDb')
        self.combo_box.addItem('TVDb')
        layout.addWidget( self.combo_box )

        self.db_id_box   = QLineEdit()
        self.db_id_box.setPlaceholderText( SEARCH_ID_TEXT )
        layout.addWidget( self.db_id_box )

        self.season_box = QLineEdit()
        self.season_box.setPlaceholderText( SEARCH_SEASON_TEXT )
        layout.addWidget( self.season_box )

        self.episode_box = QLineEdit()
        self.episode_box.setPlaceholderText( SEARCH_EPISODE_TEXT )
        layout.addWidget( self.episode_box )

        self.search_btn = QPushButton('Search')
        layout.addWidget( self.search_btn )

        self.setLayout( layout )

    def _reset(self):
        self.combo_box.setCurrentIndex(0)
        self.db_id_box.setText('')
        self.season_box.setText('')
        self.episode_box.setText('')

    def register_func(self, func):
        """
        Connect function to search button

        Arguments:
            func : Function reference to register to the 
                search button

        """

        self.search_btn.clicked.connect( func )

    def search(self, *args, **kwargs):
        """
        Method to run when the 'Search' button is pushed.

        Parses information in search boxes and makes API request

        Arguments:
            *args: Any, none used

        Keyword arguments:
            **kwargs: Any, none used

        Returns:
            An instance of either TVDbMovie, TVDbEpisode, TMDbMovie, TMDbEpisode
                based on search criteria. If bad criteria, then returns None.

        """

        db_name = self.combo_box.currentText()
        dbID    = self.db_id_box.text()
        season  = self.season_box.text()
        episode = self.episode_box.text()

        if dbID == '':
            self.log.error('No database ID set')
            return None

        # Set args to list with just dbID for now
        args = [dbID]
        if season != '' and episode != '':
            args.extend( [season, episode] )

        # If the db_name is empty; i.e., user did not pick a database
        if db_name == '':
            if len(args) == 3:
                db_name = 'TVDb'
                self.combo_box.setCurrentIndex(2)
            else:
                db_name = 'TMDb'
                self.combo_box.setCurrentIndex(1)

        if db_name == 'TVDb':
            info = (
                _episode.TVDbEpisode( *args )
                if len(args) == 3 else
                _movie.TVDbMovie( *args )
            )
        elif db_name == 'TMDb':
            info = (
                _episode.TMDbEpisode( *args )
                if len(args) == 3 else
                _movie.TMDbMovie( *args )
            )
        else:
            self.log.error( 'Something went wrong' )
            return None

        return info.metadata()

class MetadataWidget( QWidget ):
    """
    Widget for defining/displaying metadata

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log    = logging.getLogger(__name__)
        self.cover  = ''
        self.layout = QGridLayout()
        self.row    = 0

        self.title    = self._add_field( *TITLE )
        self.series   = self._add_field( *SERIES )
        self.season   = self._add_field( *SEASON,  colspan=2)
        self.row     -=2
        self.episode  = self._add_field( *EPISODE, colspan=2, col=2)
        self.year     = self._add_field( *YEAR )
        self.rating   = self._add_field( *RATING )
        self.sPlot    = self._add_field( *SPLOT,    textedit=True)
        self.row     -= 2
        self.comment  = self._add_field( *COMMENT,  textedit=True, col=4, rowspan=3)
        self.lPlot    = self._add_field( *LPLOT,    textedit=True)
        self.genre    = self._add_field( *GENRE )
        self.cur_file = self._add_field( *CURFILE, colspan=5 )

        label        = QLabel('Poster/Coverart')
        self.poster  = QLabel()
        self.poster.setFixedSize(320, 180)
        self.layout.addWidget( label,       0, 4)
        self.layout.addWidget( self.poster, 1, 4, 6, 1)

        self.setLayout( self.layout )

    def _add_field(self, label, placeholder, textedit = False, col=0, rowspan=1, colspan=4):
        label  = QLabel( label )
        if textedit:
            widget = QTextEdit()
        else:
            widget = QLineEdit()
        widget.setPlaceholderText( placeholder )
        self.layout.addWidget(label,  self.row,   col,       1, colspan)
        self.layout.addWidget(widget, self.row+1, col, rowspan, colspan)
        self.row += 2
        return widget

    def _update_cover(self, info):
        pix        = None
        self.cover = info.get('cover', '')
        if self.cover:
            if isinstance(self.cover, bytes):
                pix = QPixmap()
                pix.loadFromData( self.cover )
            elif os.path.isfile( self.cover ):
                pix = QPixmap( self.cover )
            else:
                cover_file = download_cover( self.cover, saveDir = CACHEDIR )
                if cover_file:
                    pix = QPixmap(cover_file)
            if pix:
                pix = pix.scaled(self.poster.width(), self.poster.height(), Qt.KeepAspectRatio)
                self.poster.setPixmap( pix )
        else:
            self.poster.setPixmap( QPixmap() )

    def _update_data(self, info):
        for key, val in info.items():
            if isinstance(val, (tuple,list)):
                val = ','.join(val)
            elif isinstance(val, int):
                val = str(val)
            info[key] = val

        self.title.setText(   info.get('title',      '') )
        self.series.setText(  info.get('seriesName', '') )
        self.season.setText(  info.get('seasonNum',  '') )
        self.episode.setText( info.get('episodeNum', '') )
        self.year.setText(    info.get('year',       '') )
        self.sPlot.setText(   info.get('sPlot',      '') )
        self.lPlot.setText(   info.get('lPlot',      '') )
        self.rating.setText(  info.get('rating',     '') )
        self.genre.setText(   info.get('genre',      '') )
        self.comment.setText( info.get('comment',    '') )
        self._update_cover( info )

        if len(info) == 0:
            self.cur_file.setText('')

    def _write_data(self):
        cur_file = self.cur_file.text()
        if cur_file == '':
            dialog = QFileDialog()
            cur_file = dialog.getOpenFileName(directory = HOME, filter=EXT_FILTER)[0]
            if cur_file == '':
                return
            self.cur_file.setText( cur_file )

        info = {
            'year'       : self.year.text(),
            'title'      : self.title.text(),
            'seriesName' : self.series.text(),
            'seasonNum'  : self.season.text(),
            'episodeNum' : self.episode.text(),
            'sPlot'      : self.sPlot.toPlainText(),
            'lPlot'      : self.lPlot.toPlainText(),
            'rating'     : self.rating.text(),
            'genre'      : self.genre.text().split(','),
            'comment'    : self.comment.toPlainText(),
            'cover'      : self.cover,
        }

        for key in ['seasonNum', 'episodeNum']:
            val = info.pop(key)
            if val:
                info[key] = int( val )
        write_tags(cur_file, info)

    def _open_file(self, fpath):
        if fpath.endswith('.mp4'):
            info = mp4_reader( fpath )
        elif fpath.endswith('.mkv'):
            info = mkv_reader( fpath )
        else:
            self.log.warning('Unsupported file type')
            return
        self._update_data( info )
        self.cur_file.setText( fpath )

class VideoTaggerGUI( QMainWindow ):
    """
    Main class for tagging GUI

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = logging.getLogger(__name__)
        self.__init_ui()

    def __init_ui(self):
        main_menu = self.menuBar()
        file_menu  = main_menu.addMenu('File')
        open_file  = QAction( '&Open File', self )
        open_file.triggered.connect( self._open_file )
        reset = QAction( '&Reset', self )
        reset.triggered.connect( self._reset )
        file_menu.addAction( open_file )
        file_menu.addSeparator()
        file_menu.addAction( reset )

        self.main_layout = QVBoxLayout()

        self.search_widget = SearchWidget()
        self.search_widget.register_func( self.get_metadata )
        self.main_layout.addWidget( self.search_widget )

        self.metadata_widget = MetadataWidget()
        self.main_layout.addWidget( self.metadata_widget )

        self.save_btn = QPushButton('Write Tags')
        self.save_btn.clicked.connect( self.metadata_widget._write_data )
        self.main_layout.addWidget( self.save_btn )

        self.main_widget = QWidget()
        self.main_widget.setLayout( self.main_layout )
        self.setCentralWidget( self.main_widget )

    def _reset(self, *args, **kwargs):
        self.search_widget._reset()
        self.metadata_widget._update_data( {} )

    def _open_file(self):
        dialog = QFileDialog()
        cur_file = dialog.getOpenFileName(directory = HOME, filter=EXT_FILTER)[0]
        if cur_file == '':
            self.log.error( 'No file selected' )
        else:
            self.metadata_widget._open_file( cur_file )

    def get_metadata(self, *args, **kwargs):
        """
        Search for metadata for file tagging

        """

        info = self.search_widget.search(self, *args, **kwargs)
        if info:
            self.metadata_widget._update_data( info )

    def close_event(self, event):
        shutil.rmtree( CACHEDIR )
        event.accept()
