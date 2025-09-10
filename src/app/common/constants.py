from .getenv import getenv

STDIO_ENV_NAME = "IS_STDIO_ENABLED"

IS_STDIO_ENABLED: bool = getenv(STDIO_ENV_NAME).as_bool()
