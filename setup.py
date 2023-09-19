#!/usr/bin/env python
import os

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

setup(
    name                 = NAME,
    description          = DESC,
    url                  = URL,
    author               = AUTH,
    author_email         = EMAIL, 
    version              = main_ns['__version__'],
    packages             = find_packages(),
    package_data         = {"" : ["*.yml", "*.ini", "*.ttf"]},
    include_package_data = True,
    install_requires     = INSTALL_REQUIRES,
    scripts              = SCRIPTS,
    zip_safe             = False,
)
