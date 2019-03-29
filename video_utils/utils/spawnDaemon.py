import logging;
import os;
def spawnDaemon( func, *args, **kwargs ):
  '''
  Name:
    spawnDaemon
  Purpose:
    A python function to spawn a daemon function
  Inputs:
    func  : Function to run
    *args : All arguments required by the function
  Outputs:
    None.
  Keywords:
    **kwargs : All keyword required by the function
  '''
  log = logging.getLogger(__name__);                                            # Get logger for the function
  try:                                                                          # Try to
    pid = os.fork();                                                            # Fork the process
  except OSError as e:                                                          # If error occured
    log.error( 'Fork failed: {} ({})'.format(e.errno, e.strerror) )
    exit(1);                                                                    # Exit with code one (1)
  else:                                                                         # Else
    if pid > 0:                                                                 # If process is the parent
      exit(0);                                                                  # Exit with code zero (0)

  # decouple from parent environment
  os.setsid();

  try:                                                                          # Try to
    pid = os.fork();                                                            # Fork the process
  except OSError as e:                                                          # If error occured
    log.error( 'Fork failed: {} ({})'.format(e.errno, e.strerror) )
    exit(1);                                                                    # Exit with code one (1)
  else:                                                                         # Else
    if pid > 0:                                                                 # If process is the parent
      exit(0);                                                                  # Exit with code zero (0)

  log.debug( 'Running function' )
  func( *args, **kwargs );                                                      # If made it here, we are in the child so run the function
  exit(0);                                                                      # Exit the child with code zero