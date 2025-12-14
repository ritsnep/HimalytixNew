(function(){
  'use strict';

  function initTypeaheads(container=document){
    const inputs = container.querySelectorAll('.account-typeahead');
    inputs.forEach(input => {
      if (input._initialized) return;
      input._initialized = true;
      const listId = input.dataset.listId;
      const hiddenName = input.dataset.hiddenName;
      const datalist = document.getElementById(listId);
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
        fetch(`/accounting/vouchers/htmx/account-lookup/?q=${encodeURIComponent(q)}&limit=10`, {credentials: 'same-origin'})
          .then(r => r.json())
          .then(data => {
            lastResults = data.results || [];
            datalist.innerHTML = '';
            lastResults.forEach(r => {
              const opt = document.createElement('option');
              opt.value = r.code + ' - ' + r.name;
              datalist.appendChild(opt);
            });
          }).catch(err => console.warn('Account lookup failed', err));
      });

      input.addEventListener('change', (e) => {
        const chosen = e.target.value;
        const hidden = input.form ? input.form.querySelector(`[name="${hiddenName}"]`) : document.querySelector(`input[name="${hiddenName}"]`);
        if (!hidden) return;
        const found = lastResults.find(r => (r.code + ' - ' + r.name) === chosen);
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