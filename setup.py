#!/usr/bin/env python
import os
import shutil
import  importlib
from distutils.util import convert_path
from setuptools import setup, find_packages
from setuptools.command.install import install

NAME  = "video_utils"
DESC  = "Package for transcoding video files to h264/h265 codec"
URL   = "https://github.com/kwodzicki/video_utils"
AUTH  = "Kyle R. Wodzicki"
EMAIL = "krwodzicki@gmail.com"

INSTALL_REQUIRES = [
    "mutagen",
    "soundfile",
    "pillow", 
    "numpy",
    "scipy",
    "requests",
    "psutil",
    "watchdog",
    "pyYAML",
    "pgsrip",
    "plexapi",
]

SCRIPTS = [
    'bin/comremove',
    'bin/MakeMKV_Watchdog',
    'bin/Plex_DVR_Watchdog',
    'bin/rename_media_plex_tag_format',
    'bin/splitOnChapter',
    'bin/plexToken',
    'bin/updateFileNames',
    'bin/videotagger',
]

main_ns  = {}
ver_path = convert_path( "{}/version.py".format(NAME) )
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

def copyConfig():

    home = os.path.expanduser('~')
    pkg  = importlib.import_module(NAME)
    src  = os.path.join(pkg.DATADIR, 'settings.yml')
    dst  = os.path.join(home, '.{}.yml'.format(NAME))
    if os.path.isfile(dst):
        if os.stat(dst).st_size > 0:
            return
    shutil.copy( src, dst)

class PostInstallCommand(install):
    """
    Post-installation for installation mode.
    Taken from https://stackoverflow.com/questions/20288711/post-install-script-w
    """
    def run(self):

        install.run(self)
        copyConfig()


setup(
  name                 = NAME,
  description          = DESC,
  url                  = URL,
  author               = AUTH,
  author_email         = EMAIL, 
  version              = main_ns['__version__'],
  packages             = find_packages(),
  cmdclass             = {'install' : PostInstallCommand},
  package_data         = {"" : ["*.ini", "*.ttf"]},
  include_package_data = True,
  install_requires     = INSTALL_REQUIRES,
  scripts              = SCRIPTS,
  zip_safe             = False,
)
