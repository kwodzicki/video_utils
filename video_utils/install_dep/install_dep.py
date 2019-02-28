#!/usr/bin/env python

"""
This is a python script that will install pkg_info.
All dependencies will be installed, the git repo cloned
from github.com, and the software built, checkend, and
installed.
"""
import os;
from .install_utils import base_installer
from . import config;

def install_dep( prefix = None, no_delete = False, 
      ccextractor = False, 
      comskip     = False,
      vobsub2srt  = False,
      cpulimit    = False,
      all_dep     = False ):
  res = base_installer( config.required, 
    prefix    = prefix, 
    no_delete = no_delete,
    logFile   = logFile,
    errFile   = errFile)
  if res != 0: return res
 
  if ccextractor or all_dep:
    res = base_installer( config.ccextractor, 
      prefix    = prefix, 
      no_delete = no_delete,
      logFile   = logFile,
      errFile   = errFile)
    if res != 0: return res
  if comskip or all_dep:
    res = base_installer( config.comskip, 
      prefix    = prefix, 
      no_delete = no_delete,
      logFile   = logFile,
      errFile   = errFile);
    if res != 0: return res
  if vobsub2srt or all_dep:
    res = base_installer( config.vobsub2srt, 
      prefix    = prefix, 
      no_delete = no_delete,
      logFile   = logFile,
      errFile   = errFile)
    if res != 0: return res
  if cpulimit or all_dep:
    res = base_installer( config.cpulimit, 
      prefix    = prefix, 
      no_delete = no_delete,
      logFile   = logFile,
      errFile   = errFile)
    if res != 0: return res



  home    = os.path.expanduser('~')
  logFile = os.path.join( home, 'video_util_dep.log');
  errFile = os.path.join( home, 'video_util_dep.err');
  res = install_comskip( prefix  = prefix,  no_delete = no_delete, 
                         logFile = logFile, errFile   = errFile);
  if res != 0: return res

  res = install_ccextractor( prefix  = prefix,  no_delete = no_delete, 
                             logFile = logFile, errFile   = errFile)
  if res != 0: return res
  
  return 0;

if __name__ == "__main__":
  import argparse;
  parser = argparse.ArgumentParser(description='For installing pkg_info.')
  parser.add_argument('--prefix', type=str, 
                  help='install architecture-independent files in PREFIX')
  parser.add_argument('--no-delete', action='store_true', 
                  help='set to KEEP the build directory')
  args = parser.parse_args();
  res  = install_all( prefix = args.prefix, no_delete = args.no_delete );
  exit( res );
