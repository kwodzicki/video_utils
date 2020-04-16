#!/usr/bin/env python
import os, shutil, importlib
from setuptools import setup, convert_path
from setuptools.command.install import install

NAME = "video_utils"
DESC = "Package for transcoding video files to h264/h265 codec"

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
  url                  = "https://github.com/kwodzicki/video_utils",
  author               = "Kyle R. Wodzicki",
  author_email         = "krwodzicki@gmail.com",
  version              = main_ns['__version__'],
  packages             = setuptools.find_packages(),
  cmdclass             = {'install' : PostInstallCommand},
  package_data         = {"" : ["*.ini", "*.ttf"]},
  include_package_data = True,
  install_requires     = [ "mutagen", "soundfile", "pillow", 
                           "numpy", "scipy",
                           "requests", "psutil", "watchdog", "pyYAML"],
  scripts              = ['bin/comremove',
                          'bin/videotagger',
                          'bin/updateFileNames',
                          'bin/MakeMKV_Watchdog',
                          'bin/Plex_DVR_Watchdog'],
  zip_safe             = False
)
