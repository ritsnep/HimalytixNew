"""
User resource
"""

from typing import Dict, Any

from .base import BaseResource


class UserResource(BaseResource):
    """
    User API resource.
    
    Example:
        >>> users = client.users.list()
        >>> me = client.users.me()
        >>> user = client.users.get(user_id=123)
    """
    
    resource_name = "user"
    endpoint_base = "/api/v1/users/"
    
    def me(self) -> Dict[str, Any]:
        """
        Get the current authenticated user.
        
        Returns:
            Current user data
        """
        endpoint = self._build_endpoint("me")
        return self.client.get(endpoint)
    
    def create(
        self,
        username: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        **additional_fields
    ) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            username: Username
            email: Email address
            password: Password
            first_name: First name (optional)
            last_name: Last name (optional)
            **additional_fields: Additional user fields
        
        Returns:
            Created user data
        """
        data = {
            "username": username,
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        }
        data.update(additional_fields)
        
        return super().create(**data)
