# Voucher Entry (HTMX) — Overview

This set of documents describes the HTMX-driven voucher entry UI introduced during the Phase 1 (Base Grid Rebuild) work. It covers configuration, templates, HTMX endpoints, developer notes, and troubleshooting tips to help onboard maintainers.

Contents
- `configuration.md` — configuration and dependencies
- `endpoints.md` — list of HTMX endpoints and what they return
- `development.md` — how to run and test locally (manual and automated checks)
- `troubleshooting.md` — common issues and debug steps

- Design goals
- Provide server-side rendered base grid with Bootstrap/dason admin styling for integration with the project UI
- Use HTMX to progressively enhance behavior (add/duplicate/delete rows, inline edits)
- Keep the UI accessible and compatible with existing Django forms and services

Status
- Phase 1 complete: base grid and row partials implemented with HTMX handlers in `accounting/views`.
- Phase 2 planned: persistent save, validation, richer account lookup, keyboard navigation, and performance tuning.
