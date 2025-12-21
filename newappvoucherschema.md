Config-Driven Voucher Entry App – Implementation Guide

This guide describes how to implement a new Django app that delivers a config‑driven UI for voucher entry. The aim is to create an isolated module which extends the existing accounting models but does not depend on legacy hard‑coded UI definitions. The configuration engine stores metadata for voucher types and drives the UI at runtime. It uses the existing posting workflow (voucher → journal → general ledger → inventory) while ensuring ACID‑compliant transactions and a single source of truth.

1 Background and Invariants

The existing system stores voucher definitions in the schema_definition column of VoucherModeConfig. At runtime the UI schema is derived from this JSON via resolve_ui_schema(); the UI never reads legacy ui_schema JSON

. Important invariants enforced by the current architecture are:

1:1 mapping between voucher and journal: each voucher has one corresponding journal and vice versa

.

Balanced journals: the sum of debits must equal the sum of credits

.

Idempotent, atomic posting: posting a voucher is safe to retry and either completes fully or rolls back

; no partial writes remain on failure

.

Immutable posted vouchers: once posted they cannot be edited; reversals or new vouchers are used for corrections

.

Audit trail: posting operations are logged with timestamps and error codes

.

A controlled vocabulary describes permitted field types (e.g., text, number, date, select, account) and how header and line schemas are structured

. The HTMX UI contract splits the voucher page into components (header, lines grid, totals, status stepper and error banner), and defines endpoints for validation, recalculation, save, post and status updates

. Each call returns a partial update (HTTP 200), a validation error (422), a conflict (409) or a forbidden (403), avoiding full page reloads

.

2 Overview of the New App

The new app (for example, voucher_config) will live alongside accounting and hold all configuration and UI rendering logic. It will not modify the existing VoucherModeConfig but will supply an alternate configuration engine using three tables:

VoucherConfigMaster – core template definition

InventoryLineConfig – item (grid) configuration

FooterChargeSetup – footer/tax charge rules

These tables form a blueprint for each voucher type. The app will also provide services to seed baseline voucher definitions, generate forms and views, and orchestrate posting. The goal is to keep all metadata in the database so that the UI can be customised without code changes.

2.1 Core Template Definition (VoucherConfigMaster)

This model replaces the “tbl_Voucher” description from the blueprint. It defines the identity and behaviour of a voucher type:

organization (ForeignKey) – ensures configurations are per‑organisation.

code (CharField, unique per organisation) – stable identifier used for mapping to journal types and seeding.

label (CharField) – human readable name, e.g., Sales Invoice or Purchase Return.

voucher_date_label, entry_date_label, ref_no_label – custom labels for header fields; if use_ref_no is false, ref_no_label can be blank.

use_ref_no (Boolean) – whether to show the reference number field.

show_time (Boolean) – show a time input alongside dates when needed (e.g., stock receipts).

show_document_details (Boolean) – toggles a section for shipment or transport details.

numbering_method (Choice: auto, manual) – determines how voucher numbers are generated.

auto_post (Boolean) – if true, posting is triggered immediately after save.

prevent_duplicate_voucher_no (Boolean) – if true, duplicate numbers are rejected.

affects_gl and affects_inventory (Boolean) – align with existing VoucherModeConfig flags

.

requires_approval (Boolean) – whether the voucher requires approval before posting.

schema_definition (JSONField) – optional override of default schema; if null, the schema is composed from the other configuration tables and defaults.

This model should have a method resolve_ui_schema() similar to VoucherModeConfig.resolve_ui_schema()

, merging the base schema with header/line/footer customisations and returning a UI schema ready for form generation.

2.2 Item‑Level Configuration (InventoryLineConfig)

This model configures columns and behaviour of the line items grid for inventory‑affecting vouchers. Fields include:

voucher_config (ForeignKey to VoucherConfigMaster).

Flags such as show_rate, show_amount, allow_free_qty, show_alternate_unit, show_discount, etc.

Inventory tracking fields: show_batch_no, show_mfg_date, show_exp_date, show_serial_no.

Decimal precision fields: qty_decimal_places, rate_decimal_places (integers controlling step attributes in the UI).

is_fixed_product (Boolean) – if true, the grid includes columns like Engine No and Chassis No for items that require additional identification.

allow_batch_in_stock_journal (Boolean) – ensures traceability in stock journals.

Default values should match typical behaviour for each voucher type (e.g., Sales shows rate and amount; Stock Transfer shows quantity only). The UI generator reads these flags to decide which columns to render.

2.3 Footer and Charge Rules (FooterChargeSetup)

This model defines automatic footer charges such as taxes or discounts:

voucher_config (ForeignKey).

ledger (ForeignKey to ChartOfAccount) – default ledger to post the charge.

calculation_type (Choice: rate, amount).

rate (DecimalField, nullable) – used when calculation_type is rate to compute rate × base_amount.

amount (DecimalField, nullable) – used when calculation_type is amount.

can_edit (Boolean) – whether users can override the auto‑calculated value in the UI.

Multiple footer rows can be defined; during voucher entry the UI will add these automatically at the bottom of the grid. When saving, the amounts will be included in the total and posted to the specified ledgers.

2.4 User‑Defined Fields

To remain flexible, keep the existing VoucherUDFConfig model (header/line UDF definitions) or create an analogous model in the new app. UDFs should support field types (text, number, date, select) and validation rules (regex, min/max, etc.), and should be injected into the header or lines at runtime.

3 Voucher Type Specialisations

Although the base model is generic (Date, Reference No, Narration, Branch), each voucher type has extensions. The new configuration app must capture these differences via configuration instead of hard‑coding them. The four primary voucher categories are:

3.1 Journal (Financial Adjustments)

Use affects_gl=True, affects_inventory=False.

UI shows a ledger allocation grid with Debit and Credit amounts. If show_item_details_in_journal is true, the grid should permit optional inventory fields (product, warehouse, quantity, etc.).

Additional configuration: allow specifying default narration templates and cost centres.

3.2 Purchasing (Inventory Inward)

affects_gl=True, affects_inventory=True.

Header includes a Party (Vendor) selector, typically filtered by a ledger group (suppliers). Extra fields: Supplier, Import Country, PP No, Vehicle No, etc., controlled via show_document_details.

Line grid uses InventoryLineConfig flags for receipts (requires unit cost); includes quantity, rate, amount, and optional Batch No, MFG/EXP dates.

Footer charges may include VAT or landed cost; these charges are distributed into the item cost when posting (landed cost allocation is implemented in posting service).

Special validations: back‑date restrictions, vendor credit limit check.

3.3 Sales (Inventory Outward)

affects_gl=True, affects_inventory=True.

Header includes a Customer (Party) selector, Credit Days, SSF Code, Destination, etc. Flags control visibility of these fields.

Rates may be auto‑selected from a price list; integration hooks can load price data on item selection.

Supports loyalty points (Sales Point) accrual in the footer or as an additional field.

3.4 Stock‑Related (Internal Movement)

affects_gl may be false for simple stock transfers; affects_inventory=True is always true.

The UI uses dual grids (source vs target) if source_godown and target_godown are different. For Stock Journal (consumption/production), a single grid may suffice but must record consumption of raw materials and production of finished goods. allow_batch_no_in_stock_journal ensures tracking.

Each voucher type can be represented by a row in VoucherConfigMaster with different flags and associated InventoryLineConfig and FooterChargeSetup entries. For example, Sales Invoice would set party_required=True, use_ref_no=True, show rates and amounts, and attach VAT and discount charges.

4 Dynamic UI Rendering Flow

The new app will use HTMX and Dason Admin components to render the UI based on configuration. The flow is:

Voucher type selection. A view lists available voucher types (rows in VoucherConfigMaster) to the user. When a user selects one, the system loads the associated blueprint.

State initialisation. Before rendering the form, the server determines:

Back‑date restrictions and fiscal period boundaries (existing functions usp_IsValidVoucher can be ported or replaced).

The next available voucher number using numbering_method and prefix/suffix rules.

Resolve UI schema. The server calls VoucherConfigMaster.resolve_ui_schema() to build a ui_schema (header and lines) from the blueprint and UDF definitions. It uses the controlled vocabulary of field types and attaches validation rules (required, regex, min/max, decimal places). A default schema can be generated via existing helper default_ui_schema()

 and then modified according to the config.

Form generation. Pass the UI schema to the unified VoucherFormFactory (imported from accounting.forms_factory or a new class in this app) to construct the header form and line formset. The form factory maps each field type to a Django form field and widget (text, textarea, select, date picker, number input) and injects validation constraints. VoucherUDFConfig.get_field_widget_attrs() shows how to attach attributes like class and step

.

HTMX rendering. The initial page loads a base template (e.g., voucher_entry_new.html), which includes HTMX targets for the header, line grid, totals, process tracker and error banner

. Each user interaction (adding lines, changing quantities, recalculating totals) triggers HTMX requests to dedicated endpoints:

Validate: checks form validity; returns 422 with inline errors if any field fails.

Recalc: recalculates totals, taxes and charges; updates the totals panel and footers.

Save: creates or updates the draft voucher (Journal) without posting; returns updated form sections.

Post: triggers the posting orchestration; updates the process tracker.

Status: used for polling during asynchronous posting; returns current step statuses.

These endpoints return partials and never perform a full page reload or redirect

. Errors are returned with stable error codes (e.g., INV-001, GL-001, VCH-002) and mapped to the correct step on the UI stepper

.

5 Saving and Persistence

The new app should reuse the existing service create_voucher_transaction (or an adapted version) to save vouchers and orchestrate posting. The typical workflow is

:

Pre‑validation: Ensure the voucher date is within the current fiscal period; verify back‑date limits and credit limits (usp_IsValidVoucher, usp_IsValidCredit). Check required fields using the form’s built‑in validators.

Header creation: Create the voucher header record (e.g., Journal or specialised voucher table) with status draft. Record header fields such as date, reference number, branch, party, narration, and user.

Line persistence: Persist line items into the appropriate tables. For general journals, lines store debit and credit amounts; for inventory vouchers, lines split into ItemAllocation (quantity, rate, discount, tax) and ItemDetails (batch, warehouse, serial number). Normalise data to avoid duplication.

Inventory metadata building: If affects_inventory=True, construct an inventory_transactions payload containing product, warehouse, quantity, unit cost, etc. This matches the metadata required in the existing posting service (product_id, warehouse_id, quantity, unit_cost, cogs_account_id, grir_account_id, optional batch/location)

.

Save voucher and metadata. Use transaction.atomic() to ensure that header, lines and metadata are saved together. Create or reuse a VoucherProcess row to record that the saved step is complete

.

Posting. If auto_post=True or the user chooses to post, call PostingService.post() to perform GL and inventory postings. The service must ensure that:

General ledger entries are created for each journal line; balanced; and idempotent.

Inventory adjustments are recorded for each inventory line with proper costing (FIFO or weighted average). Missing metadata triggers codes INV-002..INV-010 and stops posting.

Transaction is atomic: if inventory posting fails (e.g., insufficient stock), the GL entries and voucher remain unposted

.

Voucher and journal status transitions to posted only on success.

If a failure occurs, a VoucherProcessError should be raised with a stable code; this error bubbles back to the HTMX view and updates the process tracker. The VoucherProcess table stores the status of each step (saved, journal, gl, inventory) with statuses pending, in_progress, done, failed

.

6 Org‑Wise Seeding and Baseline Set

To ensure consistent behaviour across all organisations, the app must include a management command (e.g., seed_voucher_definitions) and an organisation creation hook. The command should:

Define a baseline set of voucher types: Journal, Cash Receipt, Cash Payment, Cash Transfer, Bank Receipt, Bank Payment, Bank Transfer, AR Receipt, AP Payment, Sales Invoice, Sales Return, Purchase Invoice, Purchase Return, Debit Note, Credit Note, Landed Cost, Stock Transfer, Stock Journal.

Create a VoucherConfigMaster row for each type with default labels, flags and schema definitions. Also create the associated InventoryLineConfig and FooterChargeSetup rows. The baseline schemas should conform to the controlled vocabulary

 and include required fields.

Map each voucher code to a JournalType by stable code (e.g., Sales Invoice → sales journal type). This mapping should be explicit in the config and used by the posting service.

Ensure idempotency: the command uses unique constraints (organization, code) so it can be run repeatedly without creating duplicates. It should backfill missing configurations on existing organisations.

7 Integration with Existing Services

The new app should extend but not duplicate core accounting services. Wherever possible, import from accounting:

Models: Use Journal, JournalLine, VoucherProcess and ChartOfAccount instead of re‑creating these tables. Reference TransactionTypeConfig for journal numbering rules and fiscal periods.

Services: Use or adapt create_voucher_transaction and PostingService.post() for saving and posting logic. Align with the invariants documented in the generic voucher flow

.

Forms: Import VoucherFormFactory from accounting.forms_factory (or move it into the new app) and ensure it can read the UI schema built by VoucherConfigMaster.resolve_ui_schema(). This ensures consistent handling of fields and validations.

Templates: Reuse voucher_entry_new.html and partial templates referenced in voucher_entry_architecture.md

. Extend them to read configuration flags (e.g., show time, show document details) and use Dason Admin components with HTMX. Provide templates for header, lines, totals, stepper and error banner; each must be replaceable per voucher type if needed.

8 UI Components and User Experience

The UI should follow the HTMX contract

 and provide real‑time feedback to the user. Key components include:

Header form: shows date fields (voucher_date_label, entry_date_label), reference number (if use_ref_no), branch, party, narration, and other header‑level fields. Hidden or disabled fields are omitted from the UI.

Line items grid: built from InventoryLineConfig and UDF definitions; supports row insertion, duplication and deletion; keyboard navigation; numeric input with proper step for decimal places; optional columns for batch, manufacturing/expiry dates, serial numbers, free quantity and alternate units.

Totals panel: shows computed totals (quantity, rate, amount, tax, discount, rounding, net amount). This panel updates via the /recalc/ endpoint whenever line or charge data changes.

Footer charges: automatically lists tax/discount rows from FooterChargeSetup and allows user edits if can_edit is true.

Process tracker (status stepper): visualises posting progress with steps Saved → Journal Created → GL Posted → Inventory Posted → Completed/Failed. It reads live data from VoucherProcess and updates via the /status/ endpoint

. Each step shows a spinner while in progress, a green check on completion or a red cross with the error code on failure.

Error banner: displays validation or posting errors. Use the stable error code and a short description; offer links to documentation or support.

All UI interactions (save, post, recalc) must preserve user input; no full page reloads or redirects occur. Buttons should be disabled during requests to prevent double submission, and idempotency tokens ensure safe resubmission.

9 Testing and Hardening

To make the system production‑ready, implement a comprehensive test suite:

Unit tests for resolve_ui_schema() verifying that the UI schema reflects configuration flags (e.g., hiding ref_no when use_ref_no is false). Test unknown field types and invalid schema definitions.

Form factory tests ensuring that each field type maps to the correct Django form and widget, that validation rules (required, regex, min/max) are injected, and that disabled fields are not required.

Posting chain tests verifying rollback and idempotency:

When inventory posting fails due to insufficient stock (trigger INV-001), ensure that GL entries and journal status remain unposted and that a clear error is returned.

When the same voucher is posted twice, ensure no duplicate journals/GL entries are created.

When two users attempt to post concurrently, enforce locking or return a 409 conflict.

Mapping tests verifying that each voucher code maps to the correct JournalType and that seeding is correct.

Seeding tests verifying that the baseline set is created for new organisations and that running the command multiple times does not create duplicates.

UI tests (integration or automated) verifying that HTMX responses return partials and that the page never reloads during interactive actions. Simulate entry of line items, recalculations, validations and posting; ensure that errors appear inline.

10 Conclusion

This document outlines how to build a config‑driven voucher entry engine as a new Django app that remains compatible with the existing posting chain. By storing voucher definitions and UI rules in VoucherConfigMaster, InventoryLineConfig and FooterChargeSetup, the system decouples the UI from the code and enables dynamic rendering. HTMX endpoints provide a smooth user experience without page reloads, and the underlying services maintain ACID‑compliant posting with idempotency. Baseline seeding ensures that all organisations start with a full set of voucher types, and comprehensive tests guard against regressions. Together, these components will deliver a robust, customisable voucher system ready for real‑world ERP demands.