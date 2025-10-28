"""
Himalytix ERP Python SDK

Official Python client library for the Himalytix ERP API.

Basic usage:
    >>> from himalytix import HimalytixClient
    >>> client = HimalytixClient(
    ...     base_url="https://api.himalytix.com",
    ...     api_key="your-api-key"
    ... )
    >>> entries = client.journal_entries.list()
"""

__version__ = "1.0.0"
__author__ = "Himalytix Development Team"
__email__ = "dev@himalytix.com"
__license__ = "MIT"

from .client import HimalytixClient
from .async_client import AsyncHimalytixClient
from .exceptions import (
    HimalytixAPIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

__all__ = [
    "HimalytixClient",
    "AsyncHimalytixClient",
    "HimalytixAPIError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "__version__",
]
