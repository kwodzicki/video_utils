Command Line Utilities
======================

This package provides a few command line utilities for some of the core components.

Commercial Removal
------------------

Commercials can be removed using the `comremove` utility, which allows for input of a Mpeg Transport Stream file (.ts), with some extra options for `.ini` file specification and CPU limiting.
For more information use the `--help` flag when running the utility.

Tagging of MP4 or MKV files
---------------------------

The `videotagger` utility tags MP4 or MKV files with data from TMDb or TVDb (pending API keys installed) either using the TMDb or TVDb id found in the file name if the file naming convention is used, or using a user supplied id. 
For more information use the `--help` flag when running the utility.

Watchdogs
---------

MakeMKV\_Watchdog
^^^^^^^^^^^^^^^^^

This watchdog is designed to be run as a service that will transcode files created by MakeMKV to h264/5 encoded files.
Note that files should conform to the naming convention outlined in `./docs/Input_File_Naming.pdf`.
When setting the output directory for converted files, it is suggested to set the directory to the directory where your Plex Libraries reside.
For example, if your libraries are on a drive mounted at `/mnt/PlexHDD`, and movies and tv shows are in directories named `Movies` and `TV Shows`, respectively, then you will want to set the output directory to `/mnt/PlexHDD`.
This way, output files will be placed inside your Plex Library tree; this watchdog will attempt to run Plex Scan if run as user `plex`.
Note that the watchdog does not try to find movie or tv directories, it will use the case-sensitive `Movies` and `TV Shows` directory names.
Future versions may allow for explicitly setting the output directories.
This watchdog does a few things:
 
 * Watches specified directory(ies) for new files, filtering by given extensions (default `.mkv`)
 * Attempts to extract subtitles to VobSub (requires [MKVToolNix][mkv])
   * Convert subtitles to SRT (requires [VobSub2SRT][vobsub]
 * Converts movie to MP4/MKV format using the `VideoConverter` class
 * Attempts to download and write MP4/MKV tags to file
 * Attempts to run `Plex Media Scanner` to add output file to Plex Library

Sample workflow for converting files:

 * Use MakeMKV to create `.mkv` file; shoud NOT save to directory being watched by this watchdog
 * Rename the file to conform to input naming convention
 * Move/copy file into watched directory
 * Let program take care of the rest

See the `makemkv_watchdog.service` file in `./systemd` directory for an example of how to set up a Linux service.
See the `makemkv_watchdog.plist` file in `./LaunchDaemons` directory for an example of how to set up a macOS service.
 
Plex\_DVR\_Watchdog
^^^^^^^^^^^^^^^^^^^

This watchdog is designed to be run as a service that will post process DVR output, namely for TV shows.
This watchdog does a few things:
 
 * Watches specified directory for new DVR files; waits to process file until they are moved to their final location by Plex
 * Attempts to get the IMDb id of the episode based on the series name, year, and episode title.
 * Renames file to match input file naming convention for video\_utils package
 * Attempts to add chapters marking commercials in file using `comskip` CLI if installed; can remove commercials if --destructive flag is set
 * Attempts to extract subtitles to SRT using `ccextractor` CLI if installed
 * Converts movie to MP4 format using the `VideoConverter` class
 * Attempts to download and write MP4 tags to file
 * Attempts to run `Plex Media Scanner` to locate `.mp4` file; re-runs scanner if source `.ts` file is deleted

Note that this watchdog can be set to run a user specified script (i.e., a post processing script that you have written).
Just use the `--script` flag when setting up the service; this will override all other flags.
