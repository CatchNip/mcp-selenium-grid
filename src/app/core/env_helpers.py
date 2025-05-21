from ast import literal_eval
from os import getenv


def getenv_as_bool(key: str):
    """Get environment variable as boolean."""
    return literal_eval(getenv(key, "False").capitalize())
