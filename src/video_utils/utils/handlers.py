"""
Specialized logging handlers

"""

import logging
from logging.handlers import RotatingFileHandler

import os
import smtplib

from functools import wraps
from email.message import EmailMessage
from threading import Thread


from .. import log
from ..config import CONFIG, ROTATING_FORMAT

EMAILNAME = 'emailer'


def send_email(func):
    """
    Function to act as decorator to send email using EMailHandler

    Arguments:
        func: Function to wrap

    Keyword arguments:
        None.

    Returns:
        Wrapped function

    """

    @wraps(func)
    def send_email_wrapper(*args, **kwargs):
        """Wrapped function for mail sending"""
        val = func(*args, **kwargs)
        # Iterate over all handlers in root logger
        for handler in log.handlers:
            # If the handler matches the EMAILNAME variable
            if handler.get_name() == EMAILNAME:
                handler.send()  # call send method
                break
        return val  # Return function return value
    return send_email_wrapper


class EMailHandler(logging.Handler):
    """
    Logging handler for sending email

    Send an email with some logging information

    """

    def __init__(self, *args, **kwargs):
        maxlogs = kwargs.pop('maxLogs', 50)
        subject = kwargs.pop('subject', None)
        super().__init__(*args, **kwargs)
        self._max = maxlogs
        self._subject = subject
        self._logs = []
        self._send_level = logging.CRITICAL
        self._is_valid = True
        self.set_name(EMAILNAME)

        info = CONFIG.get('email', None)
        if info is None:
            self._is_valid = False
            return

        send_from = info.get('send_from', None)
        if send_from is None:
            self._is_valid = False
            return

        send_to = self.parse_send_to(info.get('send_to', None))
        if not send_to:
            self._is_valid = False

    def __bool__(self):
        return self._is_valid

    def emit(self, record):
        """Overload emit to send email"""

        with self.lock:
            if len(self._logs) > self._max:
                self._logs.pop(0)
            self._logs.append(self.format(record))
        if record.levelno >= self._send_level:
            self.send()

    def set_send_level(self, level):
        """
        Set the level at which logs are automatically
        emailed. For example, if the SendLevel is set
        to logging.WARNING, if a log with level WARNING
        or higher is encountered, an email will be sent.
        Note that if this level is set lower than the
        logger level, the email my be empty.

        Arguments:
          level (int): The logging level

        Keyword arguments:
          None

        Returns:
          None

        """

        if isinstance(level, int):
            self._send_level = level

    def parse_send_to(self, send_to):
        """
        Parse list of send-to emails

        Parse the list of send-to emails from the config yaml file

        Arguments:
            send_to (list,tuple,str) : Emails address to send logs to

        Returns:
            str,None : String of comma separated emails if list could be
                parsed, None otherwise

        """

        if isinstance(send_to, (list, tuple,)):
            return ','.join([s for s in send_to if s is not None])
        if isinstance(send_to, str):
            return send_to
        return None

    def send(self, subject=None):
        """
        Actually send the email


        Keyword arguments:
            subject (str) : Custom subject line for the email

        Returns:
            bool : True on send attempted, False on failure

        """

        if not self:
            return False
        with self.lock:
            body = '\n'.join(self._logs)
            self._logs = []
        if body == '':
            return False

        email = CONFIG['email']
        send_from = email['send_from']
        send_to = self.parse_send_to(email['send_to'])
        msg = EmailMessage()
        if subject:
            msg['Subject'] = subject
        elif self._subject:
            msg['Subject'] = self._subject

        msg['From'] = send_from['user']
        msg['To'] = send_to
        msg.set_content(body)

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


class RotatingFile(Thread):
    """
    A class that acts like the logging.handlers.RotatingFileHander;
    writing data out to a file until file grows too large, then rolling
    over.

    This class is intended to be used for stdout and stderr for calls to
    subprocess module routines, such as the Popen constructor. However, there
    are many other applications for this class.

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.rw = None  # Initialize read/write pipe as None
        self.callback = kwargs.pop('callback', None)
        for key, val in ROTATING_FORMAT.items():
            if key not in kwargs:
                kwargs[key] = val

        formatter = kwargs.pop('formatter', None)
        self.log = RotatingFileHandler(*args, **kwargs)
        if isinstance(formatter, logging.Formatter):
            self.log.setFormatter(formatter)
        else:
            self.log.setFormatter(
                logging.Formatter('%(asctime)s - %(message)s')
            )

    def __enter__(self, *args, **kwargs):
        self.start()

    def __exit__(self, *args, **kwargs):
        self.close()

    def setFormatter(self, *args):
        """Set the formatter for the log handler"""

        self.log.setFormatter(*args)

    def start(self):
        """Overload thread start method"""

        self.rw = os.pipe()  # Open a pipe
        super().start()  # Call supercalls start method

    def run(self):
        """
        Overloads the run method; this method will run in own thread.

        Reads data from pipe and passes to self.log.emit

        Arguments:
          None

        Keyword arguments:
          None

        Returns:
          None

        """

        # Open the read-end of pipe
        with os.fdopen(self.rw[0]) as fid:
            # Iterate over all lines
            for line in iter(fid.readline, ''):
                record = logging.LogRecord(
                    '', 20, '', '', line.rstrip(), '', '',
                )
                self.log.emit(record)  # Pass line to rotating logger
                if self.callback:  # If call back is set
                    self.callback(line)  # Pass line to call back
        self.close()

    def close(self):
        """Method to clean up the pipe and logging file"""

        # If read/write pip IS set
        if self.rw:
            os.close(self.rw[1])  # Close the write-end of pipe
            self.rw = None  # Set rw to None
        self.log.close()  # Close the log

    def fileno(self):
        """Method to get underlying file pointer; in this case pipe"""

        # If read/write pipe NOT set
        if not self.rw:
            self.start()  # Start thread
        return self.rw[1]  # Return write-end of pipe


def init_log_file(format_dict: dict) -> None:
    """
    Initialize new handlers given options

    Given a dictionary of options for a handler, attempted to define
    a new handler for the package logger

    Argumenst:
        format_dict (dict) : Information for setting up a new handler for
            the package logger

    Returns:

    """

    # Iterate over all handlers attached to package logger
    for handler in log.handlers:
        # If a handler is already defined that matches name of that requested
        if handler.get_name() == format_dict['name']:
            return

    log_dir = os.path.dirname(format_dict['file'])
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    rfh = RotatingFileHandler(format_dict['file'], **ROTATING_FORMAT)
    rfh.setFormatter(format_dict['formatter'])
    rfh.setLevel(format_dict['level'])
    rfh.set_name(format_dict['name'])
    log.addHandler(rfh)

    info = os.stat(format_dict['file'])
    # If file permissions match those requested, return
    if (
        info.st_mode & format_dict['permissions']
    ) == format_dict['permissions']:
        return

    # Attempt to set logging file permissions
    try:
        os.chmod(format_dict['file'], format_dict['permissions'])
    except:
        log.info('Failed to change log permissions; this may cause issues')
