# Voucher System Audit & Validation Plan

Context: The Generic Voucher Entry system now uses atomic transactions and strict schema validation.
Objective: Verify data integrity, UI responsiveness, and rollback capabilities.

## Phase 1: Schema & UI Rendering
1. Load Test: Load the voucher creation page for VM-JV (General Journal).
   - Verify Journal Date defaults to Today.
   - Verify Account field renders as a Typeahead (not a standard select).
   - Verify Debit/Credit fields accept decimals only.
2. Schema Injection:
   - Inject a ui_schema with a mandatory custom field Ref_ID.
   - Verify the UI reflects this field as required (*).

## Phase 2: Transactional Integrity (Critical Path)
3. Happy Path:
   - Input: Valid Header, 2 Balanced Lines (Dr 100, Cr 100).
   - Action: Click Post.
   - Expectation:
     - Voucher status = POSTED.
     - GL Entries created.
     - User redirected to Detail View.
4. Rollback Test:
   - Input: Valid Header, Balanced Lines, but Inventory Item with 0 stock.
   - Action: Click Post.
   - Expectation:
     - UI shows "Validation Error: Insufficient Stock".
     - DB: No Journal created. No GL entries created.
5. Draft Test:
   - Input: Valid Header, Unbalanced Lines (Dr 100, Cr 0).
   - Action: Click Save Draft.
   - Expectation: Voucher saved with status DRAFT. No GL entries.

## Phase 3: Stress & Concurrency
6. Concurrency Check:
   - Simulate 2 users posting against the same Inventory Item simultaneously.
   - Expectation: One succeeds, one receives a row version or optimistic lock error.
