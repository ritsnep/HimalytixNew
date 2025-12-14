/**
 * Simple account typeahead for Voucher Entry
 * - Uses `/vouchers/htmx/account-lookup/` which returns JSON {results: [...]}
 * - Populates <datalist> and maps display -> account id
 * - On selection, sets hidden input value and triggers change so HTMX posts update
 */
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
        // find id by matching display text
        const found = lastResults.find(r => (r.code + ' - ' + r.name) === chosen);
        if (found) {
          hidden.value = found.id;
          // trigger change so HTMX posts
          hidden.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => initTypeaheads());
  document.addEventListener('htmx:afterSwap', (e) => initTypeaheads(e.detail.target || document));
  // Expose for tests
  window.initVoucherTypeaheads = initTypeaheads;
})();
