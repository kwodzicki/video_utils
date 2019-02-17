import logging;
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