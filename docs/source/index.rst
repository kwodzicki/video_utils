.. video_utils documentation master file, created by
   sphinx-quickstart on Thu May  7 19:11:47 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to video_utils's documentation!
=======================================

**video\_utils** is a Python package containing many tools useful for converting video files to h264/h265 encoded MP4 or MKV files.

Main features
^^^^^^^^^^^^^
* Compatible with Python3
* Will try to download SRT subtitles from opensubtitles.org if no subtitles in input file
* Can tag movies and TV shows
* Can extract closed captions and VOBSUB subtitles from input file and convert to SRT files (dependencies required)
* Can be set to use a certain percentage of CPU available (dependency required)
 
.. toctree::
   :maxdepth: 2
   :caption: Contents:

   dependencies
   naming/index
   tagging
   comskip
   clis
   api/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
