import os, shutil

from PyQt5.QtWidgets import QMainWindow, QWidget, QFileDialog, QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QAction
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt

from ..config import APPDIR
from . import Movie, Episode
from .utils import downloadCover 
from .writers import writeTags
from .readers import mp4Reader

HOME                = os.path.expanduser('~')
HOME                = '/mnt/Media_6TB/testing'
CACHE_DIR           = os.path.join(APPDIR, 'poster_cache')

EXT_FILTER          = "Videos (*.mp4 *.mkv)"

SEARCH_ID_TEXT      = 'Series or Movie ID'
SEARCH_SEASON_TEXT  = 'Season # (optional)'
SEARCH_EPISODE_TEXT = 'Episode # (optional)' 

os.makedirs(CACHE_DIR, exist_ok = True)

class SearchWidget( QWidget ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    layout      = QHBoxLayout()

    self.comboBox = QComboBox()
    self.comboBox.addItem('')
    self.comboBox.addItem('TMDb')
    self.comboBox.addItem('TVDb')
    layout.addWidget( self.comboBox )

    self.dbID_box   = QLineEdit()
    self.dbID_box.setPlaceholderText( SEARCH_ID_TEXT )
    layout.addWidget( self.dbID_box )

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
    self.comboBox.setCurrentIndex(0)
    self.dbID_box.setText('')
    self.season_box.setText('')
    self.episode_box.setText('')

  def registerFunc(self, func):
    self.search_btn.clicked.connect( func )

  def search(self, *args, **kwargs):
    '''
    Purpose:
      Method to run when the 'Search' button is pushed.
      Parses information in search boxes and makes API request
    Inputs:
      Any, none used
    Keywords:
      Any, none used
    Returns:
      An instance of either TVDbMovie, TVDbEpisode, TMDbMovie, TMDbEpisode
      based on search criteria. If bad criteria, then returns None.
    '''
    dbName  = self.comboBox.currentText()                                                   # Use current text as db name
    dbID    = self.dbID_box.text()
    season  = self.season_box.text()
    episode = self.episode_box.text() 

    if dbID == '':                                                                    # If dbID is None
      print('No database ID set')                                                       # Error
      return None                                                                       # Return None
    else:                                                                               # Else
      args = [dbID]                                                                     # Set args to list with just dbID for now
      if season != '' and episode != '':                                    # If both season and episode are NOT None
        args.extend( [season, episode] )                                                # Extend the args list
      if dbName == '':                                                                  # If the dbName is empty; i.e., user did not pick a database
        if len(args) == 3:                                                              # If there are 3 arguments
          dbName = 'TVDb'                                                               # Default to TVDb because is tv episode
          self.comboBox.setCurrentIndex(2)                                                   # Change comboBox value to be TVDb
        else:                                                                           # Else
          dbName = 'TMDb'                                                               # Set dbName to TMDb
          self.comboBox.setCurrentIndex(1)                                                   # Change comboBox value to be TMDb

    if dbName == 'TVDb':                                                                # If TVDb
      if len(args) == 3:                                                                # If episode
        info = Episode.TVDbEpisode( *args )                                             # Get episode
      else:                                                                             # Else
        info = Movie.TVDbMovie( *args )                                                 # Get movie
    elif dbName == 'TMDb':                                                              # Else, if TMDb
      if len(args) == 3:                                                                # If episode
        info = Episode.TMDbEpisode( *args )                                             # Get episode
      else:                                                                             # Else
        info = Movie.TMDbMovie( *args )                                                 # Get movie
    else:                                                                               # Else, something went wrong
      print( 'Error' )
      return None                                                                       # Return None

    return info.metadata()                                                              # Return Info

class MetadataWidget( QWidget ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.cover  = ''
    self.layout = QGridLayout()
    self.row    = 0

    self.title   = self._addField('Title',    'Movie or Episode title' )
    self.series  = self._addField('Series',   'TV series title' )
    self.season  = self._addField('Season',   'Season number',  colspan=2); self.row-=2
    self.episode = self._addField('Episode',  'Episode number', colspan=2, col=2)
    self.year    = self._addField('Year',     'Year of release/airing' )
    self.rating  = self._addField('Rating',   'Content rating' )
    self.sPlot   = self._addField('Synopsis', 'Short synopsis of movie/episode', True); self.row -= 2
    self.comment = self._addField('Comments', 'User comments', textedit=True, col=4, rowspan=3)
    self.lPlot   = self._addField('Summary',  'Longer summary of movie/episode', True)
    self.genre   = self._addField('Genre',    'Comma separated list of genres' )
    self.curFile = self._addField('Current File', 'No file currently loaded', colspan=5 )

   
    label        = QLabel('Poster/Coverart')
    self.poster  = QLabel()
    self.poster.setFixedSize(320, 180)
    self.layout.addWidget( label,       0, 4)
    self.layout.addWidget( self.poster, 1, 4, 6, 1)

    self.setLayout( self.layout )

  def _addField(self, label, placeholder, textedit = False, col=0, rowspan=1, colspan=4):
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
 
  def _updateCover(self, info):
    pix        = None
    self.cover = info.get('cover', '')
    if self.cover:
      if isinstance(self.cover, bytes):
        pix = QPixmap() 
        pix.loadFromData( self.cover ) 
      else:
        coverFile = downloadCover( self.cover, saveDir = CACHE_DIR )
        if coverFile:
          pix = QPixmap(coverFile) 
      if pix:
        pix = pix.scaled(self.poster.width(), self.poster.height(), Qt.KeepAspectRatio)
        self.poster.setPixmap( pix )
    else:
      self.poster.setPixmap( QPixmap() )

  def _updateData(self, info):
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
    self._updateCover( info )

    if len(info) == 0: self.curFile.setText('')

  def _writeData(self):
    curFile = self.curFile.text()
    if curFile == '':
      dialog = QFileDialog()
      curFile = dialog.getOpenFileName(directory = HOME, filter=EXT_FILTER)[0]
      if curFile == '':
        return
      self.curFile.setText( curFile )

    info = {'year'       : self.year.text(),
            'title'      : self.title.text(),
            'seriesName' : self.series.text(),
            'seasonNum'  : self.season.text(),
            'episodeNum' : self.episode.text(),
            'sPlot'      : self.sPlot.toPlainText(),
            'lPlot'      : self.lPlot.toPlainText(),
            'rating'     : self.rating.text(),
            'genre'      : self.genre.text().split(','),
            'comment'    : self.comment.toPlainText(),
            'cover'      : self.cover
    }

    for key in ['seasonNum', 'episodeNum']:
      val = info.pop(key)
      if val: info[key] = int( val )
    writeTags(curFile, info)

  def _openFile(self, filePath):
    if filePath.endswith('.mp4'):
      info = mp4Reader( filePath )
      self._updateData( info )
      self.curFile.setText( filePath )
    elif filePath.endswith('.mkv'):
      print('Loading metadata from MKV file')
    else:
      print('Unsupported file type')


class VideoTaggerGUI( QMainWindow ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__initUI()

  def __initUI(self):
    mainMenu = self.menuBar()
    fileMenu = mainMenu.addMenu('File')    
    openFile = QAction( '&Open File', self )
    openFile.triggered.connect( self._openFile )
    reset = QAction( '&Reset', self )
    reset.triggered.connect( self._reset )
    fileMenu.addAction( openFile )
    fileMenu.addSeparator()
    fileMenu.addAction( reset )

    self.mainLayout = QVBoxLayout()

    self.searchWidget = SearchWidget()
    self.searchWidget.registerFunc( self.getMetadata )
    self.mainLayout.addWidget( self.searchWidget )

    self.metadataWidget = MetadataWidget()
    self.mainLayout.addWidget( self.metadataWidget )

    self.saveBtn = QPushButton('Write Tags')
    self.saveBtn.clicked.connect( self.metadataWidget._writeData )
    self.mainLayout.addWidget( self.saveBtn )
 
    self.mainWidget = QWidget()
    self.mainWidget.setLayout( self.mainLayout )
    self.setCentralWidget( self.mainWidget )

  def _reset(self, *args, **kwargs):
    self.searchWidget._reset()
    self.metadataWidget._updateData( {} )

  def _openFile(self):
    dialog = QFileDialog()
    curFile = dialog.getOpenFileName(directory = HOME, filter=EXT_FILTER)[0]
    if curFile == '':
      print( 'No file selected' )
    else:
      self.metadataWidget._openFile( curFile )

  def getMetadata(self, *args, **kwargs):
    info = self.searchWidget.search(self, *args, **kwargs)
    if info:
      self.metadataWidget._updateData( info )

  def closeEvent(self, event):
    shutil.rmtree( CACHE_DIR )
    event.accept()
