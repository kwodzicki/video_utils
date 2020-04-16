import logging
from logging.handlers import RotatingFileHandler

import os

import smtplib
from email.message import EmailMessage

from threading import Thread, Lock

from .. import log
from ..config import CONFIG, ROTATING_FORMAT

EMAILNAME = 'emailer'

############################################################################### 
def sendEMail( func ):
  '''
  Purpose:
    Function to act as decorator to send email using EMailHandler
  Inputs:
    func   : Function to wrap
  Keywords:
    None.
  Returns:
    Wrapped function
  '''
  def sendEMailWrapper(*args, **kwargs):
    val = func(*args, **kwargs)
    for handler in log.handlers:                        # Iterate over all handlers in root logger
      if handler.get_name() == EMAILNAME:               # If the handler matches the EMAILNAME variable
        handler.send()                                  # call send method
        break                                           # Break for loop
    return val                                          # Return function return value
  return sendEMailWrapper   

############################################################################### 
class EMailHandler( logging.Handler ):                                          
  def __init__(self, *args, **kwargs):                       
    maxLogs = kwargs.pop('maxLogs', 50)
    subject = kwargs.pop('subject', None)
    super().__init__(*args, **kwargs);                                              # Initialize base class
    self._max       = maxLogs
    self._subject   = subject
    self._logs      = []
    self._sendLevel = logging.CRITICAL
    self._isValid   = True
    self.set_name( EMAILNAME )

    info = CONFIG.get('email', None)
    if info is None: 
      self._isValid = False
      return

    send_from = info.get('send_from', None)
    if send_from is None: 
      self._isValid = False
      return

    send_to   = self.parse_send_to( info.get('send_to',  None) )
    if not send_to:
      self._isValid = False
  
  ##################################                                            
  def __bool__(self):
    return self._isValid

  ##################################                                            
  def emit(self, record):                                                           # Overload the emit method                        
    with self.lock:
      if len(self._logs) > self._max:
        self._logs.pop(0) 
      self._logs.append( self.format(record) )
    if record.levelno >= self._sendLevel:
      self.send()

  ##################################                                            
  def setSendLevel(self, level):
    '''
    Purpose:
      Set the level at which logs are automatically 
      emailed. For example, if the SendLevel is set
      to logging.WARNING, if a log with level WARNING
      or higher is encountered, an email will be sent.
      Note that if this level is set lower than the
      logger level, the email my be empty.
    Inputs:
      level   : The logging level
    Keywords:
      None.
    Returns:
      None.
    '''
    if isinstance(level, int):
      self._sendLevel = level
   
  ##################################                                            
  def parse_send_to(self, send_to):
    if isinstance(send_to, (list, tuple,)):
      return ','.join( [s for s in send_to if s is not None] )
    elif isinstance(send_to, str):
      return send_to
    return None
 
  ##################################                                            
  def send(self, subject = None):
    if not self: return
    with self.lock:
      body = '\n'.join(self._logs)
      self._logs = []
    if body == '': return

    email     = CONFIG['email']
    send_from = email['send_from']
    send_to   = self.parse_send_to( email['send_to'] ) 
    msg = EmailMessage()
    if subject:
      msg['Subject'] = subject
    elif self._subject:
      msg['Subject'] = self._subject

    msg['From']    = send_from['user'] 
    msg['To']      = send_to
    msg.set_content( body )

    try:
      server = smtplib.SMTP_SSL(send_from['server'], send_from['port'])
    except:
      return False
    try:
      server.login(send_from['user'], send_from['pass'])                            
    except:
      return False
    try:
      server.sendmail(send_from['user'], send_to, msg.as_string())            
    except:
      pass
    try:
      server.close() 
    except:
      pass
    return True

########################################################################################
class RotatingFile( Thread ):
  '''
  A class that acts like the logging.handlers.RotatingFileHander;
  writing data out to a file until file grows too large, then rolling
  over.

  This class is intended to be used for stdout and stderr for calls to
  subprocess module routines, such as the Popen constructor. However, there
  are many other applications for this class.
  '''
  def __init__(self, *args, **kwargs):
    super().__init__()
    self.rw         = None                                                              # Initialize read/write pipe as None
    self.callback   = kwargs.pop('callback', None)                                      # Pop off 'callback' keyword; set to None
    for key, val in ROTATING_FORMAT.items():
      if key not in kwargs:
        kwargs[key] = val

    formatter       = kwargs.pop('formatter', None)
    self.log        = RotatingFileHandler(*args, **kwargs)                              # Initialize rotating file handler
    if isinstance(formatter, logging.Formatter):
      self.log.setFormatter( formatter )                                                # Set formatting
    else:
      self.log.setFormatter( logging.Formatter( '%(asctime)s - %(message)s' ) )

  def __enter__(self, *args, **kwargs):
    self.start()

  def __exit__(self, *args, **kwargs):
    self.close()

  def setFormatter(self, *args):
    self.log.setFormatter( *args )

  def start(self):
    self.rw = os.pipe()                                                                 # Open a pipe
    super().start()                                                                     # Call supercalls start method

  def run(self):
    '''
    Purpose:
      Overloads the run method; this method will run in own thread.
      Reads data from pipe and passes to self.log.emit
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      None.
    '''
    with os.fdopen(self.rw[0]) as fid:                                                  # Open the read-end of pipe
      for line in iter(fid.readline, ''):                                               # Iterate over all lines
        record = logging.LogRecord('', 20, '', '', line.rstrip(), '', '')
        self.log.emit( record )                                                         # Pass line to rotating logger
        if self.callback:                                                               # If call back is set
          self.callback( line )                                                         # Pass line to call back
    self.close()

  def close(self):
    '''
    Purpose:
      Method to clean up the pipe and logging file
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      None.
    '''
    if self.rw:                                                                         # If rw is set
      os.close(self.rw[1])                                                              # Close the write-end of pipe
      self.rw = None                                                                    # Set rw to None
    self.log.close()                                                                    # Close the log
 
  def fileno(self):
    '''
    Purpose:
      Method to get underlying file pointer; in this case pipe
    Inputs:
      None.
    Keywords:
      None.
    Returns:
      None.
    '''
    if not self.rw:                                                                     # If read/write pipe NOT set
      self.start()                                                                      # Start thread
    return self.rw[1]                                                                   # Return write-end of pipe


########################################################################################
def initLogFile( formatDict ):
  noHandler = True;                                                             # Initialize noHandle
  for handler in log.handlers:                                                  # Iterate over all ha
    if handler.get_name() == formatDict['name']:                                   # If handler name mat
      noHandler = False;                                                        # Set no handler fals
      break;                                                                    # Break for loop

  if noHandler:
    logDir = os.path.dirname( formatDict['file'] );
    if not os.path.isdir( logDir ):
      os.makedirs( logDir )
    rfh = RotatingFileHandler( formatDict['file'], **ROTATING_FORMAT )
    rfh.setFormatter( formatDict['formatter'] )
    rfh.setLevel(     formatDict['level']     )                                   # Set the logging lev
    rfh.set_name(     formatDict['name']      )                                   # Set the log name
    log.addHandler( rfh )                                                      # Add hander to the m

    info = os.stat( formatDict['file'] );                                          # Get information abo
    if (info.st_mode & formatDict['permissions']) != formatDict['permissions']:       # If the permissions
      try:                                                                      # Try to
        os.chmod( formatDict['file'], formatDict['permissions'] );                    # Set the permissions
      except:
        log.info('Failed to change log permissions; this may cause issues')

