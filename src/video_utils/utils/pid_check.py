"""
Check for already running process

Utilities for checking if a process with the same name/pid is currently
running so that multiple instances of code are not running at the same
time, namely the file watchdogs

"""

import logging
import os
import json
import psutil


def pid_store(fpath):
    """
    Store information about the current process in a JSON formatted file

    Arguments:
        fpath (str): Full path of file to write data to

    Keyword arguments:
        None

    Returns:
        bool: True if file created, False otherwise

    """

    log = logging.getLogger(__name__)
    fdir = os.path.dirname(fpath)
    try:
        os.makedirs(fdir, exist_ok=True)
    except PermissionError as err:
        log.error('Do not have correct permissions: %s', err)
        return False
    except Exception as err:
        log.error('Something went wrong: %s', err)
        return False

    # Get current process id
    pid = os.getpid()
    # Iterate over all processes
    for proc in psutil.process_iter():
        if proc.pid == pid:
            data = {
                'pid': pid,
                'name': proc.name(),
                'time': proc.create_time(),
            }
            with open(fpath, mode='w', encoding='utf8') as fid:
                json.dump(data, fid)
            return True
    log.error('Failed to find process matching current PID')
    return False


def pid_running(fpath):
    """
    Check if process is already running

    Check if current process is already running based on data in
    JSON formatted file created by pid_store()

    Arguments:
        fpath (str): Full path of file to check pid information against

    Keyword arguments:
        None

    Returns:
        bool: True if process is already running, False otherwise

    """

    # if the fpath file exists
    if os.path.isfile(fpath):
        # Read in the data
        with open(fpath, mode='r', encoding='utf8') as fid:
            info = json.load(fid)

        # If the pid exists
        if psutil.pid_exists(info['pid']):
            # Iterate over processes
            for proc in psutil.process_iter():
                if proc.pid == info['pid'] and proc.name() == info['name']:
                    # Get  process creation time
                    create_time = proc.create_time()
                    # If the process was created within one (1) second
                    # of reference process
                    if abs(create_time - info['time']) < 1.0:
                        return True

    pid_store(fpath)
    return False
