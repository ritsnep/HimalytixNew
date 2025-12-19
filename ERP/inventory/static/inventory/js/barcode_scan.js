document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('barcode-scanner-form');
  const input = document.getElementById('barcode-input');
  const resultCard = document.getElementById('scanner-results');
  const productBlock = document.getElementById('scanner-product');
  const locationsContainer = document.getElementById('scanner-locations');

  const showError = (message) => {
    productBlock.innerHTML = `<div class="alert alert-warning">${message}</div>`;
    locationsContainer.innerHTML = '';
    resultCard.hidden = false;
  };

  const renderLocations = (list) => {
    if (!list.length) {
      locationsContainer.innerHTML = '<p class="text-muted mb-0">No stock on hand.</p>';
      return;
    }

    const rows = list.map(item => `
      <tr>
        <td>${item.warehouse}</td>
        <td>${item.location || '—'}</td>
        <td>${item.batch || '—'}</td>
        <td class="text-end">${item.quantity.toFixed(4)}</td>
      </tr>
    `).join('');

    locationsContainer.innerHTML = `
      <table class="table table-sm table-striped mb-0">
        <thead class="table-light">
          <tr>
            <th>Warehouse</th>
            <th>Location</th>
            <th>Batch</th>
            <th class="text-end">Qty</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  };

  const renderProduct = (product) => {
    productBlock.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <h5 class="mb-1">${product.code} - ${product.name}</h5>
          <div class="small text-muted">
            SKU: ${product.sku || '—'} | Barcode: ${product.barcode || '—'}
          </div>
        </div>
        <button class="btn btn-outline-secondary btn-sm" type="button" id="clear-scanner">Clear</button>
      </div>
    `;
    document.getElementById('clear-scanner').addEventListener('click', () => {
      input.value = '';
      resultCard.hidden = true;
    });
  };

  const lookupBarcode = (code) => {
    fetch(`/inventory/barcode-scan/?code=${encodeURIComponent(code)}`, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
    })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => Promise.reject(err.error || 'Error looking up barcode.'));
        }
        return response.json();
      })
      .then(data => {
        renderProduct(data.product);
        renderLocations(data.locations);
        resultCard.hidden = false;
      })
      .catch(error => showError(error));
  };

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) {
      return;
    }
    lookupBarcode(value);
  });
});
