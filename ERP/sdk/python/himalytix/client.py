"""
Main synchronous client for Himalytix ERP API
"""

import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .resources import (
    JournalEntryResource,
    UserResource,
    TenantResource,
)
from .exceptions import (
    HimalytixAPIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)


class HimalytixClient:
    """
    Main client for interacting with the Himalytix ERP API.
    
    Args:
        base_url: Base URL of the API (e.g., "https://api.himalytix.com")
        api_key: API key for authentication (optional)
        username: Username for JWT authentication (optional)
        password: Password for JWT authentication (optional)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
        verify_ssl: Whether to verify SSL certificates (default: True)
        user_agent: Custom user agent string (optional)
    
    Example:
        >>> client = HimalytixClient(
        ...     base_url="https://api.himalytix.com",
        ...     api_key="your-api-key"
        ... )
        >>> entries = client.journal_entries.list()
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: bool = True,
        user_agent: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.user_agent = user_agent or f"himalytix-python-sdk/1.0.0"
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        # JWT tokens
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # Initialize with JWT if credentials provided
        if username and password:
            self._authenticate_jwt(username, password)
        
        # Initialize resource endpoints
        self.journal_entries = JournalEntryResource(self)
        self.users = UserResource(self)
        self.tenants = TenantResource(self)
    
    def _authenticate_jwt(self, username: str, password: str) -> None:
        """Authenticate using JWT and store tokens."""
        response = self.session.post(
            f"{self.base_url}/api/token/",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid username or password")
        
        response.raise_for_status()
        data = response.json()
        
        self._access_token = data.get("access")
        self._refresh_token = data.get("refresh")
        # Assume token expires in 1 hour (adjust based on your settings)
        self._token_expires_at = datetime.now() + timedelta(hours=1)
    
    def _refresh_jwt_token(self) -> None:
        """Refresh JWT access token using refresh token."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available")
        
        response = self.session.post(
            f"{self.base_url}/api/token/refresh/",
            json={"refresh": self._refresh_token},
            timeout=self.timeout,
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Refresh token expired. Please re-authenticate.")
        
        response.raise_for_status()
        data = response.json()
        
        self._access_token = data.get("access")
        self._token_expires_at = datetime.now() + timedelta(hours=1)
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
        }
        
        # Check if JWT token needs refresh
        if self._access_token and self._token_expires_at:
            if datetime.now() >= self._token_expires_at - timedelta(minutes=5):
                self._refresh_jwt_token()
        
        # Add authentication header
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        elif self.api_key:
            headers["Authorization"] = f"Api-Key {self.api_key}"
        
        return headers
    
    def _handle_response(self, response: requests.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        # Rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=retry_after,
            )
        
        # Authentication errors
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed")
        
        # Not found
        if response.status_code == 404:
            raise NotFoundError("Resource not found")
        
        # Validation errors
        if response.status_code == 400:
            try:
                errors = response.json()
            except ValueError:
                errors = {"detail": response.text}
            raise ValidationError("Validation failed", errors=errors)
        
        # Server errors
        if response.status_code >= 500:
            raise ServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
            )
        
        # Other client errors
        if response.status_code >= 400:
            try:
                error_detail = response.json().get("detail", response.text)
            except ValueError:
                error_detail = response.text
            raise HimalytixAPIError(
                f"API error: {error_detail}",
                status_code=response.status_code,
            )
        
        # Success - return JSON or None
        if response.status_code == 204:
            return None
        
        try:
            return response.json()
        except ValueError:
            return response.text
    
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/api/v1/journal-entries/")
            params: Query parameters
            json: JSON request body
            **kwargs: Additional arguments to pass to requests
        
        Returns:
            Response data (dict, list, or None)
        
        Raises:
            HimalytixAPIError: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                    **kwargs
                )
                return self._handle_response(response)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    raise HimalytixAPIError(f"Connection failed after {self.max_retries} attempts: {e}")
                continue
        
        if last_exception:
            raise HimalytixAPIError(f"Request failed: {last_exception}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a GET request."""
        return self.request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make a POST request."""
        return self.request("POST", endpoint, json=json)
    
    def put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make a PUT request."""
        return self.request("PUT", endpoint, json=json)
    
    def patch(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make a PATCH request."""
        return self.request("PATCH", endpoint, json=json)
    
    def delete(self, endpoint: str) -> Any:
        """Make a DELETE request."""
        return self.request("DELETE", endpoint)
    
    def set_tenant(self, tenant_id: int) -> None:
        """
        Set the current tenant context for subsequent requests.
        
        Args:
            tenant_id: ID of the tenant to switch to
        """
        # This would typically set a header or make an API call
        # to switch tenant context in a multi-tenant system
        self.session.headers["X-Tenant-ID"] = str(tenant_id)
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
