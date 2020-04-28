import os
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QPushButton, QComboBox, QLineEdit, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QPixmap

from . import Movie, Episode, utils

HOME                = os.path.expanduser('~')
SEARCH_ID_TEXT      = 'Series or Movie ID'
SEARCH_SEASON_TEXT  = 'Season # (optional)'
SEARCH_EPISODE_TEXT = 'Episode # (optional)' 

class VideoTaggerGUI( QMainWindow ):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__initUI()

  def __initUI(self):
    self.mainLayout = QVBoxLayout()

    self.__searchBox()

    self.poster     = QLabel()
    self.mainLayout.addWidget( self.poster )
 
    self.mainWidget = QWidget()
    self.mainWidget.setLayout( self.mainLayout )
    self.setCentralWidget( self.mainWidget )

  def __searchBox(self):
    layout      = QHBoxLayout()

    options_cb = QComboBox()
    options_cb.addItem('')
    options_cb.addItem('TMDb')
    options_cb.addItem('TVDb')
    layout.addWidget( options_cb )

    dbID_box   = QLineEdit()
    dbID_box.setPlaceholderText( SEARCH_ID_TEXT )
    layout.addWidget( dbID_box )

    season_box = QLineEdit()
    season_box.setPlaceholderText( SEARCH_SEASON_TEXT ) 
    layout.addWidget( season_box )

    episode_box = QLineEdit()
    episode_box.setPlaceholderText( SEARCH_EPISODE_TEXT )
    layout.addWidget( episode_box )

    search_btn = QPushButton('Search')
    search_btn.clicked.connect( self.getMetadata )
    layout.addWidget( search_btn )

    self.search = QWidget()
    self.search.setLayout( layout )

    self.mainLayout.addWidget( self.search )

  def getMetadata(self, *args, **kwargs):
    info = self._dbQuery(self, *args, **kwargs)
    if info is not None:
      cover     = info._getCover()
      if cover:
        coverFile = utils.downloadCover( cover, saveDir = HOME )
        if coverFile:    
          self.poster.setPixmap( QPixmap(coverFile) )
          os.remove( coverFile )

  def _dbQuery(self, *args, **kwargs):
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
    comboBox = self.search.findChildren( QComboBox )[0]                                 # Get combobox from search widget
    dbName   = comboBox.currentText()                                                   # Use current text as db name

    dbID = season = episode = None                                                      # Default dbID, season, and episode to None
    lineEdit = self.search.findChildren( QLineEdit )                                    # Get all LineEdit objects in search widget
    for line in lineEdit:                                                               # Iterate over all LineEdit objects
      txt   = line.text()                                                               # Get test of the object
      if txt != '':                                                                     # If text is not empty
        phTXT = line.placeholderText()                                                  # Get the placeholder text
        if phTXT == SEARCH_ID_TEXT:                                                     # If placeholder text is the database text
          dbID = txt                                                                    # Set dbID to current text
        elif phTXT == SEARCH_SEASON_TEXT:                                               # Else, if the season text
          season = txt                                                                  # Set season to current text
        elif phTXT == SEARCH_EPISODE_TEXT:                                              # Else, if episode text
          episode = txt                                                                 # Set episode to current text

    if dbID is None:                                                                    # If dbID is None
      print('No database ID set')                                                       # Error
      return None                                                                       # Return None
    else:                                                                               # Else
      args = [dbID]                                                                     # Set args to list with just dbID for now
      if season is not None and episode is not None:                                    # If both season and episode are NOT None
        args.extend( [season, episode] )                                                # Extend the args list
      if dbName == '':                                                                  # If the dbName is empty; i.e., user did not pick a database
        if len(args) == 3:                                                              # If there are 3 arguments
          dbName = 'TVDb'                                                               # Default to TVDb because is tv episode
          comboBox.setCurrentIndex(2)                                                   # Change comboBox value to be TVDb
        else:                                                                           # Else
          dbName = 'TMDb'                                                               # Set dbName to TMDb
          comboBox.setCurrentIndex(1)                                                   # Change comboBox value to be TMDb

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

    return info                                                                         # Return Info
