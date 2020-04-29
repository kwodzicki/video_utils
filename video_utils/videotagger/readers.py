from mutagen import mp4

from . import MP42COMMON

'''
Have to check for MP4FreeForm. If is instance, then run
.decode() method to get values. May be in a list, so 
have to iterate over list; i.e., list of MP4FreeForm objects
'''
def mp4Reader( filePath ):
  obj  = mp4.MP4( filePath )
  info = {}
  for key, val in obj.items():
    if key in MP42COMMON:
      info[ MP42COMMON[key] ] = val
  return info
