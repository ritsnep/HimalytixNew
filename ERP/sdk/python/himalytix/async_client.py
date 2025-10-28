"""
Async client for Himalytix ERP API (stub for future implementation)
"""

from typing import Optional


class AsyncHimalytixClient:
    """
    Async client for Himalytix ERP API.
    
    TODO: Implement async support using httpx.
    
    Example:
        >>> async with AsyncHimalytixClient(
        ...     base_url="https://api.himalytix.com",
        ...     api_key="your-api-key"
        ... ) as client:
        ...     entries = await client.journal_entries.list()
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        **kwargs
    ):
        raise NotImplementedError(
            "Async support is not yet implemented. "
            "Install with: pip install himalytix-erp-client[async]"
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
