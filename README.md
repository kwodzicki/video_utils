# video_utils

**video_utils** is a Python package containing many tools useful for converting vidoe files to h264/h265 encoded MKV or MP4 files.

## Main features

* Compatible with Python3
* Platform-independent (?)
* Will try to download SRT subtitles from opensubtitles.org if no subtitles in input file
* Can tag movies and TV shows:
	- Requires the [videotagger][videotagger] Python package
* Can extract VOBSUB subtitles from input file and convert to SRT files (dependencies required)
* Can be set to use a certain percentage of CPU available (dependency required)

## File Naming

Be sure to look over the file naming convention in the documents folder to
ensure that metadata is properly downloaded.

## Installation

Whenever it's possible, please always use the latest version from the repository.
To install it using `pip`:

    pip install git+https://github.com/kwodzicki/makemkv_to_mp4

## Dependencies

In order for this program to work, a few command-line utilities are required.
There are separated below into required and optional utilities below:

### Required
* [HandBrakeCLI][handbrake] - Performs the transcoding
* [MediaInfo][mediainfo]    - Used to get stream information for transcode settings

### Optional
* [MKVToolNix][mkv]    - Used to extract VobSub subtitles from MKV files
* [VobSub2SRT][vobsub] - Used to convert VobSub subtitles to SRT subtitles
* [cpulimit][cpu]      - Used to prevent HandBrakeCLI from using 100% of CPU

## Code example

    # create and instance of the makemkv_to_mp4 class
    from makemkv_to_mp4 import makemkv_to_mp4
    mkv = makemkv_to_mp4()

    # set path to file to convert
    file = '/path/to/file/Forgetting Sarah Marshall..2008.tt0800039.mkv'

    # transcode the file
    mkv.transcode( file )

## Automated converting

Automated converting can be done using the MKV_Cron_Convert.py script. The script
is designed to look through one (or more) directory for `.mkv` files and 
transcode them, one at a time, to a designated output directory until no more
remain in the input directory. All options available in the `makemkv_to_mp4`
class can be set in the script. Set up a cron job to call this script and simply 
place new files into the designated input folder(s) and let your computer take
care of the rest.

## License

makemkv_to_mp4 is released under the terms of the GNU GPL v3 license.

[handbrake]: https://handbrake.fr/downloads2.php
[mediainfo]: https://mediaarea.net/en/MediaInfo
[tagger]: https://github.com/kwodzicki/videotagger
[cpu]: https://github.com/opsengine/cpulimit
[mkv]: https://mkvtoolnix.download/
[vobsub]: https://github.com/ruediger/VobSub2SRT
[videotagger]: https://github.com/kwodzicki/videotagger
