"""
Example usage of the Himalytix ERP Python SDK
"""

from himalytix import HimalytixClient
from himalytix.exceptions import NotFoundError, ValidationError

# =============================================================================
# INITIALIZATION
# =============================================================================

# Option 1: API Key authentication (recommended for production)
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key-here"
)

# Option 2: JWT authentication
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    username="user@example.com",
    password="your-password"
)

# Option 3: With custom configuration
client = HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key",
    timeout=60,  # Request timeout
    max_retries=5,  # Retry attempts
    verify_ssl=True,  # SSL verification
    user_agent="MyApp/2.0"
)

# =============================================================================
# JOURNAL ENTRIES
# =============================================================================

print("=" * 70)
print("JOURNAL ENTRIES EXAMPLES")
print("=" * 70)

# Create a journal entry
entry = client.journal_entries.create(
    date="2024-10-18",
    amount=1500.00,
    description="Software license payment",
    account_code="5100"
)
print(f"\n✅ Created journal entry #{entry['id']}")
print(f"   Date: {entry['date']}")
print(f"   Amount: ${entry['amount']}")
print(f"   Description: {entry['description']}")

# List journal entries with pagination
print("\n📋 Listing journal entries:")
entries = client.journal_entries.list(
    page=1,
    page_size=10,
    date_from="2024-10-01",
    date_to="2024-10-31"
)

print(f"   Total: {entries.count} entries")
print(f"   Page: 1, Showing: {len(entries.results)} entries")

for entry in entries.results:
    print(f"   - {entry['date']}: {entry['description']} (${entry['amount']})")

# Iterate through all entries (automatic pagination)
print("\n🔄 Iterating through all entries:")
count = 0
for entry in client.journal_entries.all(page_size=50):
    count += 1
    if count <= 5:  # Show first 5
        print(f"   {count}. {entry['date']}: {entry['description']}")

print(f"   ... ({count} total entries)")

# Get a specific entry
try:
    entry = client.journal_entries.get(entry_id=1)
    print(f"\n📄 Retrieved entry #{entry['id']}: {entry['description']}")
except NotFoundError:
    print("\n❌ Entry #1 not found")

# Update an entry
try:
    updated = client.journal_entries.update(
        entry_id=1,
        description="Updated: Software license payment"
    )
    print(f"\n✏️ Updated entry #{updated['id']}")
except NotFoundError:
    print("\n❌ Entry not found for update")

# Export to CSV
try:
    csv_data = client.journal_entries.export(
        format="csv",
        date_from="2024-10-01",
        date_to="2024-10-31"
    )
    
    with open("journal_entries.csv", "wb") as f:
        f.write(csv_data)
    
    print("\n💾 Exported entries to journal_entries.csv")
except Exception as e:
    print(f"\n❌ Export failed: {e}")

# =============================================================================
# USERS
# =============================================================================

print("\n" + "=" * 70)
print("USER EXAMPLES")
print("=" * 70)

# Get current user
me = client.users.me()
print(f"\n👤 Current user: {me['username']} ({me['email']})")

# List users
users = client.users.list(page=1, page_size=10)
print(f"\n👥 Total users: {users.count}")

for user in users.results[:5]:
    print(f"   - {user['username']}: {user.get('first_name', '')} {user.get('last_name', '')}")

# Create a new user
try:
    new_user = client.users.create(
        username="johndoe",
        email="john@example.com",
        password="SecurePass123!",
        first_name="John",
        last_name="Doe"
    )
    print(f"\n✅ Created user: {new_user['username']}")
except ValidationError as e:
    print(f"\n❌ Validation error: {e.errors}")

# Get a specific user
try:
    user = client.users.get(user_id=1)
    print(f"\n📄 User #{user['id']}: {user['username']}")
except NotFoundError:
    print("\n❌ User not found")

# =============================================================================
# TENANTS
# =============================================================================

print("\n" + "=" * 70)
print("TENANT EXAMPLES")
print("=" * 70)

# List tenants
tenants = client.tenants.list()
print(f"\n🏢 Total tenants: {tenants.count}")

for tenant in tenants.results:
    print(f"   - {tenant['name']} (schema: {tenant['schema_name']})")

# Get current tenant
try:
    current = client.tenants.current()
    print(f"\n🏢 Current tenant: {current['name']}")
except Exception as e:
    print(f"\n⚠️ No current tenant: {e}")

# Create a new tenant
try:
    new_tenant = client.tenants.create(
        name="Acme Corporation",
        schema_name="acme_corp"
    )
    print(f"\n✅ Created tenant: {new_tenant['name']}")
except ValidationError as e:
    print(f"\n❌ Validation error: {e.errors}")

# Switch tenant context
try:
    client.set_tenant(tenant_id=1)
    print("\n🔄 Switched to tenant #1")
except Exception as e:
    print(f"\n❌ Failed to switch tenant: {e}")

# =============================================================================
# ERROR HANDLING
# =============================================================================

print("\n" + "=" * 70)
print("ERROR HANDLING EXAMPLES")
print("=" * 70)

from himalytix.exceptions import (
    HimalytixAPIError,
    AuthenticationError,
    RateLimitError,
)

# Handle not found
try:
    entry = client.journal_entries.get(entry_id=999999)
except NotFoundError:
    print("\n❌ Entry not found (expected)")

# Handle validation errors
try:
    entry = client.journal_entries.create(
        date="invalid-date",  # This will fail
        amount="not-a-number",
        description=""
    )
except ValidationError as e:
    print(f"\n❌ Validation errors (expected):")
    for field, errors in e.errors.items():
        print(f"   - {field}: {errors}")

# Handle rate limiting
try:
    # Make many requests quickly
    for i in range(200):
        client.journal_entries.list(page=1)
except RateLimitError as e:
    print(f"\n⏳ Rate limited (expected). Retry after {e.retry_after}s")

# =============================================================================
# CONTEXT MANAGER
# =============================================================================

print("\n" + "=" * 70)
print("CONTEXT MANAGER EXAMPLE")
print("=" * 70)

# Use context manager for automatic cleanup
with HimalytixClient(
    base_url="https://api.himalytix.com",
    api_key="your-api-key"
) as client:
    entries = client.journal_entries.list(page=1, page_size=5)
    print(f"\n✅ Retrieved {len(entries.results)} entries")
    # Session automatically closed when exiting context

print("\n✅ Session closed automatically")

# =============================================================================
# BATCH OPERATIONS
# =============================================================================

print("\n" + "=" * 70)
print("BATCH OPERATIONS EXAMPLE")
print("=" * 70)

# Create multiple entries
entries_to_create = [
    {"date": "2024-10-18", "amount": 100.00, "description": "Entry 1"},
    {"date": "2024-10-18", "amount": 200.00, "description": "Entry 2"},
    {"date": "2024-10-18", "amount": 300.00, "description": "Entry 3"},
]

created = []
for data in entries_to_create:
    try:
        entry = client.journal_entries.create(**data)
        created.append(entry)
        print(f"✅ Created: {entry['description']}")
    except Exception as e:
        print(f"❌ Failed: {data['description']} - {e}")

print(f"\n✅ Created {len(created)} entries")

# =============================================================================
# DONE
# =============================================================================

print("\n" + "=" * 70)
print("✅ ALL EXAMPLES COMPLETED")
print("=" * 70)
print("\nFor more information, visit:")
print("  - Documentation: https://docs.himalytix.com")
print("  - API Reference: https://api.himalytix.com/docs/")
print("  - GitHub: https://github.com/himalytix/python-sdk")
print()
