Automated Tagging
=====================

This package includes code to tag MP4 and MKV video files using data from various websites.
These include The Movie Database (TMDb) and The TV Database (TVDb).
However, to enable use of TMDb and TVDb, API keys are required. 

Obtaining API keys
------------------

TMDb
^^^^

To get an API key for TMDb, you must go to their website and create an account.
After you have created an account, go to your account settings, and then API.
From there you can create an API key; the v3 key is what is required.

TVDb
^^^^

To get an API key for TVDb, you must go to their website and create an account.
After you have created an account, go to API Access and generate a new key.

Installing API keys
-------------------

After you have generated your own API keys, there are two ways to install them.

.. _method1:

Method 1 - :code:`~/.video_utils.yml` file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method requires you to create a file in your home directory named :code:`.video_utils.yml`.
If this does not make sense, :ref:`method2` may be the way to go.

After this file is created, you can add your API key(s) to it.
Note that if you only registered for one API key, you should only place that one in the file.
The file is JSON formatted::

    TMDB_API_KEY : YOUR_TMDb_KEY_HERE
    TVDB_API_KEY : YOUR_TVDb_KEY_HERE

After you add your API key(s), you can save and close the file.
You won't have to worry about this again unless you need to change your keys!
Note that Settings in the :code:`.video_utils.yml` are overriden by environment variables; see next section.

.. _method2:

Method 2 - Environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method requires you to set environment variables that the :code:`video_utils` package can use to get the API keys.
These variables must be set for the user that will be running the package.
To do this, simply add the following lines to your :code:`~/.bashrc` or :code:`~/.bash_profile`::

    export TVDB_API_KEY="YOUR_TVDb_KEY_HERE"
    export TMDB_API_KEY="YOUR_TMDb_KEY_HERE"

If code will be run under a user without a home directory, or you just want to make sure that the envrionment variables are defined for all users, you can add the environment variable definitions to the :code:`/etc/profile` file the same way you did above. 

To limit the definition of the variables to specifc users, you can filter by their uid.
For example, if your user is uid 456, then you could add the following to :code:`/etc/profile`::

    # Add TVDB_API_KEY and TMDB_API_KEY environment variables to user with uid 456
    if [ "$(id -u)" -eq 456 ]; then
        export TVDB_API_KEY="YOUR_TVDb_KEY_HERE"
        export TMDB_API_KEY="YOUR_TMDb_KEY_HERE"
    fi

