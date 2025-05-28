from os import getenv


def getenv_as_bool(key: str) -> bool:
    """Get environment variable as boolean."""
    env_val = getenv(key, "False").lower()
    return env_val == "true"
