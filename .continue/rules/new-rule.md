---
description: A description of your rule
---

You are helping on a multi-tenant ERP (Django + Bootstrap/HTMX).
Hard rules:
- Never break tenant isolation (always filter by tenant_id/branch_id).
- Prefer service-layer functions; keep views thin.
- All financial posting must be transactional (atomic).
- Follow existing naming conventions and folder structure.
When changing code:
- Explain why, list impacted modules, and provide a verification checklist.
