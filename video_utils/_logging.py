import logging;
import stat;
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
  'file'        : '/tmp/Plex_DVR_PostProcess.log',
  'name'        : 'plex_dvr',
  'maxBytes'    : 10 * 1024**2,
  'backupCount' : 4,
  'level'       : logging.DEBUG,
  'formatter'   : logging.Formatter( 
                '%(levelname)-.4s - %(asctime)s - %(name)s.%(funcName)-15.15s - %(message)s',
                '%Y-%m-%d %H:%M:%S'),
  'permissions' : stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
                  stat.S_IRGRP | stat.S_IWGRP  | \
                  stat.S_IROTH | stat.S_IWOTH
}