(function(){
  'use strict';

  function displayText(r){
    if (!r) return '';
    const text = r.text || r.display;
    if (text) return String(text);
    const code = (r.code || '').toString();
    const name = (r.name || '').toString();
    const joined = `${code}${code && name ? ' - ' : ''}${name}`.trim();
    return joined || name || code;
  }

  function initTypeaheads(container=document){
    const inputs = container.querySelectorAll('.account-typeahead, .generic-typeahead');
    inputs.forEach(input => {
      if (input._initialized) return;
      input._initialized = true;
      const endpoint = input.dataset.endpoint || '/accounting/journal-entry/lookup/accounts/';

      const listId = input.dataset.listId || input.getAttribute('list') || (input.id ? `${input.id}__list` : `typeahead-${Math.random().toString(36).slice(2)}`);
      let datalist = document.getElementById(listId);
      if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = listId;
        document.body.appendChild(datalist);
      }
      input.setAttribute('list', listId);

      const hiddenName = input.dataset.hiddenName || (input.name ? input.name.replace(/_display$/, '') : '');
      let lastQuery = '';
      let lastResults = [];

      input.addEventListener('input', (e) => {
        const q = e.target.value.trim();
        if (!q || q.length < 1) {
          datalist.innerHTML = '';
          return;
        }
        if (q === lastQuery) return;
        lastQuery = q;
        // Prefer the explicit endpoint; if none given, fall back to the stable journal-entry account lookup.
        const endpoints = endpoint
          ? [endpoint]
          : ['/accounting/journal-entry/lookup/accounts/'];

        function attemptFetch(i) {
          if (i >= endpoints.length) {
            console.warn('Typeahead lookup exhausted all endpoints');
            datalist.innerHTML = '';
            return;
          }
          const url = `${endpoints[i]}?q=${encodeURIComponent(q)}&limit=10`;
          fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json', 'HX-Request': 'true'}})
            .then(r => {
              const ct = (r.headers.get('content-type') || '').toLowerCase();

              // Bail early on HTTP errors or HTML responses (login pages/404 templates)
              if (!r.ok || ct.includes('text/html')) {
                r.text().then(txt => console.warn('Typeahead lookup non-JSON/HTTP issue', r.status, ct, url, txt.slice(0, 120)));
                attemptFetch(i + 1);
                return null;
              }

              // If it is JSON but parsing fails, treat it as a failure and try the next endpoint.
              return r.json().catch(err => {
                console.warn('Typeahead lookup JSON parse failed', err, url);
                attemptFetch(i + 1);
                return null;
              });
            })
            .then(data => {
              if (!data) return;
              lastResults = Array.isArray(data.results) ? data.results : [];
              datalist.innerHTML = '';
              lastResults.forEach(r => {
                const opt = document.createElement('option');
                opt.value = displayText(r);
                datalist.appendChild(opt);
              });
            })
            .catch(err => {
              console.warn('Typeahead lookup failed', err, url);
              attemptFetch(i + 1);
            });
        }

        attemptFetch(0);
      });

      input.addEventListener('change', (e) => {
        const chosen = e.target.value;
        const hidden = input.form ? input.form.querySelector(`[name="${hiddenName}"]`) : document.querySelector(`input[name="${hiddenName}"]`);
        if (!hidden) return;
        const found = lastResults.find(r => displayText(r) === chosen);
        if (found) {
          hidden.value = found.id;
          hidden.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });
  }

  function initKeyboardNavigation(container=document) {
    const gridRows = container.querySelectorAll('[id^="line-"]');
    gridRows.forEach(row => {
      const inputs = row.querySelectorAll('input[type="text"], input[type="number"]');
      inputs.forEach(input => {
        input.addEventListener('keydown', (e) => {
          handleGridKeydown(e, input, row);
        });
      });
    });
  }

  function handleGridKeydown(e, currentInput, currentRow) {
    const inputs = Array.from(currentRow.querySelectorAll('input[type="text"], input[type="number"]'));
    const currentIndex = inputs.indexOf(currentInput);
    const allRows = Array.from(document.querySelectorAll('[id^="line-"]'));
    const currentRowIndex = allRows.indexOf(currentRow);

    switch (e.key) {
      case 'Enter':
        e.preventDefault();
        if (e.shiftKey) {
          // Shift+Enter: move to previous row, same column
          if (currentRowIndex > 0) {
            const prevRow = allRows[currentRowIndex - 1];
            const prevInputs = prevRow.querySelectorAll('input[type="text"], input[type="number"]');
            if (prevInputs[currentIndex]) {
              prevInputs[currentIndex].focus();
            }
          }
        } else {
          // Enter: move to next row, same column
          if (currentRowIndex < allRows.length - 1) {
            const nextRow = allRows[currentRowIndex + 1];
            const nextInputs = nextRow.querySelectorAll('input[type="text"], input[type="number"]');
            if (nextInputs[currentIndex]) {
              nextInputs[currentIndex].focus();
            }
          } else {
            // Last row: add new row
            const addButton = document.querySelector('button[hx-post*="add-row"]');
            if (addButton) {
              addButton.click();
            }
          }
        }
        break;

      case 'Tab':
        e.preventDefault();
        if (e.shiftKey) {
          // Shift+Tab: move to previous input
          if (currentIndex > 0) {
            inputs[currentIndex - 1].focus();
          } else if (currentRowIndex > 0) {
            // Move to last input of previous row
            const prevRow = allRows[currentRowIndex - 1];
            const prevInputs = prevRow.querySelectorAll('input[type="text"], input[type="number"]');
            if (prevInputs.length > 0) {
              prevInputs[prevInputs.length - 1].focus();
            }
          }
        } else {
          // Tab: move to next input
          if (currentIndex < inputs.length - 1) {
            inputs[currentIndex + 1].focus();
          } else if (currentRowIndex < allRows.length - 1) {
            // Move to first input of next row
            const nextRow = allRows[currentRowIndex + 1];
            const nextInputs = nextRow.querySelectorAll('input[type="text"], input[type="number"]');
            if (nextInputs.length > 0) {
              nextInputs[0].focus();
            }
          } else {
            // Last input of last row: add new row
            const addButton = document.querySelector('button[hx-post*="add-row"]');
            if (addButton) {
              addButton.click();
            }
          }
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (currentRowIndex > 0) {
          const prevRow = allRows[currentRowIndex - 1];
          const prevInputs = prevRow.querySelectorAll('input[type="text"], input[type="number"]');
          if (prevInputs[currentIndex]) {
            prevInputs[currentIndex].focus();
          }
        }
        break;

      case 'ArrowDown':
        e.preventDefault();
        if (currentRowIndex < allRows.length - 1) {
          const nextRow = allRows[currentRowIndex + 1];
          const nextInputs = nextRow.querySelectorAll('input[type="text"], input[type="number"]');
          if (nextInputs[currentIndex]) {
            nextInputs[currentIndex].focus();
          }
        } else {
          // Last row: add new row
          const addButton = document.querySelector('button[hx-post*="add-row"]');
          if (addButton) {
            addButton.click();
          }
        }
        break;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTypeaheads();
    initKeyboardNavigation();
  });
  document.addEventListener('htmx:afterSwap', (e) => {
    initTypeaheads(e.detail.target || document);
    initKeyboardNavigation(e.detail.target || document);
  });
  window.initVoucherTypeaheads = initTypeaheads;
})();