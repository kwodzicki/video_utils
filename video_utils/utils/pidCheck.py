import logging
import os, json, psutil

def pidStore( fPath ):
  '''
  Purpose:
    Function to store information about the current process in 
    a JSON formatted file
  Inputs:
    fPath   : Full path of file to write data to
  Keywords:
    None.
  Returns:
    Boolean, True if file created, False otherwise
  '''
  log  = logging.getLogger(__name__)
  fDir = os.path.dirname( fPath )
  try:
    os.makedirs( fDir, exist_ok=True )
  except os.PermissionError as err:
    log.error('Do not have correct permissions: {}'.format(err))
    return False
  except Exception as err:
    log.error('Something went wrong: {}'.format(err))
    return False
  else:
    pass
    

  pid = os.getpid()                                                                     # Get current process id
  for proc in psutil.process_iter():                                                    # Iterate over all processes
    if proc.pid == pid:                                                                 # If process id matches current pid
      with open( fPath, 'w' ) as fid:                                                   # Open file for writing
        json.dump( {'pid'  : pid, 
                    'name' : proc.name(), 
                    'time' : proc.create_time() }, fid )                                # Write data to File
      return True                                                                       # Return True
  log.error('Failed to find process matching current PID')
  return False

def pidRunning( fPath ):
  '''
  Purpose:
    Function to check if current process is already running based on 
    data in JSON formatted file created by pidStore()
  Inputs:
    fPath   : Full path of file to check pid information against
  Keywords:
    None.
  Returns:
    Boolean, True if process is already running, False otherwise
  '''
  if os.path.isfile( fPath ):                                                           # if the fPath file exists
    with open( fPath, 'r' ) as fid:                                                     # Open for reading
      info = json.load( fid )                                                           # Read in data
      
    if psutil.pid_exists( info['pid'] ):                                                # If the pid exists
      for proc in psutil.process_iter():                                                # Iterate over processes
        if proc.pid == info['pid'] and proc.name() == info['name']:                     # If found pid AND the process name matches
          pt = proc.create_time()                                                       # Get  process creation time
          if abs(pt - info['time']) < 1.0:                                              # If the process was created within one (1) second of reference process
            return True                                                                 # Assume they are same process and return True

  pidStore( fPath )                                                                     # If made here, then process is not running, so store current information 
  return False                                                                          # Return False; pid is not running
