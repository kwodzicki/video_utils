import logging
import smtplib
from email.message import EmailMessage
from threading import Lock

HOST = 'smtp.gmail.com'  
PORT = 465 

############################################################################### 
class EMailHandler( logging.Handler ):                                          
  def __init__(self, sender, passwd, *args, **kwargs):                       
    super().__init__(*args, **kwargs);                                              # Initialize base class
    self._max     = kwargs.pop('maxLogs', 50)
    self._sender  = sender
    self._passwd  = passwd
    self._logs    = []

  ##################################                                            
  def emit(self, record):                                                           # Overload the emit method                        
    with self.lock:
      if len(self._logs) > self._max:
        self._logs.pop(0) 
      self._logs.append( self.format(record) )

  def send(self, send_to, subject = None):
    with self.lock:
      body = '\n'.join(self._logs)
      self._logs = []

    if isinstance(send_to, (list, tuple,)):
      send_to = ', '.join(send_to)
    elif not isinstance(send_to, str):
      raise Exception('Must input string')
    
    msg = EmailMessage()
    if subject: msg['Subject'] = subject
    msg['From']    = self._sender
    msg['To']      = send_to 
    msg.set_content( body )

    try:
      server = smtplib.SMTP_SSL(HOST, PORT)
    except:
      return 
    try:
      server.login(self._sender, self._passwd)                            
    except:
      return
    try:
      server.sendmail(self._sender, send_to, msg.as_string())            
    except:
      pass
    try:
      server.close() 
    except:
      pass
