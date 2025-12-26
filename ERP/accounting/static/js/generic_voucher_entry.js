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

    const focusNextInput = (current) => {
        if (!current) return;
        const form = current.closest('form') || voucherForm;
        if (!form) return;
        const focusables = Array.from(form.querySelectorAll('input, select, textarea'))
            .filter(el => !el.disabled && el.type !== 'hidden' && el.offsetParent !== null);
        const idx = focusables.indexOf(current);
        if (idx >= 0 && idx < focusables.length - 1) {
            const next = focusables[idx + 1];
            next.focus();
            if (typeof next.select === 'function') next.select();
        }
    };

    const debounce = (fn, delay = 200) => {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    };

    const displayText = (r) => {
        if (!r) return '';
        const text = r.text || r.display || r.label;
        if (text) return String(text);
        const code = (r.code || r.account_code || r.item_code || '').toString();
        const name = (r.name || r.account_name || r.display_name || '').toString();
        const joined = `${code}${code && name ? ' - ' : ''}${name}`.trim();
        return joined || name || code;
    };

    const ADD_NEW_HANDLERS = {
        account: () => window.open('/accounting/chart-of-accounts/create/', '_blank'),
        costcenter: () => window.open('/accounting/cost-centers/create/', '_blank'),
        department: () => window.open('/accounting/departments/create/', '_blank'),
        project: () => window.open('/accounting/projects/create/', '_blank'),
    };

        const outsideHandler = (evt) => {
            if (!container || !anchor) return;
            if (container.contains(evt.target) || anchor.contains(evt.target)) return;
            close();
        };

        const render = () => {
            if (!container || !listEl) return;
            const addLabel = (onAddNew && onAddNew.label) ? onAddNew.label : '+ Add New';
            const addMeta = (onAddNew && onAddNew.meta) ? onAddNew.meta : '';
            const total = items.length + (onAddNew ? 1 : 0);
            listEl.innerHTML = '';
            items.forEach((item, idx) => {
                const div = document.createElement('div');
                div.className = 've-suggest-item';
                if (idx === activeIndex) div.classList.add('active');
                div.innerHTML = `<div class="ve-title">${displayText(item)}</div><div class="ve-sub">${item.path || item.meta || ''}</div>`;
                div.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    if (onSelect) onSelect(item);
                    close();
                });
                listEl.appendChild(div);
            });
            if (onAddNew) {
                const addDiv = document.createElement('div');
                addDiv.className = 've-suggest-item ve-add-new';
                if (activeIndex === total - 1) addDiv.classList.add('active');
                addDiv.innerHTML = `<div class="ve-title">${addLabel}</div>${addMeta ? `<div class="ve-sub">${addMeta}</div>` : ''}`;
                addDiv.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    if (typeof onAddNew.handler === 'function') onAddNew.handler();
                    close();
                });
                listEl.appendChild(addDiv);
            }
        };

        const open = (inputEl, choices, meta = {}) => {
            ensure();
            anchor = inputEl;
            items = Array.isArray(choices) ? choices : [];
            onSelect = meta.onSelect;
            onAddNew = meta.onAddNew;
            activeIndex = 0;
            render();
            position();
            container.classList.add('open');
            window.addEventListener('resize', position);
            window.addEventListener('scroll', position, true);
            document.addEventListener('click', outsideHandler, true);
        };

        const move = (delta) => {
            if (!items.length && !onAddNew) return;
            const total = items.length + (onAddNew ? 1 : 0);
            activeIndex = (activeIndex + delta + total) % total;
            render();
        };

        const selectActive = () => {
            const total = items.length + (onAddNew ? 1 : 0);
            if (!total) return;
            if (activeIndex === items.length) {
                if (onAddNew && typeof onAddNew.handler === 'function') onAddNew.handler();
                close();
                return;
            }
            const choice = items[activeIndex];
            if (choice && typeof onSelect === 'function') onSelect(choice);
            close();
        };

        const isOpenFor = (el) => container && container.classList.contains('open') && anchor === el;

        return { open, close, move, selectActive, isOpenFor };
    })();

    const normalizeHiddenName = (displayInput) => {
        if (!displayInput) return null;
        const fromName = displayInput.name ? displayInput.name.replace(/_display$/, '') : null;
        const raw = displayInput.dataset.hiddenName;
        if (raw && fromName && raw !== fromName && !raw.includes('-') && fromName.includes('-')) {
            return fromName;
        }
        return raw || fromName;
    };

    const resolveTypeaheadHidden = async (displayInput, raw) => {
        if (!displayInput) return;
        const endpoint = displayInput.dataset.endpoint;
        if (!endpoint) return;
        if (shouldBackoff(endpoint)) return;
        const hidden = getHiddenInput(displayInput);
        if (!hidden) return;

        const q = (raw || '').toString().trim();
        if (!q) return;
        try {
            const token = q.split(' - ')[0].trim();
            const search = token || q;
            const resp = await fetch(
                `${endpoint}?q=${encodeURIComponent(search)}&limit=10`,
                {
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                },
            );
            const payload = await parseJsonResponse(resp, endpoint);
            if (!payload) return;
            const results = (payload && payload.results) ? payload.results : [];
            const qLower = q.toLowerCase();
            const tokenLower = (token || '').toLowerCase();
            const found =
                results.find(r => (r.code || '').toString().toLowerCase() === qLower) ||
                (tokenLower ? results.find(r => (r.code || '').toString().toLowerCase() === tokenLower) : null) ||
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

    const getHiddenInput = (displayInput) => {
        const hiddenName = normalizeHiddenName(displayInput);
        if (!hiddenName || !voucherForm) return null;
        let hidden = null;
        try {
            hidden = voucherForm.querySelector(`input[type="hidden"][name="${CSS.escape(hiddenName)}"]`);
        } catch (err) {
            hidden = null;
        }
        if (hidden) return hidden;

        const raw = displayInput?.dataset?.hiddenName;
        if (!raw) return null;
        const row = displayInput.closest('.generic-line-row') || displayInput.closest('tr') || displayInput.closest('.grid-cell');
        if (row) {
            hidden = row.querySelector(`input[type="hidden"][name$="-${raw}"]`);
            if (hidden) return hidden;
            hidden = row.querySelector(`input[type="hidden"][name$="${raw}"]`);
            if (hidden) return hidden;
        }
        return null;
    };

    const selectLookupResult = (inputEl, choice) => {
        const hidden = getHiddenInput(inputEl);
        inputEl.value = displayText(choice);
        if (hidden) {
            hidden.value = choice?.id || choice?.value || '';
            triggerInput(hidden);
        }
        triggerInput(inputEl);
        AccountSuggest.close();
        focusNextInput(inputEl);
    };

    const rateLimitUntil = new Map();

    const shouldBackoff = (endpoint) => {
        const until = rateLimitUntil.get(endpoint);
        return until && until > Date.now();
    };

    const recordRateLimit = (endpoint, resp) => {
        if (!endpoint) return;
        let retryAfter = 2;
        const header = resp.headers.get('Retry-After');
        if (header) {
            const parsed = Number.parseFloat(header);
            if (!Number.isNaN(parsed)) {
                retryAfter = parsed;
            }
        }
        rateLimitUntil.set(endpoint, Date.now() + Math.max(1, retryAfter) * 1000);
    };

    const parseJsonResponse = async (resp, endpoint) => {
        if (!resp) return null;
        const ct = (resp.headers.get('content-type') || '').toLowerCase();
        if (resp.status === 429) {
            recordRateLimit(endpoint, resp);
            console.warn('Typeahead lookup rate limited', endpoint);
            return null;
        }
        if (resp.status === 401 || resp.status === 403) {
            console.warn('Typeahead lookup unauthorized', endpoint);
            return null;
        }
        if (resp.redirected && resp.url && resp.url.includes('/accounts/login')) {
            console.warn('Typeahead lookup redirected to login', endpoint);
            return null;
        }
        if (!ct.includes('application/json')) {
            try {
                const txt = await resp.text();
                console.warn('Typeahead lookup non-JSON response', resp.status, endpoint, txt.slice(0, 120));
            } catch (err) {
                console.warn('Typeahead lookup non-JSON response', resp.status, endpoint);
            }
            return null;
        }
        try {
            return await resp.json();
        } catch (err) {
            console.warn('Typeahead lookup JSON parse failed', err, endpoint);
            return null;
        }
    };

    const fetchSuggestions = async (term, endpoint) => {
        if (!endpoint || !term) return [];
        if (shouldBackoff(endpoint)) return [];
        try {
            const resp = await fetch(
                `${endpoint}?q=${encodeURIComponent(term)}&limit=10`,
                {
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                },
            );
            if (!resp.ok && resp.status !== 429) return [];
            const data = await parseJsonResponse(resp, endpoint);
            if (Array.isArray(data?.results)) return data.results;
            return [];
        } catch (err) {
            console.warn('lookup fetch failed', err);
            return [];
        }
    };

    const buildAddNewMeta = (inputEl) => {
        const kind = (inputEl.dataset.lookupKind || '').toLowerCase();
        const addUrl = inputEl.dataset.addUrl;
        const handler = addUrl ? () => window.open(addUrl, '_blank') : (ADD_NEW_HANDLERS[kind] || null);
        if (!handler) return null;
        const labelMap = {
            account: '+ Add New Account',
            costcenter: '+ Add New Cost Center',
            department: '+ Add New Department',
            project: '+ Add New Project',
            taxcode: '+ Add New Tax Code',
            vendor: '+ Add New Vendor',
            supplier: '+ Add New Vendor',
            customer: '+ Add New Customer',
            client: '+ Add New Customer',
            product: '+ Add New Product',
            item: '+ Add New Product',
            service: '+ Add New Product',
            inventoryitem: '+ Add New Product',
        };
        const metaMap = {
            account: 'Opens Chart of Accounts',
            costcenter: 'Opens Cost Centers',
            department: 'Opens Departments',
            project: 'Opens Projects',
            taxcode: 'Opens Tax Codes',
            vendor: 'Opens Vendors',
            supplier: 'Opens Vendors',
            customer: 'Opens Customers',
            client: 'Opens Customers',
            product: 'Opens Products',
            item: 'Opens Products',
            service: 'Opens Products',
            inventoryitem: 'Opens Products',
        };
        return { label: labelMap[kind] || '+ Add New', meta: metaMap[kind] || '', handler };
    };

    const bindSuggestInput = (inputEl) => {
        if (!inputEl || inputEl._suggestBound) return;
        inputEl._suggestBound = true;
        const runSuggest = debounce(async () => {
            const term = (inputEl.value || '').trim();
            if (!term) {
                AccountSuggest.close();
                return;
            }
            const endpoint = inputEl.dataset.endpoint;
            const suggestions = await fetchSuggestions(term, endpoint);
            if (!suggestions.length && !buildAddNewMeta(inputEl)) {
                AccountSuggest.close();
                return;
            }
            AccountSuggest.open(inputEl, suggestions, {
                onSelect: (choice) => selectLookupResult(inputEl, choice),
                onAddNew: buildAddNewMeta(inputEl),
            });
        }, 180);

        inputEl.addEventListener('input', runSuggest);
        inputEl.addEventListener('focus', runSuggest);
        inputEl.addEventListener('keydown', (e) => {
            if (AccountSuggest.isOpenFor(inputEl)) {
                if (e.key === 'ArrowDown') { e.preventDefault(); AccountSuggest.move(1); return; }
                if (e.key === 'ArrowUp') { e.preventDefault(); AccountSuggest.move(-1); return; }
                if (e.key === 'Enter') { e.preventDefault(); AccountSuggest.selectActive(); return; }
                if (e.key === 'Escape') { e.preventDefault(); AccountSuggest.close(); return; }
            }
        });

        inputEl.addEventListener('blur', () => {
            const hidden = getHiddenInput(inputEl);
            if (hidden && !hidden.value && (inputEl.value || '').trim()) {
                resolveTypeaheadHidden(inputEl, inputEl.value);
            }
            setTimeout(() => {
                if (!AccountSuggest.isOpenFor(inputEl)) return;
                AccountSuggest.close();
            }, 200);
        });
    };

    const initSuggestInputs = (scope = document) => {
        const candidates = scope.querySelectorAll('.account-typeahead, .generic-typeahead, .ve-suggest-input');
        candidates.forEach(bindSuggestInput);
    };

    const updateSummary = () => {
        const rows = Array.from(linesContainer.querySelectorAll('.generic-line-row'));
        const linesData = rows.map(row => ({
            debit_amount: row.querySelector('input[name$="-debit_amount"]')?.value || '0',
            credit_amount: row.querySelector('input[name$="-credit_amount"]')?.value || '0',
            quantity: row.querySelector('input[name$="-quantity"]')?.value || '0',
            DELETE: row.querySelector('input[name$="-DELETE"]')?.checked || false
        }));
        const chargesData = []; // If charges are present, collect them
        htmx.ajax('POST', `/accounting/generic-voucher/${voucherCode}/summary/`, {
            values: { lines: JSON.stringify(linesData), charges: JSON.stringify(chargesData) },
            target: '#summary-container' // Assume a container for summary
        });
    };
        if (countLabel) {
            countLabel.textContent = `Showing ${total} line${total === 1 ? '' : 's'}`;
        }

        if (totalFormsInput) {
            totalFormsInput.value = total;
        }

        const debitEl = document.getElementById('summary-total-debit');
        const creditEl = document.getElementById('summary-total-credit');
        const diffEl = document.getElementById('summary-total-diff');
        const qtyEl = document.getElementById('summary-total-qty');
        const lineEl = document.getElementById('summary-line-total');
        if (debitEl) debitEl.textContent = formatNumber(totalDebit, 2);
        if (creditEl) creditEl.textContent = formatNumber(totalCredit, 2);
        if (diffEl) diffEl.textContent = formatNumber(totalDebit - totalCredit, 2);
        if (qtyEl) qtyEl.textContent = formatNumber(totalQty, 2);
        if (lineEl) lineEl.textContent = formatNumber(totalLine, 2);
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

        if (AccountSuggest.isOpenFor(target)) {
            if (e.key === 'ArrowDown') { e.preventDefault(); AccountSuggest.move(1); return; }
            if (e.key === 'ArrowUp') { e.preventDefault(); AccountSuggest.move(-1); return; }
            if (e.key === 'Enter') { e.preventDefault(); AccountSuggest.selectActive(); return; }
            if (e.key === 'Escape') { e.preventDefault(); AccountSuggest.close(); return; }
        }

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

    const formatNumber = (val, places = 2) => {
        const num = Number.isFinite(val) ? val : 0;
        return num.toFixed(places);
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
            showStatus('Importing CSV...', 'info');
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
            initSuggestInputs(event.detail.target);

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
    initSuggestInputs(document);
    // Header inputs: add data-hkey attributes (for keyboard helpers and consistent selectors)
    const initHeaderHkeys = () => {
        try {
            const form = document.getElementById('voucher-form') || document.querySelector('form');
            if (!form) return;
            const headerSection = form.querySelector('.header-card');
            if (!headerSection) return;
            headerSection.querySelectorAll('input[name], select[name], textarea[name]').forEach(el => {
                const name = el.name || '';
                // Attempt to map names like header-date or header[date] or date
                let key = name.replace(/^.*\[([^\]]+)\].*$/, '$1');
                if (!key || key === name) {
                    // fallback strip prefix before last '-'
                    const parts = name.split('-');
                    key = parts.length > 1 ? parts.slice(-1)[0] : name;
                }
                if (key) {
                    el.setAttribute('data-hkey', key);
                }
            });
        } catch (err) {
            // non-fatal
            console.warn('initHeaderHkeys failed', err);
        }
    };
    // run once on load
    initHeaderHkeys();
    document.addEventListener('htmx:afterSwap', (e) => {
        // re-run when header swapped via HTMX
        initHeaderHkeys();
        if (e.detail && e.detail.target) {
            initSuggestInputs(e.detail.target);
        }
    });
    
    /*
     * When server returns 422 (validation failed) HTMX fires `htmx:responseError`.
     * By default HTMX will not swap the response into the DOM for error statuses.
     * Here we handle 422 responses and inject the server-rendered panel HTML
     * into `#generic-voucher-panel`, re-initialize relevant behaviours and
     * focus/scroll the first invalid field so the user sees validation feedback.
     */
    const focusFirstInvalidPanel = () => {
        try {
            const panel = document.getElementById('generic-voucher-panel');
            if (!panel) return false;

            // Prefer explicit field-level feedback
            const feedback = panel.querySelector('.invalid-feedback.d-block');
            if (feedback) {
                // 1) try to find a nearby visible input/select/textarea
                let field = feedback.closest('div')?.querySelector('input, select, textarea');
                // 2) previous sibling fallback
                if (!field) {
                    const prev = feedback.previousElementSibling;
                    if (prev && ['INPUT', 'SELECT', 'TEXTAREA'].includes(prev.tagName)) field = prev;
                }
                // 3) try to find a display input and resolve to hidden input (typeahead/display patterns)
                if (!field) {
                    const display = feedback.closest('.form-group, .grid-cell, .header-card')?.querySelector('input[name$="_display"], input[data-hidden-name], .dual-calendar__ad, .dual-calendar__bs');
                    if (display) {
                        // if display found, try to get the hidden real input
                        const hidden = getHiddenInput(display) || display;
                        field = hidden || display;
                        // if display is a dual-calendar visible input, focus that instead
                        if (display.classList && (display.classList.contains('dual-calendar__ad') || display.classList.contains('dual-calendar__bs'))) {
                            field = display;
                        }
                    }
                }
                // 4) fallback to any already-marked invalid field or first input
                if (!field) {
                    field = panel.querySelector('input.is-invalid, select.is-invalid, textarea.is-invalid') || panel.querySelector('input, select, textarea');
                }

                if (field) {
                    try { field.focus({ preventScroll: false }); } catch (e) { field.focus(); }
                    try { field.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {}
                    field.classList.add('is-invalid');
                    field.setAttribute('aria-invalid', 'true');
                    return true;
                }
            }

            // If there are line-level errors, focus first offending row
            const errRow = panel.querySelector('.table-danger, .error-row');
            if (errRow) {
                const field = errRow.querySelector('input, select, textarea');
                if (field) {
                    try { field.focus({ preventScroll: false }); } catch (e) { field.focus(); }
                    try { field.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {}
                    return true;
                }
            }

            // Finally, scroll to and highlight the top alert if present
            const alert = panel.querySelector('.alert-danger, .alert-warning');
            if (alert) {
                try { alert.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {}
                return true;
            }
        } catch (err) {
            console.warn('focusFirstInvalidPanel failed', err);
        }
        return false;
    };

    const applyInvalidFeedbackClasses = (panel) => {
        try {
            if (!panel) panel = document.getElementById('generic-voucher-panel');
            if (!panel) return;
            const feedbacks = Array.from(panel.querySelectorAll('.invalid-feedback.d-block'));
            feedbacks.forEach((fb) => {
                // find associated field and mark invalid + aria
                const findField = () => {
                    // 1. try immediate previous input/select/textarea
                    let prev = fb.previousElementSibling;
                    for (let i = 0; i < 6 && prev; i += 1) {
                        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(prev.tagName)) return prev;
                        const inner = prev.querySelector('input, select, textarea');
                        if (inner) return inner;
                        prev = prev.previousElementSibling;
                    }
                    // 2. look for display inputs (typeahead) in same group and resolve hidden
                    const group = fb.closest('.form-group, .grid-cell, .header-card');
                    if (group) {
                        const display = group.querySelector('input[name$="_display"], input[data-hidden-name]');
                        if (display) {
                            const hidden = getHiddenInput(display) || display;
                            return hidden || display;
                        }
                        // dual-calendar special case
                        const dual = group.querySelector('.dual-calendar__ad, .dual-calendar__bs');
                        if (dual) return dual;
                    }
                    // 3. search parent container for any input/select/textarea
                    const p = fb.parentElement;
                    if (p) {
                        const inner = p.querySelector('input, select, textarea');
                        if (inner) return inner;
                    }
                    // 4. walk up ancestors and look for inputs nearby
                    let anc = fb.parentElement;
                    for (let depth = 0; depth < 6 && anc; depth += 1) {
                        const inner = anc.querySelector('input, select, textarea');
                        if (inner) return inner;
                        anc = anc.parentElement;
                    }
                    return null;
                };
                const field = findField();
                if (field) {
                    field.classList.add('is-invalid');
                    field.setAttribute('aria-invalid', 'true');
                    if (!fb.id) fb.id = `fv_err_${Math.random().toString(36).slice(2, 9)}`;
                    try { field.setAttribute('aria-describedby', fb.id); } catch (e) {}
                    // if we marked a hidden input, also mark its visible display counterpart
                    try {
                        if (field.type === 'hidden') {
                            const display = panel.querySelector(`input[name="${CSS.escape(field.name + '_display')}"]`) || panel.querySelector(`input[data-hidden-name='${CSS.escape(field.name)}']`);
                            if (display) display.classList.add('is-invalid');
                        }
                    } catch (e) {}
                }
            });
        } catch (err) {
            console.warn('applyInvalidFeedbackClasses failed', err);
        }
    };

    document.body.addEventListener('htmx:responseError', (evt) => {
        try {
            const xhr = evt.detail && evt.detail.xhr;
            if (!xhr) return;
            // Treat 422 as validation response and swap into panel
            if (xhr.status === 422) {
                const panel = document.getElementById('generic-voucher-panel');
                if (!panel) return;
                panel.innerHTML = xhr.responseText;

                // re-init behaviours for swapped content
                reindexRows();
                updateSummary();
                initColumnResizers();
                initSuggestInputs(panel);
                initHeaderHkeys();

                // apply server-rendered invalid-feedback mapping (adds is-invalid, aria attributes)
                try { applyInvalidFeedbackClasses(panel); } catch (e) { /* non-fatal */ }

                // focus first invalid control
                setTimeout(() => focusFirstInvalidPanel(), 50);
            }
        } catch (err) {
            console.warn('htmx responseError handler failed', err);
        }
    });
})();

// New enhancements
// Set attributes on load
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[type="number"]').forEach(input => {
        input.setAttribute('min', '0.01');
        input.setAttribute('step', '0.01');
    });
});

// Inline validation
document.addEventListener('blur', (e) => {
    if (e.target.classList.contains('required') && !e.target.value) {
        e.target.classList.add('is-invalid');
    }
});

// Toasts
function showToast(message, type) {
    const toast = document.getElementById(`${type}-toast`);
    if (toast) {
        toast.textContent = message;
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3000);
    }
}

// Confirmations
function confirmAction(action, url) {
    const modal = document.getElementById('confirm-delete-modal');
    if (modal) {
        modal.style.display = 'block';
        document.getElementById('confirm-delete-btn').onclick = () => {
            // Perform action
            modal.style.display = 'none';
        };
    }
}

// beforeUnload
window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedChanges()) e.preventDefault();
});

function hasUnsavedChanges() {
    // Check if form has changes
    return false; // Placeholder
}
