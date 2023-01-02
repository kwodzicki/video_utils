Command Line Utilities
======================

This package provides a few command line utilities for some of the core components.

Commercial Removal
------------------

Commercials can be removed using the :code:`comremove` utility, which allows for input of a Mpeg Transport Stream file (:code:`.ts`), with some extra options for :code:`.ini` file specification and CPU limiting.
For more information use the :code:`--help` flag when running the utility.

Tagging of MP4 or MKV files
---------------------------

The :code:`videotagger` utility tags MP4 or MKV files with data from TMDb or TVDb (pending API keys installed) either using the TMDb or TVDb id found in the file name if the file naming convention is used, or using a user supplied id. 
For more information use the :code:`--help` flag when running the utility.

plexToken
---------

This CLI is used to obtain an API token for triggering scans of Movie/TV Show sections after files are converted.
When run, the user will be prompted for the name of their Plex server, their Plex account credentials, and their 2FA token.
This information is not stored anywhere in the code and is passed directly in to the plexapi python package.
The token created using the login information IS stored locally so that the token can be used programatically in the future.

If you are uncomforatable logging in through this script (and the plexapi package), you can do so manually and store the required information in a pickle file located at :code:`~/Libarary/Application Support/.plexToken`.
The data should be formated as :code:`{'baseurl' : url, 'token' : token'}` where :code:`baseurl` is the base url for the Plex server and :code:`token` is the token returned by the authentication service.
A token can also be obtained by looking at the XML information for any item in your library.
See the Plex forums for more information on how to do this.

Watchdogs
---------

MakeMKV\_Watchdog
^^^^^^^^^^^^^^^^^

This watchdog is designed to be run as a service that will transcode files created by MakeMKV to h264/5 encoded files.
Note that files should conform to the naming convention outlined in :code:`./docs/Input_File_Naming.pdf`.
When setting the output directory for converted files, it is suggested to set the directory to the directory where your Plex Libraries reside.
For example, if your libraries are on a drive mounted at :code:`/mnt/PlexHDD`, and movies and tv shows are in directories named :code:`Movies` and :code:`TV Shows`, respectively, then you will want to set the output directory to :code:`/mnt/PlexHDD`.
This way, output files will be placed inside your Plex Library tree; this watchdog will attempt to run Plex Scan if run as user :code:`plex`.
Note that the watchdog does not try to find movie or tv directories, it will use the case-sensitive :code:`Movies` and :code:`TV Shows` directory names.
Future versions may allow for explicitly setting the output directories.
This watchdog does a few things:
 
 * Watches specified directory(ies) for new files, filtering by given extensions (default `.mkv`)
 * Attempts to extract subtitles to VobSub (requires `MKVToolNix`_)
 * Convert subtitles to SRT (requires `VobSub2SRT`_)
 * Converts movie to MP4/MKV format using the `VideoConverter` class
 * Attempts to download and write MP4/MKV tags to file
 * Attempts to run :code:`Plex Media Scanner` to add output file to Plex Library

Sample workflow for converting files:

 * Use MakeMKV to create :code:`.mkv` file; shoud NOT save to directory being watched by this watchdog
 * Rename the file to conform to input naming convention
 * Move/copy file into watched directory
 * Let program take care of the rest

See the :code:`makemkv_watchdog.service` file in :code:`./systemd` directory for an example of how to set up a Linux service.
See the :code:`makemkv_watchdog.plist` file in :code:`./LaunchDaemons` directory for an example of how to set up a macOS service.
 
Plex\_DVR\_Watchdog
^^^^^^^^^^^^^^^^^^^

This watchdog is designed to be run as a service that will post process DVR output, namely for TV shows.
This watchdog does a few things:
 
 * Watches specified directory for new DVR files; waits to process file until they are moved to their final location by Plex
 * Attempts to get the IMDb id of the episode based on the series name, year, and episode title.
 * Renames file to match input file naming convention for video\_utils package
 * Attempts to add chapters marking commercials in file using :code:`comskip` CLI if installed; can remove commercials if --destructive flag is set
 * Attempts to extract subtitles to SRT using :code:`ccextractor` CLI if installed
 * Converts movie to MP4 format using the :code:`VideoConverter` class
 * Attempts to download and write MP4 tags to file
 * Attempts to run :code:`Plex Media Scanner` to locate :code:`.mp4` file; re-runs scanner if source :code:`.ts` file is deleted

Note that this watchdog can be set to run a user specified script (i.e., a post processing script that you have written).
Just use the :code:`--script` flag when setting up the service; this will override all other flags.

.. _MKVToolNix: https://mkvtoolnix.download
.. _VobSub2SRT: https://github.com/ruediger/VobSub2SRT 
