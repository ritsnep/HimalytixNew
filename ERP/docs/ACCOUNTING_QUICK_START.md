# Accounting Module - Quick Start Guide

## Manual Journal Entries

### Creating a Journal Entry

There are two ways to create manual journal entries:

#### Option 1: Django Admin (Simple)

1. **Access Django Admin**
   - Navigate to `/admin/accounting/journal/`
   - Click "Add Journal +"

2. **Fill Header Information**
   - **Organization**: Auto-selected
   - **Journal Type**: Select (e.g., General Journal)
   - **Period**: Select open accounting period
   - **Journal Date**: Enter date within selected period
   - **Reference**: Optional (e.g., "ADJ-2025-001")
   - **Description**: Enter meaningful description
   - **Currency**: Defaults to USD
   - **Exchange Rate**: Defaults to 1.0

3. **Add Journal Lines**
   - Scroll to "Journal lines" section
   - For each line:
     - **Account**: Select from dropdown
     - **Description**: Optional line description
     - **Debit Amount**: Enter if debit, otherwise leave 0
     - **Credit Amount**: Enter if credit, otherwise leave 0
     - **Department/Project/Cost Center**: Optional
   - Click "Add another Journal line" for more lines

4. **Save**
   - Click "Save" button
   - System auto-calculates totals
   - Check "Imbalance" field - should show "✓ Balanced (0.00)"

#### Option 2: Web Interface (User-Friendly)

1. **Navigate to Manual Journals**
   - Go to `/accounting/manual-journals/`
   - Click "New Journal Entry"

2. **Fill Form**
   - Enter header details (same as admin)
   - Add lines in the table
   - Real-time balance calculation shows at bottom
   - Balance status updates automatically

3. **Create**
   - Click "Create Journal"
   - System validates and saves
   - Redirects to journal list

### Posting a Journal Entry

**Prerequisites:**
- Journal must be balanced (Debit = Credit)
- Period must be open
- You must have "Can post journal" permission

**Steps:**

1. **View Journal Detail**
   - From journal list, click journal number
   - Or click "View" button

2. **Review**
   - Check all lines are correct
   - Verify balance status shows "Balanced"
   - Check totals

3. **Post**
   - Click "Post Journal" button
   - Confirm the action
   - System:
     - Validates journal
     - Creates General Ledger entries
     - Updates account balances
     - Locks journal
     - Sets status to "Posted"

### Editing a Journal

- **Draft Journals Only**: Can be edited
- **Posted Journals**: Cannot be edited (locked)

**To Edit:**
1. Go to journal detail page
2. Click "Edit" button
3. Modify as needed
4. Click "Update Journal"
5. Re-post if needed

## Reports

### Trial Balance

**Purpose**: Verify that total debits equal total credits across all accounts.

**Access**: `/accounting/advanced-reports/trial-balance/`

**Usage:**
1. Select "As of" date
2. Click "Filter" or press Enter
3. Report shows:
   - Account code and name
   - Account type
   - Debit balance
   - Credit balance
   - Link to drill down to ledger

4. **Check Balance**:
   - Look at totals section
   - Should see "Balanced ✓" if debits = credits
   - "Out of Balance ⚠" if not matched

5. **Drill Down**:
   - Click "Ledger" link next to any account
   - Opens General Ledger filtered to that account

6. **Export**:
   - Click CSV, Excel, or PDF button
   - Download report

### General Ledger

**Purpose**: View all transactions for accounts with running balances.

**Access**: `/accounting/reports/general-ledger/`

**Usage:**
1. Select date range (Start Date and End Date)
2. (Optional) Select specific account
3. Click "Filter"
4. Report shows:
   - Date of transaction
   - Account code and name
   - Journal number (clickable)
   - Reference
   - Description
   - Debit amount
   - Credit amount
   - Running balance

5. **Click Journal Number**:
   - Opens journal detail
   - View full journal entry

6. **Export**:
   - Click CSV, Excel, or PDF
   - Download report

## Common Workflows

### Workflow 1: Recording Expense Payment

**Example**: Paid $500 office rent by check

1. Create Journal Entry
2. Header:
   - Type: General Journal
   - Date: Payment date
   - Description: "Office rent payment - January 2025"
3. Lines:
   - Line 1: Debit "Rent Expense" $500
   - Line 2: Credit "Cash in Bank" $500
4. Save and Post

### Workflow 2: Recording Revenue

**Example**: Received $1,000 for services

1. Create Journal Entry
2. Header:
   - Type: General Journal
   - Date: Receipt date
   - Description: "Service revenue - Client ABC"
3. Lines:
   - Line 1: Debit "Cash" $1,000
   - Line 2: Credit "Service Revenue" $1,000
4. Save and Post

### Workflow 3: Adjusting Entry

**Example**: Accrue $300 unpaid salary

1. Create Journal Entry
2. Header:
   - Type: General Journal
   - Date: End of period
   - Description: "Accrued salaries - December 2025"
3. Lines:
   - Line 1: Debit "Salary Expense" $300
   - Line 2: Credit "Salaries Payable" $300
4. Save and Post

### Workflow 4: Month-End Trial Balance

1. Navigate to Trial Balance report
2. Select last day of month as "As of" date
3. Review balances
4. Check that report shows "Balanced ✓"
5. If imbalanced:
   - Review journal entries for the period
   - Check for missing or incorrect postings
   - Correct and re-post
6. Export for records
7. Archive PDF with month-end documents

## Troubleshooting

### Problem: Journal Won't Post

**Symptoms**: Error message when clicking "Post Journal"

**Solutions:**
1. **Check Balance**:
   - Total Debit must equal Total Credit
   - Review imbalance amount
   - Add/adjust lines to balance

2. **Check Period**:
   - Period must be "Open"
   - If closed, reopen period (with permission)
   - Or change journal date to open period

3. **Check Permissions**:
   - User must have "Can post journal" permission
   - Contact administrator if needed

4. **Check Journal Date**:
   - Must fall within selected period dates
   - Adjust date or period

### Problem: Trial Balance Not Balanced

**Symptoms**: Difference is not 0.00

**Solutions:**
1. **Review Recent Journals**:
   - Check journals posted in period
   - Look for incomplete entries
   - Verify all lines have account assigned

2. **Check Draft Journals**:
   - Unposted journals don't appear in GL
   - Post all completed journals

3. **Review GL Entries**:
   - Use General Ledger report
   - Look for orphaned entries
   - Check for duplicate postings

4. **Contact Support**:
   - If issue persists, export trial balance
   - Note difference amount
   - Contact IT/Accounting support

### Problem: Can't Edit Journal

**Symptoms**: Edit button disabled or missing

**Solutions:**
1. **Check Status**:
   - Only "Draft" journals can be edited
   - Posted journals are locked
   - View status in detail page

2. **Check Permissions**:
   - Need "Can change voucher entry" permission
   - Contact administrator

3. **Reverse and Re-Enter**:
   - For posted journals, use reversal function
   - Create new correcting entry

## Best Practices

### 1. Descriptive Information
- Use clear, specific descriptions
- Include reference numbers
- Note source documents

### 2. Consistent Numbering
- Use reference field for internal tracking
- Follow organizational naming convention
- Examples: "ADJ-2025-001", "REV-INV-1234"

### 3. Review Before Posting
- Double-check all amounts
- Verify account selections
- Confirm balance is zero
- Review period and date

### 4. Regular Reconciliation
- Run trial balance at month-end
- Review general ledger for key accounts
- Compare to source documents
- Investigate discrepancies immediately

### 5. Backup Documentation
- Export and save reports monthly
- Keep PDF copies of trial balance
- Archive general ledger reports
- Document adjusting entries

### 6. Period Management
- Close periods promptly after review
- Don't post to closed periods
- Use next period for corrections
- Document period-end procedures

## Procurement & Landed Cost

- Purchase invoice lines already capture optional PO and receipt references; use `perform_three_way_match` with PO/receipt snapshots to flag over/short/price variances.
- To capitalise freight or duty after a bill is posted:
  1. Post the purchase invoice with a warehouse and GR/IR account so inventory is received.
  2. Go to `/admin/accounting/landedcostdocument/` and add a Landed Cost document for that invoice (basis by value or quantity, currency/exchange rate defaults to the invoice but can be overridden).
  3. Add one or more cost lines (shipping, duty, insurance) and pick the payable/expense account to credit.
  4. Use the “Apply landed cost” admin action: the system spreads cost across inventory lines, debits inventory, credits the selected account, posts a journal using the invoice exchange rate, and updates `InventoryItem.unit_cost` with a new weighted cost.
- Confirm impact by reviewing the landed cost journal and the updated inventory valuation (Stock Ledger + InventoryItem).

## Quick Reference

### Journal Entry Rules
- ✅ Every journal must balance (Debit = Credit)
- ✅ Every line has ONE side: debit OR credit
- ✅ At least one line required
- ✅ Journal date must be in selected period
- ✅ Period must be open for posting
- ❌ Cannot edit posted journals
- ❌ Cannot post unbalanced journals

### Account Types
- **Assets**: Normal balance = Debit (e.g., Cash, Accounts Receivable)
- **Liabilities**: Normal balance = Credit (e.g., Accounts Payable, Loans)
- **Equity**: Normal balance = Credit (e.g., Capital, Retained Earnings)
- **Revenue**: Normal balance = Credit (e.g., Sales, Service Revenue)
- **Expenses**: Normal balance = Debit (e.g., Rent, Salaries, Utilities)

### Keyboard Shortcuts (in forms)
- **Tab**: Move to next field
- **Shift+Tab**: Move to previous field
- **Enter**: Submit form (be careful!)
- **Ctrl+S**: Save (if enabled)

---

## Need Help?

- **Documentation**: See `ACCOUNTING_IMPLEMENTATION_SUMMARY.md`
- **Admin**: Contact your system administrator
- **Support**: Submit ticket with error details and screenshots

---

**Last Updated**: December 4, 2025
