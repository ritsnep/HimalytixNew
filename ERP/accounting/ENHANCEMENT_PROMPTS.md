# Accounting Module Enhancement Prompts

This document contains a series of prompts for fixes and enhancements to the accounting module, based on a comprehensive audit of the existing codebase.

## Phase 1: Core Transactional Enhancements

### 1.1. SAP-style Spreadsheet Import

**Prompt:**

"Implement a feature to import journal entries from a spreadsheet, following the specifications in `JOURNAL_IMPORT_TEMPLATE.md`. This should include a file upload interface, a backend service for parsing and validation, and robust error handling."

**Key Files to Modify:**

*   `accounting/views/views_import.py`
*   `accounting/services/journal_import_service.py`
*   `accounting/templates/accounting/journal_import.html`
*   `accounting/forms/journal_import_form.py`

### 1.2. Business Central-style Background Validation

**Prompt:**

"Introduce a non-blocking validation pane for journal entries that runs in the background. This should include a validation service that can be triggered via HTMX, and a UI component (issue pane/fact-box) to display validation results in real-time."

**Key Files to Modify:**

*   `accounting/views/journal_entry_view.py`
*   `accounting/services/validation.py`
*   `accounting/templates/accounting/partials/_journal_validation_panel.html`
*   `accounting/static/accounting/js/journal_entry.js`

### 1.3. JD Edwards-style Open-Period Date Shields

**Prompt:**

"Enhance the existing validation in `services.py` and `forms.py` to enforce that transactions can only be posted to open accounting periods. This should include clear error messages and a robust date-checking mechanism."

**Key Files to Modify:**

*   `accounting/services.py`
*   `accounting/forms.py`
*   `accounting/models.py`

## Phase 2: User Experience and Accessibility

### 2.1. Odoo-style "Hold Ctrl" Shortcut Overlay

**Prompt:**

"Add a keyboard shortcut overlay that appears when the 'Ctrl' key is held down. This should be implemented using JavaScript and should display a list of available shortcuts in a clear and accessible format."

**Key Files to Modify:**

*   `accounting/static/accounting/js/journal_entry.js`
*   `accounting/templates/accounting/journal_entry.html`

### 2.2. AG Grid-level Keyboard Navigation

**Prompt:**

"Enhance the keyboard navigation in the journal entry line grid to support advanced features such as arrow key navigation, 'Enter' to edit, and 'Escape' to cancel. This should be implemented using JavaScript and should be fully accessible."

**Key Files to Modify:**

*   `accounting/static/accounting/js/journal_entry.js`
*   `accounting/templates/accounting/partials/journal_line_form.html`

### 2.3. WCAG 2.2 AA Accessibility

**Prompt:**

"Review and update the UI components in the accounting module to ensure they meet WCAG 2.2 AA accessibility standards. This should include a focus on target size, focus visibility, and color contrast."

**Key Files to Modify:**

*   `accounting/static/accounting/css/journal_entry.css`
*   `accounting/templates/accounting/journal_entry.html`
*   `accounting/templates/accounting/partials/*.html`

## Phase 3: Advanced Features and Integrations

### 3.1. QuickBooks-style Drag-Drop Receipt Capture and OCR Hooks

**Prompt:**

"Implement a drag-and-drop file upload feature for receipts in the journal entry form. This should include an integration with an OCR service to extract data from the uploaded receipts and populate the journal lines."

**Key Files to Modify:**

*   `accounting/views/journal_entry_view.py`
*   `accounting/static/accounting/js/journal_entry.js`
*   `accounting/services.py`

### 3.2. Infor CloudSuite-style Recurring Voucher Engine

**Prompt:**

"Add support for recurring journal entries by creating a model to store recurring transaction templates and implementing a scheduled task to generate journal entries from these templates."

**Key Files to Modify:**

*   `accounting/models.py`
*   `accounting/management/commands/generate_recurring_journals.py`
*   `accounting/views/recurring_journal_views.py`

### 3.3. NetSuite-inspired AI Suggest Endpoint

**Prompt:**

"Create an AI-powered suggestion service that provides suggestions for completing journal lines. This should include an API endpoint that can be called from the UI to fetch suggestions based on the current journal entry."

**Key Files to Modify:**

*   `accounting/api/views.py`
*   `accounting/services.py`
*   `accounting/static/accounting/js/journal_entry.js`

## Phase 4: Architectural Enhancements

### 4.1. Oracle GL-style Multi-Currency and Parallel Ledgers

**Prompt:**

"Enhance the multi-currency support and add parallel ledgers to the accounting module. This is a major architectural change and will require a separate, detailed plan. The initial phase should focus on modifying the `Journal`, `JournalLine`, and `GeneralLedger` models to handle multiple valuations."

**Key Files to Modify:**

*   `accounting/models.py`
*   `accounting/services.py`
*   `accounting/forms.py`