#!/usr/bin/env python

import os;
from imdb import IMDb

imdb = IMDb();
def file_rename( in_file ):
  series, se, title = in_file.split(' - ');
  outDir = os.path.dirname( in_file );
  tmp    = title.split('.')
  tmp    = title.split('.')
  ext    = tmp[-1]
  title  = '.'.join(tmp[:-1]);
  res    = imdb.search_episode( title );
  for r in res:
    if r['episode of'].lower() in series.lower():
      new = '{} - {}.tt{}.{}'.format(se.lower(), title, r.getID(), ext);
      new = os.path.join( outDir, new )
      os.rename( in_file, os.path.join(dir, new));
      return True;
  return False;
if __name__ == "__main__":
  import sys;
  if len(sys.argv) == 2:
    file_rename( sys.argv[1] )