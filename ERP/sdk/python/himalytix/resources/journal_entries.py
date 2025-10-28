"""
Journal Entry resource
"""

from typing import Optional, Dict, Any
from datetime import date

from .base import BaseResource


class JournalEntryResource(BaseResource):
    """
    Journal Entry API resource.
    
    Example:
        >>> entries = client.journal_entries.list(
        ...     date_from="2024-10-01",
        ...     date_to="2024-10-31"
        ... )
        >>> entry = client.journal_entries.create(
        ...     date="2024-10-18",
        ...     amount=1000.00,
        ...     description="Payment received"
        ... )
    """
    
    resource_name = "journal_entry"
    endpoint_base = "/api/v1/journal-entries/"
    
    def list(
        self,
        page: int = 1,
        page_size: int = 50,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        account_code: Optional[str] = None,
        **filters
    ):
        """
        List journal entries with optional filters.
        
        Args:
            page: Page number
            page_size: Items per page
            date_from: Filter entries from this date (YYYY-MM-DD)
            date_to: Filter entries to this date (YYYY-MM-DD)
            account_code: Filter by account code
            **filters: Additional filter parameters
        """
        params = {}
        
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if account_code:
            params["account_code"] = account_code
        
        params.update(filters)
        
        return super().list(page=page, page_size=page_size, **params)
    
    def create(
        self,
        date: str,
        amount: float,
        description: str,
        account_code: Optional[str] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """
        Create a new journal entry.
        
        Args:
            date: Entry date (YYYY-MM-DD)
            amount: Transaction amount
            description: Entry description
            account_code: Account code (optional)
            **additional_fields: Additional entry fields
        
        Returns:
            Created journal entry data
        """
        data = {
            "date": date,
            "amount": amount,
            "description": description,
        }
        
        if account_code:
            data["account_code"] = account_code
        
        data.update(additional_fields)
        
        return super().create(**data)
    
    def export(
        self,
        format: str = "csv",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> bytes:
        """
        Export journal entries to CSV or Excel.
        
        Args:
            format: Export format ("csv" or "xlsx")
            date_from: Filter from date
            date_to: Filter to date
        
        Returns:
            File content as bytes
        """
        params = {"format": format}
        
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        
        endpoint = self._build_endpoint("export")
        
        # Special handling for file downloads
        response = self.client.session.get(
            f"{self.client.base_url}{endpoint}",
            params=params,
            headers=self.client._get_headers(),
        )
        response.raise_for_status()
        
        return response.content
