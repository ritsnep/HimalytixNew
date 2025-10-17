# Journal Entry Spreadsheet Import Template

This document defines the format for importing journal entries from a spreadsheet (CSV or Excel).

## File Format

The import file must be a flat list where each row represents a single journal line. Lines are grouped into journal entries using a `grouping_key`.

### Columns

| Column Name           | Required | Data Type      | Description                                                                 |
| --------------------- | -------- | -------------- | --------------------------------------------------------------------------- |
| `grouping_key`        | Yes      | Text           | A unique identifier to group lines into a single journal entry.             |
| `journal_date`        | Yes      | Date (YYYY-MM-DD) | The date of the journal entry.                                              |
| `journal_type_code`   | Yes      | Text           | The code of the Journal Type (e.g., 'GJ' for General Journal).              |
| `journal_reference`   | No       | Text           | An optional reference for the journal header.                               |
| `journal_description` | No       | Text           | An optional description for the journal header.                             |
| `currency_code`       | Yes      | Text (3 chars) | The currency code for the journal (e.g., 'USD').                            |
| `exchange_rate`       | Yes      | Decimal        | The exchange rate. Use `1` for the base currency.                           |
| `account_code`        | Yes      | Text           | The account code from the Chart of Accounts.                                |
| `line_description`    | No       | Text           | An optional description for the journal line.                               |
| `debit_amount`        | Yes      | Decimal        | The debit amount. Use `0` if the line is a credit.                          |
| `credit_amount`       | Yes      | Decimal        | The credit amount. Use `0` if the line is a debit.                          |
| `department_code`     | No       | Text           | The code for the department dimension.                                      |
| `project_code`        | No       | Text           | The code for the project dimension.                                         |
| `cost_center_code`    | No       | Text           | The code for the cost center dimension.                                     |

### Example

| grouping_key | journal_date | journal_type_code | journal_reference | journal_description | currency_code | exchange_rate | account_code | line_description | debit_amount | credit_amount | department_code | project_code | cost_center_code |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| BATCH-001    | 2024-08-05   | GJ                | REF-123           | Monthly Salaries    | USD           | 1             | 1000         | Cash             | 0            | 5000          |                 |              |                  |
| BATCH-001    | 2024-08-05   | GJ                | REF-123           | Monthly Salaries    | USD           | 1             | 5000         | Salaries Expense | 5000         | 0             | HR              |              | CC-HR            |
| BATCH-002    | 2024-08-06   | GJ                | REF-124           | Office Supplies     | USD           | 1             | 1000         | Cash             | 0            | 250           |                 |              |                  |
| BATCH-002    | 2024-08-06   | GJ                | REF-124           | Office Supplies     | USD           | 1             | 5010         | Supplies Expense | 250          | 0             | ADMIN           |              | CC-ADMIN         |