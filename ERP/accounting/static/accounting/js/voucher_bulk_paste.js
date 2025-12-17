(function () {
  'use strict';

  const GRID_SELECTOR = '#grid-rows [id^="line-"]';

  function getLookupEndpoint() {
    const app = document.getElementById('app');
    return (app && app.dataset.endpointAccountLookup) || '/accounting/journal-entry/lookup/accounts/';
  }

  function parseRows(raw) {
    return raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const cells = line.split(/\t|,/).map((c) => c.trim());
        return {
          account: cells[0] || '',
          description: cells[1] || '',
          debit: cells[2] || '',
          credit: cells[3] || '',
        };
      });
  }

  function once(eventName, resolver) {
    return new Promise((resolve) => {
      const handler = (evt) => {
        resolver(evt, handler, resolve);
      };
      document.addEventListener(eventName, handler, { once: true });
    });
  }

  async function ensureRowCount(count) {
    const addBtn = document.querySelector('#voucher-grid button[name="add_line"]');
    if (!addBtn) {
      throw new Error('Add Line button not found.');
    }
    while (document.querySelectorAll(GRID_SELECTOR).length < count) {
      const swapPromise = once('htmx:afterSwap', (evt, handler, resolve) => {
        const target = evt.detail && evt.detail.target;
        if (target && target.closest && target.closest('#grid-rows')) {
          resolve();
        } else {
          document.addEventListener('htmx:afterSwap', handler, { once: true });
        }
      });
      addBtn.click();
      await swapPromise;
    }
  }

  async function lookupAccountId(accountCode) {
    if (!accountCode) {
      return null;
    }
    try {
      const resp = await fetch(`${getLookupEndpoint()}?q=${encodeURIComponent(accountCode)}&limit=5`, {
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'HX-Request': 'true'},
      });
      const ct = (resp.headers.get('content-type') || '').toLowerCase();
      if (!resp.ok || ct.includes('text/html')) {
        console.warn('Account lookup non-JSON/HTTP issue', resp.status, ct);
        return null;
      }
      const payload = await resp.json();
      const match =
        (payload.results || []).find((item) => item.code === accountCode) ||
        (payload.results || []).find((item) => `${item.code} - ${item.name}` === accountCode);
      return match || null;
    } catch (err) {
      console.warn('Account lookup failed', err);
      return null;
    }
  }

  function triggerInput(input) {
    if (!input) return;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  async function fillRow(rowEl, rowData) {
    const accountInput = rowEl.querySelector('.account-typeahead');
    const hiddenAccount = rowEl.querySelector('input[name$="-account"]');
    if (rowData.account && accountInput) {
      accountInput.value = rowData.account;
      const account = await lookupAccountId(rowData.account);
      if (account && hiddenAccount) {
        accountInput.value = `${account.code} - ${account.name}`;
        hiddenAccount.value = account.id;
        triggerInput(hiddenAccount);
      }
    }

    const descriptionInput = rowEl.querySelector('input[name*="-description"]');
    if (descriptionInput && rowData.description) {
      descriptionInput.value = rowData.description;
      triggerInput(descriptionInput);
    }

    const debitInput = rowEl.querySelector('input[name*="-debit_amount"]');
    if (debitInput && rowData.debit) {
      debitInput.value = rowData.debit;
      triggerInput(debitInput);
    }

    const creditInput = rowEl.querySelector('input[name*="-credit_amount"]');
    if (creditInput && rowData.credit) {
      creditInput.value = rowData.credit;
      triggerInput(creditInput);
    }
  }

  async function applyRows(rows) {
    for (let index = 0; index < rows.length; index += 1) {
      await ensureRowCount(index + 1);
      const currentRows = document.querySelectorAll(GRID_SELECTOR);
      const rowEl = currentRows[index];
      if (rowEl) {
        // eslint-disable-next-line no-await-in-loop
        await fillRow(rowEl, rows[index]);
      }
    }
  }

  function setFeedback(message, type = 'info') {
    const box = document.getElementById('bulkPasteFeedback');
    if (!box) return;
    box.classList.remove('d-none', 'alert-info', 'alert-danger', 'alert-success');
    box.classList.add(`alert-${type}`);
    box.textContent = message;
  }

  function clearFeedback() {
    const box = document.getElementById('bulkPasteFeedback');
    if (!box) return;
    box.classList.add('d-none');
    box.textContent = '';
  }

  document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('bulkPasteModal');
    if (!modalEl) {
      return;
    }
    const applyBtn = modalEl.querySelector('[data-bulk-action="apply"]');
    const textarea = modalEl.querySelector('#bulkPasteInput');
    if (!applyBtn || !textarea) {
      return;
    }
    applyBtn.addEventListener('click', async () => {
      clearFeedback();
      const rows = parseRows(textarea.value || '');
      if (!rows.length) {
        setFeedback('Nothing to paste. Provide at least one row.', 'danger');
        return;
      }
      applyBtn.disabled = true;
      try {
        await applyRows(rows);
        setFeedback(`Imported ${rows.length} row(s).`, 'success');
        textarea.value = '';
        if (window.bootstrap && bootstrap.Modal.getInstance(modalEl)) {
          bootstrap.Modal.getInstance(modalEl).hide();
        }
      } catch (err) {
        console.error(err);
        setFeedback(err.message || 'Unable to paste rows.', 'danger');
      } finally {
        applyBtn.disabled = false;
      }
    });
    modalEl.addEventListener('hidden.bs.modal', () => {
      clearFeedback();
    });
  });
})();
