"""
Utility to check if CLI is installed

"""

import sys
from subprocess import check_output, STDOUT


def check_cli(cli):
    """
    Check if CLI is installed

    Determine if given command line interface (CLI)
    program is installed on the machine.

    Arguments:
        cli (str) : Name of CLI to check is installed.

    Returns:
        str : Path to the CLI executable

    """

    if sys.platform == 'win32':
        cmd = ['where', cli]
    else:
        cmd = ['which', cli]

    try:
        path = check_output(cmd, stderr=STDOUT)
    except:
        path = None

    if path is None:
        raise Exception(
          "The following required command line utility was NOT found." +
          " If it is installed, be sure it is in your PATH: " +
          cli
        )

    return path.decode().rstrip()
