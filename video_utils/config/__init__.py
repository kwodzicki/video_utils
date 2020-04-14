import logging
import os, stat, json

PKGNAME = __name__.split('.')[0]                                                        # Get root name of package 
HOME    = os.path.expanduser('~')
APPDIR  = os.path.join( HOME,   'Library', 'Application Support', PKGNAME )
LOGDIR  = os.path.join( APPDIR, 'Logs' )
CONFIG  = os.path.join( HOME,   '.{}rc'.format(PKGNAME) )
try:
  with open(CONFIG, 'r') as fid:
    CONFIG = json.load( fid )
except:
  CONFIG = {}
COMSKIPINI = os.path.join( os.path.dirname( __file__ ), 'comskip.ini' )
 
'''Settings for screen logger and file logger'''
screenFMT  = { 
  'name'      : 'main',
  'level'     : logging.CRITICAL,
  'formatter' : logging.Formatter(
                '%(levelname)-8s - %(asctime)s - %(name)s - %(message)s',
                '%Y-%m-%d %H:%M:%S')
}
fileFMT    = {
  'level'     : logging.INFO,
  'formatter' : logging.Formatter( 
                '%(levelname)-.4s - %(funcName)-15.15s - %(message)s',
                '%Y-%m-%d %H:%M:%S')
}

plexFMT    = {
  'pidFile'     : os.path.join( APPDIR, 'Plex_DVR_Watchdog.pid'),
  'file'        : os.path.join( LOGDIR, 'Plex_DVR_Watchdog.log'),
  'transcode'   : os.path.join( LOGDIR, 'Plex_DVR_Watchdog_Transcode.log'), 
  'name'        : 'plex_dvr',
  'maxBytes'    : 5 * 1024**2,
  'backupCount' : 4,
  'level'       : logging.DEBUG,
  'formatter'   : logging.Formatter( 
                '%(levelname)-.4s - %(asctime)s - %(name)s.%(funcName)-15.15s - %(message)s',
                '%Y-%m-%d %H:%M:%S'),
  'permissions' : stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
                  stat.S_IRGRP | stat.S_IWGRP  | \
                  stat.S_IROTH | stat.S_IWOTH
}

MakeMKVFMT = {
  'pidFile'     : os.path.join( APPDIR, 'MakeMKV_Watchdog.pid'),
  'file'        : os.path.join( LOGDIR, 'MakeMKV_Watchdog.log'),
  'name'        : 'MakeMKV',
  'maxBytes'    : 5 * 1024**2,
  'backupCount' : 4,
  'level'       : logging.DEBUG,
  'formatter'   : logging.Formatter( 
                '%(levelname)-.4s - %(asctime)s - %(name)s.%(funcName)-15.15s - %(message)s',
                '%Y-%m-%d %H:%M:%S'),
  'permissions' : stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
                  stat.S_IRGRP | stat.S_IWGRP  | \
                  stat.S_IROTH | stat.S_IWOTH
}

# do NOT use opensubtitles info in other programs, register for your own
opensubtitles = {
  'url'        : 'https://api.opensubtitles.org:443/xml-rpc',
  'user_agent' : 'makemkv_to_mp4'
};


plex_dvr = {
  'queueFile' : os.path.join( APPDIR, 'plex_dvr_convert_queue.pic' ), 
  'lock_file' : '/tmp/Plex_DVR_PostProcess.lock',
  'lock_perm' : stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
                stat.S_IRGRP | stat.S_IWGRP  | \
                stat.S_IROTH | stat.S_IWOTH
}                                   # Path to a lock file to stop multiple instances from running at same time
