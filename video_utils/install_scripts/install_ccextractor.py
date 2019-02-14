#!/usr/bin/env python

"""
This is a python script that will install ccextractor.
All dependencies will be installed, the git repo cloned
from github.com, and the software built, checkend, and
installed.
"""

import os, sys, argparse;
from subprocess import Popen, PIPE, STDOUT;


parser = argparse.ArgumentParser(description='For installing ccextractor.')
parser.add_argument('--prefix', type=str, 
	                help='install architecture-independent files in PREFIX')
parser.add_argument('--no-delete', action='store_true', 
	                help='set to KEEP the build directory')
args = parser.parse_args();

progName = 'ccextractor';                                                       # Program name
gitURL   = 'https://github.com/CCExtractor/ccextractor.git';                    # URL to code on github

home     = os.path.expanduser('~');                                             # Get user home directory
path     = os.path.join( home, '{}_build'.format(progName));                    # Build path to local directory
gitPath  = os.path.join( path, progName);                                       # Build path for local repo
git_cmd  = ['git', 'clone', gitURL, gitPath];                                   # Command to download the git repo
err_test = 'Error: (This help screen was shown because there were no input files)'; # Warning command to look for when testing the program

if not os.path.isdir( path ): os.makedirs(path);

if sys.platform == 'darwin':                                                    # If we are on a mac
  packages = ['pkg-config', 'autoconf', 'automake', 'libtool', 
              'tesseract', 'leptonica'];                                        # List of packages to install
  dep_cmd  = ['brew', 'install'] + packages;                                    # Command to run for installing packages
  cwd_path = os.path.join(gitPath, 'mac');                                      # Location of working directory for building the program
elif sys.platform == 'linux2':                                                  # If we are on a linux system
  packages = ['cmake', 'gcc', 'autoconf',
              'libglew-dev', 'libglfw3-dev', 'libcurl4-gnutls-dev', 
              'tesseract-ocr', 'libtesseract-dev', 
              'libleptonica-dev'];                                              # List of packages to install
  dep_cmd  = ['sudo', 'apt-get', 'install', '-y'] + packages;                   # Command to run for installing packages
  cwd_path = os.path.join( gitPath, 'linux');                                   # Location of working directory for building the program

###################
print( 'Installing dependencies' );
with open( os.path.join(path, 'dependencies.log'), 'w' ) as log:
  with open( os.path.join(path, 'dependencies.err'), 'w' ) as err:
    proc = Popen( dep_cmd, stdout = log, stderr = err );                        # Run command to install dependencies
proc.communicate();                                                             # Wait for command to finish
if proc.returncode != 0: 
  print( 'Check dependencies.err for issues' );
  exit( proc.returncode );                                                      # If the return code is NOT zero, exit

###################
print( 'Cloning git repo' );
with open( os.path.join(path, 'git_clone.log'), 'w' ) as log:
  with open( os.path.join(path, 'git_clone.err'), 'w' ) as err:
    proc = Popen( git_cmd, stdout = log, stderr = err );                        # Run command to install dependencies
proc.communicate();                                                           # Wait for command to finish
if proc.returncode != 0: 
  print( 'Check git_clone.err for issues' );
  exit( proc.returncode );                                                      # If the return code is NOT zero, exit

####################
print( 'Running autogen.sh' );
with open( os.path.join(path, 'autogen.log'), 'w' ) as log:
  with open( os.path.join(path, 'autogen.err'), 'w' ) as err:
    proc = Popen( './autogen.sh', cwd = cwd_path, stdout = log, stderr = err ); # Run autogen command
proc.communicate();                                                             # Wait for command to finish
if proc.returncode != 0: 
  print( 'Check augtgen.err for issues' );
  exit( proc.returncode );

######################
print( 'Configuring...' );
if args.prefix is None:
  cmd = './configure';
else:
  cmd = ['./configure', '--prefix={}'.format( args.prefix )];
with open( os.path.join(path, 'configure.log'), 'w' ) as log:
  with open( os.path.join(path, 'configure.err'), 'w' ) as err:
    proc = Popen( cmd, cwd = cwd_path, stdout = log, stderr = err );            # Run configure command
proc.communicate();
if proc.returncode != 0: 
  print( 'Check configure.err for issues' );
  exit( proc.returncode );
  
#######################
print( 'Building...' );
with open( os.path.join(path, 'build.log'), 'w' ) as log:
  with open( os.path.join(path, 'build.err'), 'w' ) as err:
    proc = Popen( 'make', cwd = cwd_path, stdout = log, stderr = err );         # Run make command
proc.communicate();
if proc.returncode != 0: 
  print( 'Check build.err for issues' );
  exit( proc.returncode );
  
#######################
print( 'Checking build...' );
proc = Popen( './'+progName, stdout = PIPE, stderr = STDOUT, cwd = cwd_path );  # Run the program, piping output for checking
test = False;                                                                   # Set test to False
line = proc.stdout.readline();                                                  # Read a line from the program output
while line != '':                                                               # While the line is NOT empty
  # print( line.rstrip() );                                                                # Print the line to the terminal
  if err_test in line: test = True;                                             # If the err_test string is in the line, set test variable to True
  line = proc.stdout.readline();                                                # Read the next line from the program output
proc.communicate();                                                             # Wait for command to fully finish

#####################
if proc.returncode == 2 and test:                                               # If the return code is 2 AND test is True
  print('Installing...')
  proc = Popen( ['sudo', 'make', 'install'], cwd = cwd_path );                  # Install the program
  proc.communicate();                                                           # Wait for process to finish
  if proc.returncode != 0: 
    exit( proc.returncode );                                                    # If the return codes is NOT zero, exit
  if not args.no_delete:
    print('Deleting build directory');
    with open(os.devnull, 'w') as DEVNULL:
      cmd  = ['rm', '-rf', path];
      proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );                   # Try to delete the directory
      proc.communicate();                                                       # Wait for process to finish
      if proc.returncode != 0:                                                  # If failed to delete
        print( 'Failed to delete build directory, trying with sudo' );          # Print a message
        cmd  = ['sudo'] + cmd;                                                  # Try a sudo delete
        proc = Popen( cmd, stdout = DEVNULL, stderr = STDOUT );                 # Try to delete the directory
        proc.communicate();                                                     # Wait for process to finish
        if proc.returncode != 0:                                                # If failed again
          print( 'There was an issue deleting the build directory!' );          # Print error
          exit(1);
else:                                                                           # Else
  print('There was probably an issue with the install');                        # Print a message
  exit( proc.returncode );                                                      # Exit
exit(0);