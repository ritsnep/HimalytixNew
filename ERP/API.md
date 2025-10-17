# REST API Usage

This project exposes basic API endpoints under `/api/v1/` using Django REST Framework and JWT authentication.

## Authentication

1. Obtain a token pair using your username and password:

```bash
POST /api/v1/token/
{
  "username": "<your username>",
  "password": "<your password>"
}
```

The response will contain an `access` and `refresh` token. Include the access token in the `Authorization` header when performing authenticated requests:

```
Authorization: Bearer <access token>
```

2. Refresh an access token:

```bash
POST /api/v1/token/refresh/
{
  "refresh": "<refresh token>"
}
```

## Endpoints

- `GET /api/v1/fiscalyears/` – list fiscal years
- `POST /api/v1/fiscalyears/` – create a fiscal year
- `GET /api/v1/fiscalyears/<id>/` – retrieve a fiscal year
- `PUT /api/v1/fiscalyears/<id>/` – update a fiscal year
- `DELETE /api/v1/fiscalyears/<id>/` – delete a fiscal year

All endpoints require authentication unless otherwise noted.