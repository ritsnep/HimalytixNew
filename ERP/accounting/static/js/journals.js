document.addEventListener('DOMContentLoaded', function() {
    const journalTypeEl = document.getElementById('journal-type');
    if (!journalTypeEl) return;

    const journalType = journalTypeEl.value;
    const table = document.getElementById('journal-table');
    const tbody = table.querySelector('tbody');
    const addRowBtn = document.getElementById('add-row');
    const descriptionTextarea = document.getElementById('description');
    const charCount = document.querySelector('small.form-text');

    let lineCounter = 1;

    const journalConfigs = {
        'General Journal': ['Date', 'Account Title & Code', 'Description', 'Post. Ref.', 'Debit', 'Credit'],
        'Sales Journal': ['Date', 'Invoice Number', 'Customer Name', 'Accounts Receivable (Debit)', 'Sales Revenue (Credit)'],
        'Purchase Journal': ['Date', 'Vendor Name', 'Invoice Number', 'Terms', 'Purchases (Debit)', 'Accounts Payable (Credit)'],
        'Cash Receipts Journal': ['Date', 'Description', 'Cash (Debit)', 'Sales Discounts (Debit)', 'Accounts Receivable (Credit)', 'Sales Revenue (Credit)', 'Other Accounts (Credit)'],
        'Cash Disbursements Journal': ['Date', 'Check Number', 'Description', 'Other Accounts (Debit)', 'Purchase Discounts (Credit)', 'Accounts Payable (Debit)', 'Cash (Credit)'],
        'Cash Payment Journal': ['Date', 'Description', 'Cash (Credit)', 'Other Accounts (Debit)'],
        'Bank Receipt Journal': ['Date', 'Description', 'Bank (Debit)', 'Other Accounts (Credit)'],
        'Bank Payment Journal': ['Date', 'Description', 'Bank (Credit)', 'Other Accounts (Debit)'],
        'Adjustment Journal': ['Date', 'Account Title & Code', 'Description', 'Post. Ref.', 'Debit', 'Credit'],
    };

    const createRow = () => {
        const row = document.createElement('tr');
        const columns = journalConfigs[journalType] || [];
        let html = '';

        columns.forEach(col => {
            if (col.toLowerCase().includes('debit')) {
                html += `<td><input type="number" class="form-control debit" value="0.00" step="0.01"></td>`;
            } else if (col.toLowerCase().includes('credit')) {
                html += `<td><input type="number" class="form-control credit" value="0.00" step="0.01"></td>`;
            } else if (col.toLowerCase().includes('date')) {
                html += `<td><input type="date" class="form-control"></td>`;
            } else {
                html += `<td><input type="text" class="form-control"></td>`;
            }
        });

        html += `<td><button type="button" class="btn btn-danger btn-sm remove-row">X</button></td>`;
        row.innerHTML = html;
        tbody.appendChild(row);
    };

    if (addRowBtn) {
        addRowBtn.addEventListener('click', createRow);
    }

    tbody.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-row')) {
            e.target.closest('tr').remove();
            updateTotals();
        }
    });

    tbody.addEventListener('input', function(e) {
        if (e.target.classList.contains('debit') || e.target.classList.contains('credit')) {
            const row = e.target.closest('tr');
            validateRow(row);
            updateTotals();
        }
    });

    if(descriptionTextarea) {
        descriptionTextarea.addEventListener('input', () => {
            const count = descriptionTextarea.value.length;
            charCount.textContent = `${count}/250`;
        });
    }

    const validateRow = (row) => {
        const debits = Array.from(row.querySelectorAll('.debit')).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);
        const credits = Array.from(row.querySelectorAll('.credit')).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);

        if ((debits > 0 && credits > 0) || (debits === 0 && credits === 0)) {
            row.classList.add('table-danger');
        } else {
            row.classList.remove('table-danger');
        }
    };

    const updateTotals = () => {
        let debitTotal = 0;
        let creditTotal = 0;

        tbody.querySelectorAll('tr').forEach(row => {
            debitTotal += Array.from(row.querySelectorAll('.debit')).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);
            creditTotal += Array.from(row.querySelectorAll('.credit')).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);
        });

        const debitTotalEl = document.getElementById('debit-total');
        const creditTotalEl = document.getElementById('credit-total');

        if (debitTotalEl) debitTotalEl.textContent = debitTotal.toFixed(2);
        if (creditTotalEl) creditTotalEl.textContent = creditTotal.toFixed(2);

        // Update multi-column totals
        const specificTotals = {};
        const footerCells = table.querySelectorAll('tfoot td[id]');
        footerCells.forEach(cell => {
            specificTotals[cell.id] = 0;
        });

        tbody.querySelectorAll('tr').forEach(row => {
            for(const key in specificTotals) {
                const inputName = key.replace('-total', '');
                const input = row.querySelector(`[name="${inputName}"]`);
                if(input) {
                    specificTotals[key] += parseFloat(input.value) || 0;
                }
            }
        });

        for(const key in specificTotals) {
            document.getElementById(key).textContent = specificTotals[key].toFixed(2);
        }


        const balance = debitTotal - creditTotal;
        const balanceEl = document.getElementById('balance');
        balanceEl.textContent = balance.toFixed(2);

        if (balance === 0) {
            balanceEl.classList.remove('text-danger');
            balanceEl.classList.add('text-success');
        } else {
            balanceEl.classList.remove('text-success');
            balanceEl.classList.add('text-danger');
        }
    };

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.target.closest('#journal-table')) {
            e.preventDefault();
            createRow();
        }
    });

    // Initial row
    createRow();
});