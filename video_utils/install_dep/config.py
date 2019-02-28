'''
Contains dictionaries with information for install scripts
such as program names and git rep URLs
'''

required = {
  'name'    : 'required_CLIs',
  'git'     : '',
  'test'    : b'',
  'autogen' : False,
  'config'  : False,
  'make'    : False,
  'dep'     : {
    'darwin' : {
      'packages' : ['handbrake', 'ffmpeg', 'mediainfo'],
      'cmd_base' : ['brew', 'install'],
      'cwd'      : ''
    },
    'linux'  : {
      'packages' : ['handbrake-cli', 'ffmpeg', 'mediainfo'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : ''
    }
  }
}

ccextractor = {
  'name'    : 'ccextractor',
  'git'     : 'https://github.com/CCExtractor/ccextractor.git',
  'test'    : b'Error: (This help screen was shown because there were no input files)',
  'autogen' : True,
  'config'  : True,
  'make'    : True,
  'dep'     : {
    'darwin' : {
      'packages' : ['pkg-config', 'autoconf', 
                              'automake',   'libtool', 
                              'tesseract',  'leptonica'],
      'cmd_base' : ['brew', 'install'],
      'cwd'      : ['mac']
    },
    'linux'  : {
      'packages' : ['cmake',         'gcc', 
                    'autoconf',      'libglew-dev', 
                    'libglfw3-dev',  'libcurl4-gnutls-dev', 
                    'tesseract-ocr', 'libtesseract-dev', 
                    'libleptonica-dev'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : 'linux'
    }
  }
}


comskip = {
  'name'    : 'comskip',
  'git'     : 'https://github.com/erikkaashoek/Comskip',
  'test'    : b'ComSkip: missing option <file>',
  'autogen' : True,
  'config'  : True,
  'make'    : True,
  'dep'     : {
    'darwin' : {
      'packages' : [],
      'cmd_base' : ['brew', 'install'],
      'cwd'      : ''
    },
    'linux'  : {
      'packages' : ['autoconf',       'automake', 
                    'ffmpeg',         'libtool', 
                    'libargtable2-0', 'libargtable2-dev',
                    'libavutil-dev',  'libavcodec-dev', 
                    'libavformat-dev'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : ''
    }
  }
}

vobsub2srt = {
  'name'    : 'vobsub2srt',
  'git'     : 'https://github.com/ruediger/VobSub2SRT',
  'test'    : b'ComSkip: missing option <file>',
  'autogen' : False,
  'config'  : True,
  'make'    : True,
  'dep'     : {
    'darwin' : {
      'packages' : ['tesseract'],
      'cmd_base' : ['brew', 'install', '--with-all-languages'],
      'cwd'      : ''
    },
    'linux'  : {
      'packages' : ['cmake',           'pkg-config',
                    'build-essential', 'libtiff5-dev', 
                    'libtesseract-dev','tesseract-ocr-eng'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : ''
    }
  }
}

cpulimit = {
  'name'    : 'cpulimit',
  'git'     : '',
  'test'    : b'',
  'autogen' : False,
  'config'  : False,
  'make'    : False,
  'dep'     : {
    'darwin' : {
      'packages' : ['cpulimit'],
      'cmd_base' : ['brew', 'install'],
      'cwd'      : ''
    },
    'linux'  : {
      'packages' : ['cpulimit'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : ''
    }
  }
}

mkvtool = {
  'name'    : 'mkvtool',
  'git'     : '',
  'test'    : b'',
  'autogen' : False,
  'config'  : False,
  'make'    : False,
  'dep'     : {
    'darwin' : {
      'packages' : ['mkvtoolnix'],
      'cmd_base' : ['brew', 'install'],
      'cwd'      : ''
    },
    'linux'  : {
      'packages' : ['mkvtoolnix'],
      'cmd_base' : ['sudo', 'apt-get', 'install', '-y'],
      'cwd'      : ''
    }
  }
}
