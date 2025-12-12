(function () {
  const appContainer = document.getElementById('journal-app');
  if (!appContainer) {
    return;
  }

  const addRowEndpoint = appContainer.dataset.addRowEndpoint;
  const duplicateRowEndpoint = appContainer.dataset.duplicateRowEndpoint;
  const bulkAddEndpoint = appContainer.dataset.bulkAddEndpoint;
  const autoBalanceEndpoint = appContainer.dataset.autoBalanceEndpoint;
  const sidePanelEndpoint = appContainer.dataset.sidePanelEndpoint;
  const linesEndpoint = appContainer.dataset.linesEndpoint;
  const journalId = appContainer.dataset.initialJournalId;
  const autoBalanceButton = document.getElementById('auto-balance');
  const columnManagerModalEl = document.getElementById('column-manager-modal');
  const columnManagerList = document.getElementById('column-manager-list');
  const columnManagerForm = document.getElementById('column-manager-form');
  const columnManagerPayload = document.getElementById('column-manager-payload');
  const columnDensitySelect = document.getElementById('column-density-select');
  const accountLookupEndpoint = appContainer.dataset.lookupAccount;
  const costCenterLookupEndpoint = appContainer.dataset.lookupCostCenter;

  const linesTableSelector = '#lines-table';
  let selectedLineIndex = 0;
  let cachedValidationErrors = [];
  let suggestionTimer = null;
  let lookupTimers = {};

  if (autoBalanceButton && autoBalanceButton.dataset.autoBalanceEnabled === 'false') {
    autoBalanceButton.disabled = true;
  }

  function queryCells() {
    return Array.from(document.querySelectorAll(`${linesTableSelector} input, ${linesTableSelector} select`));
  }

  function nextCell(element, direction) {
    const cells = queryCells();
    const idx = cells.indexOf(element);
    if (idx === -1) {
      return null;
    }
    const rowCells = Array.from(element.closest('tr').querySelectorAll('input, select'));
    const cols = rowCells.length;
    let nextIdx;
    switch (direction) {
      case 'right':
        nextIdx = idx + 1;
        break;
      case 'left':
        nextIdx = idx - 1;
        break;
      case 'down':
        nextIdx = idx + cols;
        break;
      case 'up':
        nextIdx = idx - cols;
        break;
      default:
        return null;
    }
    return cells[nextIdx] || null;
  }

  function collectRowValues(row) {
    const values = {};
    row.querySelectorAll('input, select').forEach((field) => {
      const match = field.name && field.name.match(/rows\[\d+\]\[(.+)\]/);
      if (match) {
        values[match[1]] = field.value;
      }
    });
    return values;
  }

  function collectAllRows() {
    const rows = [];
    document.querySelectorAll(`${linesTableSelector} tbody tr`).forEach((row) => {
      rows.push(collectRowValues(row));
    });
    return rows;
  }

  function collectHeaderValues() {
    const headerSection = document.getElementById('journal-header');
    const values = {};
    if (!headerSection) {
      return values;
    }
    headerSection.querySelectorAll('input[name^="header["], select[name^="header["], textarea[name^="header["]').forEach((field) => {
      const match = field.name && field.name.match(/header\[(.+)\]/);
      if (match) {
        values[match[1]] = field.value;
      }
    });
    return values;
  }

  function computeTotals(rows) {
    const totals = { dr: 0, cr: 0 };
    rows.forEach((row) => {
      const debit = parseFloat(row.dr || row.debit || row.debit_amount || 0) || 0;
      const credit = parseFloat(row.cr || row.credit || row.credit_amount || 0) || 0;
      totals.dr += debit;
      totals.cr += credit;
    });
    totals.diff = totals.dr - totals.cr;
    return totals;
  }

  function refreshSidePanel() {
    if (!sidePanelEndpoint) {
      return;
    }
    const payload = {
      rows: collectAllRows(),
      header: collectHeaderValues(),
    };
    htmx.ajax('GET', sidePanelEndpoint, {
      target: '#journal-sidebar',
      swap: 'outerHTML',
      values: {
        journalId: journalId,
        selectedIndex: selectedLineIndex,
        validationErrors: JSON.stringify(cachedValidationErrors),
        payload: JSON.stringify(payload),
      },
    });
  }

  function getColumnMetadata() {
    const metadata = document.getElementById('lines-column-metadata');
    const fallbackDensity = appContainer.dataset.lineDensity || 'comfortable';
    if (!metadata) {
      return { catalog: [], density: fallbackDensity };
    }
    try {
      const parsed = JSON.parse(metadata.dataset.columnCatalog || '{}');
      return {
        catalog: Array.isArray(parsed.catalog) ? parsed.catalog : [],
        density: parsed.density || fallbackDensity,
      };
    } catch (error) {
      return { catalog: [], density: fallbackDensity };
    }
  }

  function renderColumnManagerList(catalog) {
    if (!columnManagerList) {
      return;
    }
    columnManagerList.innerHTML = '';
    catalog.forEach((column) => {
      const item = document.createElement('li');
      item.className = 'list-group-item d-flex justify-content-between align-items-center gap-2';
      item.dataset.key = column.key;
      const controlsDisabled = column.configurable ? '' : ' disabled';
      const checkboxDisabled = column.configurable ? '' : ' disabled';
      item.innerHTML = `
        <div class="form-check d-flex align-items-center gap-2">
          <input class="form-check-input" type="checkbox" ${column.visible ? 'checked' : ''}${checkboxDisabled}>
          <label class="form-check-label mb-0">${column.label || column.key}</label>
        </div>
        <div class="btn-group btn-group-sm" role="group">
          <button type="button" class="btn btn-outline-secondary move-up"${controlsDisabled}>&uarr;</button>
          <button type="button" class="btn btn-outline-secondary move-down"${controlsDisabled}>&darr;</button>
        </div>
      `;
      columnManagerList.appendChild(item);
    });
  }

  function moveListItem(item, direction) {
    if (!item || !item.parentElement) {
      return;
    }
    const reference = direction < 0 ? item.previousElementSibling : item.nextElementSibling;
    if (!reference) {
      return;
    }
    if (direction < 0) {
      item.parentElement.insertBefore(item, reference);
    } else {
      item.parentElement.insertBefore(reference, item);
    }
  }

  function prepareColumnPreferences() {
    if (!columnManagerList || !columnManagerPayload) {
      return;
    }
    const columns = [];
    Array.from(columnManagerList.querySelectorAll('li')).forEach((item, index) => {
      const key = item.dataset.key;
      if (!key) {
        return;
      }
      const checkbox = item.querySelector('input[type="checkbox"]');
      columns.push({
        key,
        order: index,
        visible: checkbox ? !!checkbox.checked : true,
      });
    });
    const density = columnDensitySelect?.value || appContainer.dataset.lineDensity || 'comfortable';
    columnManagerPayload.value = JSON.stringify({
      lineColumns: columns,
      density,
    });
  }

  function showAlert(message, type = 'info') {
    const alerts = document.getElementById('app-alerts');
    if (!alerts) {
      return;
    }
    alerts.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`;
  }

  function isLastRow(element) {
    const row = element.closest(`${linesTableSelector} tbody tr`);
    if (!row) {
      return false;
    }
    const rows = document.querySelectorAll(`${linesTableSelector} tbody tr`);
    return rows.length && rows[rows.length - 1] === row;
  }

  function applyLastLineSuggestion() {
    const rows = document.querySelectorAll(`${linesTableSelector} tbody tr`);
    if (!rows.length) {
      return;
    }
    const totals = computeTotals(collectAllRows());
    if (Math.abs(totals.diff) < 0.01) {
      return;
    }
    const targetField = totals.diff > 0 ? 'cr' : 'dr';
    const lastRow = rows[rows.length - 1];
    const inputRole = targetField === 'dr' ? 'debit' : 'credit';
    const input = lastRow.querySelector(`input[data-role="${inputRole}"]`);
    if (!input) {
      return;
    }
    const existing = parseFloat(input.value) || 0;
    if (existing > 0) {
      return;
    }
    input.value = Math.abs(totals.diff).toFixed(2);
  }

  function scheduleLastLineSuggestion() {
    clearTimeout(suggestionTimer);
    suggestionTimer = setTimeout(() => {
      applyLastLineSuggestion();
      refreshSidePanel();
    }, 300);
  }

  function reindexRows() {
    const tbody = document.querySelector(`${linesTableSelector} tbody`);
    if (!tbody) {
      return;
    }
    Array.from(tbody.querySelectorAll('tr')).forEach((row, idx) => {
      row.dataset.rowIndex = idx;
      row.id = `line-${idx}`;
      row.querySelectorAll('input, select').forEach((input) => {
        if (!input.name) {
          return;
        }
        const match = input.name.match(/rows\[\d+\]\[(.+)\]/);
        if (match) {
          input.name = `rows[${idx}][${match[1]}]`;
        }
        if (input.dataset.lookup) {
          const listId = `${input.dataset.lookup}-options-${idx}`;
          input.setAttribute('list', listId);
          const dl = row.querySelector(`datalist#${listId}`) || row.querySelector('datalist');
          if (dl) {
            dl.id = listId;
          }
        }
      });
      const accountResults = row.querySelector('.account-results');
      if (accountResults) {
        accountResults.id = `account-results-${idx}`;
      }
    });
  }

  function triggerAddRow() {
    if (!addRowEndpoint) {
      return;
    }
    const rowCount = document.querySelectorAll(`${linesTableSelector} tbody tr`).length;
    htmx.ajax('GET', addRowEndpoint, {
      target: '#lines-table tbody',
      swap: 'beforeend',
      values: { index: rowCount, journalId: journalId },
    });
  }

  function handleDuplicate(row) {
    if (!duplicateRowEndpoint) {
      return;
    }
    const rowData = collectRowValues(row);
    htmx.ajax('POST', duplicateRowEndpoint, {
      target: row,
      swap: 'afterend',
      values: {
        row: JSON.stringify(rowData),
        journalId: journalId,
      },
    });
  }

  function handleDelete(row) {
    if (row && row.parentElement) {
      row.remove();
      reindexRows();
      refreshSidePanel();
    }
  }

  function handlePaste(event) {
    if (!bulkAddEndpoint) {
      return;
    }
    const clipboard = event.clipboardData.getData('text/plain');
    if (!clipboard) {
      return;
    }
    htmx.ajax('POST', bulkAddEndpoint, {
      target: '#lines-table tbody',
      swap: 'beforeend',
      values: {
        clipboard: clipboard,
        journalId: journalId,
      },
    });
  }

  function initAutoBalance() {
    if (!autoBalanceButton || !autoBalanceEndpoint) {
      return;
    }
    autoBalanceButton.addEventListener('click', function (event) {
      event.preventDefault();
      const payload = {
        header: collectHeaderValues(),
        lines: collectAllRows(),
      };
      htmx.ajax('POST', autoBalanceEndpoint, {
        target: '#lines-section',
        swap: 'innerHTML',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
    });
  }

  document.addEventListener('keydown', function (event) {
    const target = event.target;
    if (!target || !target.closest(linesTableSelector)) {
      return;
    }
    if (['Tab', 'Enter', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
      event.preventDefault();
      let direction;
      if (event.key === 'Enter') {
        direction = 'down';
      } else if (event.key === 'Tab') {
        direction = event.shiftKey ? 'left' : 'right';
      } else if (event.key.startsWith('Arrow')) {
        direction = event.key.replace('Arrow', '').toLowerCase();
      }
      const next = nextCell(target, direction);
      if (next) {
        next.focus();
      } else if (['Enter', 'Tab'].includes(event.key) && direction !== 'left') {
        triggerAddRow();
      }
    }
  });

  function handleLookup(input, type) {
    const endpoint = type === 'account' ? accountLookupEndpoint : type === 'costCenter' ? costCenterLookupEndpoint : null;
    if (!endpoint) {
      return;
    }
    const listId = `${type}-options-${input.dataset.rowIndex || 0}`;
    input.setAttribute('list', listId);
    let datalist = document.getElementById(listId);
    if (!datalist) {
      datalist = document.createElement('datalist');
      datalist.id = listId;
      input.parentElement.appendChild(datalist);
    }
    const query = input.value || '';
    clearTimeout(lookupTimers[listId]);
    lookupTimers[listId] = setTimeout(() => {
      fetch(`${endpoint}?q=${encodeURIComponent(query)}`, { credentials: 'same-origin' })
        .then((resp) => resp.json())
        .then((data) => {
          if (!data || !Array.isArray(data.results)) {
            return;
          }
          datalist.innerHTML = data.results
            .map((item) => {
              const label = `${item.code || ''} - ${item.name || ''}`.trim();
              return `<option value="${label}"></option>`;
            })
            .join('');
        })
        .catch(() => {});
    }, 200);
  }

  function initializeLookups() {
    document.querySelectorAll(`${linesTableSelector} input[data-lookup]`).forEach((input) => {
      handleLookup(input, input.dataset.lookup);
    });
  }

  document.addEventListener('focusin', function (event) {
    const target = event.target;
    if (!target || !target.closest(linesTableSelector)) {
      return;
    }
    const row = target.closest('tr');
    if (!row) {
      return;
    }
    const idx = row.dataset.rowIndex || Array.from(row.parentElement.children).indexOf(row);
    selectedLineIndex = parseInt(idx, 10) || 0;
    refreshSidePanel();
  });

  document.addEventListener('input', function (event) {
    const target = event.target;
    if (!target || !target.closest(linesTableSelector)) {
      return;
    }
    const lookupType = target.dataset.lookup;
    if (lookupType) {
      handleLookup(target, lookupType);
    }
    const role = target.dataset.role;
    if (!['debit', 'credit'].includes(role)) {
      return;
    }
    if (!isLastRow(target)) {
      return;
    }
    scheduleLastLineSuggestion();
  });

  document.addEventListener('copy', function (event) {
    const target = event.target;
    if (!target || !target.closest(linesTableSelector)) {
      return;
    }
    const row = target.closest('tr');
    if (!row) {
      return;
    }
    event.preventDefault();
    const rowValues = collectRowValues(row);
    const text = Object.values(rowValues).join('\t');
    event.clipboardData.setData('text/plain', text);
  });

  document.addEventListener('paste', function (event) {
    const target = event.target;
    if (!target || !target.closest(linesTableSelector)) {
      return;
    }
    event.preventDefault();
    handlePaste(event);
  });

  if (columnManagerList) {
    columnManagerList.addEventListener('click', function (event) {
      const button = event.target.closest('.move-up, .move-down');
      if (!button) {
        return;
      }
      const listItem = button.closest('li');
      if (!listItem) {
        return;
      }
      if (button.classList.contains('move-up')) {
        moveListItem(listItem, -1);
      } else {
        moveListItem(listItem, 1);
      }
    });
  }

  columnManagerForm?.addEventListener('submit', function () {
    prepareColumnPreferences();
  });

  if (columnManagerModalEl) {
    columnManagerModalEl.addEventListener('shown.bs.modal', function () {
      const metadata = getColumnMetadata();
      renderColumnManagerList(metadata.catalog);
      if (columnDensitySelect) {
        columnDensitySelect.value = metadata.density || columnDensitySelect.value || 'comfortable';
      }
    });
  }

  document.addEventListener('click', function (event) {
    const button = event.target.closest('.remove-row, .duplicate-row');
    if (!button) {
      return;
    }
    event.preventDefault();
    const row = button.closest('tr');
    if (button.classList.contains('duplicate-row')) {
      handleDuplicate(row);
      return;
    }
    handleDelete(row);
  });

  document.body.addEventListener('htmx:afterSwap', function (event) {
    const target = event.detail.target;
    if (!target) {
      return;
    }
    if (target.closest(linesTableSelector) || target.id === 'lines-table-body') {
      reindexRows();
    }
  });

  document.body.addEventListener('htmx:afterRequest', function (event) {
    try {
      const header = event.detail.xhr.getResponseHeader('HX-Trigger');
      if (header) {
        const payload = JSON.parse(header);
        if (payload.validationErrors) {
          cachedValidationErrors = payload.validationErrors;
        }
        if (payload.alert) {
          showAlert(payload.alert, payload.alertType || 'info');
        }
        if (payload.refreshSidePanel) {
          refreshSidePanel();
        }
        if (payload.refreshLines && linesEndpoint) {
          const nextPayload = {
            rows: collectAllRows(),
            header: collectHeaderValues(),
          };
          htmx.ajax('GET', linesEndpoint, {
            target: '#lines-section',
            swap: 'innerHTML',
            values: {
              journalId: journalId,
              payload: JSON.stringify(nextPayload),
            },
          });
        }
      }
    } catch (error) {}
  });

  initAutoBalance();
  initializeLookups();
})();
