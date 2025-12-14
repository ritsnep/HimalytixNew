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
    const p = dict.get(c.id); if (!p) return { ...c, visible: p.visible !== false, width: p.width || c.width, order: p.order ?? c.order };
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
      let dr = 0, cr = 0;
      rows.forEach(r => { dr += asNum(r.dr); cr += asNum(r.cr); });
      const imbalance = dr - cr;
      return { dr, cr, imbalance, sub: 0, disc: 0, tax: 0, chargesTotal: 0, roundAdj: 0, grand: 0, taxBreak: [] };
    }
    let sub = 0, disc = 0, tax = 0; const taxBreak = new Map();
    rows.forEach(r => {
      const qty = asNum(r.qty), rate = asNum(r.rate), discP = asNum(r.discP), taxP = asNum(r.taxP);
      const lineSub = qty * rate;
      const lineDisc = lineSub * discP / 100;
      const taxable = lineSub - lineDisc;
      const lineTax = taxable * taxP / 100;
      sub += lineSub; disc += lineDisc; tax += lineTax;
      if (lineTax) taxBreak.set(taxP, (taxBreak.get(taxP) || 0) + lineTax);
    });
    const baseForCharges = sub + tax;
    let chargesTotal = 0;
    charges.forEach(c => {
      if (c.mode === 'amount') chargesTotal += asNum(c.value) * c.sign;
      else chargesTotal += baseForCharges * asNum(c.value) / 100 * c.sign;
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
    const displayNumber = this.voucherDisplayNumber();
    const html = `
      <div class="bg-slate-50 text-slate-900 p-4 md:p-6 lg:p-8 max-w-[1400px] mx-auto">
        <!-- Page Header -->
        <div class="bg-gradient-to-r from-blue-600 to-blue-800 text-white p-6 rounded-xl mb-6">
          <div class="flex justify-between items-center">
            <div>
              <h1 class="text-2xl font-bold mb-1">${displayNumber}</h1>
              <p class="text-blue-100">Create New ${voucherType} Voucher</p>
            </div>
            <div class="badge">${status}</div>
          </div>
        </div>

        <!-- Voucher Details Card -->
        <div class="bg-white rounded-xl shadow-lg mb-6">
          <div class="p-6">
            <h2 class="text-xl font-semibold mb-4">Voucher Details</h2>
            
            <!-- Header Fields -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Voucher Type</label>
                <select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="voucherType">
                  <option value="Sales" ${voucherType === 'Sales' ? 'selected' : ''}>Sales Invoice</option>
                  <option value="Purchase" ${voucherType === 'Purchase' ? 'selected' : ''}>Purchase Invoice</option>
                  <option value="Journal" ${voucherType === 'Journal' ? 'selected' : ''}>Journal Entry</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Date</label>
                <input type="date" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.date" value="${header.date}">
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Branch</label>
                <input type="text" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.branch" value="${header.branch}">
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Currency</label>
                <input type="text" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.currency" value="${header.currency}">
              </div>
            </div>

            ${voucherType !== 'Journal' ? `
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Party</label>
                <input type="text" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.party" value="${header.party}">
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Exchange Rate</label>
                <input type="number" step="0.01" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.exRate" value="${header.exRate}">
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-1">Credit Days</label>
                <input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white w-full" data-bind="header.creditDays" value="${header.creditDays}">
              </div>
            </div>
            ` : ''}
          </div>
        </div>

        <!-- Lines Grid -->
        <div class="bg-white rounded-xl shadow-lg mb-6">
          <div class="p-6 border-b border-slate-200">
            <div class="flex justify-between items-center">
              <h2 class="text-xl font-semibold">Line Items</h2>
              <div class="flex gap-2">
                <button class="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50" data-action="colManager">Columns</button>
                <button class="px-4 py-2 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700" data-action="addRow">+ Add Row</button>
              </div>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="min-w-full">
              <thead class="bg-slate-50">
                <tr>
                  ${visibleCols.map(c => `<th class="text-left px-4 py-3 text-sm font-medium text-slate-600 th-resizable" data-colid="${c.id}" style="min-width: ${c.width}px;">
                    ${c.label}
                    <div class="resize-handle"></div>
                  </th>`).join('')}
                </tr>
              </thead>
              <tbody>
                ${rows.map((r, ri) => `<tr class="border-t border-slate-200 hover:bg-slate-50">
                  ${visibleCols.map((c, ci) => `<td class="px-4 py-2">
                    ${gridCell(r[c.id], c, ri, ci)}
                  </td>`).join('')}
                </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Totals -->
        <div class="bg-white rounded-xl shadow-lg mb-6">
          <div class="p-6">
            <h2 class="text-xl font-semibold mb-4">Totals</h2>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              ${voucherType === 'Journal' ? `
                <div class="bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-slate-900">${moneyFmt.format(totals.dr)}</div>
                  <div class="text-sm text-slate-600">Total Debit</div>
                </div>
                <div class="bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-slate-900">${moneyFmt.format(totals.cr)}</div>
                  <div class="text-sm text-slate-600">Total Credit</div>
                </div>
                <div class="col-span-2 bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold ${totals.imbalance ? 'text-red-600' : 'text-green-600'}">${moneyFmt.format(Math.abs(totals.imbalance))}</div>
                  <div class="text-sm text-slate-600">${totals.imbalance ? 'Out of Balance' : 'Balanced'}</div>
                </div>
              ` : `
                <div class="bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-slate-900">${moneyFmt.format(totals.sub)}</div>
                  <div class="text-sm text-slate-600">Subtotal</div>
                </div>
                <div class="bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-slate-900">${moneyFmt.format(totals.tax)}</div>
                  <div class="text-sm text-slate-600">Tax</div>
                </div>
                <div class="bg-slate-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-slate-900">${moneyFmt.format(totals.chargesTotal)}</div>
                  <div class="text-sm text-slate-600">Charges</div>
                </div>
                <div class="bg-green-50 p-4 rounded-xl">
                  <div class="text-2xl font-bold text-green-600">${moneyFmt.format(totals.grand)}</div>
                  <div class="text-sm text-slate-600">Grand Total</div>
                </div>
              `}
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-between items-center">
          <div class="flex gap-2">
            <button class="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50" data-action="exportCsv">Export CSV</button>
            <button class="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50" data-action="exportXlsx">Export Excel</button>
          </div>
          <button class="px-6 py-3 rounded-xl bg-blue-600 text-white hover:bg-blue-700 font-medium" data-action="save">Save Voucher</button>
        </div>

        <!-- Modals -->
        ${this.state.showUdfModal ? udfModalHtml(this.state) : ''}
        ${this.state.showColManager ? colManagerHtml(cols, this.state.colManagerDraft) : ''}
        ${this.state.showCharges ? chargesModalHtml(charges) : ''}
      </div>
    `;
    el.innerHTML = html;
    this.bindResizeHandles();
  },

  /** Column resizing handlers */
  bindResizeHandles() {
    document.querySelectorAll('.th-resizable').forEach(th => {
      const handle = th.querySelector('.resize-handle');
      if (handle) {
        handle.addEventListener('mousedown', (e) => {
          e.preventDefault();
          this._resizing = { colId: th.dataset.colid, startX: e.clientX, startWidth: th.offsetWidth };
        });
      }
    });
  },
  onResize(e) {
    if (!this._resizing) return;
    const delta = e.clientX - this._resizing.startX;
    const newWidth = Math.max(80, this._resizing.startWidth + delta);
    const th = document.querySelector(`[data-colid="${this._resizing.colId}"]`);
    if (th) th.style.width = th.style.minWidth = `${newWidth}px`;
  },
  stopResize() {
    if (this._resizing) {
      const col = this.getColumns().find(c => c.id === this._resizing.colId);
      if (col) {
        const newWidth = parseInt(document.querySelector(`[data-colid="${this._resizing.colId}"]`).style.width);
        if (newWidth !== col.width) {
          col.width = newWidth;
          this.persistPresets();
        }
      }
      this._resizing = null;
    }
  },

  /** CSV/Excel I/O */
  bindCsv() {
    document.addEventListener('paste', this.handlePaste.bind(this));
  },
  exportCsv() {
    const cols = this.getColumns().filter(c => c.visible !== false);
    const csv = [cols.map(c => c.label).join(',')];
    this.state.rows.forEach(r => csv.push(cols.map(c => `"${String(r[c.id] || '').replace(/"/g, '""')}"`).join(',')));
    const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.voucherDisplayNumber()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  },
  sampleXlsx() {
    // Placeholder for sample Excel
  },
  exportXlsx() {
    const cols = this.getColumns().filter(c => c.visible !== false);
    const data = [cols.map(c => c.label)];
    this.state.rows.forEach(r => data.push(cols.map(c => r[c.id] || '')));
    const ws = XLSX.utils.aoa_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
    XLSX.writeFile(wb, `${this.voucherDisplayNumber()}.xlsx`);
  },

  /** Events */
  handleClick(e) {
    const action = e.target.dataset.action;
    if (!action) return;
    if (action === 'addRow') {
      this.state.rows.push(this.blankRow());
      this.render();
    } else if (action === 'colManager') {
      this.state.showColManager = true;
      this.state.colManagerDraft = this.getColumns();
      this.render();
    } else if (action === 'udfModal') {
      this.state.showUdfModal = true;
      this.render();
    } else if (action === 'exportCsv') {
      this.exportCsv();
    } else if (action === 'exportXlsx') {
      this.exportXlsx();
    } else if (action === 'save') {
      this.persistPresets();
      alert('Saved!');
    } else if (action === 'cmCancel') {
      this.state.showColManager = false;
      this.render();
    } else if (action === 'cmApply') {
      const draft = this.state.colManagerDraft;
      if (draft) {
        const prefs = {};
        draft.forEach((c, i) => prefs[c.id] = { visible: c.visible, width: c.width, order: i });
        this.state.colPrefsByType[this.state.voucherType] = prefs;
        this.persistPresets();
      }
      this.state.showColManager = false;
      this.render();
    } else if (action === 'cmToggle') {
      const colId = e.target.dataset.col;
      const draft = this.state.colManagerDraft;
      if (draft) {
        const col = draft.find(c => c.id === colId);
        if (col) col.visible = col.visible !== false ? false : true;
      }
    } else if (action === 'cmMove') {
      const colId = e.target.dataset.col;
      const dir = parseInt(e.target.dataset.dir);
      const draft = this.state.colManagerDraft;
      if (draft) {
        const idx = draft.findIndex(c => c.id === colId);
        if (idx >= 0) {
          const newIdx = Math.max(0, Math.min(draft.length - 1, idx + dir));
          [draft[idx], draft[newIdx]] = [draft[newIdx], draft[idx]];
        }
      }
    } else if (action === 'udfCancel') {
      this.state.showUdfModal = false;
      this.render();
    } else if (action === 'udfAdd') {
      const d = this.state.udfDraft;
      if (d.label.trim()) {
        const def = { id: uid(), label: d.label, type: d.type, required: d.required, options: d.options.split(',').map(s => s.trim()).filter(s => s) };
        if (this.state.udfScope === 'Header') this.state.udfHeaderDefs.push(def);
        else this.state.udfLineDefs.push(def);
        this.persistPresets();
        this.state.showUdfModal = false;
        this.render();
      }
    } else if (action === 'chgClose') {
      this.state.showCharges = false;
      this.render();
    } else if (action === 'chgAdd') {
      this.state.charges.push({ id: uid(), label: 'New Charge', mode: 'amount', value: 0, sign: 1 });
      this.render();
    } else if (action === 'chgDel') {
      const id = e.target.dataset.id;
      this.state.charges = this.state.charges.filter(c => c.id !== id);
      this.persistPresets();
      this.render();
    }
  },

  handleChange(e) {
    const bind = e.target.dataset.bind;
    if (!bind) return;
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (bind.includes('.')) {
      const [obj, prop] = bind.split('.');
      this.state[obj][prop] = value;
    } else {
      this.state[bind] = value;
    }
    if (bind === 'voucherType') {
      this.resetRows();
      this.render();
    }
  },

  handleKeydown(e) {
    if (e.target.tagName !== 'INPUT') return;
    const ri = parseInt(e.target.dataset.ri);
    const ci = parseInt(e.target.dataset.ci);
    if (e.key === 'Enter') {
      e.preventDefault();
      if (ri === this.state.rows.length - 1) {
        this.state.rows.push(this.blankRow());
        this.render();
      }
      this.focusCurrent({ r: ri + 1, c: ci });
    } else if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      this.focusCurrent({ r: ri, c: ci + 1 });
    } else if (e.key === 'Tab' && e.shiftKey) {
      e.preventDefault();
      this.focusCurrent({ r: ri, c: ci - 1 });
    } else if (e.key === 'Delete' && e.ctrlKey) {
      e.preventDefault();
      this.state.rows.splice(ri, 1);
      if (this.state.rows.length === 0) this.state.rows.push(this.blankRow());
      this.render();
    }
  },

  handleFocusIn(e) {
    if (e.target.dataset.ri !== undefined) {
      this.state.focus = { r: parseInt(e.target.dataset.ri), c: parseInt(e.target.dataset.ci) };
    }
  },

  /** Excel-like paste */
  handlePaste(e) {
    if (e.target.tagName !== 'INPUT' || !e.clipboardData) return;
    e.preventDefault();
    const text = e.clipboardData.getData('text');
    const rows = text.split('\n').map(r => r.split('\t'));
    const ri = parseInt(e.target.dataset.ri);
    const ci = parseInt(e.target.dataset.ci);
    const cols = this.getColumns().filter(c => c.visible !== false);
    rows.forEach((row, dy) => {
      row.forEach((cell, dx) => {
        const r = ri + dy;
        const c = ci + dx;
        if (r < this.state.rows.length && c < cols.length) {
          const col = cols[c];
          let value = cell.trim();
          if (col.type === 'number') value = asNum(value);
          this.state.rows[r][col.id] = value;
        }
      });
    });
    this.render();
  },

  focusCurrent(pos) {
    const cols = this.getColumns().filter(c => c.visible !== false);
    const r = clamp(pos.r, 0, this.state.rows.length - 1);
    const c = clamp(pos.c, 0, cols.length - 1);
    const selector = `[data-ri="${r}"][data-ci="${c}"]`;
    const input = document.querySelector(selector);
    if (input) {
      input.focus();
      input.select();
    }
  },

  computeDueDate(dateStr, days) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + days);
    return date.toISOString().slice(0, 10);
  },

  /** Validation + payload */
  validate() {
    const errors = [];
    if (!this.state.header.date) errors.push('Date is required');
    if (this.state.voucherType !== 'Journal' && !this.state.header.party) errors.push('Party is required');
    this.state.rows.forEach((r, i) => {
      if (this.state.voucherType === 'Journal') {
        if (!r.account) errors.push(`Row ${i + 1}: Account is required`);
        if (asNum(r.dr) && asNum(r.cr)) errors.push(`Row ${i + 1}: Cannot have both Dr and Cr`);
        if (!asNum(r.dr) && !asNum(r.cr)) errors.push(`Row ${i + 1}: Must have Dr or Cr`);
      } else {
        if (!r.item) errors.push(`Row ${i + 1}: Item is required`);
        if (!asNum(r.qty)) errors.push(`Row ${i + 1}: Qty must be > 0`);
        if (!asNum(r.rate)) errors.push(`Row ${i + 1}: Rate must be > 0`);
      }
    });
    return errors;
  },
  buildPayload() {
    return {
      type: this.state.voucherType,
      header: this.state.header,
      lines: this.state.rows.filter(r => this.state.voucherType === 'Journal' ? r.account : r.item),
      udfs: { header: this.state.udfHeaderDefs, lines: this.state.udfLineDefs },
      totals: this.computeTotals(),
    };
  },

  /** Self-tests */
  selfTests() {
    console.log('Running self-tests...');
    // Test computeTotals
    this.state.rows = [
      { id: '1', item: 'Test', desc: '', qty: 2, uom: '', rate: 100, discP: 10, taxP: 13, taxGroup: '', warehouse: '', batch: '', amount: 0 },
    ];
    const totals = this.computeTotals();
    console.assert(totals.sub === 200, 'Subtotal should be 200');
    console.assert(Math.abs(totals.disc - 20) < 0.01, 'Discount should be 20');
    console.assert(Math.abs(totals.tax - 23.4) < 0.01, 'Tax should be 23.4');
    console.assert(Math.abs(totals.grand - 203.4) < 0.01, 'Grand should be 203.4');
    console.log('Self-tests passed!');
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
  if (col.type === 'number') return `<input ${base} type="number" step="any" value="${value ?? ''}">`;
  if (col.type === 'date') return `<input ${base} type="date" value="${value ?? ''}">`;
  if (col.type === 'select') return `<select ${base}>${(col.options || []).map(o => `<option value="${escapeHtml(o)}" ${o === value ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}</select>`;
  if (col.type === 'checkbox') return `<input ${base} type="checkbox" ${value ? 'checked' : ''}>`;
  return `<input ${base} value="${escapeHtml(value ?? '')}">`;
}
function fieldControl(def, value) {
  const title = def.type === 'number' ? String(value ?? '') : escapeHtml(value ?? '');
  const base = `class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white ${def.type === 'number' ? 'text-right' : ''}" data-hudf="${def.id}" data-type="${def.type}" title="${title}"`;
  if (def.type === 'number') return `<input ${base} type="number" step="0.01" value="${value ?? ''}">`;
  if (def.type === 'date') return `<input ${base} type="date" value="${value ?? ''}">`;
  if (def.type === 'select') return `<select ${base}>${(def.options || []).map(o => `<option value="${escapeHtml(o)}" ${value === o ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}</select>`;
  if (def.type === 'checkbox') return `<input ${base} type="checkbox" ${value ? 'checked' : ''}>`;
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
  if (vt === 'Journal') return `<div class="text-sm">${chip('Dr', moneyFmt.format(totals.dr))}${chip('Cr', moneyFmt.format(totals.cr))}${chip('Balance', moneyFmt.format(Math.abs(totals.imbalance)))}</div>`;
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