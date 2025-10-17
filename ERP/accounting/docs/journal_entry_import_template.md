# Journal Entry Import Template

This document defines the required format for importing journal entries via spreadsheet into the system.

## File Format

The import file must be a CSV (Comma Separated Values) file. Each row in the CSV represents a line item of a journal entry. Multiple line items can be grouped into a single journal entry using the `grouping_key` column.

### Grouping Key

The `grouping_key` is a mandatory column used to associate multiple lines with a single journal entry. All rows that share the same `grouping_key` will be combined to form one journal entry. For a journal entry to be valid, the sum of `debit_amount` must equal the sum of `credit_amount` for all lines sharing the same `grouping_key`.

## Required Columns

The following table lists all required columns, their expected data types, and a description of their purpose and validation rules.

The following table lists all required columns, their expected data types, and a description of their purpose.

| `exchange_rate`   | Decimal   | The exchange rate if the transaction is in a foreign currency. Default to 1.0 for base currency. | `1.0`             |
| `document_number` | String    | An optional document number associated with the entry.                      | `DOC-001`         |