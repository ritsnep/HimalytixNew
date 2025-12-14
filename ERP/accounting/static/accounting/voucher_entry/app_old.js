'use strict';

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
    const p = dict.get(c.id); if (!p) /* Line 41 omitted */
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
    // Load initial state from Django if provided
    if (window.initialState) {
      this.state = { ...this.state, ...window.initialState };
    }

    const presets = loadPresets();
    this.state.colPrefsByType = presets.colPrefsByType || this.state.colPrefsByType;
    this.state.udfHeaderDefs = presets.udfHeaderDefs || this.state.udfHeaderDefs;
    this.state.udfLineDefs = presets.udfLineDefs || this.state.udfLineDefs;
    this.state.collapsed = presets.collapsed || this.state.collapsed;
    this.state.charges = presets.charges || this.state.charges;
    this.state.numbering = presets.numbering || this.state.numbering;

    // Ensure default Header UDF present
    if (!this.state.udfHeaderDefs.some(x => x.label.toLowerCase().includes('invoice'))) {
      this.state.udfHeaderDefs.push({ id: 'invoice_no', label: 'Invoice No.', type: 'text', required: false, options: [] });
    }

    this.resetRows();
    this.render();

    // Global listeners (column resize)
    if (!this._resizeBound) {
      this._resizeBound = true;
      document.addEventListener('mousedown', this.onResize.bind(this));
      document.addEventListener('mouseup', this.stopResize.bind(this));
    }
  },

  getColumns() {
    const { voucherType, udfLineDefs, colPrefsByType } = this.state;
    return buildColumns(voucherType, udfLineDefs, colPrefsByType[voucherType]);
  },
  blankRow() {
    if (this.state.voucherType === 'Journal') /* Line 113 omitted */
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
    if (voucherType === 'Journal') {/* Lines 128-131 omitted */}
    let sub = 0, disc = 0, tax = 0; const taxBreak = new Map();
    rows.forEach(r => {/* Lines 134-142 omitted */});
    const baseForCharges = sub + tax;
    let chargesTotal = 0;
    charges.forEach(c => {/* Lines 146-150 omitted */});
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
    /* Lines 175-363 omitted */
  },

  /** Column resizing handlers */
  bindResizeHandles() {/* Lines 367-378 omitted */},
  onResize(e) {/* Lines 380-386 omitted */},
  stopResize() {/* Lines 388-398 omitted */},

  /** CSV/Excel I/O */
  bindCsv() {/* Lines 402-425 omitted */},
  exportCsv() {/* Lines 427-433 omitted */},
  sampleXlsx() {/* Lines 435-442 omitted */},
  exportXlsx() {/* Lines 444-451 omitted */},

  /** Events */
  handleClick(e) {/* Lines 455-510 omitted */},

  handleChange(e) {/* Lines 513-547 omitted */},

  handleKeydown(e) {/* Lines 550-562 omitted */},

  handleFocusIn(e) {/* Lines 565-569 omitted */},

  /** Excel-like paste */
  handlePaste(e) {/* Lines 573-590 omitted */},

  focusCurrent() {/* Lines 593-596 omitted */},

  computeDueDate(dateStr, days) {/* Lines 599-602 omitted */},

  /** Validation + payload */
  validate() {/* Lines 606-618 omitted */},
  buildPayload() {/* Lines 620-624 omitted */},

  /** Self-tests */
  selfTests() {/* Lines 628-641 omitted */}
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
  if (col.type === 'number') /* Line 663 omitted */
  if (col.type === 'date') /* Line 664 omitted */
  if (col.type === 'select') /* Line 665 omitted */
  if (col.type === 'checkbox') /* Line 666 omitted */
  return `<input ${base} value="${escapeHtml(value ?? '')}">`;
}
function fieldControl(def, value) {
  const title = def.type === 'number' ? String(value ?? '') : escapeHtml(value ?? '');
  const base = `class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white ${def.type === 'number' ? 'text-right' : ''}" data-hudf="${def.id}" data-type="${def.type}" title="${title}"`;
  if (def.type === 'number') /* Line 672 omitted */
  if (def.type === 'date') /* Line 673 omitted */
  if (def.type === 'select') /* Line 674 omitted */
  if (def.type === 'checkbox') /* Line 675 omitted */
  return `<input ${base} value="${escapeHtml(value || '')}">`;
}
function escapeHtml(s) { return String(s).replace(/[&<>\"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }
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
  if (vt === 'Journal') /* Line 699 omitted */
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
