# Changelog

# Changelog

## [Unreleased] - 2025-11-23

### Fixed

-   Journal line inline formset now auto-assigns sequential `line_number` values and re-enforces balanced debit/credit validation, preventing null constraint failures during voucher creation/editing.
-   Phase 2 voucher view tests were updated to include required `fx_rate`/`journal_line_id` fields and improved diagnostics, eliminating `NoneType` access errors when responses redirect.

## [1.0.0] - 2023-10-27

### Added

-   **Journal Import Feature:** Implemented a robust journal import system allowing users to upload CSV, Excel, and JSON files. The system includes data validation, error handling, and a dry-run mode.
-   **Recurring Journals:** Introduced a feature for creating and managing recurring journal entries, with customizable schedules and templates.
-   **Config-Driven UI:** The user interface is now dynamically generated based on JSON schemas (`ui.json`, `validation.json`), allowing for flexible and easily updatable forms.
-   **AI-Powered Suggestion Helper:** A new `/suggest` API endpoint provides intelligent suggestions for journal entries, leveraging a machine learning model.
-   **Architectural Enhancements:**
    -   Refactored the application to use a service-oriented architecture, improving modularity and testability.
    -   Introduced a repository pattern for data access, decoupling business logic from the database.
    -   Implemented a centralized configuration system for managing application settings.

### Changed

-   **Static Code Audit Resolutions:** Addressed all major issues identified in the initial static code audit, including security vulnerabilities, code smells, and performance bottlenecks.
-   **Improved Error Handling:** Enhanced error handling across the application to provide more informative feedback to users.
-   **UI/UX Improvements:** Refined the user interface for a more intuitive and streamlined user experience.

### Remaining TODOs

-   **Parallel Ledger Posting:** The current implementation posts ledger entries sequentially. A future enhancement will be to process these in parallel for improved performance.
-   **Full ML Integration for AI Helper:** The AI helper is currently based on a pre-trained model. The next phase will involve integrating a full machine learning pipeline for continuous training and improvement.
-   **Comprehensive End-to-End Testing:** While unit and integration tests are in place, a full suite of end-to-end tests using a framework like Cypress is needed to ensure application stability.