"""
Base API class for TVDb and TMDb

"""

from datetime import datetime

DATEFMT = '%Y-%m-%d'


def convert_date(info: dict) -> dict:
    """
    Function to convert any date information into a datetime object

    Arguments:
        info (dict)  : JSON response data from TMDb or TVDb API

    Keyword arguments:
        None

    Returns:
        dict: Updated info dictionary where date strings have been
            converted to datetime objects

    """

    # If info is a list or tuple return recursive call to convert_date
    # on each element
    if isinstance(info, (list, tuple)):
        return [convert_date(i) for i in info]

    if isinstance(info, dict):
        for key, val in info.items():
            # If value is list,tuple,dict
            if isinstance(val, (list, tuple, dict)):
                # Set value of info[key] to result of recursive call
                info[key] = convert_date(val)
            # Else, if 'date' or 'Aired' in key
            elif ('date' in key) or ('Aired' in key):
                try:
                    info[key] = datetime.strptime(val, DATEFMT)
                except:
                    info[key] = None
    return info
