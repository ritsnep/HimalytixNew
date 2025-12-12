// Handle journal entry form operations
(function () {
  const tbody = document.querySelector("#journal-grid-body");
  const totalForms = document.querySelector("#id_lines-TOTAL_FORMS");
  const template = document.querySelector("#line-empty-form");
  const totals = {
    debit: document.getElementById("total-debit"),
    credit: document.getElementById("total-credit"),
    imbalance: document.querySelector("#imbalance-container span")
  };

  function recalcTotals() {
    let d = 0, c = 0;
    tbody.querySelectorAll('tr.journal-line-row:not(.d-none)').forEach(tr => {
      const di = tr.querySelector('[name$="-debit_amount"]');
      const ci = tr.querySelector('[name$="-credit_amount"]');
      d += parseFloat(di?.value || 0);
      c += parseFloat(ci?.value || 0);
    });
    totals.debit.textContent = d.toFixed(2);
    totals.credit.textContent = c.toFixed(2);
    const diff = (d - c);
    totals.imbalance.textContent = (diff === 0 ? "Balanced" : `Imbalance: ${diff.toFixed(2)}`);
    totals.imbalance.classList.toggle("text-danger", diff !== 0);
    totals.imbalance.classList.toggle("text-success", diff === 0);
  }

  document.addEventListener("htmx:afterOnLoad", (e) => {
    // Increment TOTAL_FORMS after a new line is added via HTMX
    if (e.detail.target && e.detail.target.id === "journal-grid-body") {
      totalForms.value = parseInt(totalForms.value, 10) + 1;
      recalcTotals();
    }
  });

  // Delegate remove: mark DELETE and hide row (works with can_delete=True)
  tbody.addEventListener("click", (e) => {
    const btn = e.target.closest(".remove-row");
    if (!btn) return;
    const tr = btn.closest("tr.journal-line-row");
    const idInput = tr.querySelector('[name$="-DELETE"]');
    if (idInput) { idInput.value = "on"; }
    tr.classList.add("d-none");
    recalcTotals();
  });

  // Recalc on any number input change
  tbody.addEventListener("input", (e) => {
    if (e.target.matches('input[type="number"]')) recalcTotals();
  });

  // Validate exchange rate field
  document.addEventListener("htmx:afterRequest", (e) => {
    const target = e.detail.target;
    if (target && target.id && target.id.includes('exchange_rate')) {
      const value = parseFloat(target.value);
      if (isNaN(value) || value <= 0) {
        target.value = '1.000000';
        // Optional: show a warning message
        console.warn('Invalid exchange rate, defaulting to 1.000000');
      }
    }
  });

  // Side panel toggle
  document.getElementById('side-panel-toggle')?.addEventListener('click', ()=>{
    document.getElementById('side-panel').classList.toggle('panel-collapsed');
  });
  document.getElementById('side-panel-fab')?.addEventListener('click', ()=>{
    document.getElementById('side-panel').classList.toggle('panel-collapsed');
  });

  recalcTotals();
})();
