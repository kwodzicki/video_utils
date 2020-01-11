# Some global configuration settings
import os, stat

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
TMDb['urlFind']    = TMDb['urlBase'] + 'find/{}';
TMDb['urlMovie']   = TMDb['urlBase'] + 'movie/{}';
TMDb['urlSeries']  = TMDb['urlBase'] + 'tv/{}';
TMDb['urlEpisode'] = TMDb['urlBase'] + 'tv/{}/season/{}/episode/{}';

lib_path = os.path.join( os.path.expanduser('~'), 'Library', 'Application Support', 'video_utils' ) 

plex_dvr = {
  'queueFile' : os.path.join( lib_path, 'plex_dvr_convert_queue.pic' ), 
  'lock_file' : '/tmp/Plex_DVR_PostProcess.lock',
  'lock_perm' : stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
                stat.S_IRGRP | stat.S_IWGRP  | \
                stat.S_IROTH | stat.S_IWOTH
}                                   # Path to a lock file to stop multiple instances from running at same time
