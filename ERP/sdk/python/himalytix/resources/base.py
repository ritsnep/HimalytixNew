"""
Base resource class for all API resources
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List, Iterator
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..client import HimalytixClient


class PaginatedResponse(BaseModel):
    """Represents a paginated API response."""
    
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[Dict[str, Any]]
    
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.next is not None
    
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.previous is not None


class BaseResource:
    """
    Base class for all API resources.
    
    Provides common CRUD operations and utilities.
    """
    
    # Subclasses should override these
    resource_name: str = ""
    endpoint_base: str = ""
    
    def __init__(self, client: "HimalytixClient"):
        self.client = client
    
    def _build_endpoint(self, *parts: str) -> str:
        """Build an API endpoint URL."""
        endpoint = self.endpoint_base
        for part in parts:
            if part:
                endpoint = f"{endpoint.rstrip('/')}/{str(part).lstrip('/')}"
        return endpoint
    
    def list(
        self,
        page: int = 1,
        page_size: int = 50,
        **filters
    ) -> PaginatedResponse:
        """
        List resources with pagination.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            **filters: Additional filter parameters
        
        Returns:
            PaginatedResponse with results
        """
        params = {
            "page": page,
            "page_size": page_size,
            **filters,
        }
        
        data = self.client.get(self.endpoint_base, params=params)
        return PaginatedResponse(**data)
    
    def all(self, page_size: int = 100, **filters) -> Iterator[Dict[str, Any]]:
        """
        Iterate over all resources, automatically handling pagination.
        
        Args:
            page_size: Number of items per page
            **filters: Additional filter parameters
        
        Yields:
            Individual resource dictionaries
        """
        page = 1
        while True:
            response = self.list(page=page, page_size=page_size, **filters)
            
            for item in response.results:
                yield item
            
            if not response.has_next:
                break
            
            page += 1
    
    def get(self, resource_id: int) -> Dict[str, Any]:
        """
        Get a single resource by ID.
        
        Args:
            resource_id: Resource ID
        
        Returns:
            Resource data as dictionary
        """
        endpoint = self._build_endpoint(str(resource_id))
        return self.client.get(endpoint)
    
    def create(self, **data) -> Dict[str, Any]:
        """
        Create a new resource.
        
        Args:
            **data: Resource data
        
        Returns:
            Created resource data
        """
        return self.client.post(self.endpoint_base, json=data)
    
    def update(self, resource_id: int, **data) -> Dict[str, Any]:
        """
        Update a resource (PATCH).
        
        Args:
            resource_id: Resource ID
            **data: Fields to update
        
        Returns:
            Updated resource data
        """
        endpoint = self._build_endpoint(str(resource_id))
        return self.client.patch(endpoint, json=data)
    
    def replace(self, resource_id: int, **data) -> Dict[str, Any]:
        """
        Replace a resource (PUT).
        
        Args:
            resource_id: Resource ID
            **data: Complete resource data
        
        Returns:
            Replaced resource data
        """
        endpoint = self._build_endpoint(str(resource_id))
        return self.client.put(endpoint, json=data)
    
    def delete(self, resource_id: int) -> None:
        """
        Delete a resource.
        
        Args:
            resource_id: Resource ID
        """
        endpoint = self._build_endpoint(str(resource_id))
        self.client.delete(endpoint)
