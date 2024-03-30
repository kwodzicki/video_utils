Dependencies
============

In order for this package to work, a few command-line utilities are required, while other are optional as they add extra functionality.
 
The required and optional utilities are listed below.

Required
^^^^^^^^
* `ffmpeg`_     - Used for transcoding, cutting comercials, audio downmixing, etc.
* `ffprobe`_    - Used metadata/information extraction
* `MediaInfo`_  - Used to get stream information for transcode settings
* `MKVToolNix`_ - Used for MKV tagging and extraction of VobSub subtitles from MKV files

Optional
^^^^^^^^
* `dovi_tool`_      - Used to extract/inject Dolby Vision metadata from HDR HEVC streams
* `hdr10plus_tool`_ - Used to extract/inject HDR10+ metadata from HDR HEVC streams
* `comskip`_        - Used to locate commercials in DVRed files
* `ccextractor`_    - Used to extract captions from DVRed TV files to SRT
* `VobSub2SRT`_     - Used to convert VobSub subtitles to SRT subtitles
* `cpulimit`_       - Used to prevent processes from using 100% of CPU

.. _ffmpeg: https://www.ffmpeg.org/
.. _MediaInfo: https://mediaarea.net/en/MediaInfo
.. _MKVToolNix: https://mkvtoolnix.download 

.. _dovi_tool: https://github.com/quietvoid/dovi_tool
.. _hdr10plus_tool: https://github.com/quietvoid/hdr10plus_tool 
.. _comskip: https://github.com/erikkaashoek/Comskip
.. _ccextractor: https://github.com/CCExtractor/ccextractor
.. _VobSub2SRT: https://github.com/ruediger/VobSub2SRT
.. _cpulimit: https://github.com/opsengine/cpulimit

