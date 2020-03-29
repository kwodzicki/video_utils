from multiprocessing import cpu_count

MAXTHREADS  = cpu_count()
MINTHREADS  = 1

HALFTHREADS = MAXTHREADS // 2
if HALFTHREADS < 1: HALFTHREADS = 1

def threadCheck(val):
  '''
  Function to check that requested number of threads is 
  integer type and is withing allowable range
  '''
  if not isinstance(val, int):                                      # If input val is NOT integer
    return MAXTHREADS                                               # Return maximum number of threads allowed
  elif val < MINTHREADS:                                            # Else, if value is less than minimum number of threads
    return MINTHREADS                                               # Return minimum number of threads
  elif val > MAXTHREADS:                                            # Else, if value greater than maximum number of threads
    return MAXTHREADS                                               # Return maximum number of threads
  return val                                                        # Finally, just return input value
