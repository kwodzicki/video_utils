import logging;
import os;
from datetime import timedelta;
from subprocess import Popen;

try:
  from .utils.limitCPUusage import limitCPUusage;
except:
  limitCPUusage = None;



class comremove( object ):
  _comskip = ['comskip', '--hwassist', '--cuvid', '--vdpau'];
  _comcut  = 'ffmpeg,-nostdin,-i,{},-ss,{},-t,{},-c,copy,{}'
  _comjoin = ''
  log      = logging.getLogger( __name__ );
  def __init__(self, ini = None, threads = None, cpulimit = None, verbose = None):
    self.ini      = ini;
    self.threads  = threads;
    self.cpulimit = cpulimit;

  ########################################################
  def run(self, in_file,  ):
    
    edl_file = self.comskip( in_file );
    tmp = self.comcut( in_file, edl_file );

  ########################################################
  def comcut(self, in_file, edl_file);
    dir  = os.path.dirname( in_file );
    fid  = open(edl_file, 'r');
    fnum = 0;
    info = fid.readline();
    while info:
      start, end = info.split([:2]);
      start = timedelta( seconds = float(start) );
      dura  = timedelta( seconds = float(end) ) - start;
      out   = os.path.join()
      cmd   = self._comcut.format(in_file, start, dura, out)
      info  = fid.readline();
    fid.close();

  ########################################################
  def comskip(self, in_file):
    cmd = self._comskip;
    if self.threads:
      cmd.append( '--threads={}'.format(self.threads) );
    if self.ini:
      cmd.append( '--ini={}'.format(self.ini) );
    out_dir = os.path.dirname( in_file );
    
    tmp_file  = '.'.join( in_file.split('.')[:-1] );                    # Get file path with no extension
    edl_file  = '{}.edl'.format(      tmp_file );                       # Path to .edl file
    txt_file  = '{}.txt'.format(      tmp_file );                       # Path to .txt file
    logo_file = '{}.logo.txt'.foramt( tmp_file );                       # Path to .logo.txt file

    cmd.append( '--output={}'.format(out_dir) );
    cmd.extend( [in_file, out_dir] );

    with open(os.path.join(out_dir, 'comskip.log'), 'w') as log:
      with open(os.path.join(out_dir, 'comskip.err'), 'w') as err:
        proc = Popen(cmd, stdout = log, stderr = err);
    if limitCPUusage and self.cpulimit:
      CPU_id = limitCPUusage(proc.pid, self.cpulimit, self.threads);  # Run cpu limit command
    proc.communicate();                                               # Wait for self.handbrake to finish completely
    try:                                                              # Try to...
      CPU_id.communicate();                                           # Communicate with CPU_id to wait for it to exit cleanly
    except:                                                           # On exception
      pass;
    os.remove( txt_file  );
    os.remove( logo_file );
    return edl_file;