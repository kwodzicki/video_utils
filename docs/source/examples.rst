Code Examples
=============

While this package offers many CLIs to aid the end-user, one can always use the APIs in their own code.
Some examples follow.

VideoConverter class
--------------------
.. code-block:: python

    # create an instance of VideoConverter class
    from video_utils.videoconverter import VideoConverter
    converter = VideoConverter()

    # set path to file to convert
    file = '/path/to/file/tmdb9870..mkv'

    # transcode the file
    converter.transcode( file )

