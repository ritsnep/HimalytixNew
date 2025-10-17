# Architectural Plan: Multi-Currency and Parallel Ledgers

This document outlines the architectural changes required to implement multi-currency and parallel ledgers in the accounting module.

## 1. Introduction

The current accounting model supports a single functional currency and transaction-level currency. This plan introduces a more robust multi-currency model and adds support for parallel ledgers, allowing for multiple accounting representations (e.g., local, IFRS, GAAP).

## 2. Proposed Model Changes

### 2.1. New Model: `Ledger`

A new `Ledger` model will be created to define the different ledgers that the organization will use.

```python
class Ledger(models.Model):
    """
    Represents an accounting ledger for a specific valuation purpose.
    """
    LEDGER_TYPE_CHOICES = [
        ('actual', 'Actual'),
        ('budget', 'Budget'),
        ('forecast', 'Forecast'),
        ('statutory', 'Statutory'),
    ]
    ledger_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='ledgers')
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    ledger_type = models.CharField(max_length=20, choices=LEDGER_TYPE_CHOICES, default='actual')
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"
```

### 2.2. `Journal` Model Modifications

The `Journal` model will be simplified by removing the currency and exchange rate fields, as these will now be handled at the line level.

**Removed Fields:**
*   `currency_code`
*   `exchange_rate`

### 2.3. `JournalLine` Model Modifications

The `JournalLine` model will be updated to include a foreign key to the `Currency` model and will store multiple valuation amounts in a JSON field.

**Modified/New Fields:**
*   `currency`: A foreign key to the `Currency` model to specify the transaction currency for the line.
*   `exchange_rate`: The exchange rate between the transaction currency and the primary ledger's currency.
*   `valuations`: A JSON field to store debit/credit amounts for each parallel ledger.

```python
class JournalLine(models.Model):
    # ... existing fields ...
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    valuations = models.JSONField(default=dict) # e.g., {'local': {'debit': 100, 'credit': 0}, 'ifrs': {'debit': 110, 'credit': 0}}
    
    # Remove redundant fields
    # functional_debit_amount
    # functional_credit_amount
```

### 2.4. `GeneralLedger` Model Modifications

The `GeneralLedger` model will be modified to include a foreign key to the new `Ledger` model. This will allow each GL entry to be associated with a specific ledger.

**Modified/New Fields:**
*   `ledger`: A foreign key to the `Ledger` model.
*   The `functional_debit_amount` and `functional_credit_amount` fields will be replaced by `debit_amount` and `credit_amount`, which will store the amounts in the ledger's currency.

```python
class GeneralLedger(models.Model):
    # ... existing fields ...
    ledger = models.ForeignKey('Ledger', on_delete=models.PROTECT)
    
    # Rename for clarity
    # debit_amount -> transaction_debit
    # credit_amount -> transaction_credit
    
    # New fields for ledger-specific amounts
    ledger_debit = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    ledger_credit = models.DecimalField(max_digits=19, decimal_places=4, default=0)

    # Remove redundant fields
    # functional_debit_amount
    # functional_credit_amount
```

## 3. Impact on Services and Forms

### 3.1. `accounting/services.py`

*   The service layer will need to be updated to handle the creation of `GeneralLedger` entries for each parallel ledger.
*   When a journal is posted, the service will iterate through the journal lines and create a `GeneralLedger` entry for each configured ledger, calculating the appropriate amounts based on the exchange rates.

### 3.2. `accounting/forms.py`

*   The `JournalLine` form will need to be updated to allow users to select a currency for each line.
*   The form will also need to handle the input of amounts in the transaction currency and display the converted amounts for the primary ledger.

## 4. Data Migration

A data migration plan will be required to update the existing data to the new model structure. This will involve:
*   Creating `Ledger` instances for each organization.
*   Populating the new `currency` field in the `JournalLine` model.
*   Migrating the existing `functional_debit_amount` and `functional_credit_amount` data to the new `valuations` field in `JournalLine` and the new `ledger_debit` and `ledger_credit` fields in `GeneralLedger`.

## 5. Conclusion

These architectural changes will provide a solid foundation for supporting multi-currency transactions and parallel ledgers, enabling more flexible and comprehensive financial reporting.