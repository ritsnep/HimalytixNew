## UDF + Inventory + Posting Flow (Himalytix)

This note documents the current end-to-end flow for user-defined fields (UDFs), inventory posting, and journal approval/posting.

### 1) User-Defined Fields (UDF) Framework
- **Models**: `UDFDefinition` (org + content type scoped metadata) and `UDFValue` (per-object values via GenericForeignKey). See `accounting/models.py` and migration `0129_udf_models.py`.
- **Admin**: Managed in `accounting/admin.py` with list filters/search for field type, content type, org.
- **Saving values**: Use `accounting.utils.udf.save_udf_values(instance, udf_data)`; it upserts values keyed by content type/org and ignores unknown field names.
- **Form/API pattern**: Fetch `UDFDefinition` for the model’s content type; inject dynamic fields (e.g., `udf_<field_name>`). On save, collect the payload and call `save_udf_values(instance, udf_payload)`.
- **Reporting**: Use `is_filterable` / `is_pivot_dim` flags to decide which UDFs to surface in filters/pivot views.

### 2) Journal Approval → Posting → GL
- **Approval stamping**: Journals carry `approved_by`/`approved_at`; approving a journal stamps these and writes an `Approval` record (see `accounting/services/journal_entry_service.py`).
- **Gating**: Journal types with `requires_approval=True` must be `approved` and have an approval record before posting. Posting locks the journal (`is_locked`) and records `posted_at/posted_by`.
- **Posting service**: `PostingService.post(journal)` validates period, balance, and status transitions; applies line effects to `ChartOfAccount.current_balance` and writes `GeneralLedger` entries.
- **Auto-numbering**: If `journal.journal_number` is blank, `journal_type.get_next_journal_number()` is invoked during posting.

### 3) Inventory Integration (Weighted Average + GR/IR)
- **Service**: `InventoryPostingService` ( `accounting/services/inventory_posting_service.py` ).
  - `record_receipt`: Updates weighted-average cost per product/warehouse via `InventoryItem`, writes `StockLedger`, and returns Dr Inventory / Cr GR/IR accounts with total cost.
  - `record_issue`: Validates on-hand, uses current weighted-average cost, writes `StockLedger`, and returns Dr COGS / Cr Inventory accounts with total cost.
- **Sales invoice hook**: `SalesInvoiceService.post_invoice(..., warehouse=...)` issues inventory for lines whose `product_code` is an inventory item: adds COGS/Inventory lines using weighted-average cost and requires a warehouse.
- **Purchase invoice hook**: `PurchaseInvoiceService.post_invoice(..., use_grir=True, warehouse=..., grir_account=...)` records receipts for inventory items: Dr Inventory / Cr GR/IR, then clears GR/IR before AP.

### 4) IRD Submission
- **Service**: `accounting/ird_service.py` builds payloads, signs them (HMAC placeholder), retries with backoff, and stores `ird_signature`, `ird_ack_id`, `ird_status`, `ird_last_response`, `ird_last_submitted_at` on `SalesInvoice`.
- Auto-submit can be enabled via setting or `submit_to_ird` flag in `SalesInvoiceService.post_invoice`.

### 5) Data & Migrations
- Relevant migrations: `0128_journal_approval_and_salesinvoice_ird_fields.py` (approval/IRD fields) and `0129_udf_models.py` (UDF tables).
- Run: `python manage.py migrate accounting` after pulling these changes.

### 6) Testing Notes
- Added unit tests for approval stamping and inventory weighted-average issue/receipt (`ERP/tests/test_services_unit.py`). They patch DB access where needed; a global coverage gate may block full pytest runs unless adjusted.
