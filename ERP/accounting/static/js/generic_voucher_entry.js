(function () {
    'use strict';

    const linesContainer = document.getElementById('lines-container');
    if (!linesContainer || !window.htmx) {
        return;
    }

    const totalFormsInput = linesContainer.querySelector('[name$="-TOTAL_FORMS"]');
    const actionStatus = document.getElementById('action-status');
    const actionMessage = document.getElementById('action-status-message');
    const lineEndpoint = linesContainer.dataset.lineEndpoint;
    const voucherCode = linesContainer.dataset.voucherCode || '';

    let statusTimer;

    const lineActionButtons = document.querySelectorAll('[data-line-action]');

    const currentRowCount = () => linesContainer.querySelectorAll('.generic-line-row').length;

    const updateSummary = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        const total = rows.length;
        let completed = 0;

        rows.forEach(row => {
            const inputs = row.querySelectorAll('input:not([type="hidden"]), select, textarea');
            const hasValue = Array.from(inputs).some(input => input.value && input.value.toString().trim() !== '');
            if (hasValue) {
                completed += 1;
            }
        });

        const incomplete = Math.max(0, total - completed);

        document.getElementById('summary-total-lines').textContent = total;
        document.getElementById('summary-completed-lines').textContent = completed;
        document.getElementById('summary-incomplete-lines').textContent = incomplete;

        const countLabel = document.getElementById('lines-count');
        if (countLabel) {
            countLabel.textContent = `Showing ${total} line${total === 1 ? '' : 's'}`;
        }

        if (totalFormsInput) {
            totalFormsInput.value = total;
        }
    };

    const reindexRows = () => {
        const rows = linesContainer.querySelectorAll('.generic-line-row');
        rows.forEach((row, idx) => {
            row.dataset.lineIndex = idx;
            const badge = row.querySelector('.line-number .badge');
            if (badge) {
                badge.textContent = `Line ${idx + 1}`;
            }
            row.querySelectorAll('input, select, textarea').forEach(el => {
                if (el.name) {
                    el.name = el.name.replace(/lines-\d+-/, `lines-${idx}-`);
                }
                if (el.id) {
                    el.id = el.id.replace(/lines-\d+-/, `lines-${idx}-`);
                }
            });
            row.querySelectorAll('label').forEach(label => {
                if (label.htmlFor) {
                    label.htmlFor = label.htmlFor.replace(/lines-\d+-/, `lines-${idx}-`);
                }
            });
        });

        if (totalFormsInput) {
            totalFormsInput.value = rows.length;
        }
    };

    const showStatus = (message, type = 'info') => {
        if (!actionStatus || !actionMessage) return;
        actionMessage.textContent = message;
        actionStatus.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        actionStatus.classList.add(`alert-${type}`);
        clearTimeout(statusTimer);
        statusTimer = setTimeout(() => {
            actionStatus.classList.add('d-none');
        }, 3500);
    };

    const removeRow = (row) => {
        if (!row) return;
        row.remove();
        reindexRows();
        updateSummary();
        showStatus('Line removed', 'warning');
    };

    const addLine = (count = 1) => {
        if (!lineEndpoint) {
            showStatus('Unable to add lines right now', 'danger');
            return;
        }

        for (let i = 0; i < count; i += 1) {
            const index = currentRowCount();
            const url = `${lineEndpoint}?voucher_code=${encodeURIComponent(voucherCode)}&index=${index}`;
            htmx.ajax('GET', url, {
                target: '#lines-container',
                swap: 'beforeend'
            });
        }
    };

    const duplicateLastLine = () => {
        const rows = linesContainer.querySelectorAll('.generic-line-row');
        if (!rows.length) {
            showStatus('Add a line before duplicating', 'danger');
            return;
        }
        const lastRow = rows[rows.length - 1];
        const clone = lastRow.cloneNode(true);
        const inputs = clone.querySelectorAll('input:not([type="hidden"]), select, textarea');
        inputs.forEach(input => {
            if (input.tagName === 'SELECT') {
                input.selectedIndex = lastRow.querySelector(`select[name="${input.name}"]`)?.selectedIndex || 0;
            }
        });
        linesContainer.appendChild(clone);
        reindexRows();
        updateSummary();
        showStatus('Last line duplicated', 'success');
    };

    const clearLines = () => {
        const rows = linesContainer.querySelectorAll('.generic-line-row');
        if (!rows.length) {
            showStatus('Nothing to clear', 'info');
            return;
        }
        rows.forEach(row => row.remove());
        reindexRows();
        updateSummary();
        showStatus('All lines cleared', 'warning');
    };

    const sortLines = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        rows.sort((a, b) => {
            const accountA = a.querySelector('select[name*="-account"] option:checked')?.textContent?.trim() || '';
            const accountB = b.querySelector('select[name*="-account"] option:checked')?.textContent?.trim() || '';
            return accountA.localeCompare(accountB);
        });
        rows.forEach(row => linesContainer.appendChild(row));
        reindexRows();
        updateSummary();
        showStatus('Lines sorted by account', 'success');
    };

    const handleQuickAction = (action) => {
        switch (action) {
            case 'add-line':
                addLine();
                break;
            case 'add-ten':
                addLine(10);
                break;
            case 'clear-lines':
                clearLines();
                break;
            case 'duplicate-last':
                duplicateLastLine();
                break;
            case 'auto-balance':
                showStatus('Auto balance will run during save', 'info');
                break;
            case 'sort':
                sortLines();
                break;
            case 'import':
            case 'export':
                showStatus('Import/Export coming soon', 'info');
                break;
            default:
                break;
        }
    };

    document.body.addEventListener('click', (event) => {
        const removeBtn = event.target.closest('.remove-line-btn');
        if (removeBtn) {
            event.preventDefault();
            const row = removeBtn.closest('.generic-line-row');
            removeRow(row);
            return;
        }

        const actionBtn = event.target.closest('[data-line-action]');
        if (actionBtn) {
            event.preventDefault();
            handleQuickAction(actionBtn.dataset.lineAction);
        }
    });

    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail && event.detail.target && event.detail.target.id === 'lines-container') {
            reindexRows();
            updateSummary();
        }
    });

    updateSummary();
})();