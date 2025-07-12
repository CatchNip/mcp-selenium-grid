"""Constants for Kubernetes operations."""

from http import HTTPStatus

# HTTP Status Codes (using Python standard library)
HTTP_NOT_FOUND = HTTPStatus.NOT_FOUND  # 404
HTTP_CONFLICT = HTTPStatus.CONFLICT  # 409

# Default timeouts and retry settings
DEFAULT_TIMEOUT = 30
DEFAULT_POLL_INTERVAL = 2
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 2
