# 🚀 Voucher Entry - Quick Reference Card

## 📋 Overview
Create journal vouchers with automatic balance validation and an intuitive interface.

---

## 🎯 Quick Start (3 Steps)

### 1️⃣ Select Configuration
Choose your voucher type from the dropdown:
- **Journal Entry** - General accounting entries
- **Payment Voucher** - Cash/bank payments
- **Receipt Voucher** - Cash/bank receipts

### 2️⃣ Fill Details
**Header Information:**
- ✅ Voucher Date (required)
- ⭕ Reference Number (optional)
- ✅ Narration (required)

**Line Items:**
- ✅ Account (required)
- ⭕ Description (optional)
- Either Debit OR Credit (not both)

### 3️⃣ Verify & Save
- ✅ Check balance indicator shows "Balanced" (green)
- ✅ Click "Save Voucher" or press `Ctrl+Enter`

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl` + `Enter` | 💾 Save voucher |
| `Ctrl` + `L` | ➕ Add new line |
| `Shift` + `?` | ❓ Show help |
| `Tab` | Navigate fields |
| `Escape` | Cancel/Close |

---

## 🎨 Visual Indicators

### Balance Status
| Color | Icon | Meaning |
|-------|------|---------|
| 🟢 Green | ✓ | **Balanced** - Ready to save |
| 🔴 Red | ⚠️ | **Unbalanced** - Fix required |

### Line Numbers
- **Blue circles** (①②③) show line sequence
- Auto-renumber when lines removed

### Required Fields
- **Red asterisk (*)** indicates mandatory

---

## 💡 Pro Tips

### ✨ Adding Lines
1. Click "+ Add Another Line Item" button
2. OR press `Ctrl+L` keyboard shortcut
3. New line appears with auto-incremented number

### 🗑️ Removing Lines
- Click red **×** button on any line (except first)
- Lines automatically renumber
- Must keep at least one line

### 💰 Debit vs Credit
- Entering **Debit** auto-clears **Credit**
- Entering **Credit** auto-clears **Debit**
- Only one can have a value per line

### 🔍 Account Search
- Click account dropdown
- Type to search by code or name
- Select from filtered results

### ⚡ Real-Time Totals
- Totals update instantly as you type
- Balance indicator changes automatically
- Save button enabled only when balanced

---

## 🚨 Common Issues & Fixes

### ❌ Can't Save Voucher
**Problem**: Save button is disabled  
**Solution**: Check balance indicator - debits must equal credits

**Example:**
```
Debit Total:  ₹5,000.00
Credit Total: ₹4,500.00
Status:       ⚠️ Unbalanced (Diff: 500.00)
```
Fix: Add ₹500.00 to credit side or reduce debit by ₹500.00

### ❌ Can't Remove Line
**Problem**: Remove button doesn't work  
**Solution**: You must keep at least one line item

### ❌ Both Debit and Credit Entered
**Problem**: Accidentally entered both amounts  
**Solution**: System auto-clears one when you enter the other

### ❌ Configuration Not Loading
**Problem**: Form doesn't appear after selecting config  
**Solution**: Click "Load Form" button after selecting configuration

---

## 📊 Example Entry

### Scenario: Office Rent Payment

**Header:**
- Date: 2024-01-15
- Reference: INV-2024-001
- Narration: Office rent for January 2024

**Lines:**
| # | Account | Description | Debit | Credit |
|---|---------|-------------|-------|--------|
| ① | Rent Expense | January rent | ₹50,000.00 | - |
| ② | Bank Account | Payment via check | - | ₹50,000.00 |

**Totals:**
- Total Debit: ₹50,000.00
- Total Credit: ₹50,000.00
- Status: ✓ **Balanced**

---

## 🎓 Double-Entry Basics

### Every transaction has 2 sides:
1. **Debit** - What we receive or expense
2. **Credit** - Where it comes from or revenue

### Rule: Debits = Credits
The fundamental accounting equation requires balance.

### Common Patterns:

**Expense Payment:**
```
Debit: Expense Account
Credit: Cash/Bank Account
```

**Revenue Receipt:**
```
Debit: Cash/Bank Account
Credit: Revenue Account
```

**Asset Purchase:**
```
Debit: Asset Account
Credit: Cash/Bank Account
```

---

## 📱 Mobile Use

### Optimized for Touch
- Larger touch targets
- Responsive layout
- Scrollable line items
- Compact design

### Mobile Tips:
- Rotate to landscape for better view
- Use Select2 search for accounts
- Tap outside dropdown to close
- Swipe to scroll line items

---

## 🔒 Permissions Required

### To Create Vouchers:
- ✅ `add_journal` permission

### To Edit Vouchers:
- ✅ `change_journal` permission
- ⚠️ Only DRAFT status can be edited

### To Delete Vouchers:
- ✅ `delete_journal` permission
- ⚠️ Only DRAFT status can be deleted

---

## 🆘 Need Help?

### In-App Help
- Press `Shift+?` for keyboard shortcuts
- Hover over labels for tooltips
- Check help text below fields

### Error Messages
- Red text shows what needs fixing
- Required fields marked with *
- Balance difference shown when unbalanced

### Support Resources
- 📧 Email: support@himalytix.com
- 📚 Full Documentation: docs.himalytix.com
- 🎥 Video Tutorials: tutorials.himalytix.com

---

## 🌟 Best Practices

### 1. Clear Descriptions
Always add meaningful descriptions to line items.
```
Good: "Rent payment for Jan 2024"
Bad:  "Payment"
```

### 2. Consistent References
Use a standard format for reference numbers.
```
Good: INV-2024-001, PAY-2024-045
Bad:  123, ABC, random text
```

### 3. Accurate Dates
Ensure voucher date matches actual transaction date.

### 4. Verify Before Saving
Double-check all amounts and accounts before submitting.

### 5. Use Appropriate Config
Select the right voucher type for your transaction.

---

## 📈 Efficiency Tips

### Speed Up Entry:
1. **Learn keyboard shortcuts** - Save 50% time
2. **Use recently used accounts** - Reduce search time
3. **Copy similar entries** - Use duplicate feature
4. **Create templates** - For recurring transactions
5. **Batch similar transactions** - Group by type

### Accuracy Tips:
1. **Verify totals** - Check green indicator
2. **Review before submit** - Scan all lines
3. **Use descriptive narrations** - Aid future audits
4. **Match source documents** - Cross-verify amounts
5. **Check account codes** - Ensure correct accounts

---

## 🎯 Success Checklist

Before clicking Save, ensure:
- [x] Configuration selected correctly
- [x] Voucher date is accurate
- [x] Narration is descriptive
- [x] All required fields filled
- [x] Accounts selected for all lines
- [x] Amounts entered correctly
- [x] Debit = Credit (green indicator)
- [x] No validation errors shown
- [x] All details reviewed

---

## 📞 Quick Contact

**Technical Issues:**  
🐛 bugs@himalytix.com

**Feature Requests:**  
💡 features@himalytix.com

**Training:**  
🎓 training@himalytix.com

**Emergency Support:**  
📞 +1-xxx-xxx-xxxx

---

**Version**: 1.0  
**Last Updated**: 2024  
**Print this card for easy reference!**

---

<div align="center">

### Made with ❤️ by Himalytix

🏔️ **Elevating Your Accounting Experience**

[Website](https://himalytix.com) | [Documentation](https://docs.himalytix.com) | [Support](https://support.himalytix.com)

</div>
