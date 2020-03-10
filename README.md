# video\_utils

**video_utils** is a Python package containing many tools useful for converting video files to h264/h265 encoded MP4 or MKV files.

## Main features

* Compatible with Python3
* Will try to download SRT subtitles from opensubtitles.org if no subtitles in input file
* Can tag movies and TV shows (MP4 files only)
* Can extract closed captions and VOBSUB subtitles from input file and convert to SRT files (dependencies required)
* Can be set to use a certain percentage of CPU available (dependency required)

## File Naming

Be sure to look over the file naming convention in the documents folder to ensure that metadata is properly downloaded.

## Installation

Whenever possible, please always use the latest version from the repository.
To install it using `pip`:

    pip install git+https://github.com/kwodzicki/video_utils

## Dependencies

In order for this package to work, a few command-line utilities are required, while other are optional as they add extra functionality.
The required and optional utilities are listed below.

#### Required
* [ffmpeg][ffmpeg]        - Used for transcoding, cutting comercials, audio downmixing, etc.
* [MediaInfo][mediainfo]  - Used to get stream information for transcode settings

#### Optional
* [comskip][comskip]       - Used to locate commercials in DVRed TV files
* [MKVToolNix][mkv]        - Used to extract VobSub subtitles from MKV files
* [ccextractor][ccextract] - Used to extract captions from DVRed TV files to SRT
* [VobSub2SRT][vobsub]     - Used to convert VobSub subtitles to SRT subtitles
* [cpulimit][cpu]          - Used to prevent processes from using 100% of CPU

## Automated MP4 Tagging

This package includes code to tag MP4 video files using data from various websites.
These include IMDb, The Movie Database (TMDb), and The TV Database (TVDb).
While the default site used to get metadata from movies and TV shows is IMDb, it is always nice to have more options to ensure that the metadata is complete and accurate.
However, to enable use of TMDb and TVDb, API keys are required. 

#### Obtaining API keys

##### TMDb

To get an API key for TMDb, you must go to their website and create an account.
After you have created an account, go to your account settings, and then API.
From there you can create an API key; the v3 key is what is required.

##### TVDb

To get an API key for TMDb, you must go to their website and create an account.
After you have created an account, go to API Access and generate a new key.

#### Installing API keys

After you have generated your own API keys, there are two ways to install them.

##### Method 1 - `.video_utilsrc` file

This method requires you to create a file in your home directory named `video_utilsrc`.
If this does not make sense, [Method 2](#method-2---environment-variables) may be the way to go.

After this file is created, you can add your API keys to it.
Note that if you only registered for one API key, you should only place that one in the file.
The file is JSON formatted:

    {
        "TVDB_API_KEY" : "YOUR_TVDb_KEY_HERE",
        "TMDB_API_KEY" : "YOUR_TMDb_KEY_HERE"
    }

After your API keys are added, you can save and close the file.
You won't have to worry about this again!
Settings in the `.video_utilsrc` are overriden by environment variables.

##### Method 2 - Environment variables

This method requires you to set environment variables that the `video_utils` package can use to get the API keys.
These variables must be set for the user that will be running the scripts.
To do this, simply add the following lines to your ~/.bashrc or ~/.bash\_profile:

    export TVDB_API_KEY="YOUR_TVDb_KEY_HERE"
    export TMDB_API_KEY="YOUR_TMDb_KEY_HERE"

If code will be run under a user without a home directory, or you just want to make sure that the envrionment variables are defined for all users, you can add the environment variable definitions to the /etc/profile file the same way you did above. 

Note that you can set the `COMSKIP_INI_DIR` in the `.video_utilsrc` file:

    {
        "COMSKIP_INI_DIR" : "/path/to/comskip_inis"
    }

Settings in the `.video_utilsrc` are overriden by environment variables.

To limit the definition of the variables to specifc users, you can filter by their uid.
For example, if your user is uid 456, then you could add the following to /etc/profile:

    # Add TVDB_API_KEY and TMDB_API_KEY environment variables to user with uid 456
    if [ "$(id -u)" -eq 456 ]; then
        export TVDB_API_KEY="YOUR_TVDb_KEY_HERE"
        export TMDB_API_KEY="YOUR_TMDb_KEY_HERE"
    fi


## Commercial skipping

To enable automated commercial skipping, ensure that the [comskip][comskip] utility is installed and in your PATH environment variable.
To tune how comskip detects commerical breaks in videos, a `.ini` file is used.
`video_utils` provides an easy way to set the `.ini` file through an environment variable as discussed below.

#### Comskip INI file

By default, the `.ini` file included in the package (`video_utils/config/comskip.ini`) will be used for commercial skippping.
To override this behavior, simply set the `COMSKIP_INI_DIR` environment variable and place the `comskip.ini` file you would like to use in that directory.
For example, say you have a `comskip.ini` file in `/path/to/comskip_inis/`.
Simply add the following line to your ~/.bashrc or ~/.bash\_profile:

	export COMSKIP_INI_DIR=/path/to/comskip_inis/

If you happen to have tuned `.ini` files for specific shows, you can also place those in the `COMSKIP_INI_DIR` directory and they will be used.
However, the file names MUST match the Plex convention for TV Show series name (i.e., Series name (year)) or Movie (i.e., Movie name (year)) for the package to find them.
If no matching series/movie `.ini` is found, then the package will fall back to the `comskip.ini` file in the directory.
Note that all files MUST end with the `.ini` extension.

If code will be run under a user without a home directory, such as Linux where Plex typically runs under the plex user, one can add the environment variable definition to the /etc/profile file, which will define it for all user on the computer.
You can also have it only defined for given users based on the uid.
For example, if your plex user is uid 456, then you could add the following to /etc/profile:

	# Add COMSKIP_INI environment variable if user plex (uid 456)
	if [ "$(id -u)" -eq 456 ]; then
            export COMSKIP_INI_DIR=/path/to/comskip_inis
	fi


## Command line utilities

This package provides a few command line utilities for some of the core components.

#### Commercial Removal
###### comremove
Commercials can be removed using the `comremove` utility, which allows for input of a Mpeg Transport Stream file (.ts), with some extra options for `.ini` file specification and CPU limiting.
For more information use the `--help` flag when running the utility.

#### Tagging of MP4 files
###### mp4tagger
The `mp4tagger` utility tags MP4 files with data from IMDb, TMDb, and TVDb (pending API keys installed) either using the IMDb id found in the file name if the file naming convention is used, or using a user supplied IMDb id. 
For more information use the `--help` flag when running the utility.

## Watchdogs

#### Conversion of MakeMKV Output
###### MakeMKV\_Watchdog
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
 * Converts movie to MP4 format using the `VideoConverter` class
 * Attempts to download and write MP4 tags to file
 * Attempts to run `Plex Media Scanner` to add output file to Plex Library

Sample workflow for convering files:

 * Use MakeMKV to create `.mkv` file; shoud NOT save to directory being watched by this watchdog
 * Rename the file to conform to input naming convention
 * Move/copy file into watched directory
 * Let program take care of the rest

See the `makemkv_watchdog.service` file in ./systemd for an example of how to set up the service.
 
#### Post Processing of Plex DVR
###### Plex\_DVR\_Watchdog
This watchdog is designed to be run as a service that will post process DVR output, namely for TV shows.
This watchdog does a few things:
 
 * Watches specified directory for new DVR files; waits to process file until
    they are moved to their final location by Plex
 * Attempts to get the IMDb id of the episode based on the series name, 
    year, and episode title.
 * Renames file to match input file naming convention for video\_utils package
 * Attempts to add chapters marking commercials in file using `comskip` CLI if installed; 
    can remove commercials if --destructive flag is set
 * Attempts to extract subtitles to SRT using `ccextractor` CLI if installed
 * Converts movie to MP4 format using the `VideoConverter` class
 * Attempts to download and write MP4 tags to file
 * Attempts to run `Plex Media Scanner` to locate `.mp4` file; re-runs scanner if
    source `.ts` file is deleted

Note that this watchdog can be set to run a user specified script (i.e., a post processing script that you have written).
Just use the `--script` flag when setting up the service; this will override all other flags.

## Code example
Of course you can always use these utilities in your own code.
A brief example of how to use the VideoConverter class is below:

    # create an instance of VideoConverter class
    from video_utils.videoconverter import VideoConverter
    converter = VideoConverter()

    # set path to file to convert
    file = '/path/to/file/Forgetting Sarah Marshall..2008.tt0800039.mkv'

    # transcode the file
    converter.transcode( file )


## License

video\_utils is released under the terms of the GNU GPL v3 license.

[ffmpeg]: https://www.ffmpeg.org/
[mediainfo]: https://mediaarea.net/en/MediaInfo
[cpu]: https://github.com/opsengine/cpulimit
[mkv]: https://mkvtoolnix.download/
[vobsub]: https://github.com/ruediger/VobSub2SRT
[comskip]: https://github.com/erikkaashoek/Comskip
[ccextract]: https://github.com/CCExtractor/ccextractor
