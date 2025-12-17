/**
 * Simple account typeahead for Voucher Entry
 * Minimal typeahead for voucher entry.
 * Default endpoint now uses journal-entry JSON lookup to avoid 404s on legacy voucher path.
 */
(function(){
  'use strict';

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
        fetch(`${endpoint}?q=${encodeURIComponent(q)}&limit=10`, {credentials: 'same-origin', headers: {'Accept': 'application/json', 'HX-Request': 'true'}})
          .then(r => {
            const ct = (r.headers.get('content-type') || '').toLowerCase();
            if (!r.ok || ct.includes('text/html')) {
              r.text().then(txt => console.warn('Typeahead lookup non-JSON/HTTP issue', r.status, ct, endpoint, txt.slice(0, 120)));
              return null;
            }
            return r.json().catch(err => {
              console.warn('Typeahead lookup JSON parse failed', err, endpoint);
              return null;
            });
          })
          .then(data => {
            if (!data) return;
            lastResults = Array.isArray(data.results) ? data.results : [];
            datalist.innerHTML = '';
            lastResults.forEach(r => {
              const opt = document.createElement('option');
              const code = r.code || '';
              const name = r.name || '';
              opt.value = `${code}${code && name ? ' - ' : ''}${name}`.trim();
              datalist.appendChild(opt);
            });
          }).catch(err => console.warn('Account lookup failed', err));
      });

      input.addEventListener('change', (e) => {
        const chosen = e.target.value;
        const hidden = input.form ? input.form.querySelector(`[name="${hiddenName}"]`) : document.querySelector(`input[name="${hiddenName}"]`);
        if (!hidden) return;
        // find id by matching display text
        const found = lastResults.find(r => {
          const code = r.code || '';
          const name = r.name || '';
          const disp = `${code}${code && name ? ' - ' : ''}${name}`.trim();
          return disp === chosen;
        });
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
