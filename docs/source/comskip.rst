Commercial skipping
===================

To enable automated commercial skipping, ensure that the `comskip`_ utility is installed and in your PATH environment variable.
To tune how comskip detects commerical breaks in videos, a :code:`.ini` file is used.
:code:`video_utils` provides an easy way to set the :code:`.ini` file through the config file or an environment variable as discussed below.

Comskip INI file
----------------

By default, the :code:`.ini` file included in the package (:code:`video_utils/config/comskip.ini`) will be used for commercial skippping.
To override this behavior, simply set the :code:`COMSKIP_INI_DIR` environment variable and place the :code:`comskip.ini` file you would like to use in that directory.
For example, say you have a :code:`comskip.ini` file in :code:`/path/to/comskip_inis/`.
Simply add the following line to your :code:`~/.bashrc` or :code:`~/.bash_profile`::

    export COMSKIP_INI_DIR=/path/to/comskip_inis/

If you happen to have tuned :code:`.ini` files for specific shows, you can also place those in the :code:`COMSKIP_INI_DIR` directory and they will be used.
However, the file names MUST match the Plex convention for TV Show series name [i.e., Series name (year)] or Movie [i.e., Movie name (year)] for the package to find them.
If no matching series/movie :code:`.ini` is found, then the package will fall back to the :code:`comskip.ini` file in the directory.
Note that all files MUST end with the :code:`.ini` extension.

If code will be run under a user without a home directory, such as Linux where Plex typically runs under the plex user, one can add the environment variable definition to the /etc/profile file, which will define it for all user on the computer.
You can also have it only defined for given users based on the uid.
For example, if your plex user is uid 456, then you could add the following to /etc/profile::

    # Add COMSKIP_INI environment variable if user plex (uid 456)
    if [ "$(id -u)" -eq 456 ]; then
        export COMSKIP_INI_DIR=/path/to/comskip_inis
    fi

Note that you can set the :code:`COMSKIP_INI_DIR` in the :code:`~/.video_utils.yml` file::

    COMSKIP_INI_DIR : /path/to/comskip_inis

Settings in the :code:`~/.video_utils.yml` are overriden by environment variables.

.. _comskip: https://github.com/erikkaashoek/Comskip 
