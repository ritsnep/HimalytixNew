(function () {
    'use strict';

    const linesContainer = document.getElementById('lines-container');
    if (!linesContainer || !window.htmx) {
        return;
    }

    const voucherForm = document.getElementById('voucher-form') || (linesContainer.closest && linesContainer.closest('form'));
    const totalFormsInput = (voucherForm || document).querySelector('[name$="-TOTAL_FORMS"]');
    const actionStatus = document.getElementById('action-status');
    const actionMessage = document.getElementById('action-status-message');
    const lineEndpoint = linesContainer.dataset.lineEndpoint;
    const voucherCode = linesContainer.dataset.voucherCode || '';

    let statusTimer;
    let pendingCsvImport = null;
    let pendingPaste = null;
    let pendingFocus = null;

    const lineActionButtons = document.querySelectorAll('[data-line-action]');

    const currentRowCount = () => linesContainer.querySelectorAll('.generic-line-row').length;

    const getRows = () => Array.from(linesContainer.querySelectorAll('.generic-line-row'));
    const getRowIndex = (row) => {
        const rows = getRows();
        return rows.indexOf(row);
    };

    const getGridCellsForRow = (row) => Array.from(row.querySelectorAll('.grid-cell'));

    const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

    const triggerInput = (input) => {
        if (!input) return;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
    };

    const displayText = (r) => {
        if (!r) return '';
        const text = r.text || r.display;
        if (text) return String(text);
        const code = (r.code || '').toString();
        const name = (r.name || '').toString();
        const joined = `${code}${code && name ? ' - ' : ''}${name}`.trim();
        return joined || name || code;
    };

    const resolveTypeaheadHidden = async (displayInput, raw) => {
        if (!displayInput) return;
        const endpoint = displayInput.dataset.endpoint;
        if (!endpoint) return;
        const hiddenName = displayInput.dataset.hiddenName || (displayInput.name ? displayInput.name.replace(/_display$/, '') : null);
        if (!hiddenName || !voucherForm) return;
        const hidden = voucherForm.querySelector(`[name="${CSS.escape(hiddenName)}"]`);
        if (!hidden) return;

        const q = (raw || '').toString().trim();
        if (!q) return;
        try {
            const resp = await fetch(`${endpoint}?q=${encodeURIComponent(q)}&limit=10`, { credentials: 'same-origin' });
            const payload = await resp.json();
            const results = (payload && payload.results) ? payload.results : [];
            const qLower = q.toLowerCase();
            const found =
                results.find(r => (r.code || '').toString().toLowerCase() === qLower) ||
                results.find(r => displayText(r).toLowerCase() === qLower) ||
                null;
            if (found) {
                displayInput.value = displayText(found);
                hidden.value = found.id;
                triggerInput(hidden);
            }
        } catch (err) {
            // non-fatal
            console.warn('Typeahead resolve failed', err);
        }
    };

    const updateSummary = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        const total = rows.length;
        let completed = 0;

        const placeholder = document.getElementById('no-lines-placeholder');
        if (placeholder) {
            placeholder.classList.toggle('d-none', total > 0);
        }

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
            row.id = `line-${idx}`;
            const numberCell = row.querySelector('.line-number-cell');
            if (numberCell) numberCell.textContent = `${idx + 1}`;
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
            const accountA = a.querySelector('input[name$="-account_display"], input[name*="-account_display"]')?.value?.trim() || '';
            const accountB = b.querySelector('input[name$="-account_display"], input[name*="-account_display"]')?.value?.trim() || '';
            return accountA.localeCompare(accountB);
        });
        rows.forEach(row => linesContainer.appendChild(row));
        reindexRows();
        updateSummary();
        showStatus('Lines sorted by account', 'success');
    };

    const focusCell = (rowIndex, colIndex) => {
        const rows = getRows();
        const row = rows[rowIndex];
        if (!row) return;
        const cells = getGridCellsForRow(row);
        const cell = cells[colIndex];
        if (!cell) return;
        cell.focus();
        if (typeof cell.select === 'function') {
            cell.select();
        }
    };

    const ensureRowsForTarget = (targetRowCount) => {
        const current = currentRowCount();
        if (targetRowCount <= current) return;
        addLine(targetRowCount - current);
    };

    const parseClipboardMatrix = (text) => {
        const raw = (text || '').replace(/\r/g, '');
        const rows = raw.split('\n').filter(r => r.length);
        return rows.map(r => r.split('\t'));
    };

    const applyPasteMatrix = async () => {
        if (!pendingPaste) return;
        const { startRow, startCol, matrix, requiredRows } = pendingPaste;
        if (currentRowCount() < requiredRows) return;

        const rows = getRows();
        for (let r = 0; r < matrix.length; r += 1) {
            const row = rows[startRow + r];
            if (!row) continue;
            const cells = getGridCellsForRow(row);
            for (let c = 0; c < matrix[r].length; c += 1) {
                const cell = cells[startCol + c];
                if (!cell) continue;
                const raw = (matrix[r][c] ?? '').toString();
                if (cell.type === 'checkbox') {
                    const v = raw.trim().toLowerCase();
                    cell.checked = ['1', 'true', 'yes', 'y', 'on'].includes(v);
                    triggerInput(cell);
                    continue;
                }
                cell.value = raw;
                triggerInput(cell);
                if (cell.classList.contains('account-typeahead') || cell.classList.contains('generic-typeahead')) {
                    // eslint-disable-next-line no-await-in-loop
                    await resolveTypeaheadHidden(cell, raw);
                }
            }
        }

        const lastRow = startRow + matrix.length - 1;
        const lastCol = startCol + (matrix[matrix.length - 1]?.length || 1) - 1;
        pendingPaste = null;
        pendingFocus = { rowIndex: clamp(lastRow, 0, currentRowCount() - 1), colIndex: Math.max(0, lastCol) };
        updateSummary();
    };

    const handleGridKeydown = (e) => {
        const target = e.target;
        if (!target || !target.classList || !target.classList.contains('grid-cell')) return;

        const row = target.closest('.generic-line-row');
        if (!row) return;
        const rowIndex = getRowIndex(row);
        const rowCells = getGridCellsForRow(row);
        const colIndex = rowCells.indexOf(target);
        if (rowIndex < 0 || colIndex < 0) return;

        const maxRow = currentRowCount() - 1;
        const isTextInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';
        const caretAtStart = isTextInput && typeof target.selectionStart === 'number' ? target.selectionStart === 0 : true;
        const caretAtEnd = isTextInput && typeof target.selectionEnd === 'number' ? target.selectionEnd === (target.value || '').length : true;

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            focusCell(clamp(rowIndex - 1, 0, maxRow), colIndex);
            return;
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (rowIndex >= maxRow) {
                pendingFocus = { rowIndex: maxRow + 1, colIndex };
                addLine(1);
                return;
            }
            focusCell(rowIndex + 1, colIndex);
            return;
        }
        if (e.key === 'ArrowLeft') {
            if (!caretAtStart) return;
            e.preventDefault();
            focusCell(rowIndex, clamp(colIndex - 1, 0, rowCells.length - 1));
            return;
        }
        if (e.key === 'ArrowRight') {
            if (!caretAtEnd) return;
            e.preventDefault();
            focusCell(rowIndex, clamp(colIndex + 1, 0, rowCells.length - 1));
            return;
        }
        if (e.key === 'Tab') {
            e.preventDefault();
            if (e.shiftKey) {
                if (colIndex > 0) {
                    focusCell(rowIndex, colIndex - 1);
                } else if (rowIndex > 0) {
                    const prevRow = getRows()[rowIndex - 1];
                    const prevCells = getGridCellsForRow(prevRow);
                    focusCell(rowIndex - 1, Math.max(0, prevCells.length - 1));
                }
            } else {
                if (colIndex < rowCells.length - 1) {
                    focusCell(rowIndex, colIndex + 1);
                } else if (rowIndex < maxRow) {
                    focusCell(rowIndex + 1, 0);
                } else {
                    pendingFocus = { rowIndex: maxRow + 1, colIndex: 0 };
                    addLine(1);
                }
            }
            return;
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            if (e.shiftKey) {
                focusCell(clamp(rowIndex - 1, 0, maxRow), colIndex);
            } else if (rowIndex >= maxRow) {
                pendingFocus = { rowIndex: maxRow + 1, colIndex };
                addLine(1);
            } else {
                focusCell(rowIndex + 1, colIndex);
            }
            return;
        }
        if (e.key === 'Delete' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            removeRow(row);
        }
    };

    const handleGridPaste = (e) => {
        const active = document.activeElement;
        if (!active || !active.classList || !active.classList.contains('grid-cell')) return;
        const row = active.closest('.generic-line-row');
        if (!row) return;
        const rowIndex = getRowIndex(row);
        const rowCells = getGridCellsForRow(row);
        const colIndex = rowCells.indexOf(active);
        if (rowIndex < 0 || colIndex < 0) return;

        const text = e.clipboardData && e.clipboardData.getData('text/plain');
        if (!text) return;
        e.preventDefault();

        const matrix = parseClipboardMatrix(text);
        if (!matrix.length) return;

        const requiredRows = rowIndex + matrix.length;
        pendingPaste = { startRow: rowIndex, startCol: colIndex, matrix, requiredRows };
        ensureRowsForTarget(requiredRows);
        // If no new rows needed, apply immediately.
        applyPasteMatrix();
    };

    const parseNumber = (val) => {
        if (val === null || val === undefined) return 0;
        const n = parseFloat(String(val).replace(/,/g, ''));
        return Number.isFinite(n) ? n : 0;
    };

    const autoBalance = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        if (!rows.length) {
            showStatus('Add at least one line to balance', 'danger');
            return;
        }

        let totalDebit = 0;
        let totalCredit = 0;
        rows.forEach(row => {
            const debit = row.querySelector('input[name$="-debit_amount"], input[name$="-debit"], input[name$="-debit_amount"]');
            const credit = row.querySelector('input[name$="-credit_amount"], input[name$="-credit"], input[name$="-credit_amount"]');
            totalDebit += parseNumber(debit?.value);
            totalCredit += parseNumber(credit?.value);
        });

        const diff = +(totalDebit - totalCredit).toFixed(4);
        if (diff === 0) {
            showStatus('Already balanced', 'success');
            return;
        }

        const lastRow = rows[rows.length - 1];
        const debitInput = lastRow.querySelector('input[name$="-debit_amount"], input[name$="-debit"]');
        const creditInput = lastRow.querySelector('input[name$="-credit_amount"], input[name$="-credit"]');
        if (!debitInput || !creditInput) {
            showStatus('No debit/credit fields found to balance', 'danger');
            return;
        }

        if (diff > 0) {
            // Debit is higher -> increase credit
            creditInput.value = (+parseNumber(creditInput.value) + diff).toFixed(4);
        } else {
            // Credit is higher -> increase debit
            debitInput.value = (+parseNumber(debitInput.value) + Math.abs(diff)).toFixed(4);
        }

        updateSummary();
        showStatus('Auto balance applied to last line', 'success');
    };

    const exportCsv = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        if (!rows.length) {
            showStatus('No lines to export', 'info');
            return;
        }

        const fieldNames = new Set();
        const lineData = rows.map(row => {
            const obj = {};
            row.querySelectorAll('input, select, textarea').forEach(el => {
                if (!el.name) return;
                const m = el.name.match(/lines-\d+-(.+)$/);
                if (!m) return;
                const key = m[1];
                fieldNames.add(key);
                obj[key] = el.value;
            });
            return obj;
        });

        const headers = Array.from(fieldNames);
        const escapeCell = (v) => {
            const s = (v ?? '').toString();
            if (s.includes('"') || s.includes(',') || s.includes('\n') || s.includes('\r')) {
                return '"' + s.replace(/"/g, '""') + '"';
            }
            return s;
        };

        const csv = [
            headers.join(','),
            ...lineData.map(row => headers.map(h => escapeCell(row[h])).join(','))
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `generic_voucher_lines_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showStatus('CSV exported', 'success');
    };

    const ensureCsvInput = () => {
        let input = document.getElementById('generic-voucher-csv-input');
        if (input) return input;
        input = document.createElement('input');
        input.type = 'file';
        input.id = 'generic-voucher-csv-input';
        input.accept = '.csv,text/csv';
        input.classList.add('d-none');
        document.body.appendChild(input);
        return input;
    };

    const importCsv = () => {
        const input = ensureCsvInput();
        input.value = '';
        input.onchange = async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            const text = await file.text();
            const lines = text.split(/\r?\n/).filter(Boolean);
            if (lines.length < 2) {
                showStatus('CSV must have header + rows', 'danger');
                return;
            }
            const headers = lines[0].split(',').map(h => h.trim());
            const rows = lines.slice(1).map(line => {
                // naive CSV split; expects simple exports from this screen
                const cols = line.split(',');
                const obj = {};
                headers.forEach((h, i) => { obj[h] = (cols[i] ?? '').trim().replace(/^"|"$/g, ''); });
                return obj;
            });

            pendingCsvImport = { rows, targetCount: rows.length };
            clearLines();
            addLine(rows.length);
            showStatus('Importing CSV…', 'info');
        };
        input.click();
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
                autoBalance();
                break;
            case 'sort':
                sortLines();
                break;
            case 'import':
                importCsv();
                break;
            case 'export':
                exportCsv();
                break;
            default:
                break;
        }
    };

    const COL_WIDTHS_KEY = `genericVoucherGridColWidths:${voucherCode || 'default'}`;

    const loadColWidths = () => {
        try {
            const raw = window.localStorage ? localStorage.getItem(COL_WIDTHS_KEY) : null;
            return raw ? JSON.parse(raw) : {};
        } catch {
            return {};
        }
    };

    const saveColWidths = (widths) => {
        try {
            if (!window.localStorage) return;
            localStorage.setItem(COL_WIDTHS_KEY, JSON.stringify(widths || {}));
        } catch {
            // ignore
        }
    };

    const applyStoredColWidths = () => {
        const widths = loadColWidths();
        const table = document.getElementById('generic-lines-table');
        if (!table) return;
        table.querySelectorAll('thead th.generic-col-header[data-col-key]').forEach((th) => {
            const key = th.dataset.colKey;
            const w = widths[key];
            if (w && Number.isFinite(w)) {
                th.style.width = `${Math.max(80, Math.round(w))}px`;
            }
        });
    };

    const initColumnResizers = () => {
        const table = document.getElementById('generic-lines-table');
        if (!table) return;

        applyStoredColWidths();
        const widths = loadColWidths();

        table.querySelectorAll('thead th.generic-col-header[data-col-key]').forEach((th) => {
            const handle = th.querySelector('.col-resizer');
            if (!handle || handle._initialized) return;
            handle._initialized = true;

            handle.addEventListener('mousedown', (e) => {
                e.preventDefault();
                const key = th.dataset.colKey;
                const startX = e.clientX;
                const startW = th.getBoundingClientRect().width;
                document.body.classList.add('gv-resizing');

                const onMove = (ev) => {
                    const dx = ev.clientX - startX;
                    const next = Math.max(80, Math.round(startW + dx));
                    th.style.width = `${next}px`;
                    widths[key] = next;
                };

                const onUp = () => {
                    document.body.classList.remove('gv-resizing');
                    window.removeEventListener('mousemove', onMove);
                    window.removeEventListener('mouseup', onUp);
                    saveColWidths(widths);
                };

                window.addEventListener('mousemove', onMove);
                window.addEventListener('mouseup', onUp);
            });
        });
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

    document.body.addEventListener('keydown', handleGridKeydown, true);
    document.body.addEventListener('paste', handleGridPaste, true);

    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail && event.detail.target && event.detail.target.id === 'lines-container') {
            reindexRows();
            updateSummary();

            initColumnResizers();

            if (pendingPaste) {
                applyPasteMatrix();
            }

            if (pendingFocus) {
                const targetRowIndex = pendingFocus.rowIndex;
                const targetColIndex = pendingFocus.colIndex;
                pendingFocus = null;
                // Wait a tick for DOM.
                setTimeout(() => {
                    focusCell(Math.min(targetRowIndex, currentRowCount() - 1), targetColIndex);
                }, 0);
            }

            if (pendingCsvImport && currentRowCount() >= pendingCsvImport.targetCount) {
                const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row')).slice(0, pendingCsvImport.targetCount);
                rows.forEach((rowEl, idx) => {
                    const data = pendingCsvImport.rows[idx] || {};
                    Object.keys(data).forEach(key => {
                        const el = rowEl.querySelector(`[name$="-${CSS.escape(key)}"]`);
                        if (el) el.value = data[key];
                    });
                });
                pendingCsvImport = null;
                updateSummary();
                showStatus('CSV imported (review account links)', 'success');
            }
        }
    });

    updateSummary();
    initColumnResizers();
})();