# Some global configuration settings
opensubtitles_url       = 'https://api.opensubtitles.org:443/xml-rpc'
opensutitles_user_agent = 'makemkv_to_mp4'; # do NOT use in other programs, register for your own

python_req = ['sys','re','time','subprocess'];
# python_opt = ['imdb', 'tvdbsimple', 'socket'];
python_opt = ['videotagger.metadata.getMetaData'];
cli_req    = ['HandBrakeCLI', 'mediainfo'];
cli_opt    = ['cpulimit', 'mkvextract', 'vobsub2srt'];