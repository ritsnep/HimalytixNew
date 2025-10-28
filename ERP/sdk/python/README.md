# Himalytix ERP Python SDK

Official Python SDK for the Himalytix ERP API.

## Installation

```bash
pip install himalytix-erp-client
```

## Quick Start

```python
from himalytix import HimalytixClient

# Initialize client
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key-here"
)

# Or use JWT authentication
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    username="user@example.com",
    password="your-password"
)

# Create a journal entry
entry = client.journal_entries.create(
    date="2024-10-18",
    amount=1000.00,
    description="Payment received",
    account_code="1000"
)
print(f"Created entry: {entry.id}")

# List journal entries with pagination
entries = client.journal_entries.list(
    page=1,
    page_size=50,
    date_from="2024-10-01",
    date_to="2024-10-31"
)

for entry in entries.results:
    print(f"{entry.date}: {entry.description} - ${entry.amount}")

# Get a specific journal entry
entry = client.journal_entries.get(entry_id=123)
print(entry.to_dict())

# Update a journal entry
updated = client.journal_entries.update(
    entry_id=123,
    description="Updated payment description"
)

# Delete a journal entry
client.journal_entries.delete(entry_id=123)
```

## Authentication

### API Key Authentication (Recommended)

```python
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key-here"
)
```

### JWT Authentication

```python
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    username="user@example.com",
    password="your-password"
)

# Token is automatically refreshed when expired
```

## Resources

### Journal Entries

```python
# Create
entry = client.journal_entries.create(
    date="2024-10-18",
    amount=1000.00,
    description="Payment",
    account_code="1000"
)

# List with filters
entries = client.journal_entries.list(
    page=1,
    page_size=50,
    date_from="2024-10-01",
    date_to="2024-10-31",
    account_code="1000"
)

# Get
entry = client.journal_entries.get(entry_id=123)

# Update
entry = client.journal_entries.update(
    entry_id=123,
    description="Updated"
)

# Delete
client.journal_entries.delete(entry_id=123)
```

### Users

```python
# List users
users = client.users.list(page=1, page_size=50)

# Get current user
me = client.users.me()

# Get specific user
user = client.users.get(user_id=456)

# Create user
user = client.users.create(
    username="newuser",
    email="newuser@example.com",
    password="securepass123"
)

# Update user
user = client.users.update(
    user_id=456,
    email="updated@example.com"
)
```

### Tenants

```python
# List tenants
tenants = client.tenants.list()

# Get current tenant
tenant = client.tenants.current()

# Create tenant
tenant = client.tenants.create(
    name="New Company",
    schema_name="new_company"
)

# Switch tenant context
client.set_tenant(tenant_id=789)
```

## Error Handling

```python
from himalytix.exceptions import (
    HimalytixAPIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError
)

try:
    entry = client.journal_entries.get(entry_id=999999)
except NotFoundError:
    print("Entry not found")
except AuthenticationError:
    print("Invalid credentials")
except ValidationError as e:
    print(f"Validation failed: {e.errors}")
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after {e.retry_after} seconds")
except HimalytixAPIError as e:
    print(f"API error: {e.message}")
```

## Pagination

```python
# Manual pagination
page = 1
while True:
    entries = client.journal_entries.list(page=page, page_size=100)
    
    for entry in entries.results:
        process_entry(entry)
    
    if not entries.has_next:
        break
    page += 1

# Automatic pagination (iterator)
for entry in client.journal_entries.all(page_size=100):
    process_entry(entry)
```

## Async Support

```python
import asyncio
from himalytix import AsyncHimalytixClient

async def main():
    async with AsyncHimalytixClient(
        base_url="https://api.himalytix.com",
        api_key="your-api-key"
    ) as client:
        # Create entry
        entry = await client.journal_entries.create(
            date="2024-10-18",
            amount=1000.00,
            description="Async payment"
        )
        
        # List entries
        entries = await client.journal_entries.list(page=1)
        
        # Batch operations
        tasks = [
            client.journal_entries.get(entry_id=i)
            for i in range(1, 11)
        ]
        results = await asyncio.gather(*tasks)

asyncio.run(main())
```

## Configuration

```python
from himalytix import HimalytixClient

client = HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key",
    timeout=30,  # Request timeout in seconds
    max_retries=3,  # Retry failed requests
    verify_ssl=True,  # SSL verification
    user_agent="MyApp/1.0"
)
```

## Development

```bash
# Clone repository
git clone https://github.com/himalytix/python-sdk.git
cd python-sdk

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=himalytix --cov-report=html

# Lint
flake8 himalytix/
black --check himalytix/
mypy himalytix/

# Format
black himalytix/
isort himalytix/
```

## Requirements

- Python 3.8+
- requests >= 2.28.0
- httpx >= 0.24.0 (for async support)
- pydantic >= 2.0.0

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: https://docs.himalytix.com
- API Reference: https://api.himalytix.com/docs/
- Issues: https://github.com/himalytix/python-sdk/issues
- Email: support@himalytix.com
