High Dynamic Range Content
==========================

Most, if not all, 4K UHD movies contain high dynamic range (HDR) information as either movie-wide information (maximum NITs for entire movie) or per-frame metadata for scene lighting (HDR10+ and Dolby Vision).
Proper support has been added for HDR re-encoding, assuming your FFmpeg install was built agains an x265 library that supports 10-bit encoding.

The Pipeline
------------
If HDR information is detected in the source video file (based on `MediaInfo`_), the `ffprobe` CLI is used to determine the content-wide HDR values to pass to the x265 encoder.
If this information is found, then the video stream is extracted from the source file in the Annex B format for use in some other (optional) tools.
Assuming they are installed, the `dovi_tool`_ and `hdr10plus_tool`_ are run on the Annex B file to extract any Dolby Vision and HDR10+ metadata, respectively.
From the results of `ffprobe` and the metadata extraction tools, x265 encoding flags are set and an HEVC encoded video-only file is created along with an all-other-streams file.

After the encoding finishes successfully, the Dolby Vision and HDR10+ metadata (if any) are injected into the video-only file so that the per-frame metadata is maintained.
Finally, the video-only and all-other-streams files are merged back together using `mkvmerge`.

.. _MediaInfo: https://mediaarea.net/en/MediaInfo
.. _dovi_tool: https://github.com/quietvoid/dovi_tool
.. _hdr10plus_tool: https://github.com/quietvoid/hdr10plus_tool
