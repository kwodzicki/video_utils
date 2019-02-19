# Some global configuration settings

# do NOT use opensubtitles info in other programs, register for your own
opensubtitles = {
  'url'        : 'https://api.opensubtitles.org:443/xml-rpc',
  'user_agent' : 'makemkv_to_mp4'
};

# Information for TMDb api requests
TMDb = {
  'urlBase'    : 'https://api.themoviedb.org/3/',
  'urlImage'   : 'http://image.tmdb.org/t/p/original/',
};
TMDb['urlFind']    = TMDb['urlBase'] + 'find/{}?external_source=imdb_id';
TMDb['urlMovie']   = TMDb['urlBase'] + 'movie/{}';
TMDb['urlSeries']  = TMDb['urlBase'] + 'tv/{}';
TMDb['urlEpisode'] = TMDb['urlBase'] + 'tv/{}/season/{}/episode/{}';
