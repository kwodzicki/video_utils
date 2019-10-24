import logging;
import stat, os;
from video_utils.config import lib_path 

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
  'file'        : os.path.join( lib_path, 'Logs', 'Plex_DVR_Watchdog.log'),
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
  'file'        : os.path.join( lib_path, 'Logs', 'MakeMKV_Watchdog.log'),
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
