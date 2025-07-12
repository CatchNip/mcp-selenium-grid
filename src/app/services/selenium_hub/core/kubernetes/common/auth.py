"""
Authentication utilities for Selenium Hub Kubernetes deployments.

This module provides helper functions for handling authentication in Kubernetes
environments, particularly for health checks and probes that require Basic
authentication headers.
"""

import base64
from typing import Any


def get_encoded_auth(settings: Any) -> str:
    """
    Get base64 encoded credentials for Basic authentication.

    This function creates the base64-encoded credentials string needed for
    Basic authentication headers in HTTP requests to Selenium Hub.

    Args:
        settings: The settings object containing Selenium Hub credentials

    Returns:
        str: Base64 encoded credentials in the format 'username:password'

    Example:
        >>> auth = get_encoded_auth(settings)
        >>> header = f"Basic {auth}"
        >>> # Use in HTTP headers: {'Authorization': header}
    """
    username = settings.selenium_hub.SELENIUM_HUB_USER.get_secret_value()
    password = settings.selenium_hub.SELENIUM_HUB_PASSWORD.get_secret_value()
    credentials = f"{username}:{password}"
    return base64.b64encode(credentials.encode()).decode()
