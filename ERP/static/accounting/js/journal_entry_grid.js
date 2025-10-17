(function() {
  const rowsEl = document.getElementById('je-grid-rows');
  const formEl = document.getElementById('je-grid-form');
  let nextIndex = parseInt(rowsEl.querySelector('tr.je-grid-row:last-child')?.dataset.index || '0', 10) + 1;

  // Insert a new row via HTMX
  async function insertRow() {
    const res = await htmx.ajax('POST', formEl.dataset.addRowUrl || getAddRowUrl(), {
      values: { next_index: nextIndex },
      target: rowsEl,
      swap: 'beforeend'
    });
    nextIndex++;
  }
  function getAddRowUrl() {
    return '/accounting/journal-entry-grid/add-row';
  }

  // Keyboard navigation and shortcuts
  rowsEl.addEventListener('keydown', function(e) {
    const cell = e.target;
    if (!cell.classList.contains('je-cell')) return;
    const row = cell.closest('tr');
    const cells = Array.from(row.querySelectorAll('.je-cell'));
    const idx = cells.indexOf(cell);
    const rowIndex = Array.from(rowsEl.querySelectorAll('tr')).indexOf(row);
    if (e.key === 'Enter') {
      e.preventDefault();
      // Down one row
      const nextRow = rowsEl.querySelectorAll('tr')[rowIndex + 1];
      if (nextRow) {
        nextRow.querySelectorAll('.je-cell')[idx]?.focus();
      } else {
        insertRow().then(() => {
          const newRow = rowsEl.querySelectorAll('tr')[rowIndex + 1];
          newRow.querySelectorAll('.je-cell')[idx]?.focus();
        });
      }
    } else if (e.ctrlKey && e.key.toLowerCase() === 'i') {
      e.preventDefault();
      insertRow();
    } else if (e.ctrlKey && e.key === 'Delete') {
      e.preventDefault();
      row.remove();
    }
  });

  // Paste handler: sends clipboard text to HTMX paste endpoint
  rowsEl.addEventListener('paste', async function(e) {
    const cell = e.target;
    if (!cell.classList.contains('je-cell')) return;
    const text = (e.clipboardData || window.clipboardData).getData('text');
    if (!text || text.indexOf('\t') === -1) return;
    e.preventDefault();
    const startRow = parseInt(cell.closest('tr').dataset.index || '0', 10);
    const form = new FormData();
    form.append('payload', text);
    form.append('start_index', startRow);
    form.append('csrfmiddlewaretoken', formEl.querySelector('[name=csrfmiddlewaretoken]').value);
    const resp = await fetch('/accounting/journal-entry-grid/paste', { method:'POST', body: form, headers: { 'HX-Request': 'true' } });
    const html = await resp.text();
    if (resp.ok) {
      // Remove existing rows from startRow on
      Array.from(rowsEl.querySelectorAll('tr')).forEach(tr => {
        const idx = parseInt(tr.dataset.index || '-1', 10);
        if (idx >= startRow) tr.remove();
      });
      rowsEl.insertAdjacentHTML('beforeend', html);
      nextIndex = parseInt(rowsEl.querySelector('tr.je-grid-row:last-child')?.dataset.index || '0', 10) + 1;
    }
  });

  // Row validation on blur for numeric fields
  rowsEl.addEventListener('blur', function(e) {
    const cell = e.target;
    if (!cell.classList.contains('je-cell')) return;
    const row = cell.closest('tr');
    const index = row.dataset.index;
    const data = new FormData(formEl);
    data.append('index', index);
    fetch('/accounting/journal-entry-grid/validate-row', { method:'POST', body:data, headers:{ 'HX-Request':'true' } })
      .then(r => r.text().then(html => ({ ok:r.ok, html })))
      .then(({ ok, html }) => {
        row.insertAdjacentHTML('afterend', html);
        row.remove();
      });
  }, true);

  // Inline account lookup (example using simple fetch; adapt to your lookup endpoint)
  rowsEl.addEventListener('input', htmx.debounce(function(e) {
    const input = e.target;
    if (!input.classList.contains('je-account')) return;
    const q = input.value || '';
    const dropdown = input.parentNode.querySelector('.dropdown-menu');
    fetch(`/accounting/journal-entry-grid/account-lookup?q=${encodeURIComponent(q)}`, { headers: { 'HX-Request':'true' } })
      .then(r => r.text())
      .then(html => {
        dropdown.innerHTML = html;
        dropdown.classList.add('show');
      });
  }, 200));

  rowsEl.addEventListener('click', function(e) {
    const opt = e.target.closest('.je-acc-opt');
    if (!opt) return;
    const td = opt.closest('td');
    const input = td.querySelector('.je-account');
    input.value = opt.dataset.label;
    td.querySelector('.dropdown-menu').classList.remove('show');
  });
})();
