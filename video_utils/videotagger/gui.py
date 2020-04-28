import os
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QPushButton, QComboBox, QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QAction
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from ..config import APPDIR
from . import Movie, Episode, utils

HOME                = os.path.expanduser('~')
SEARCH_ID_TEXT      = 'Series or Movie ID'
SEARCH_SEASON_TEXT  = 'Season # (optional)'
SEARCH_EPISODE_TEXT = 'Episode # (optional)' 
CACHE_DIR           = os.path.join(APPDIR, 'poster_cache')

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
    self.cover = None
    layout     = QGridLayout()


    label      = QLabel('Title')
    self.title = QLineEdit()
    self.title.setPlaceholderText( 'Movie or Episode title' )
    layout.addWidget(label,      0, 0) 
    layout.addWidget(self.title, 1, 0) 

    label       = QLabel('Series')
    self.series = QLineEdit()
    self.series.setPlaceholderText( 'TV series title' )
    layout.addWidget(label,       2, 0) 
    layout.addWidget(self.series, 3, 0) 

    label     = QLabel('Year')
    self.year = QLineEdit()
    self.year.setPlaceholderText( 'Year of release/airing' )
    layout.addWidget(label,     4, 0) 
    layout.addWidget(self.year, 5, 0) 

    label       = QLabel('Poster/Coverart')
    self.poster = QLabel()
    self.poster.setFixedSize(320, 180)
    layout.addWidget( label,       0, 1)
    layout.addWidget( self.poster, 1, 1, 20, 1)

    self.setLayout( layout )

  def _updateCover(self, info):
    cover = info.get('cover', None)
    if cover:
      coverFile = utils.downloadCover( cover, saveDir = CACHE_DIR )
      if coverFile:
        self.cover = coverFile
        pix = QPixmap(coverFile) 
        pix = pix.scaled(self.poster.width(), self.poster.height(), Qt.KeepAspectRatio)
        self.poster.setPixmap( pix )
    else:
      self.poster.setPixmap( QPixmap() )

  def updateData(self, info):
    self.title.setText(  info.get('title',      '') )
    self.series.setText( info.get('seriesName', '') )
    self.year.setText(   info.get('year',       '') )
    #self._updateCover( info )

  def writeData(self, fpath):
    print(fpath)

class VideoTaggerGUI( QMainWindow ):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__initUI()

  def __initUI(self):
    #mainMenu = self.menuBar()
    #fileMenu = mainMenu.addMenu('File')    
    #resetButton = QAction()
    #resetButton.setText('Reset')
    #resetButton.triggered.connect( self._reset )
    #mainMenu.addAction( resetButton )


    self.mainLayout = QVBoxLayout()

    self.searchWidget = SearchWidget()
    self.searchWidget.registerFunc( self.getMetadata )
    self.mainLayout.addWidget( self.searchWidget )

    self.metadataWidget = MetadataWidget()
    self.mainLayout.addWidget( self.metadataWidget )
 
    self.mainWidget = QWidget()
    self.mainWidget.setLayout( self.mainLayout )
    self.setCentralWidget( self.mainWidget )

  def _reset(self, *args, **kwargs):
    self.metadataWidget.updateData( {} )

  def getMetadata(self, *args, **kwargs):
    info = self.searchWidget.search(self, *args, **kwargs)
    if info:
      self.metadataWidget.updateData( info )

