"""
Custom exceptions for the Himalytix SDK
"""

from typing import Optional, Dict, Any


class HimalytixAPIError(Exception):
    """Base exception for all Himalytix API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class AuthenticationError(HimalytixAPIError):
    """Raised when authentication fails (401)."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class NotFoundError(HimalytixAPIError):
    """Raised when a resource is not found (404)."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(HimalytixAPIError):
    """Raised when request validation fails (400)."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code=400, response=errors)
        self.errors = errors or {}


class RateLimitError(HimalytixAPIError):
    """Raised when rate limit is exceeded (429)."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ServerError(HimalytixAPIError):
    """Raised when a server error occurs (5xx)."""
    
    def __init__(self, message: str = "Server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)


class ConfigurationError(HimalytixAPIError):
    """Raised when the SDK is misconfigured."""
    
    def __init__(self, message: str = "SDK configuration error"):
        super().__init__(message)
