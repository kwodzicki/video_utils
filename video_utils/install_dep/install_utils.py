import os, sys;
from subprocess import Popen, PIPE, STDOUT, DEVNULL

home = os.path.expanduser('~');                                             # Get user home directory

def subProc( cmd, mode = 'w', pipe = False, devnull = False, stdout = None, stderr = None, **kwargs ):
  '''
  Purpose:
    Simple wrapper for the subprocess.Popen class
  Inputs:
    cmd   : List with command line arguments for Popen
  Keywords:
    mode    : Mode for any log files fed to stdout or stderr keywords
    pipe    : Set to true to pipe stdout and stderr; If set function 
              will return a Popen object to interact with
    devnull : Set to pipe all output to null
    stdout  : Path to ouptut file to write stdout to
    stderr  : path to ouptut file to write stderr to
    All other valid Popen keywords
  '''
  if pipe:
    stdout = PIPE;
    stderr = STDOUT;
  elif devnull:
    stdout = DEVNULL;
    stderr = STDOUT;
  else:
    stdout = open( stdout, mode ) if stdout else STDOUT;
    stderr = open( stderr, mode ) if stderr else STDOUT;

  proc = Popen( cmd, stdout = stdout, stderr = stderr, **kwargs );       # Run command to install dependencies
  if pipe: return proc;
  proc.communicate();                                                             # Wait for command to finish

  if type(stdout) is not int: stdout.close();
  if type(stderr) is not int:
    stderr.close();
    if proc.returncode != 0:
      print( 'Check {} for issues'.format(stderr.name) );

  return proc.returncode;


def base_installer( pkg_info, prefix = None, no_delete = False, logFile = None, errFile = None):
  '''
  Purpose:
    General function for installing programs that require the following:
      - Install of dependencies from apt-get or the like
      - Clone of git repo
      - Running of an autogen.sh script
      - Running of configure script
      - Running of a make script
      - Testing to see if command built
      - Running of 'make install' command
    Two such CLIs that have such a build order are comskip and 
    ccextractor
  Inputs:
    pkg_info  : Dictionary with information about package 
                 dependencies, build locations, etc.
  Keywords:
    prefix    : Installation prefix for the CLI
    no_delete : Set to keep the build directory. Default is to
                  delete build directory after successful install
    logFile   : Path to file to log all stdout to while building
    errFile   : Path to file to log all stderr to while building
  '''
  progName = pkg_info['name'];                                                   # Program name
  path     = os.path.join( home, '{}_build'.format(progName));                    # Build path to local directory
  gitPath  = os.path.join( path, progName);                                       # Build path for local repo
  if pkg_info['git'] != '':
    git_cmd  = ['git', 'clone', pkg_info['git'], gitPath];                                   # Command to download the git repo
  else:
    git_cmd = None;
  
  if not os.path.isdir( path ): os.makedirs(path);
  if logFile is None: 
    logFile = '{}_install.log'.format(progName);
    logFile = os.path.join(path, logFile);
  if errFile is None: 
    errFile = '{}_install.err'.format(progName);
    errFile = os.path.join(path, errFile);
  

  dep_cmd  = pkg_info['dep'][sys.platform]['cmd_base'];
  dep_cmd += pkg_info['dep'][sys.platform]['packages'];
  cwd_path = os.path.join(gitPath, pkg_info['dep'][sys.platform]['cwd']);     # Location of working directory for building the program

  ###################
  print( 'Installing dependencies' );
  res = subProc( dep_cmd, mode='a', stdout=logFile, stderr=errFile )
  if res != 0: return res;                                                      # If the return code is NOT zero, exit
  
  ###################
  if git_cmd:
    print( 'Cloning git repo' );
    res = subProc( git_cmd, mode='a', stdout=logFile, stderr=errFile )
    if res != 0: return res;                                                      # If the return code is NOT zero, exit
  
  ####################
  if pkg_info['autogen']:
    print( 'Running autogen.sh' );
    res = subProc( './autogen.sh', mode='a', cwd=cwd_path, stdout=logFile, stderr=errFile ); # Run autogen command
    if res != 0: return res;                                                      # If the return code is NOT zero, exit
  
  ######################
  if pkg_info['config']:
    print( 'Configuring...' );
    cmd = ['./configure'];
    if prefix: cmd.append( '--prefix={}'.format( prefix ) );
    res = subProc( cmd, mode='a', cwd=cwd_path, stdout=logFile, stderr=errFile );          # Run configure command
    if res != 0: return res;                                                      # If the return code is NOT zero, exit
      
  #######################
  if pkg_info['make']:
    print( 'Building...' );
    res =  subProc( 'make', mode='a', cwd=cwd_path, stdout=logFile, stderr=errFile );         # Run make command
    if res != 0: return res;                                                      # If the return code is NOT zero, exit
    
    #######################
    print( 'Checking build...' );
    proc = subProc( './'+progName, pipe=True, cwd=cwd_path );                     # Run the program, piping output for checking
    test = False;                                                                 # Set test to False
    line = proc.stdout.readline();                                                # Read a line from the program output
    while line:                                                                   # While the line is NOT empty
      if pkg_info['test'] in line: test = True;                                             # If the err_test string is in the line, set test variable to True
      line = proc.stdout.readline();                                              # Read the next line from the program output
    proc.communicate();                                                           # Wait for command to fully finish
    
    #####################
    if proc.returncode == 2 and test:                                             # If the return code is 2 AND test is True
      print('Installing...')
      cmd = ['make', 'install']
      res = subProc( cmd, devnull = True, cwd = cwd_path );                       # Install the program
      if res != 0:                                                                # If failed to delete
        cmd = ['sudo'] + cmd;                                                     # Try a sudo delete
        res = subProc( cmd, devnull = True, cwd = cwd_path  );                    # Try to delete the directory
        if res != 0:                                                              # If failed again
          return res;
      if not no_delete:
        print('Deleting build directory');
        cmd = ['rm', '-rf', path];
        res = Popen( cmd, devnull = True );                                       # Try to delete the directory
        if res != 0:
          return res
    else:                                                                         # Else
      print('There was probably an issue with the build');                        # Print a message
      return proc.returncode;                                                     # Exit
  return 0;
