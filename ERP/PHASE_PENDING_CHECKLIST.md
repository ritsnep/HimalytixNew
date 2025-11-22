# Pending Phase Checklist

All earlier phase-specific TODO docs were removed in favor of this single list. Cross-reference `Docs/consolidated_todo_register.md` for background; only the items still requiring action are tracked below.

## 1. Accounting / Journal Entry Hardening
- [ ] Run the full regression matrix in `accounting/tests/` (posting, depreciation, reconciliation, workflow) and document any remaining failures before sign-off.

## 2. Tally-Inspired Enhancements
- [ ] Coordinate with QA to validate multi-currency, reporting, cheque/bank utilities, and deployment-readiness scenarios.
- [ ] Capture the results of those QA passes in the consolidated register and mark the section complete once sign-off is received.

## 3. Streamlit V2 Initiative (Milestones M0–M6)
- [ ] Re-verify the Streamlit `/V2` skeleton plus auth bridge, tenancy propagation, DRF endpoints, UI pages, security posture, observability hooks, and deployment manifests.
- [ ] Update the status of `ERP/V2/TODO_*.md` sections inside the consolidated register with evidence links (code refs, tests, dashboards).

## 4. Documentation & Release Prep
- [ ] After each verification above, refresh `Docs/consolidated_todo_register.md` so completed scopes move out of this checklist.
- [ ] When every section is verified, archive this file along with the consolidated register for release tagging.
