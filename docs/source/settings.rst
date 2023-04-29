User settings
=============
The user settings file is a YAML formatted file that allows the user to easily set:

  - API keys (see :doc:`Automated Tagging <./api/modules>`)
  - The comskip INI directory (see :doc:`Commerical Skipping <./comskip>`)
  - Email alerts (see :doc:`Email Alerts <./email>`)

This file will be copied to :code:`~/.video_utils.yml` on package install if it does not exist already.

The file is laidout in three (3) sections.

  #. Sets the API keys for TMDb and TVDb.
  #. Sets the directory where :code:`comskip.ini` files are located.
  #. Sets up an email smtp server for sending email updates and the email address(es) that should receive the updates.

The contents of the file are below:
 
.. code-block:: yaml

    #####################
    # API Keys
    TVDB_API_KEY :    # Set to string containing API key for TV Database 
    TMDB_API_KEY :    # Set to string containing API key for The Movie Database
    
    
    #####################
    # Comskip settings
    COMSKIP_INI_DIR : # Set to string containing full path to directory containing comskip ini files
    
    #####################
    # This section defines email inforamtion for logging
    email:
      send_from:
        server : smtp.gmail.com   # Gmail smtp server address; change to match service you are using
        port   : 465              # SSL port
        user   :                  # User name for logging into the send_from account
        pass   :                  # Password for logging in; should be app password if using Google
      send_to:
        -                         # First email address to send information to
        -                         # Second email addres to send inforamtion to, etc.
