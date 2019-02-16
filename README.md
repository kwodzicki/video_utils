# video_utils

**video_utils** is a Python package containing many tools useful for converting vidoe files to h264/h265 encoded MKV or MP4 files.

## Main features

* Compatible with Python3
* Will try to download SRT subtitles from opensubtitles.org if no subtitles in input file
* Can tag movies and TV shows
* Can extract closed captions and VOBSUB subtitles from input file and convert to SRT files (dependencies required)
* Can be set to use a certain percentage of CPU available (dependency required)

## File Naming

Be sure to look over the file naming convention in the documents folder to
ensure that metadata is properly downloaded.

## Installation

Whenever it's possible, please always use the latest version from the repository.
To install it using `pip`:

    pip install git+https://github.com/kwodzicki/video_utils

## Dependencies

In order for this program to work, a few command-line utilities are required.
There are separated below into required and optional utilities below:

### Required
* [HandBrakeCLI][handbrake] - Performs the transcoding
* [ffmpeg][ffmpeg]          - Used for cutting comercials, audio downmixing, etc.
* [MediaInfo][mediainfo]    - Used to get stream information for transcode settings

### Optional
* [comskip][comskip]       - Used to locate commercials in DVRed TV files
* [MKVToolNix][mkv]        - Used to extract VobSub subtitles from MKV files
* [ccextractor][ccextract] - Used to extract captions from DVRed TV files to SRT
* [VobSub2SRT][vobsub]     - Used to convert VobSub subtitles to SRT subtitles
* [cpulimit][cpu]          - Used to prevent processes from using 100% of CPU

### Comskip INI file

To easily have comskip use a specific ini file, define a COMSKIP_INI environment
variable for the user that will be running the scripts. To do this, simply add
the following line to your .bashrc or .bash_profile:

	export COMSKIP_INI=/path/to/comskip.ini

If code will be run under a user without a home directory, such as on a
raspberry pi where Plex typically runs under the plex user, one can add the
environment variable definition to the /etc/profile file, which will define it
for all user on the computer. You can also have it only defined for given users
based on the uid. For example, if your plex user is uid 456, then you could add
the following to /etc/profile:

	# Add COMSKIP_INI environment variable if user plex (uid 456)
	if [ "$(id -u)" -eq 456 ]; then
  		export COMSKIP_INI=/path/to/comskip.ini
	fi


## Code example

    # create and instance of videoconverter class
    from video_utils import videoconverter
    converter = videoconverter()

    # set path to file to convert
    file = '/path/to/file/Forgetting Sarah Marshall..2008.tt0800039.mkv'

    # transcode the file
    converter.transcode( file )

## Automated converting

Automated converting can be done using the MKV_Cron_Convert.py script. The script
is designed to look through one (or more) directory for `.mkv` files and 
transcode them, one at a time, to a designated output directory until no more
remain in the input directory. All options available in the `makemkv_to_mp4`
class can be set in the script. Set up a cron job to call this script and simply 
place new files into the designated input folder(s) and let your computer take
care of the rest.

## License

video_utils is released under the terms of the GNU GPL v3 license.

[handbrake]: https://handbrake.fr/downloads2.php
[ffmpeg]: https://www.ffmpeg.org/
[mediainfo]: https://mediaarea.net/en/MediaInfo
[cpu]: https://github.com/opsengine/cpulimit
[mkv]: https://mkvtoolnix.download/
[vobsub]: https://github.com/ruediger/VobSub2SRT
[comskip]: https://github.com/erikkaashoek/Comskip
[ccextract]: https://github.com/CCExtractor/ccextractor
