# API Migration Guide: v0 → v1

## Overview
This guide helps developers migrate from legacy API endpoints to the new versioned v1 API.

## Breaking Changes

### 1. URL Structure
**Before (Legacy):**
```
/api/resource/
```

**After (v1):**
```
/api/v1/resource/
```

### 2. Authentication
No changes - still supports:
- Session Authentication (cookies)
- Token Authentication (Bearer tokens)

### 3. Response Format
**Before:**
```json
{
  "data": [...],
  "count": 10
}
```

**After:**
```json
{
  "count": 10,
  "next": "http://api.example.com/api/v1/resource/?page=2",
  "previous": null,
  "results": [...]
}
```

### 4. Error Responses
**Before:**
```json
{
  "error": "Invalid request"
}
```

**After:**
```json
{
  "detail": "Invalid request",
  "code": "invalid_request",
  "field_errors": {
    "email": ["This field is required"]
  }
}
```

## Headers

### API Version Header
All v1 responses include:
```
API-Version: v1
```

### Deprecation Notice
Deprecated endpoints include:
```
Deprecation: true
Sunset: 2025-12-31
Link: </api/v1/>; rel="successor-version"
```

## Endpoint Mapping

| Legacy Endpoint | v1 Endpoint | Notes |
|----------------|-------------|-------|
| `/api/accounts/` | `/api/v1/accounts/` | Pagination added |
| `/api/invoices/` | `/api/v1/invoices/` | - |
| `/api/journals/` | `/api/v1/journals/` | Response format changed |

## Code Examples

### Python (requests)
**Before:**
```python
import requests

response = requests.get('https://api.example.com/api/accounts/')
data = response.json()['data']
```

**After:**
```python
import requests

response = requests.get('https://api.example.com/api/v1/accounts/')
data = response.json()['results']
```

### JavaScript (fetch)
**Before:**
```javascript
fetch('/api/accounts/')
  .then(res => res.json())
  .then(data => console.log(data.data));
```

**After:**
```javascript
fetch('/api/v1/accounts/')
  .then(res => res.json())
  .then(data => console.log(data.results));
```

## Testing
Run migration tests:
```bash
python manage.py test api.tests.test_migration
```

## Support
- **Documentation:** https://docs.himalytix.com/api/v1/
- **Changelog:** https://docs.himalytix.com/api/changelog/
- **Support:** api-support@himalytix.com

## Timeline
- **v0 Deprecation:** 2025-10-01
- **v0 Sunset:** 2025-12-31
- **v1 Stable:** 2025-09-01
