# Journal Entry Integration Status

The journal-entry replacement pack is now wired into production-grade backend endpoints and UI states.

- Journal drafts persist through `journal_save_draft`, with header UDF values, charges, attachments, and metadata stored on the `Journal` record.
- Submit / approve / reject / post flows reuse `JournalEntryService`, enforce per-user permissions, and return hydrated payloads to the grid.
- Lightweight JSON search endpoints power account and cost-centre resolution so grid cells sync with master data.
- The HTMX-style grid now honours backend statuses, disables actions when unavailable, surfaces validation errors, and exposes workflow buttons based on the user’s permissions.
- New pytest coverage (`tests/test_journal_entry_api.py`) exercises draft/save/approve and validation failure scenarios.

Follow-up enhancements can iterate on dedicated attachment UX and richer auto-complete widgets, but the original TODO list is complete.
