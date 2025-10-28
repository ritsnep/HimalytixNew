# ADR-0003: Technology Stack Selection

**Status:** Accepted  
**Date:** 2024-Q1  
**Decision Makers:** CTO, Engineering Team  
**Technical Story:** Project Initialization

---

## Context and Problem Statement

What technology stack should Himalytix ERP use to balance developer productivity, performance, scalability, and cost-effectiveness for the Nepal market? The system must support multi-tenancy, complex accounting logic, and modern UX while being maintainable by a small team.

## Decision Drivers

* **Developer Productivity**: Fast feature development
* **Ecosystem Maturity**: Stable libraries, strong community
* **Performance**: Handle 1000+ concurrent users
* **Cost**: Minimize infrastructure costs
* **Talent Availability**: Developers in Nepal familiar with stack
* **Scalability**: Grow to 100+ tenants without re-architecture
* **Security**: Proven track record in financial applications

## Considered Options

1. **Django + HTMX + Alpine.js** (Python monolith with HTML-over-the-wire)
2. **Node.js + React + PostgreSQL** (JavaScript full-stack SPA)
3. **Laravel + Vue.js + MySQL** (PHP monolith with SPA frontend)

## Decision Outcome

**Chosen option:** "Django + HTMX + Alpine.js", because:
- Django's "batteries included" philosophy accelerates development
- Strong accounting/financial libraries (decimal handling, transactions)
- HTMX reduces frontend complexity (no build step for simple interactions)
- PostgreSQL mature support for multi-tenancy (schema isolation)
- Security built-in (CSRF, SQL injection prevention, auth)
- Python talent available in Nepal

### Implementation Details

**Backend:**
- **Framework**: Django 5.1.2
- **API**: Django REST Framework (for mobile/integrations)
- **Database**: PostgreSQL 14+ (schema-based multi-tenancy)
- **Cache**: Redis (Celery broker, session store)
- **Task Queue**: Celery (async jobs, scheduled tasks)

**Frontend:**
- **HTMX**: 1.9+ (HTML-over-the-wire for dynamic interactions)
- **Alpine.js**: 3.x (lightweight reactivity for UI components)
- **Tailwind CSS**: 3.x (utility-first styling)
- **Chart.js**: Visualizations (financial dashboards)

**DevOps:**
- **Deployment**: Docker + Render/Heroku (staging), AWS/DigitalOcean (production)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana, Structlog
- **Error Tracking**: Sentry (future)

### Positive Consequences

* Rapid development (Django ORM, admin, auth out-of-the-box)
* Reduced frontend complexity (HTMX vs. React state management)
* Strong security defaults (Django security middleware)
* PostgreSQL reliability for financial data
* Cost-effective (single-server monolith for early stages)
* Excellent debugging tools (Django Debug Toolbar, structlog)

### Negative Consequences

* HTMX limits rich client-side interactions (mitigated by Alpine.js)
* Python GIL limits CPU-bound concurrency (mitigated by async views, Celery)
* Monolith deployment (requires full redeploy vs. microservices)
* Tailwind CSS learning curve for designers unfamiliar with utility-first

## Pros and Cons of the Options

### Django + HTMX + Alpine.js

* **Good**, rapid development (Django scaffolding, ORM, admin)
* **Good**, simple deployment (monolith, no microservice complexity)
* **Good**, excellent security (OWASP Top 10 coverage)
* **Good**, PostgreSQL multi-tenancy support
* **Good**, reduced JavaScript complexity (HTMX vs. React)
* **Neutral**, HTMX newer paradigm (less community resources vs. React)
* **Bad**, GIL limits CPU parallelism (mitigated by Celery)

### Node.js + React + PostgreSQL

* **Good**, JavaScript everywhere (frontend + backend)
* **Good**, rich client-side interactions (React ecosystem)
* **Good**, async-first architecture (no GIL)
* **Bad**, no built-in admin (need to build custom)
* **Bad**, more boilerplate (ORM setup, auth, validation)
* **Bad**, build complexity (Webpack, Babel, npm)
* **Bad**, weaker financial libraries (decimal precision issues)

### Laravel + Vue.js + MySQL

* **Good**, rapid development (Laravel scaffolding, Eloquent ORM)
* **Good**, strong PHP ecosystem in Nepal
* **Good**, Vue.js progressive adoption
* **Bad**, MySQL multi-tenancy support weaker than PostgreSQL
* **Bad**, fewer financial/accounting libraries vs. Python
* **Neutral**, PHP talent pool shrinking globally

## Links

* Tech stack documented: [readme.md](../../readme.md), [requirements.txt](../../requirements.txt)
* HTMX philosophy: https://htmx.org/essays/
* Django security: https://docs.djangoproject.com/en/stable/topics/security/

---

## Compliance and Review

* **Reviewed by:** CTO, Tech Lead, Security Engineer
* **Review date:** 2024-Q1
* **Next review:** 2025-Q4 (annual architecture review)
