# ADR-0001: Multi-Tenancy Architecture

**Status:** Accepted  
**Date:** 2024-Q3  
**Decision Makers:** Architecture Team  
**Technical Story:** Phase 1-2 Implementation

---

## Context and Problem Statement

Himalytix ERP targets the Nepal market where multiple organizations (businesses, NGOs, cooperatives) require isolated accounting systems. How should we architect the system to support multiple tenants while ensuring data isolation, performance, and maintainability?

## Decision Drivers

* **Data Isolation**: Complete separation of tenant data to prevent data leaks
* **Performance**: Query performance should not degrade with tenant count
* **Scalability**: Support for 100+ tenants without architectural changes
* **Compliance**: Nepal regulatory requirements for data privacy
* **Development Velocity**: Minimize complexity for developers
* **Cost**: Infrastructure costs should scale linearly with usage

## Considered Options

1. **Separate Databases** (Database-per-tenant)
2. **Shared Database with Row-Level Security** (Schema-per-tenant)
3. **Shared Database with Tenant Column** (Discriminator column)

## Decision Outcome

**Chosen option:** "Shared Database with Row-Level Security (Schema-per-tenant)", because:
- Provides strong data isolation without database proliferation
- PostgreSQL schema support is mature and performant
- Simplifies backup/restore and migrations
- Reduces infrastructure overhead vs. database-per-tenant
- Better performance than discriminator column approach

### Implementation Details

- **Middleware**: `tenancy.middleware.ActiveTenantMiddleware` sets tenant context per request
- **Models**: Base models inherit tenant foreign key
- **Queries**: All queries automatically filtered by active tenant
- **Migrations**: Applied across all tenant schemas
- **Admin**: Super-admin can switch tenant context

### Positive Consequences

* Strong data isolation (schema-level separation)
* Simplified infrastructure (single PostgreSQL instance)
* Developer-friendly (transparent tenant filtering)
* Scalable to 100+ tenants without re-architecture
* Easier disaster recovery (single database backup)

### Negative Consequences

* Schema migrations require iteration over all tenants
* PostgreSQL-specific (not database-agnostic)
* Tenant switching requires superadmin privileges
* Schema count limits (PostgreSQL handles 1000s well)

## Pros and Cons of the Options

### Separate Databases (Database-per-tenant)

* **Good**, absolute data isolation
* **Good**, independent scaling per tenant
* **Bad**, high infrastructure costs (connection pooling, backups)
* **Bad**, migration complexity (N databases)
* **Bad**, cross-tenant reporting nearly impossible

### Shared Database with Row-Level Security (Schema-per-tenant)

* **Good**, strong isolation via PostgreSQL schemas
* **Good**, moderate infrastructure costs
* **Good**, manageable migrations
* **Good**, cross-tenant analytics possible
* **Neutral**, PostgreSQL-specific
* **Bad**, schema-level operations require iteration

### Shared Database with Tenant Column (Discriminator)

* **Good**, database-agnostic
* **Good**, simple implementation
* **Good**, trivial migrations
* **Bad**, weak isolation (application-enforced)
* **Bad**, risk of tenant data leaks via query bugs
* **Bad**, performance degrades with data volume (index bloat)

## Links

* Implemented in: `tenancy/middleware.py`, `tenancy/models.py`
* Related: [architecture_overview.md](../../architecture_overview.md)
* PostgreSQL Schemas: https://www.postgresql.org/docs/current/ddl-schemas.html

---

## Compliance and Review

* **Reviewed by:** Principal Engineer, Security Lead
* **Review date:** 2024-Q3
* **Next review:** 2025-Q4 (annual)
