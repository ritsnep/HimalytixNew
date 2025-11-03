'use strict';

// ---- Django Integration Header ----
// CSRF helper (Django default cookie name)
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}
const CSRFTOKEN = getCookie('csrftoken');

// Read endpoints from the root element (#app). If not present, we fallback to local behaviors.
const __root = document.getElementById('app');
const Endpoints = {
  save: __root?.dataset?.endpointSave || null,
  submit: __root?.dataset?.endpointSubmit || null,
  approve: __root?.dataset?.endpointApprove || null,
};

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRFTOKEN || ''
    },
    body: JSON.stringify(payload)
  });
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch(e) { /* non-JSON response */ }
  return { ok: res.ok, status: res.status, data, text };
}

function notify(msg) { try { console.info(msg); } catch {} alert(msg); }
// ---- End Django Integration Header ----


/** Local persistence + utils */
const LS_KEY = 'voucherEntryPresets_v5';
const moneyFmt = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const asNum = (v, d = 0) => { if (v === null || v === undefined) return d; const x = parseFloat(String(v).replace(/,/g, '')); return Number.isNaN(x) ? d : x; };
const uid = () => Math.random().toString(36).slice(2, 10);
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const loadPresets = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch { return {}; } };
const savePresets = (obj) => localStorage.setItem(LS_KEY, JSON.stringify(obj));

/** Base columns for item & journal modes */
const BASE_ITEM_COLS = [
  { id: 'item', label: 'Item/Service', type: 'text', width: 220 },
  { id: 'desc', label: 'Description', type: 'text', width: 220 },
  { id: 'qty', label: 'Qty', type: 'number', width: 90, align: 'right', def: 1 },
  { id: 'uom', label: 'UOM', type: 'text', width: 90 },
  { id: 'rate', label: 'Rate', type: 'number', width: 110, align: 'right' },
  { id: 'discP', label: 'Disc %', type: 'number', width: 90, align: 'right', def: 0 },
  { id: 'taxP', label: 'Tax %', type: 'number', width: 90, align: 'right', def: 13 },
  { id: 'taxGroup', label: 'Tax Group', type: 'text', width: 130 },
  { id: 'warehouse', label: 'Warehouse', type: 'text', width: 140 },
  { id: 'batch', label: 'Batch/Lot', type: 'text', width: 120 },
  { id: 'amount', label: 'Amount', type: 'calc', width: 140, align: 'right' },
];
const BASE_JOURNAL_COLS = [
  { id: 'account', label: 'Account', type: 'text', width: 260 },
  { id: 'narr', label: 'Narration', type: 'text', width: 260 },
  { id: 'dr', label: 'Dr', type: 'number', width: 140, align: 'right', def: 0 },
  { id: 'cr', label: 'Cr', type: 'number', width: 140, align: 'right', def: 0 },
  { id: 'costCenter', label: 'Cost Center', type: 'text', width: 160 },
];

function buildColumns(vType, udfLineDefs, colPrefs) {
  const base = vType === 'Journal' ? [...BASE_JOURNAL_COLS] : [...BASE_ITEM_COLS];
  udfLineDefs.forEach(f => base.push({ id: f.id, label: `UDF: ${f.label}`, type: f.type, width: 160, options: f.options || [] }));
  let merged = base.map((c, i) => ({ order: i, visible: true, ...c }));
  if (!colPrefs) return merged;
  const dict = new Map(colPrefs.map((p, i) => [p.id, { ...p, order: i }]));
  merged = merged.map(c => {
    const p = dict.get(c.id); if (!p) return c;
    return { ...c, visible: p.visible !== false, width: p.width || c.width, order: p.order ?? c.order };
  });
  merged.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  return merged;
}

const App = {
  state: {
    voucherType: 'Sales',
    status: 'Draft',
    header: {
      party: '',
      date: new Date().toISOString().slice(0, 10),
      branch: 'Main',
      currency: 'NPR',
      exRate: 1,
      creditDays: 0,
      priceInclusiveTax: true,
    },
    notes: '',
    collapsed: { header: false, actions: false, notes: false, totals: false },
    udfHeaderDefs: [],
    udfLineDefs: [],
    colPrefsByType: {},
    rows: [],
    charges: [
      { id: uid(), label: 'Freight', mode: 'amount', value: 0, sign: 1 },
      { id: uid(), label: 'Discount @ Bill', mode: 'percent', value: 0, sign: -1 },
    ],
    numbering: { prefix: { Sales: 'SI', Purchase: 'PI', Journal: 'JV' }, nextSeq: { Sales: 1, Purchase: 1, Journal: 1 }, width: 4 },
    focus: { r: 0, c: 0 },
    showUdfModal: false,
    udfScope: 'Header',
    udfDraft: { label: '', type: 'text', required: false, options: '' },
    showColManager: false,
    colManagerDraft: [],
    showCharges: false,
  },

  init() {
    const presets = loadPresets();
    this.state.colPrefsByType = presets.colPrefsByType || {};
    this.state.udfHeaderDefs = presets.udfHeaderDefs || [];
    this.state.udfLineDefs = presets.udfLineDefs || [];
    this.state.collapsed = presets.collapsed || this.state.collapsed;
    this.state.charges = presets.charges || this.state.charges;
    this.state.numbering = presets.numbering || this.state.numbering;

    // Ensure default Header UDF present
    if (!this.state.udfHeaderDefs.some(x => x.label.toLowerCase().includes('invoice'))) {
      this.state.udfHeaderDefs.push({ id: 'udf_' + uid(), label: 'Invoice No.', type: 'text', required: true });
    }

    this.resetRows();
    this.render();

    // Global listeners (column resize)
    if (!this._resizeBound) {
      this._onMouseMove = (ev) => this.onResize(ev);
      this._onMouseUp = (ev) => this.stopResize(ev);
      window.addEventListener('mousemove', this._onMouseMove);
      window.addEventListener('mouseup', this._onMouseUp);
      this._resizeBound = true;
    }
  },

  getColumns() {
    const { voucherType, udfLineDefs, colPrefsByType } = this.state;
    return buildColumns(voucherType, udfLineDefs, colPrefsByType[voucherType]);
  },
  blankRow() {
    if (this.state.voucherType === 'Journal') return { id: uid(), account: '', narr: '', dr: 0, cr: 0, costCenter: '' };
    return { id: uid(), item: '', desc: '', qty: 1, uom: '', rate: 0, discP: 0, taxP: 13, taxGroup: 'VAT 13%', warehouse: '', batch: '', amount: 0 };
  },
  resetRows(n = 5) { this.state.rows = Array.from({ length: n }, () => this.blankRow()); },

  voucherDisplayNumber() {
    const vt = this.state.voucherType; const n = this.state.numbering.nextSeq[vt] || 1;
    const pref = this.state.numbering.prefix[vt] || vt[0]; const w = this.state.numbering.width || 4;
    return `${pref}-${String(n).padStart(w, '0')}`;
  },

  /** Totals engine (VAT, discounts, charges, journal balance) */
  computeTotals() {
    const { voucherType, rows, header, charges } = this.state;
    if (voucherType === 'Journal') {
      const dr = rows.reduce((s, r) => s + asNum(r.dr), 0);
      const cr = rows.reduce((s, r) => s + asNum(r.cr), 0);
      return { dr, cr, diff: +(dr - cr).toFixed(2) };
    }
    let sub = 0, disc = 0, tax = 0; const taxBreak = new Map();
    rows.forEach(r => {
      const qty = asNum(r.qty, 0), rate = asNum(r.rate, 0), dP = asNum(r.discP, 0), tP = asNum(r.taxP, 0);
      const lineBase = qty * rate;
      const lineDisc = (lineBase * dP) / 100;
      const taxable = header.priceInclusiveTax ? (lineBase - lineDisc) / (1 + tP / 100 || 1) : (lineBase - lineDisc);
      const lineTax = taxable * (tP / 100);
      const lineAmount = taxable + lineTax;
      sub += taxable; disc += lineDisc; tax += lineTax; r.amount = +lineAmount.toFixed(2);
      if (tP > 0) taxBreak.set(tP, (taxBreak.get(tP) || 0) + lineTax);
    });
    const baseForCharges = sub + tax;
    let chargesTotal = 0;
    charges.forEach(c => {
      const v = asNum(c.value, 0);
      if (!v) return;
      const add = c.mode === 'percent' ? baseForCharges * (v / 100) : v;
      chargesTotal += (c.sign === -1 ? -1 : 1) * add;
    });
    const roundAdj = +(Math.round((sub + tax + chargesTotal) * 100) / 100 - (sub + tax + chargesTotal)).toFixed(2);
    const grand = +(sub + tax + chargesTotal + roundAdj).toFixed(2);
    return { sub, disc, tax, chargesTotal, roundAdj, grand, taxBreak: [...taxBreak.entries()].sort((a, b) => a[0] - b[0]) };
  },

  persistPresets() {
    const { colPrefsByType, udfHeaderDefs, udfLineDefs, collapsed, charges, numbering } = this.state;
    const current = loadPresets();
    current.colPrefsByType = colPrefsByType;
    current.udfHeaderDefs = udfHeaderDefs;
    current.udfLineDefs = udfLineDefs;
    current.collapsed = collapsed;
    current.charges = charges;
    current.numbering = numbering;
    savePresets(current);
  },

  /** UI */
  render() {
    const el = document.getElementById('app');
    const { voucherType, status, header, udfHeaderDefs, udfLineDefs, rows, collapsed, notes, charges } = this.state;
    const cols = this.getColumns();
    const visibleCols = cols.filter(c => c.visible !== false);
    const totals = this.computeTotals();

    el.innerHTML = `
      <header class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-semibold tracking-tight">Voucher Entry</h1>
          <span class="px-2 py-1 rounded-lg text-xs bg-slate-200 text-slate-800">${voucherType}</span>
          <span class="text-xs px-2 py-1 rounded-full ${status === 'Draft' ? 'bg-yellow-100 text-yellow-800' : status === 'Submitted' ? 'bg-blue-100 text-blue-800' : 'bg-emerald-100 text-emerald-800'}">${status}</span>
          <span class="badge">No: <strong>${this.voucherDisplayNumber()}</strong></span>
          <span class="text-xs text-slate-500 ml-2">Excel paste + Sample Excel export</span>
        </div>
        <div class="flex gap-2">
          <div class="inline-flex rounded-xl p-1 bg-slate-100 text-sm">
            ${['Sales', 'Purchase', 'Journal'].map(v => `
              <button data-action="setType" data-type="${v}"
                class="px-3 py-1.5 rounded-lg transition ${voucherType === v ? 'bg-white shadow font-medium' : 'text-slate-600 hover:bg-white/60'}">${v}</button>
            `).join('')}
          </div>
          <button data-action="saveDraft" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Save Draft</button>
          <button data-action="submit" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Submit</button>
          <button data-action="approve" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm bg-emerald-600 text-white hover:bg-emerald-700">Approve</button>
        </div>
      </header>

      <section class="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="col-span-2 rounded-2xl border bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Header</h2>
            <button data-action="toggleSection" data-section="header" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show header">${collapsed.header ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.header ? headerSummary(header, voucherType) : `
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            ${voucherType !== 'Journal' ? Labeled('Customer/Supplier', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" placeholder="Search name / phone" value="${escapeHtml(header.party)}" data-hkey="party" title="${escapeHtml(header.party)}">`) : ''}
            ${Labeled('Date', `<input type="date" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${header.date}" data-hkey="date" title="${header.date}">`)}
            ${Labeled('Branch', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${escapeHtml(header.branch)}" data-hkey="branch" title="${escapeHtml(header.branch)}">`)}
            ${Labeled('Currency', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${escapeHtml(header.currency)}" data-hkey="currency" title="${escapeHtml(header.currency)}">`)}
            ${Labeled('Exchange Rate', `<input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white text-right" value="${header.exRate}" data-hkey="exRate" title="${header.exRate}">`)}
            ${Labeled('Credit Days', `<input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white text-right" value="${header.creditDays}" data-hkey="creditDays" title="${header.creditDays}">`)}
            ${voucherType !== 'Journal' ? Labeled('Prices are', `
              <select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-hkey="priceInclusiveTax" title="${header.priceInclusiveTax ? 'Tax Inclusive' : 'Tax Exclusive'}">
                <option value="inc" ${header.priceInclusiveTax ? 'selected' : ''} >Tax Inclusive</option>
                <option value="exc" ${!header.priceInclusiveTax ? 'selected' : ''} >Tax Exclusive</option>
              </select>
            `) : ''}
            ${udfHeaderDefs.map(f => Labeled(`UDF: ${escapeHtml(f.label)}${f.required ? ' *' : ''}`, fieldControl(f, header[f.id] ?? '', 'header'))).join('')}
          </div>
          <div class="mt-3 flex flex-wrap gap-2 items-center">
            <button data-action="openUdf" data-scope="Header" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+ UDF (Header)</button>
            ${udfHeaderDefs.map(f => `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs cursor-pointer hover:bg-slate-200" data-action="removeUdf" data-scope="Header" data-udfid="${f.id}">U:${escapeHtml(f.label)} ✕</span>`).join('')}
          </div>`}
        </div>

        <div class="rounded-2xl border bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Actions</h2>
            <button data-action="toggleSection" data-section="actions" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show actions">${collapsed.actions ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.actions ? actionsSummary(rows, cols) : `
          <div class="flex flex-wrap gap-2">
            <button data-action="addRow" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Add Row</button>
            <button data-action="add10" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+10 Rows</button>
            <button data-action="clearRows" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Clear Rows</button>
            <button data-action="openCols" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Columns</button>
            <button data-action="saveCols" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Save Columns</button>
            <button data-action="resetCols" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Reset Columns</button>
            <button data-action="importCsv" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Import CSV</button>
            <input id="csvFile" type="file" accept=".csv,text/csv" class="hidden" />
            <button data-action="exportCsv" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Export CSV</button>
            <button data-action="sampleXlsx" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Sample Excel (.xlsx)</button>
            <button data-action="exportXlsx" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Export Excel (.xlsx)</button>
            <button data-action="runTests" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Run Tests</button>
          </div>
          <p class="text-xs text-slate-500 mt-2">Tip: paste cells copied from Excel directly into the grid. Use arrow keys / Tab / Enter. Ctrl+Delete removes row.</p>
          <div class="mt-3 flex gap-2 items-center">
            <button data-action="attach" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Attachments</button>
          </div>`}
        </div>
      </section>

      <section class="mt-5 rounded-2xl border bg-white p-4 shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold">Lines</h2>
          <div class="flex items-center gap-3">
            <button data-action="openUdf" data-scope="Line" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+ UDF (Line)</button>
            ${udfLineDefs.map(f => `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs cursor-pointer hover:bg-slate-200" data-action="removeUdf" data-scope="Line" data-udfid="${f.id}">L:${escapeHtml(f.label)} ✕</span>`).join('')}
          </div>
        </div>

        <div id="grid" class="mt-3 overflow-auto border rounded-xl scroll-shadow" style="max-height: 440px">
          <table class="min-w-full text-sm table-fixed">
            <colgroup>
              <col style="width:40px">
              ${visibleCols.map(c => `<col data-colid="${c.id}" style="width:${c.width || 140}px">`).join('')}
              <col style="width:48px">
            </colgroup>
            <thead class="bg-slate-50 sticky top-0 z-10">
              <tr>
                <th class="w-10 sticky-col text-left px-2 py-2">#</th>
                ${visibleCols.map(c => `
                  <th class="text-left px-2 py-2 whitespace-nowrap th-resizable" data-colid="${c.id}">
                    <div class="relative">${escapeHtml(c.label)}<span class="resize-handle" data-colid="${c.id}"></span></div>
                  </th>`).join('')}
                <th class="w-10"></th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((row, ri) => `
                <tr class="odd:bg-white even:bg-slate-50/40 hover:bg-amber-50">
                  <td class="sticky-col text-center text-xs text-slate-500 px-1">${ri + 1}</td>
                  ${visibleCols.map((col, vi) => `
                    <td class="px-1 py-0.5" title="${cellTitle(row[col.id], col)}">
                      ${col.type === 'calc'
        ? `<div class="text-right font-medium tabular-nums pr-1 truncate-cell" title="${moneyFmt.format(row[col.id] || 0)}">${moneyFmt.format(row[col.id] || 0)}</div>`
        : gridCell(row[col.id], col, ri, vi)}
                    </td>`).join('')}
                  <td class="text-center">
                    <button data-action="delRow" data-ri="${ri}" class="text-xs text-red-600 hover:underline">Del</button>
                  </td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </section>

      <section class="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="rounded-2xl border bg-white p-4 shadow-sm lg:col-span-2">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Notes & Audit</h2>
            <button data-action="toggleSection" data-section="notes" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show notes">${collapsed.notes ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.notes ? notesSummary(notes, status) : `
          <textarea class="h-28 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" placeholder="Internal note / customer note / delivery note ..." data-action="bindNotes">${escapeHtml(notes)}</textarea>
          <div class="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-slate-600">
            <div>Created: <strong>you</strong></div>
            <div>Created On: <strong>${new Date().toLocaleString()} </strong></div>
            <div>Last Edited: <strong>${new Date().toLocaleTimeString()} </strong></div>
            <div>Status: <strong>${status} </strong></div>
          </div>
          <div class="mt-3">${keyboardHelp()}</div>`}
        </div>

        <div class="rounded-2xl border bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Totals</h2>
            <button data-action="toggleSection" data-section="totals" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show totals">${collapsed.totals ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.totals ? totalsSummary(this.state.voucherType, totals) : `
          ${voucherType === 'Journal' ? `
            <div class="space-y-1 text-sm">
              ${rowKV('Total Dr', moneyFmt.format(totals.dr))}
              ${rowKV('Total Cr', moneyFmt.format(totals.cr))}
              ${rowKV('Difference', `<span class="${Math.abs(totals.diff) < 0.001 ? 'text-emerald-700' : 'text-red-700'}">${moneyFmt.format(totals.diff)}</span>`)}
            </div>
          ` : `
            <div class="space-y-1 text-sm">
              ${rowKV('Subtotal', moneyFmt.format(totals.sub))}
              ${rowKV('Discounts', moneyFmt.format(totals.disc))}
              ${totals.taxBreak.map(([p, val]) => rowKV(`Tax ${p}%`, moneyFmt.format(val))).join('')}
              ${rowKV('Addl. Charges (±)', moneyFmt.format(totals.chargesTotal))}
              ${rowKV('Rounding', moneyFmt.format(totals.roundAdj))}
              <div class="border-t my-1"></div>
              ${rowKV('<strong>Grand Total</strong>', `<strong>${moneyFmt.format(totals.grand)}</strong>`)}
              <div class="mt-2 text-xs text-slate-500">Due Date: <strong>${this.computeDueDate(header.date, header.creditDays)}</strong></div>
            </div>
          `}
          <div class="mt-3 flex gap-2">
            <button data-action="paymentTerms" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50 w-full">Payment Terms</button>
            <button data-action="toggleCharges" class="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50 w-full">Additional Charges</button>
          </div>`}
        </div>
      </section>

      <footer class="mt-6 text-center text-xs text-slate-500">
        Built for demo. No backend. Columns & widths persist per voucher in localStorage.
      </footer>

      ${this.state.showUdfModal ? udfModalHtml(this.state) : ''}
      ${this.state.showColManager ? colManagerHtml(this.getColumns(), this.state.colManagerDraft) : ''}
      ${this.state.showCharges ? chargesModalHtml(charges) : ''}
    `;

    setTimeout(() => { this.focusCurrent(); this.bindResizeHandles(); this.bindCsv(); }, 0);
    const grid = document.getElementById('grid');
    grid.addEventListener('paste', (e) => this.handlePaste(e));
    el.onclick = (ev) => this.handleClick(ev);
    el.onchange = (ev) => this.handleChange(ev);
    el.onkeydown = (ev) => this.handleKeydown(ev);
    el.onfocusin = (ev) => this.handleFocusIn(ev);
    el.oninput = (ev) => { if (ev.target && ev.target.getAttribute('data-action') === 'bindNotes') { this.state.notes = ev.target.value; this.persistPresets(); } };
  },

  /** Column resizing handlers */
  bindResizeHandles() {
    const handles = document.querySelectorAll('.resize-handle');
    handles.forEach(h => {
      h.onmousedown = (e) => {
        e.preventDefault();
        const colId = h.getAttribute('data-colid');
        const colEl = document.querySelector(`col[data-colid="${colId}"]`);
        const startX = e.clientX;
        const startW = parseInt(colEl.style.width, 10) || 140;
        this._resizing = { colId, startX, startW };
      };
    });
  },
  onResize(e) {
    if (!this._resizing) return;
    const { colId, startX, startW } = this._resizing;
    const delta = e.clientX - startX;
    const newW = Math.max(60, startW + delta);
    const colEl = document.querySelector(`col[data-colid="${colId}"]`);
    if (colEl) colEl.style.width = newW + 'px';
  },
  stopResize() {
    if (!this._resizing) return;
    const { colId } = this._resizing;
    const colEl = document.querySelector(`col[data-colid="${colId}"]`);
    const newW = parseInt(colEl.style.width, 10) || 140;
    const vt = this.state.voucherType;
    const cols = this.getColumns();
    const nextPrefs = cols.map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width: id === colId ? newW : width, order }));
    this.state.colPrefsByType[vt] = nextPrefs;
    this.persistPresets();
    this._resizing = null;
  },

  /** CSV/Excel I/O */
  bindCsv() {
    const input = document.getElementById('csvFile');
    if (!input) return;
    input.onchange = (e) => {
      const file = e.target.files?.[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const txt = String(reader.result || '');
        const lines = txt.split(/\r?\n/).filter(Boolean);
        if (!lines.length) return;
        const cols = this.getColumns().filter(c => c.visible !== false && c.type !== 'calc');
        const header = lines[0].split(',').map(s => s.trim());
        const mapIdx = header.map(h => cols.findIndex(c => c.label.toLowerCase() === h.toLowerCase() || c.id.toLowerCase() === h.toLowerCase()));
        const out = [];
        for (let i = 1; i < lines.length; i++) {
          const row = this.blankRow();
          const cells = lines[i].split(',');
          mapIdx.forEach((ci, j) => { if (ci >= 0) { const col = cols[ci]; row[col.id] = col.type === 'number' ? asNum(cells[j], 0) : cells[j]; } });
          out.push(row);
        }
        this.state.rows = out.length ? out : this.state.rows; this.render();
      };
      reader.readAsText(file);
    };
  },
  exportCsv() {
    const cols = this.getColumns().filter(c => c.visible !== false);
    const header = cols.map(c => c.id).join(',');
    const lines = [header];
    this.state.rows.forEach(r => lines.push(cols.map(c => (r[c.id] ?? '')).join(',')));
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `voucher_rows_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url);
  },
  sampleXlsx() {
    const cols = this.getColumns().filter(c => c.visible !== false && c.type !== 'calc');
    const header = cols.map(c => c.label);
    const sampleRow = cols.map(c => { if (c.type === 'number') return 0; if (c.id === 'qty') return 1; if (c.id === 'taxP') return 13; return ''; });
    const ws = XLSX.utils.aoa_to_sheet([header, sampleRow]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Sample');
    XLSX.writeFile(wb, `sample_${this.state.voucherType.toLowerCase()}_${new Date().toISOString().slice(0,10)}.xlsx`);
  },
  exportXlsx() {
    const cols = this.getColumns().filter(c => c.visible !== false);
    const header = cols.map(c => c.label);
    const rows = this.state.rows.map(r => cols.map(c => r[c.id] ?? ''));
    const ws = XLSX.utils.aoa_to_sheet([header, ...rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Voucher');
    XLSX.writeFile(wb, `voucher_${this.state.voucherType.toLowerCase()}_${new Date().toISOString().slice(0,10)}.xlsx`);
  },

  /** Events */
  handleClick(e) {
    const t = e.target;
    const action = t.getAttribute('data-action');
    if (!action) return;
    if (action === 'setType') {
      const type = t.getAttribute('data-type');
      if (type && type !== this.state.voucherType) {
        this.state.voucherType = type;
        this.resetRows();
        this.state.focus = { r: 0, c: 0 };
        this.render();
      }
    }
    if (action === 'toggleSection') { const s = t.getAttribute('data-section'); this.state.collapsed[s] = !this.state.collapsed[s]; this.persistPresets(); this.render(); }
    if (action === 'saveDraft') {
      const payload = this.buildPayload();
      this.persistPresets();
      if (Endpoints.save) {
        postJSON(Endpoints.save, payload).then(r => {
          if (r.ok) { notify('Draft saved on server.'); }
          else { console.warn('Server rejected draft save:', r.status, r.text); notify('Draft save failed on server. Saved locally.'); }
        }).catch(err => { console.error(err); notify('Server unreachable. Draft saved locally (console shows payload).'); });
      } else {
        console.log('Draft payload', payload);
        notify('Draft saved locally (console shows payload).');
      }
    }
    if (action === 'submit') {
      const errs = this.validate(); 
      if (errs.length) return alert('Fix issues:\n- ' + errs.join('\n- '));
      const payload = this.buildPayload();
      if (Endpoints.submit) {
        postJSON(Endpoints.submit, payload).then(r => {
          if (r.ok) { this.state.status = 'Submitted'; this.render(); notify('Submitted to server.'); }
          else { console.warn('Server rejected submit:', r.status, r.text); notify('Submit failed on server. Kept as Draft.'); }
        }).catch(err => { console.error(err); notify('Server unreachable. Submit not sent.'); });
      } else {
        this.state.status = 'Submitted';
        this.render();
        notify('Submitted locally (no backend endpoint configured).');
      }
    }
    if (action === 'approve') {
      if (this.state.status !== 'Submitted') return alert('Submit first');
      const payload = this.buildPayload();
      if (Endpoints.approve) {
        postJSON(Endpoints.approve, payload).then(r => {
          if (r.ok) { this.state.status = 'Approved'; this.render(); notify('Approved on server.'); }
          else { console.warn('Server rejected approve:', r.status, r.text); notify('Approve failed on server.'); }
        }).catch(err => { console.error(err); notify('Server unreachable. Approve not sent.'); });
      } else {
        this.state.status = 'Approved';
        this.render();
        notify('Approved locally (no backend endpoint configured).');
      }
    }

    if (action === 'addRow') { this.state.rows.push(this.blankRow()); this.render(); }
    if (action === 'add10') { for (let i = 0; i < 10; i++) this.state.rows.push(this.blankRow()); this.render(); }
    if (action === 'clearRows') { this.resetRows(); this.render(); }
    if (action === 'delRow') { const ri = +t.getAttribute('data-ri'); this.state.rows.splice(ri, 1); this.render(); }

    if (action === 'openUdf') { this.state.udfScope = t.getAttribute('data-scope') || 'Header'; this.state.udfDraft = { label: '', type: 'text', required: false, options: '' }; this.state.showUdfModal = true; this.render(); }
    if (action === 'removeUdf') { const scope = t.getAttribute('data-scope'); const id = t.getAttribute('data-udfid'); if (scope === 'Header') this.state.udfHeaderDefs = this.state.udfHeaderDefs.filter(x => x.id !== id); else this.state.udfLineDefs = this.state.udfLineDefs.filter(x => x.id !== id); this.persistPresets(); this.render(); }
    if (action === 'udfCancel') { this.state.showUdfModal = false; this.render(); }
    if (action === 'udfAdd') {
      const d = this.state.udfDraft;
      if (!d.label.trim()) return alert('Label is required');
      const out = { id: 'udf_' + uid(), label: d.label.trim(), type: d.type, required: !!(d.required === true || d.required === '1') };
      if (d.type === 'select') out.options = (d.options || '').split(',').map(s => s.trim()).filter(Boolean);
      if (this.state.udfScope === 'Header') this.state.udfHeaderDefs.push(out); else this.state.udfLineDefs.push(out);
      this.state.showUdfModal = false; this.persistPresets(); this.render();
    }

    if (action === 'openCols') { const cols = this.getColumns(); this.state.colManagerDraft = cols.map((c, i) => ({ ...c, order: i })); this.state.showColManager = true; this.render(); }
    if (action === 'cmCancel') { this.state.showColManager = false; this.render(); }
    if (action === 'cmToggle') { const id = t.getAttribute('data-col'); this.state.colManagerDraft = this.state.colManagerDraft.map(x => x.id === id ? { ...x, visible: !(x.visible !== false) } : x); this.render(); }
    if (action === 'cmMove') { const id = t.getAttribute('data-col'); const dir = +t.getAttribute('data-dir'); const arr = this.state.colManagerDraft; const idx = arr.findIndex(x => x.id === id); const j = clamp(idx + dir, 0, arr.length - 1); const [x] = arr.splice(idx, 1); arr.splice(j, 0, x); this.render(); }
    if (action === 'cmApply') { const vt = this.state.voucherType; this.state.colPrefsByType[vt] = this.state.colManagerDraft.map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width, order })); this.state.showColManager = false; this.persistPresets(); this.render(); }
    if (action === 'saveCols') { const vt = this.state.voucherType; const cols = this.getColumns(); this.state.colPrefsByType[vt] = cols.map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width, order })); this.persistPresets(); alert('Column prefs saved.'); }
    if (action === 'resetCols') { const vt = this.state.voucherType; delete this.state.colPrefsByType[vt]; this.persistPresets(); this.render(); }

    if (action === 'importCsv') { const el = document.getElementById('csvFile'); if (el) el.click(); }
    if (action === 'exportCsv') { this.exportCsv(); }
    if (action === 'sampleXlsx') { this.sampleXlsx(); }
    if (action === 'exportXlsx') { this.exportXlsx(); }

    if (action === 'attach') { alert('Attach files: wire this to your uploader'); }
    if (action === 'paymentTerms') { alert('Wire Payment Terms & Due Date calc to your backend'); }
    if (action === 'toggleCharges') { this.state.showCharges = true; this.render(); }
    if (action === 'chgClose') { this.state.showCharges = false; this.render(); }
    if (action === 'chgAdd') { this.state.charges.push({ id: uid(), label: 'New Charge', mode: 'amount', value: 0, sign: 1 }); this.persistPresets(); this.render(); }
    if (action === 'chgDel') { const id = t.getAttribute('data-id'); this.state.charges = this.state.charges.filter(c => c.id !== id); this.persistPresets(); this.render(); }

    if (action === 'runTests') { this.selfTests(); alert('Self-tests executed. Check console for assertions.'); }
  },

  handleChange(e) {
    const t = e.target;
    const hkey = t.getAttribute('data-hkey');
    if (hkey) {
      if (hkey === 'priceInclusiveTax') this.state.header[hkey] = (t.value === 'inc');
      else if (hkey === 'exRate' || hkey === 'creditDays') this.state.header[hkey] = asNum(t.value, hkey === 'exRate' ? 1 : 0);
      else this.state.header[hkey] = t.value;
      this.persistPresets(); this.render(); return;
    }
    if (t.getAttribute('data-hudf')) {
      const id = t.getAttribute('data-hudf'); const type = t.getAttribute('data-type');
      if (type === 'checkbox') this.state.header[id] = !!t.checked; else if (type === 'number') this.state.header[id] = asNum(t.value); else this.state.header[id] = t.value;
      this.persistPresets(); this.render(); return;
    }
    if (t.classList.contains('cell-input')) {
      const ri = +t.getAttribute('data-ri'); const colId = t.getAttribute('data-colid'); const type = t.getAttribute('data-type');
      const row = this.state.rows[ri];
      if (type === 'checkbox') row[colId] = !!t.checked; else if (type === 'number') row[colId] = asNum(t.value); else row[colId] = t.value;
      this.render();
    }
    if (t.getAttribute('data-udf-draft')) {
      const key = t.getAttribute('data-udf-draft');
      if (key === 'required') this.state.udfDraft.required = (t.value === '1');
      else this.state.udfDraft[key] = t.value;
    }
    if (t.getAttribute('data-chg-id')) {
      const id = t.getAttribute('data-chg-id');
      const key = t.getAttribute('data-chg-key');
      const idx = this.state.charges.findIndex(c => c.id == id); if (idx < 0) return;
      if (key == 'label') this.state.charges[idx].label = t.value;
      if (key == 'mode') this.state.charges[idx].mode = t.value;
      if (key == 'value') this.state.charges[idx].value = asNum(t.value, 0);
      if (key == 'sign') this.state.charges[idx].sign = (t.value === '-1' ? -1 : 1);
      this.persistPresets(); this.render();
    }
  },

  handleKeydown(e) {
    const t = e.target;
    if (!t.classList.contains('cell-input')) return;
    const ri = +t.getAttribute('data-ri');
    const ci = +t.getAttribute('data-ci');
    const editableCols = this.getColumns().filter(c => c.visible !== false && c.type !== 'calc');
    const maxR = this.state.rows.length - 1; const maxC = editableCols.length - 1;
    if (e.key === 'ArrowDown') { e.preventDefault(); this.state.focus = { r: clamp(ri + 1, 0, maxR), c: ci }; this.focusCurrent(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); this.state.focus = { r: clamp(ri - 1, 0, maxR), c: ci }; this.focusCurrent(); }
    if (e.key === 'ArrowRight' || (e.key === 'Tab' && !e.shiftKey)) { e.preventDefault(); this.state.focus = { r: ri, c: clamp(ci + 1, 0, maxC) }; this.focusCurrent(); }
    if (e.key === 'ArrowLeft' || (e.key === 'Tab' && e.shiftKey)) { e.preventDefault(); this.state.focus = { r: ri, c: clamp(ci - 1, 0, maxC) }; this.focusCurrent(); }
    if (e.key === 'Enter') { e.preventDefault(); this.state.rows.splice(ri + 1, 0, this.blankRow()); this.state.focus = { r: ri + 1, c: 0 }; this.render(); }
    if (e.key === 'Delete' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.state.rows.splice(ri, 1); this.state.focus = { r: clamp(ri, 0, Math.max(0, this.state.rows.length - 1)), c: 0 }; this.render(); }
  },

  handleFocusIn(e) {
    const t = e.target; if (!t.classList.contains('cell-input')) return;
    this.state.focus = { r: +t.getAttribute('data-ri'), c: +t.getAttribute('data-ci') };
    document.querySelectorAll('.cell-focus').forEach(x => x.classList.remove('cell-focus'));
    t.classList.add('cell-focus');
  },

  /** Excel-like paste */
  handlePaste(e) {
    const t = document.activeElement; if (!t || !t.classList.contains('cell-input')) return;
    const ri = +t.getAttribute('data-ri'); const ci = +t.getAttribute('data-ci');
    const text = e.clipboardData.getData('text/plain'); if (!text) return;
    e.preventDefault();
    const lines = text.replace(/\r/g, '').split('\n').filter(Boolean).map(ln => ln.split('\t'));
    const editableCols = this.getColumns().filter(c => c.visible !== false && c.type !== 'calc');
    for (let r = 0; r < lines.length; r++) {
      const rowIdx = ri + r; if (!this.state.rows[rowIdx]) this.state.rows[rowIdx] = this.blankRow();
      for (let c = 0; c < lines[r].length; c++) {
        const colIdx = ci + c; const col = editableCols[colIdx]; if (!col) continue;
        const raw = lines[r][c]; let val = raw;
        if (col.type === 'number') val = asNum(raw, 0);
        if (col.type === 'checkbox') val = ['1', 'true', 'yes', 'y', 'on'].includes(String(raw).toLowerCase());
        this.state.rows[rowIdx][col.id] = val;
      }
    }
    this.render();
  },

  focusCurrent() {
    const { r, c } = this.state.focus;
    const input = document.querySelector(`.cell-input[data-ri="${r}"][data-ci="${c}"]`);
    if (input) { input.focus(); input.select?.(); }
  },

  computeDueDate(dateStr, days) {
    const d = new Date(dateStr || new Date()); if (!Number.isFinite(days)) return d.toISOString().slice(0, 10);
    const out = new Date(d.getTime() + (asNum(days, 0) * 86400000));
    return out.toISOString().slice(0, 10);
  },

  /** Validation + payload */
  validate() {
    const errs = [];
    const { header, voucherType, udfHeaderDefs, udfLineDefs, rows } = this.state;
    if (!header.date) errs.push('Date is required');
    if (voucherType !== 'Journal' && !header.party) errs.push('Party/Customer/Supplier is required');
    udfHeaderDefs.forEach(f => { if (f.required && (header[f.id] === undefined || header[f.id] === '')) errs.push(`Header UDF '${f.label}' is required`); });
    if (voucherType === 'Journal') {
      const { diff } = this.computeTotals(); if (Math.abs(diff) > 0.001) errs.push('Journal is not balanced (Dr != Cr)');
    } else {
      const nonEmpty = rows.filter(r => (r.item || '').trim() !== ''); if (!nonEmpty.length) errs.push('At least one line with Item/Service is required');
    }
    rows.forEach((r, i) => udfLineDefs.forEach(f => { if (f.required && (r[f.id] === undefined || r[f.id] === '')) errs.push(`Row ${i + 1}: UDF '${f.label}' is required`); }));
    return errs;
  },
  buildPayload() {
    const columns = this.getColumns().map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width, order }));
    const { voucherType, header, rows, udfHeaderDefs, udfLineDefs, notes, charges, numbering } = this.state;
    const totals = this.computeTotals();
    return { voucherType, header, rows, udfHeaderDefs, udfLineDefs, columns, notes, charges, numbering, totals };
  },

  /** Self-tests */
  selfTests() {
    this.state.voucherType = 'Sales';
    this.state.rows = [{ qty: 2, rate: 100, discP: 10, taxP: 13 }, { qty: 1, rate: 50, discP: 0, taxP: 0 }].map(x => ({ id: uid(), item: 'x', desc: '', uom: '', warehouse: '', batch: '', taxGroup: '', ...x }));
    const t1 = this.computeTotals();
    console.assert(t1.grand > 0 && Math.abs(t1.sub + t1.tax + t1.chargesTotal + t1.roundAdj - t1.grand) < 0.01, 'Totals add up');

    this.state.voucherType = 'Journal'; this.resetRows(2); this.state.rows[0].dr = 100; this.state.rows[1].cr = 100;
    const t2 = this.computeTotals(); console.assert(Math.abs(t2.diff) < 0.001, 'Journal should balance');

    this.state.voucherType = 'Sales'; this.resetRows(1); this.state.rows[0] = { ...this.state.rows[0], qty: 1, rate: 100, discP: 0, taxP: 0 };
    this.state.charges = [{ id: uid(), label: 'Add 10%', mode: 'percent', value: 10, sign: 1 }];
    const t3 = this.computeTotals(); console.assert(Math.abs(t3.chargesTotal - 10) < 0.01, '10% charge must be 10');
    this.state.charges = [{ id: uid(), label: 'Freight', mode: 'amount', value: 0, sign: 1 }, { id: uid(), label: 'Discount @ Bill', mode: 'percent', value: 0, sign: -1 }];
    this.state.voucherType = 'Sales'; this.resetRows(); this.render();
  }
};

/** Small UI helpers */
function Labeled(label, inner) { return `<label class="flex flex-col gap-1 text-sm"><span class="text-slate-600">${label}</span>${inner}</label>`; }
function rowKV(k, vHtml) { return `<div class="flex items-center justify-between"><span class="text-slate-600">${k}</span><span class="font-medium tabular-nums">${vHtml}</span></div>`; }
function keyboardHelp() {
  return `<div class="rounded-xl border bg-slate-50 p-3 text-xs leading-6">
    <div class="font-medium mb-1">Keyboard Shortcuts</div>
    <ul class="list-disc pl-5 grid grid-cols-1 md:grid-cols-2 gap-x-6">
      <li>Drag header edge to resize column</li>
      <li>Arrows / Tab: move between cells</li>
      <li>Shift+Tab: move backward</li>
      <li>Enter: insert a new row below</li>
      <li>Ctrl+Delete: delete current row</li>
      <li>Paste: Ctrl+V from Excel/Sheets to auto-fill grid</li>
    </ul>
  </div>`;
}
function gridCell(value, col, ri, vi) {
  const title = col.type === 'number' ? String(value ?? '') : escapeHtml(value ?? '');
  const base = `class="cell-input h-8 px-2 py-1 rounded-lg border border-slate-300 bg-white ${col.align === 'right' ? 'text-right' : ''}" data-ri="${ri}" data-ci="${vi}" data-colid="${col.id}" data-type="${col.type}" title="${title}"`;
  if (col.type === 'number') return `<input ${base} value="${value ?? ''}">`;
  if (col.type === 'date') return `<input type="date" ${base} value="${value ?? ''}">`;
  if (col.type === 'select') return `<select ${base}>${['', ...(col.options || [])].map(o => `<option value="${escapeHtml(o)}" ${(value || '') === o ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}</select>`;
  if (col.type === 'checkbox') return `<input type="checkbox" ${base} ${value ? 'checked' : ''}>`;
  return `<input ${base} value="${escapeHtml(value ?? '')}">`;
}
function fieldControl(def, value) {
  const title = def.type === 'number' ? String(value ?? '') : escapeHtml(value ?? '');
  const base = `class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white ${def.type === 'number' ? 'text-right' : ''}" data-hudf="${def.id}" data-type="${def.type}" title="${title}"`;
  if (def.type === 'number') return `<input type="number" ${base} value="${value}">`;
  if (def.type === 'date') return `<input type="date" ${base} value="${value}">`;
  if (def.type === 'select') return `<select ${base}>${['', ...(def.options || [])].map(o => `<option value="${escapeHtml(o)}" ${(value || '') === o ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}</select>`;
  if (def.type === 'checkbox') return `<div class="h-10 flex items-center"><input type="checkbox" ${base} ${value ? 'checked' : ''}></div>`;
  return `<input ${base} value="${escapeHtml(value || '')}">`;
}
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }
function cellTitle(val, col) { return col.type === 'number' ? String(val ?? '') : escapeHtml(val ?? ''); }

function headerSummary(h, vt) {
  return `<div class="text-sm flex flex-wrap gap-2">
    ${vt !== 'Journal' ? chip('Party', escapeHtml(h.party || '—')) : ''}
    ${chip('Date', escapeHtml(h.date || '—'))}
    ${chip('Branch', escapeHtml(h.branch || '—'))}
    ${chip('Currency', escapeHtml(h.currency || '—'))}
    ${vt !== 'Journal' ? chip('Pricing', h.priceInclusiveTax ? 'Tax Inclusive' : 'Tax Exclusive') : ''}
  </div>`;
}
function actionsSummary(rows, cols) {
  const visible = cols.filter(c => c.visible !== false).length;
  return `<div class="text-sm flex flex-wrap gap-2">${chip('Rows', rows.length)}${chip('Visible Cols', visible)}${chip('Hidden Cols', Math.max(0, cols.length - visible))}</div>`;
}
function notesSummary(notes, status) {
  const short = (notes || '').trim().slice(0, 80) || '—';
  return `<div class="text-sm">${chip('Notes', escapeHtml(short))}${chip('Status', escapeHtml(status))}</div>`;
}
function totalsSummary(vt, totals) {
  if (vt === 'Journal') return `<div class="text-sm">${chip('Dr', moneyFmt.format(totals.dr))}${chip('Cr', moneyFmt.format(totals.cr))}${chip('Diff', moneyFmt.format(totals.diff))}</div>`;
  return `<div class="text-sm">${chip('Subtotal', moneyFmt.format(totals.sub))}${chip('Tax', moneyFmt.format(totals.tax))}${chip('Grand', moneyFmt.format(totals.grand))}</div>`;
}
function chip(k, v) { return `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700"><span class="text-slate-500">${k}:</span> <span class="font-medium">${v}</span></span>`; }

/** Modals */
function udfModalHtml(state) {
  const d = state.udfDraft; const scope = state.udfScope;
  return `
  <div class="modal-backdrop" data-action="udfCancel">
    <div class="bg-white rounded-2xl shadow-xl w-[560px] max-w-[95vw] p-4" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold">Add UDF – ${scope} level</h3>
        <button class="text-slate-500 hover:text-black" data-action="udfCancel">✕</button>
      </div>
      <div class="grid grid-cols-2 gap-3">
        ${Labeled('Label *', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${escapeHtml(d.label)}" data-udf-draft="label">`)}
        ${Labeled('Type', `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-udf-draft="type">
            <option value="text" ${d.type === 'text' ? 'selected' : ''}>Text</option>
            <option value="number" ${d.type === 'number' ? 'selected' : ''}>Number</option>
            <option value="date" ${d.type === 'date' ? 'selected' : ''}>Date</option>
            <option value="select" ${d.type === 'select' ? 'selected' : ''}>Dropdown</option>
            <option value="checkbox" ${d.type === 'checkbox' ? 'selected' : ''}>Checkbox</option>
          </select>`)}
        ${Labeled('Required?', `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-udf-draft="required">
            <option value="0" ${!d.required ? 'selected' : ''}>No</option>
            <option value="1" ${d.required ? 'selected' : ''}>Yes</option>
          </select>`)}
        ${Labeled('Options (CSV for Dropdown)', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" placeholder="e.g. Cash, Credit, Cheque" value="${escapeHtml(d.options || '')}" data-udf-draft="options">`)}
      </div>
      <div class="flex justify-end gap-2 mt-4">
        <button data-action="udfCancel" class="px-3 py-2 rounded-xl border">Cancel</button>
        <button data-action="udfAdd" class="px-3 py-2 rounded-xl bg-emerald-600 text-white">Add Field</button>
      </div>
    </div>
  </div>`;
}
function colManagerHtml(cols, draft) {
  const rows = (draft && draft.length ? draft : cols).map((c, i) => ({ ...c, order: i }));
  return `
  <div class="modal-backdrop" data-action="cmCancel">
    <div class="bg-white rounded-2xl shadow-xl w-[680px] max-w-[96vw] p-4" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold">Columns</h3>
        <button class="text-slate-500 hover:text-black" data-action="cmCancel">✕</button>
      </div>
      <div class="max-h-[60vh] overflow-auto rounded-xl border">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 sticky top-0">
            <tr><th class="text-left px-3 py-2">Column</th><th class="text-left px-3 py-2">Visible</th><th class="px-3 py-2">Order</th></tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr class="odd:bg-white even:bg-slate-50/40">
                <td class="px-3 py-2">${escapeHtml(r.label)}</td>
                <td class="px-3 py-2"><button class="px-2 py-1 rounded border" data-action="cmToggle" data-col="${r.id}">${r.visible !== false ? 'Hide' : 'Show'}</button></td>
                <td class="px-3 py-2 text-right space-x-1">
                  <button class="px-2 py-1 rounded border" data-action="cmMove" data-col="${r.id}" data-dir="-1">↑</button>
                  <button class="px-2 py-1 rounded border" data-action="cmMove" data-col="${r.id}" data-dir="1">↓</button>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="flex justify-end gap-2 mt-4">
        <button data-action="cmCancel" class="px-3 py-2 rounded-xl border">Cancel</button>
        <button data-action="cmApply" class="px-3 py-2 rounded-xl bg-emerald-600 text-white">Apply</button>
      </div>
    </div>
  </div>`;
}
function chargesModalHtml(charges) {
  return `
  <div class="modal-backdrop" data-action="chgClose">
    <div class="bg-white rounded-2xl shadow-xl w-[760px] max-w-[96vw] p-4" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold">Additional Charges</h3>
        <button class="text-slate-500 hover:text-black" data-action="chgClose">✕</button>
      </div>
      <div class="max-h-[60vh] overflow-auto rounded-xl border">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 sticky top-0">
            <tr>
              <th class="text-left px-3 py-2">Label</th>
              <th class="text-left px-3 py-2">Mode</th>
              <th class="text-left px-3 py-2">Value</th>
              <th class="text-left px-3 py-2">Sign (+/-)</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            ${charges.map(c => `
              <tr class="odd:bg-white even:bg-slate-50/40">
                <td class="px-3 py-2"><input class="h-9 px-2 py-1 rounded-lg border border-slate-300 bg-white w-full" value="${escapeHtml(c.label)}" data-chg-id="${c.id}" data-chg-key="label"></td>
                <td class="px-3 py-2">
                  <select class="h-9 px-2 py-1 rounded-lg border border-slate-300 bg-white" data-chg-id="${c.id}" data-chg-key="mode"> 
                    <option value="amount" ${c.mode === 'amount' ? 'selected' : ''}>Amount</option>
                    <option value="percent" ${c.mode === 'percent' ? 'selected' : ''}>Percent of Taxable+Tax</option>
                  </select>
                </td>
                <td class="px-3 py-2"><input type="number" class="h-9 px-2 py-1 rounded-lg border border-slate-300 bg-white text-right" value="${c.value}" data-chg-id="${c.id}" data-chg-key="value"></td>
                <td class="px-3 py-2">
                  <select class="h-9 px-2 py-1 rounded-lg border border-slate-300 bg-white" data-chg-id="${c.id}" data-chg-key="sign">
                    <option value="1" ${c.sign === 1 ? 'selected' : ''}>+</option>
                    <option value="-1" ${c.sign === -1 ? 'selected' : ''}>-</option>
                  </select>
                </td>
                <td class="px-3 py-2 text-right"><button class="px-2 py-1 rounded border text-red-600" data-action="chgDel" data-id="${c.id}">Delete</button></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="flex justify-between items-center mt-4">
        <button data-action="chgAdd" class="px-3 py-2 rounded-xl border">+ Add Charge</button>
        <button data-action="chgClose" class="px-3 py-2 rounded-xl bg-emerald-600 text-white">Done</button>
      </div>
    </div>
  </div>`;
}

/** Boot */
window.App = App;
window.addEventListener('DOMContentLoaded', () => App.init());
