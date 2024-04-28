#!/usr/bin/env python
# To get subtitle SRT files from opensubtitles.org

"""
Interface with opensubtitles API

Various utilities for try to download SRT subtitle files from opensubtitles
website using information entered by user or from information parsed from
file name

"""

import logging
import os
import time
from base64 import standard_b64decode
from zlib import decompress
from xmlrpc.client import ServerProxy

from ..config import opensubtitles as opensubs_config

# List of some common video extensions
EXT = ('.avi', '.m4v', '.mp4', '.mkv', '.mpeg', '.mov', '.wmv')


class OpenSubtitles(ServerProxy):
    """A python class to download SRT subtitles for opensubtitles.org."""

    api_url = opensubs_config['url']
    user_agent = opensubs_config['user_agent']
    title = None
    imdb = None
    lang = ['eng']
    verbose = False
    nsubs = 1
    sort = 'score'
    track_num = None
    get_forced = False

    server_lang = 'en'  # Set up the server
    attempts = 10

    def __init__(
        self,
        username: str | None = None,
        userpass: str | None = None,
        verbose: bool = False,
        **kwargs,
    ):
        """
        Initialize the OpenSubtitles class.

        Some code borrowed from:
         https://github.com/chripede/opensubtitle-downloader

        To download the top 5 subtiles for foreign language parts and
        full movie based on score in english, the call word look like::

            >>> subs = OpenSubtitles().get_subtitles('/path/to/file', nsubs=5)

        as the default for sorting is score and english is the
        default language.

        To download the 5 newest subtitles in Russian for foreign
        language parts and full movie the call word look like::

            >>> subs = OpenSubtitles(
            ...     '/path/to/file',
            ...     lang='rus',
            ...     nsubs=5,
            ...     sort='date',
            ... )

        Arguments:
            None

        Keyword arguments:
            username (str): User name for opensubtitles.org.
            userpass (str): Password for opensubtitles.org. Recommend that
                this be the md5 hash of the password and not
                the plain text of the password for slightly
                better security
            **kwargs

        Returns:
            Save an SRT subtitle file with same convetion as movie
            file IF a subtitle is found.

        """

        super().__init__(opensubs_config['url'], verbose=False)

        self.__log = logging.getLogger(__name__)

        self.username = username if isinstance(username, str) else ''
        self.userpass = userpass if isinstance(userpass, str) else ''
        self.verbose = verbose
        self.subs = None

        self.login_token = None

    def _parse_kwargs(self, **kwargs):
        """Method to parse keyword arguments into class attributes"""

        self.title = kwargs.get('title', None)
        self.imdb = kwargs.get('imdb', None)
        self.lang = kwargs.get('lang', None)
        self.verbose = kwargs.get('verbose', False)
        self.nsubs = kwargs.get('nsubs', 1)
        self.sort = kwargs.get('sort', 'score').lower()
        self.track_num = kwargs.get('track_num', None)
        self.get_forced = kwargs.get('get_forced', False)

        if self.track_num:
            self.track_num = int(self.track_num)
        # Make sure lang attribute is iterable
        if not isinstance(self.lang, (tuple, list,)):
            self.lang = [self.lang]
        if len(self.lang) == 0:
            self.lang = ['eng']

    def get_subtitles(self, fpath: str, **kwargs) -> list[str] | None:
        """
        Attempt to log-in to, download from, and log-out of the server.

        No user interaction requried.

        Arguments:
            fpath (str): Full path to the movie file to download SRT file for.

        Keyword arguments:
            title (str): Set to title of movie to search for.
                Default is to use title from file.
            imdb (str): Set to IMDb id of moive to search for.
                Default is to try to get IMDb id from file name.
            lang (str,list): String of list of strings to language to download
                subtitle in using ISO 639-2 code. Default is english (eng).
            verbose (bool): Set to True to increase verbosity.
                Default isFalse
            nsubs (int): Set to the number of files subtitles to download
                for each file. Default is one (1).
            sort (str): Set the sorting method used for downloading.
                Sorted in descending order.
                Options are
                    - score     : Sort based on score (default)
                    - downloads : Sort based on number of times downloaded
                    - date      : Sort based on upload date
            track_num (int): Set to specific 'track' number for labeling.
                Default is to start at zero.
            get_forced (bool): Set to True to get only forced subtitles.
                Default is to get full.

        Returns:
            Save an SRT subtitle file with same convetion as movie
                file IF a subtitle is found.

        """

        self._parse_kwargs(**kwargs)
        self.login()
        self.search_subs(fpath=fpath)
        files = self.save_srt(fpath=fpath)
        self.logout()
        return files

    def search_subs(self, **kwargs) -> None:
        """search for, download, and save subtitles."""

        if self.login_token is None:
            return
        self.__log.info("Searching for subtitles...")

        # Initialize search attribute with language(s) set;
        # keyword input overrides class attribute lang
        search = {
            'sublanguageid': ','.join(kwargs.get('lang', self.lang)),
        }

        # If IMDb is input
        if ('imdb' in kwargs) or self.imdb:
            search['imdbid'] = kwargs.get('imdb', self.imdb).replace('tt', '')
        # Else if a title is input
        elif ('title' in kwargs) or self.title:
            search['movie name'] = kwargs.get('title', self.title)
        # Else, if file is set use information from the file name
        elif 'fpath' in kwargs:
            fpath = kwargs.get('fpath')
            # Split file basename on period
            tmp = os.path.basename(fpath).split('.')
            # Index of where IMDb id is supposed to be based on whether
            # there is a file extension or not
            index = -2 if fpath.lower().endswith(EXT) else -1
            # If there is more than one element in the list after split on
            # period and the length of the value where the IMDb id should be
            # is greater than two (2)
            if len(tmp) > 1 and len(tmp[index]) > 2:
                # If the first two (2) letters of the second last string are tt
                if tmp[index][:2] == 'tt':
                    search['imdbid'] = tmp[index][2:]
            if 'imdbid' not in search:
                search['movie name'] = tmp[0]

        if ('imdbid' not in search) and ('movie name' not in search):
            return

        # Try a few times to download SRT
        for _ in range(self.attempts):
            try:
                resp = self.SearchSubtitles(self.login_token, [search])
            except:
                time.sleep(1)
                continue

            if self.check_status(resp):
                # Sleep 0.3 seconds so that request limit is NOT reached
                time.sleep(0.3)
                # If the data tag in the response is False
                if resp['data'] is False:
                    self.__log.info("No subtitles found")
                    return
                # If the data tag has a length of zero (0)
                if len(resp['data']) == 0:
                    self.__log.info("No subtitles found")
                    return
                # Sort the subtitles
                self.sort_subs(resp['data'])
                return

    def sort_subs(self, sub_data):
        """Sort subtitles by score, download count, and date."""

        self.subs = {}
        keys = (
            ('Score', 'score'),
            ('SubDownloadsCnt', 'downloads'),
            ('SubAddDate', 'date')
        )

        # Iterate over all languages
        for lang in self.lang:
            # Initialize dictionary to store sorted subtitle informatio
            self.subs[lang] = {
                'score': None,
                'downloads': None,
                'date': None,
            }
            subs = []
            for sub in sub_data:
                # If sub is type string, then assume sub_data is a
                # dictionary and set sub to information for key 'sub'
                if isinstance(sub, str):
                    sub = sub_data[sub]
                test = (
                    int(sub['SubBad']) != 1 and
                    sub['SubFormat'] == 'srt' and
                    sub['SubLanguageID'] == lang
                )
                if test is False:
                    continue

                if self.get_forced:
                    if int(sub['SubForeignPartsOnly']) == 1:
                        subs.append(sub)
                elif int(sub['SubForeignPartsOnly']) == 0:
                    subs.append(sub)

            for sub in subs:
                if len(sub) == 0:
                    self.subs[lang] = None
                # Work on sub titles will all movie text if any were found
                else:
                    # Iterate over the keys
                    for key in keys:
                        self.subs[lang][key[1]] = []
                        vals = [i[key[0]] for i in subs]
                        # Get indices, in reverse order, for sorting
                        index = sorted(
                            range(len(vals)),
                            key=vals.__getitem__,
                            reverse=True,
                        )
                        # Append the dictionaries to the subs_all attribute in
                        # descending order
                        for i in index:
                            self.subs[lang][key[1]].append(subs[i])

    def save_srt(self, fpath=''):
        """Save the SRT subtitle data to file"""

        files = []
        if self.subs is None:
            return None

        track = -1 if self.track_num is None else self.track_num - 1

        # If the file name has any of these extensions
        if fpath.lower().endswith(EXT):
            srt_base, _ = os.path.splitext(fpath)
        else:
            srt_base = fpath

        for lang in self.lang:
            self.__log.info(
                'Language: %s, forced: %s',
                lang,
                self.get_forced,
            )
            subs = self.subs[lang][self.sort]
            if subs is None:
                self.__log.info('  No subtitle(s) found')
                continue

            # Iterate over number of subtitle files to grab
            for i in range(self.nsubs):
                if i >= len(subs):
                    break
                track += 1

                # Add the subtitle track num and lang code to the file name
                srt = f"{srt_base}.{track:d}.{lang}"
                # Append forced if forced flag set
                if self.get_forced:
                    srt = f"{srt}.forced"
                srt = f"{srt}.srt"

                if os.path.isfile(srt):
                    self.__log.info('  File already exists...Skipping!')
                    files.append(srt)
                    continue

                dirname = os.path.dirname(srt)
                if not os.path.isdir(dirname):
                    os.makedirs(dirname)
                data = self.download(subs[i])
                if data is not None:
                    with open(srt, 'wb') as fid:
                        fid.write(data)
                    files.append(srt)
        return files

    def download(self, sub):
        """Download subtitle file and return the decompressed data."""

        self.__log.info('  Downloading subtitle...')
        for _ in range(self.attempts):
            # Download the subtitle
            try:
                resp = self.DownloadSubtitles(
                    self.login_token,
                    [sub['IDSubtitleFile']]
                )
            except:
                time.sleep(0.5)
                continue

            # If the response is Okay
            if self.check_status(resp):
                # Encode the data to ascii
                tmp = resp['data'][0]['data'].encode('ascii')
                if isinstance(tmp, str):
                    decoded = standard_b64decode(tmp)
                else:
                    decoded = standard_b64decode(resp['data'][0]['data'])
                return decompress(decoded, 15 + 32)

        self.__log.error('  Failed to download subtitle!')
        return None

    def login(self):
        """Log in to OpenSubtitles"""

        self.__log.info("Login to opensubtitles.org...")
        for _ in range(self.attempts):
            # Try to login
            try:
                resp = self.LogIn(
                    self.username,
                    self.userpass,
                    self.server_lang,
                    self.user_agent,
                )
            except:
                time.sleep(1)
                continue

            # If the response is Okay
            if self.check_status(resp):
                self.login_token = resp['token']
                return

        # If get to here, login failed
        self.__log.error("Failed to login!")
        self.login_token = None

    def logout(self):
        """Log out from OpenSubtitles"""

        # If the login token is None, then NOT logged in and just return
        if self.login_token is None:
            return

        self.__log.info("Logout of opensubtitles.org...")
        for _ in range(self.attempts):
            try:
                resp = self.LogOut(self.login_token)
            except:
                time.sleep(1)
                continue

            if self.check_status(resp):
                self.login_token = None
                return

        # If get to here, logout failed
        self.__log.error("Failed to logout!")
        self.login_token = None

    def check_status(self, resp):
        """
        Check request status

        Anything other than "200 OK" raises a UserWarning

        """

        try:
            if resp['status'].upper() != '200 OK':
                self.__log.error("Response error from %s", self.api_url)
                self.__log.error("Response status was: %s", resp['status'])
                return False
            return True
        except:
            self.__log.error("No response from API!")
            return False


########################################################################
# Set up command line arguments for the function
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OpenSubtitles")
    parser.add_argument(
        "file",
        type=str,
        help="Path to file subtitles are for.",
    )
    parser.add_argument(
        "--imdb",
        type=str,
        help="IMDb id starting with tt.",
    )
    args = parser.parse_args()

    logger = logging.getLogger('__main__')
    logger.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    logger.addHandler(sh)

    _ = OpenSubtitles().get_subtitles(args.file, imdb=args.imdb)
#   exit(x)
