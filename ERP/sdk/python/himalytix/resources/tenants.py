"""
Tenant resource
"""

from typing import Dict, Any

from .base import BaseResource


class TenantResource(BaseResource):
    """
    Tenant API resource.
    
    Example:
        >>> tenants = client.tenants.list()
        >>> tenant = client.tenants.current()
        >>> client.set_tenant(tenant_id=123)
    """
    
    resource_name = "tenant"
    endpoint_base = "/api/v1/tenants/"
    
    def current(self) -> Dict[str, Any]:
        """
        Get the current tenant context.
        
        Returns:
            Current tenant data
        """
        endpoint = self._build_endpoint("current")
        return self.client.get(endpoint)
    
    def create(
        self,
        name: str,
        schema_name: str,
        **additional_fields
    ) -> Dict[str, Any]:
        """
        Create a new tenant.
        
        Args:
            name: Tenant name
            schema_name: Database schema name
            **additional_fields: Additional tenant fields
        
        Returns:
            Created tenant data
        """
        data = {
            "name": name,
            "schema_name": schema_name,
        }
        data.update(additional_fields)
        
        return super().create(**data)
