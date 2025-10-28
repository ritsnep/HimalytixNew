# 🏗️ Himalytix ERP Architecture Documentation

**Version:** 1.0  
**Last Updated:** October 18, 2024

---

## 📋 Table of Contents
1. [System Architecture](#system-architecture)
2. [Data Flow Diagrams](#data-flow-diagrams)
3. [Deployment Architecture](#deployment-architecture)
4. [Multi-Tenancy Architecture](#multi-tenancy-architecture)
5. [API Architecture](#api-architecture)
6. [Security Architecture](#security-architecture)

---

## 🏛️ System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        A[Web Browser] --> B[HTMX/Alpine.js]
        C[Mobile App] --> D[REST API Client]
    end
    
    subgraph "Load Balancer"
        E[Nginx/HAProxy]
    end
    
    subgraph "Application Layer"
        F[Django Web Server<br/>Gunicorn]
        G[Celery Workers]
        H[Celery Beat<br/>Scheduler]
    end
    
    subgraph "Data Layer"
        I[(PostgreSQL<br/>Primary)]
        J[(PostgreSQL<br/>Replica)]
        K[(Redis<br/>Cache/Broker)]
    end
    
    subgraph "Observability"
        L[Prometheus]
        M[Grafana]
        N[Jaeger<br/>Tracing]
    end
    
    subgraph "External Services"
        O[S3/GCS<br/>Backups]
        P[SMTP<br/>Email]
        Q[OAuth<br/>Providers]
    end
    
    B --> E
    D --> E
    E --> F
    F --> G
    F --> H
    F --> I
    F --> J
    F --> K
    G --> I
    G --> K
    H --> I
    H --> K
    
    F --> L
    L --> M
    F --> N
    
    F --> O
    F --> P
    F --> Q
    
    style F fill:#4CAF50
    style I fill:#2196F3
    style K fill:#FF9800
    style L fill:#9C27B0
```

---

## 📊 Data Flow Diagrams

### 1. User Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web Server
    participant R as Redis Cache
    participant DB as PostgreSQL
    participant J as JWT Service
    
    U->>W: POST /accounts/login/
    W->>W: Rate Limit Check
    W->>DB: Verify Credentials
    DB-->>W: User Data
    W->>J: Generate JWT Token
    J-->>W: Access + Refresh Tokens
    W->>R: Cache User Session
    W-->>U: 200 OK + Tokens
    
    Note over U,W: Subsequent Requests
    U->>W: GET /api/v1/users/me/
    W->>W: Validate JWT
    W->>R: Check Cache
    alt Cache Hit
        R-->>W: Cached User Data
    else Cache Miss
        W->>DB: Query User Data
        DB-->>W: User Data
        W->>R: Update Cache
    end
    W-->>U: 200 OK + User Data
```

### 2. Journal Entry Creation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web Server
    participant C as Celery Worker
    participant DB as PostgreSQL
    participant T as Tracing (Jaeger)
    
    U->>W: POST /api/v1/journal-entries/
    W->>T: Start Trace Span
    W->>W: Validate Payload
    W->>DB: Begin Transaction
    DB-->>W: Transaction Started
    W->>DB: Insert Journal Entry
    W->>DB: Update Account Balances
    W->>DB: Create Audit Log
    DB-->>W: Commit Success
    W->>C: Queue Email Notification
    W->>T: End Trace Span
    W-->>U: 201 Created
    
    C->>DB: Fetch Notification Data
    C->>C: Render Email Template
    C->>SMTP: Send Email
    SMTP-->>C: Delivery Confirmation
```

### 3. Multi-Tenant Request Flow

```mermaid
graph LR
    A[Request] --> B{Extract Tenant}
    B --> C[Middleware:<br/>ActiveTenantMiddleware]
    C --> D{Tenant Valid?}
    D -->|Yes| E[Set Schema Context]
    D -->|No| F[403 Forbidden]
    E --> G[Query PostgreSQL<br/>with SET search_path]
    G --> H[Execute View Logic]
    H --> I[Return Response]
    
    style C fill:#4CAF50
    style E fill:#2196F3
    style F fill:#F44336
```

---

## 🚀 Deployment Architecture

### Production Deployment (AWS/GCP)

```mermaid
graph TB
    subgraph "CDN Layer"
        A[CloudFlare CDN]
    end
    
    subgraph "Load Balancer"
        B[AWS ALB/<br/>GCP Load Balancer]
    end
    
    subgraph "Auto-Scaling Group"
        C1[Web Server 1<br/>EC2/Compute]
        C2[Web Server 2<br/>EC2/Compute]
        C3[Web Server 3<br/>EC2/Compute]
    end
    
    subgraph "Background Workers"
        D1[Celery Worker 1]
        D2[Celery Worker 2]
        E[Celery Beat]
    end
    
    subgraph "Managed Services"
        F[(RDS PostgreSQL<br/>Multi-AZ)]
        G[(ElastiCache Redis<br/>Cluster)]
    end
    
    subgraph "Storage"
        H[S3/GCS<br/>Static Files]
        I[S3/GCS<br/>Backups]
    end
    
    subgraph "Monitoring"
        J[CloudWatch/<br/>Cloud Monitoring]
        K[Prometheus<br/>Grafana]
    end
    
    A --> B
    B --> C1
    B --> C2
    B --> C3
    
    C1 --> F
    C2 --> F
    C3 --> F
    
    C1 --> G
    C2 --> G
    C3 --> G
    
    D1 --> F
    D1 --> G
    D2 --> F
    D2 --> G
    E --> F
    E --> G
    
    C1 --> H
    F -.-> I
    
    C1 -.-> J
    C1 -.-> K
    
    style F fill:#2196F3
    style G fill:#FF9800
    style H fill:#4CAF50
```

### Docker Compose Development

```mermaid
graph TB
    subgraph "Docker Network: erp-network"
        subgraph "Application Containers"
            A[web:8000<br/>Django+Gunicorn]
            B[celery<br/>Worker]
            C[celery-beat<br/>Scheduler]
        end
        
        subgraph "Data Containers"
            D[(postgres:5432<br/>PostgreSQL 16)]
            E[(redis:6379<br/>Redis 7)]
        end
        
        subgraph "Observability Containers"
            F[jaeger:16686<br/>Tracing UI]
            G[prometheus:9090<br/>Metrics]
            H[grafana:3000<br/>Dashboards]
        end
    end
    
    A --> D
    A --> E
    B --> D
    B --> E
    C --> D
    C --> E
    
    A --> F
    A --> G
    G --> H
    
    style A fill:#4CAF50
    style D fill:#2196F3
    style E fill:#FF9800
```

---

## 🏢 Multi-Tenancy Architecture

### Schema-per-Tenant Model

```mermaid
graph TB
    subgraph "PostgreSQL Database"
        subgraph "Public Schema"
            A[tenants table<br/>id, name, schema_name]
            B[users table<br/>id, email, tenant_id]
        end
        
        subgraph "Tenant: acme_corp"
            C1[journal_entries]
            C2[accounts]
            C3[transactions]
        end
        
        subgraph "Tenant: demo_inc"
            D1[journal_entries]
            D2[accounts]
            D3[transactions]
        end
    end
    
    E[Request] --> F{Middleware}
    F --> G[Extract tenant from<br/>subdomain/header]
    G --> H[SET search_path = tenant_schema]
    H --> I{Execute Query}
    I --> C1
    I --> D1
    
    style A fill:#9C27B0
    style C1 fill:#4CAF50
    style D1 fill:#2196F3
```

### Tenant Isolation Flow

```mermaid
sequenceDiagram
    participant R as Request
    participant M as Middleware
    participant DB as PostgreSQL
    participant V as View
    
    R->>M: GET /api/v1/accounts/<br/>Host: acme.erp.com
    M->>M: Parse Subdomain: "acme"
    M->>DB: SELECT * FROM tenants<br/>WHERE domain='acme.erp.com'
    DB-->>M: Tenant(id=1, schema='acme_corp')
    M->>DB: SET search_path = 'acme_corp'
    M->>V: request.tenant = Tenant(id=1)
    V->>DB: SELECT * FROM accounts
    Note over DB: Queries run in<br/>acme_corp schema
    DB-->>V: Account data
    V-->>R: 200 OK + JSON
```

---

## 🔌 API Architecture

### RESTful API Structure

```mermaid
graph LR
    subgraph "API Versioning"
        A[/api/v1/] --> B{Router}
        C[/api/v2/] --> B
    end
    
    subgraph "Resources"
        B --> D[/users/]
        B --> E[/journal-entries/]
        B --> F[/accounts/]
        B --> G[/reports/]
    end
    
    subgraph "Middleware Stack"
        H[Rate Limiting]
        I[Authentication<br/>JWT]
        J[Permissions]
        K[Versioning]
    end
    
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L[ViewSet/View]
    
    style B fill:#4CAF50
    style I fill:#2196F3
```

### OpenAPI Documentation Flow

```mermaid
graph TB
    A[DRF ViewSets] --> B[drf-spectacular]
    B --> C[OpenAPI 3.1 Schema]
    C --> D[/api/schema/]
    D --> E[SwaggerUI<br/>/api/docs/]
    D --> F[ReDoc<br/>/api/redoc/]
    
    G[Client] --> E
    G --> F
    E --> H[Interactive API Testing]
    F --> I[API Documentation]
    
    style C fill:#4CAF50
    style E fill:#2196F3
    style F fill:#FF9800
```

---

## 🔒 Security Architecture

### Defense in Depth

```mermaid
graph TB
    subgraph "Layer 1: Network"
        A[CDN DDoS Protection]
        B[WAF Rules]
        C[Rate Limiting]
    end
    
    subgraph "Layer 2: Application"
        D[Security Headers<br/>CSP, HSTS, etc.]
        E[Input Validation]
        F[CSRF Protection]
    end
    
    subgraph "Layer 3: Authentication"
        G[JWT Tokens]
        H[OAuth 2.0]
        I[MFA Optional]
    end
    
    subgraph "Layer 4: Authorization"
        J[Role-Based Access<br/>RBAC]
        K[Row-Level Security]
        L[Tenant Isolation]
    end
    
    subgraph "Layer 5: Data"
        M[Encryption at Rest<br/>AES-256]
        N[Encryption in Transit<br/>TLS 1.3]
        O[Database Backups<br/>Encrypted]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    L --> M
    M --> N
    N --> O
    
    style A fill:#F44336
    style G fill:#4CAF50
    style M fill:#2196F3
```

### Authentication & Authorization Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web Server
    participant J as JWT Service
    participant P as Permissions
    participant DB as Database
    
    U->>W: POST /api/v1/auth/login/
    W->>DB: Verify Credentials
    DB-->>W: User + Roles
    W->>J: Generate Tokens
    J-->>W: Access + Refresh JWT
    W-->>U: 200 OK + Tokens
    
    Note over U,W: Authenticated Request
    U->>W: GET /api/v1/accounts/<br/>Authorization: Bearer <token>
    W->>J: Validate Token
    J-->>W: Token Valid + User ID
    W->>P: Check Permissions
    P->>DB: Get User Roles
    DB-->>P: Roles: [accountant, viewer]
    P-->>W: Permission Granted
    W->>DB: Query Accounts<br/>(with tenant filter)
    DB-->>W: Account Data
    W-->>U: 200 OK + JSON
```

---

## 📈 Observability Architecture

### Metrics, Logs, and Traces (MLT)

```mermaid
graph TB
    subgraph "Application"
        A[Django Views]
    end
    
    subgraph "Metrics"
        B[Prometheus Client<br/>django-prometheus]
        C[Prometheus Server]
        D[Grafana Dashboards]
    end
    
    subgraph "Logs"
        E[Structlog<br/>JSON Logging]
        F[CloudWatch Logs/<br/>ELK Stack]
    end
    
    subgraph "Traces"
        G[OpenTelemetry<br/>Auto-instrumentation]
        H[Jaeger Backend]
        I[Jaeger UI]
    end
    
    A --> B
    A --> E
    A --> G
    
    B --> C
    C --> D
    
    E --> F
    
    G --> H
    H --> I
    
    style A fill:#4CAF50
    style C fill:#FF9800
    style H fill:#2196F3
```

---

## 🔄 CI/CD Pipeline

```mermaid
graph LR
    A[Git Push] --> B[GitHub Actions]
    B --> C{Lint & Format}
    C -->|Pass| D[Security Scan]
    C -->|Fail| Z[❌ Fail Build]
    D --> E[Run Tests<br/>pytest + coverage]
    E -->|Pass| F{Coverage >= 80%?}
    E -->|Fail| Z
    F -->|Yes| G[Build Docker Image]
    F -->|No| Z
    G --> H[Push to Registry]
    H --> I[Deploy Staging]
    I --> J[Smoke Tests]
    J -->|Pass| K[Manual Approval]
    J -->|Fail| L[Rollback]
    K --> M[Deploy Production]
    M --> N[Health Checks]
    N -->|Pass| O[✅ Success]
    N -->|Fail| L
    
    style O fill:#4CAF50
    style Z fill:#F44336
    style M fill:#2196F3
```

---

## 📝 Component Relationships

### Django Apps Dependency Graph

```mermaid
graph TD
    A[dashboard<br/>Core Settings] --> B[tenancy<br/>Multi-Tenancy]
    A --> C[usermanagement<br/>Auth]
    B --> D[accounting<br/>Journal Entries]
    C --> D
    B --> E[Inventory<br/>Stock Management]
    C --> E
    D --> F[voucher_schema<br/>Voucher Config]
    E --> F
    A --> G[api<br/>REST Endpoints]
    D --> G
    E --> G
    C --> G
    
    style A fill:#9C27B0
    style B fill:#4CAF50
    style D fill:#2196F3
    style G fill:#FF9800
```

---

## 📚 Additional Resources

- [Deployment Runbook](../runbooks/deployment-rollback.md)
- [Scaling Guide](../runbooks/scaling.md)
- [Incident Response](../runbooks/incident-response.md)
- [API Migration Guide](../API_MIGRATION_v1.md)

---

**Maintained by:** DevOps Team  
**Last Review:** October 18, 2024  
**Next Review:** January 18, 2025
