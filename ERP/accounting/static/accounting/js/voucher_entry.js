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
  reject: __root?.dataset?.endpointReject || null,
  post: __root?.dataset?.endpointPost || null,
};
const DEFAULT_JOURNAL_TYPE = __root?.dataset?.defaultJournalType || 'JN';
const INITIAL_JOURNAL_ID_RAW = __root?.dataset?.initialJournalId || '';
const INITIAL_JOURNAL_ID = INITIAL_JOURNAL_ID_RAW ? Number(INITIAL_JOURNAL_ID_RAW) || null : null;
const DETAIL_URL_TEMPLATE = __root?.dataset?.detailUrlTemplate || null;
const LOOKUPS = {
  account: __root?.dataset?.lookupAccount || null,
  costCenter: __root?.dataset?.lookupCostCenter || null,
};
const SUPPORTED_CURRENCIES = (__root?.dataset?.supportedCurrencies || '').split(',').filter(Boolean);
const PERMISSIONS = {
  submit: __root?.dataset?.canSubmit === 'true',
  approve: __root?.dataset?.canApprove === 'true',
  reject: __root?.dataset?.canReject === 'true',
  post: __root?.dataset?.canPost === 'true',
};
const STATUS_LABEL_MAP = {
  draft: 'Draft',
  awaiting_approval: 'Awaiting Approval',
  approved: 'Approved',
  rejected: 'Rejected',
  posted: 'Posted',
  submitted: 'Submitted',
};

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRFTOKEN || ''
    },
    credentials: 'same-origin',
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

const titleCase = (value) => {
  if (!value) return '';
  return String(value)
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

function normalizeChoiceList(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw.map((item) => {
      if (item && typeof item === 'object') {
        const value = item.value === undefined || item.value === null ? '' : String(item.value);
        return { ...item, value, label: item.label ?? value };
      }
      const value = item === null || item === undefined ? '' : String(item);
      return { value, label: value };
    });
  }
  if (typeof raw === 'object') {
    return Object.entries(raw).map(([value, label]) => ({
      value: value === null || value === undefined ? '' : String(value),
      label: label === null || label === undefined ? String(value) : String(label),
    }));
  }
  return [];
}

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

const HEADER_FIELD_KEY_MAP = {
  journal_date: 'date',
  currency: 'currency',
  description: 'description',
  reference_number: 'reference',
  journal_type: 'journalTypeCode',
  branch: 'branch',
};
const LINE_FIELD_KEY_MAP = {
  description: 'narr',
  debit_amount: 'dr',
  credit_amount: 'cr',
  cost_center: 'costCenter',
  project: 'project',
  department: 'department',
  tax_code: 'taxCode',
};
const STANDARD_HEADER_KEYS = new Set(['party', 'date', 'currency', 'exRate', 'creditDays', 'priceInclusiveTax', 'reference', 'description', 'branch', 'journalTypeCode']);

const App = {
  state: {
    voucherType: 'Journal',
    journalTypeCode: DEFAULT_JOURNAL_TYPE,
    journalId: INITIAL_JOURNAL_ID,
    journalNumber: '',
    status: 'draft',
    configUrl: __root?.dataset?.configUrl || null,
    supportedCurrencies: SUPPORTED_CURRENCIES,
    header: {
      party: '',
      date: new Date().toISOString().slice(0, 10),
      branch: 'Main',
      currency: SUPPORTED_CURRENCIES[0] || 'NPR',
      exRate: 1,
      creditDays: 0,
      priceInclusiveTax: true,
      reference: '',
      description: '',
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
    availableVoucherTypes: ['Journal'],
    detailUrlTemplate: DETAIL_URL_TEMPLATE,
    serverTotals: null,
    attachments: [],
    metadata: {},
    headerDefaults: {},
    lineDefaults: {},
    choiceMaps: { header: {}, line: {} },
    isSaving: false,
    headerFieldDefs: [],
    configLineDefs: [],
    configBaseOverrides: {},
    dynamicLineKeys: [],
  },
  lastConfigRequest: { code: null, id: null },

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

    if (!Array.isArray(this.state.rows) || !this.state.rows.length) {
      this.resetRows();
    }
    this.render();
    const initialType = this.state.journalTypeCode || DEFAULT_JOURNAL_TYPE;
    const initialConfigId = this.state.metadata?.configId || null;
    if (this.state.configUrl) {
      this.fetchConfig(initialType, initialConfigId);
    }
    if (this.state.journalId) {
      this.fetchJournal(this.state.journalId);
    }

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
    const { voucherType, udfLineDefs, colPrefsByType, configLineDefs, configBaseOverrides } = this.state;
    let cols = buildColumns(voucherType, udfLineDefs, colPrefsByType[voucherType]);
    if (voucherType === 'Journal' && configBaseOverrides) {
      cols = cols.map((col) => {
        if (configBaseOverrides[col.id]) {
          return { ...col, ...configBaseOverrides[col.id] };
        }
        return col;
      });
    }
    if (voucherType === 'Journal' && Array.isArray(configLineDefs) && configLineDefs.length) {
      configLineDefs.forEach((extra) => {
        const existing = cols.find((c) => c.id === extra.id);
        if (existing) {
          Object.assign(existing, extra);
        } else {
          cols.push({ order: cols.length + 1, visible: true, ...extra });
        }
      });
    }
    return cols;
  },
  setSaving(flag) {
    this.state.isSaving = !!flag;
    this.render();
  },
  blankRow() {
    if (this.state.voucherType === 'Journal') {
      const base = {
        id: uid(),
        accountId: null,
        accountCode: '',
        accountName: '',
        account: '',
        narr: '',
        dr: 0,
        cr: 0,
        costCenterId: null,
        costCenter: '',
        projectId: null,
        project: '',
        departmentId: null,
        department: '',
        taxCodeId: null,
        taxCode: '',
        udf: {},
      };
      (this.state.dynamicLineKeys || []).forEach((key) => {
        if (base[key] === undefined) base[key] = '';
      });
      const defaults = this.state.lineDefaults || {};
      Object.keys(defaults).forEach((key) => {
        if (base[key] === undefined || base[key] === '') {
          base[key] = defaults[key];
        }
      });
      return base;
    }
    return { id: uid(), item: '', desc: '', qty: 1, uom: '', rate: 0, discP: 0, taxP: 13, taxGroup: 'VAT 13%', warehouse: '', batch: '', amount: 0 };
  },
  resetRows(n = 5) { this.state.rows = Array.from({ length: n }, () => this.blankRow()); },

  voucherDisplayNumber() {
    if (this.state.journalNumber) return this.state.journalNumber;
    const vt = this.state.voucherType; const n = this.state.numbering.nextSeq[vt] || 1;
    const pref = this.state.numbering.prefix[vt] || vt[0]; const w = this.state.numbering.width || 4;
    return `${pref}-${String(n).padStart(w, '0')}`;
  },

  statusLabel() {
    const status = (this.state.status || 'draft').toLowerCase();
    const label = STATUS_LABEL_MAP[status];
    if (label) return label;
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  },

  statusBadgeClass() {
    const status = (this.state.status || 'draft').toLowerCase();
    if (status === 'draft') return 'draft';
    if (status === 'awaiting_approval' || status === 'submitted') return 'submitted';
    if (status === 'approved' || status === 'posted') return 'approved';
    if (status === 'rejected') return 'rejected';
    return '';
  },

  handleServerErrors(response) {
    const details = response?.data?.details;
    if (details?.errors?.length) {
      alert('Fix issues:\n- ' + details.errors.join('\n- '));
    } else if (response?.data?.error) {
      notify(response.data.error);
    } else {
      notify('Server rejected the request.');
    }
  },

  lookupAccount(query) {
    const token = (query || '').trim();
    if (!LOOKUPS.account || !token) return Promise.resolve(null);
    const code = token.split(/\s|-/)[0];
    const url = `${LOOKUPS.account}?q=${encodeURIComponent(code)}`;
    return fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(resp => resp.json().catch(() => ({})))
      .then(data => {
        const results = Array.isArray(data?.results) ? data.results : [];
        if (!results.length) return null;
        const exact = results.find(r => (r.code || '').toLowerCase() === code.toLowerCase());
        return exact || results[0] || null;
      })
      .catch(err => {
        console.error('Account lookup failed', err);
        return null;
      });
  },

  resolveAccount(row, value) {
    return this.lookupAccount(value).then(match => {
      if (match) {
        row.accountId = match.id;
        row.accountCode = match.code;
        row.accountName = match.name;
        row.account = `${match.code} - ${match.name}`;
      }
    });
  },

  lookupCostCenter(query) {
    const token = (query || '').trim();
    if (!LOOKUPS.costCenter || !token) return Promise.resolve(null);
    const code = token.split(/\s|-/)[0];
    const url = `${LOOKUPS.costCenter}?q=${encodeURIComponent(code)}`;
    return fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(resp => resp.json().catch(() => ({})))
      .then(data => {
        const results = Array.isArray(data?.results) ? data.results : [];
        if (!results.length) return null;
        const exact = results.find(r => (r.code || '').toLowerCase() === code.toLowerCase());
        return exact || results[0] || null;
      })
      .catch(err => {
        console.error('Cost center lookup failed', err);
        return null;
      });
  },

  resolveCostCenter(row, value) {
    return this.lookupCostCenter(value).then(match => {
      if (match) {
        row.costCenterId = match.id;
        row.costCenter = match.code;
      }
    });
  },

  availableVoucherTypes() {
    const arr = this.state.availableVoucherTypes;
    if (Array.isArray(arr) && arr.length) return arr;
    return ['Journal'];
  },

  normalizeRow(row = {}) {
    const toStringValue = (value) => (value === null || value === undefined ? '' : String(value));
    const toNumericId = (value) => {
      if (value === null || value === undefined || value === '') return null;
      const num = Number(value);
      return Number.isNaN(num) ? null : num;
    };
    const projectValueRaw = row.project ?? row.projectId ?? '';
    const departmentValueRaw = row.department ?? row.departmentId ?? '';
    const taxValueRaw = row.taxCode ?? row.taxCodeId ?? row.tax_code ?? '';
    const normalized = {
      id: row.id ?? uid(),
      accountId: row.accountId ?? null,
      accountCode: row.accountCode ?? '',
      accountName: row.accountName ?? '',
      account: row.account ?? row.accountCode ?? '',
      narr: row.narr ?? '',
      dr: asNum(row.dr, 0),
      cr: asNum(row.cr, 0),
      costCenterId: row.costCenterId ?? null,
      costCenter: row.costCenter ?? '',
      projectId: row.projectId ?? toNumericId(projectValueRaw),
      project: toStringValue(projectValueRaw),
      projectLabel: row.projectLabel ?? row.project_name ?? row.projectName ?? '',
      departmentId: row.departmentId ?? toNumericId(departmentValueRaw),
      department: toStringValue(departmentValueRaw),
      departmentLabel: row.departmentLabel ?? row.department_name ?? row.departmentName ?? '',
      taxCodeId: row.taxCodeId ?? row.tax_code_id ?? toNumericId(taxValueRaw),
      taxCode: toStringValue(taxValueRaw),
      taxCodeLabel: row.taxCodeLabel ?? row.taxCode_code ?? row.taxCodeName ?? '',
      udf: {},
    };
    const udfData = row && typeof row.udf === 'object' ? row.udf : {};
    Object.entries(udfData).forEach(([key, value]) => {
      normalized.udf[key] = value;
      normalized[key] = value;
    });
    (this.state.dynamicLineKeys || []).forEach((key) => {
      if (normalized[key] === undefined) normalized[key] = row[key] ?? '';
    });
    const defaults = this.state.lineDefaults || {};
    Object.keys(defaults).forEach((key) => {
      const current = normalized[key];
      if (current === undefined || current === '' || current === null) {
        normalized[key] = defaults[key];
      }
    });
    return normalized;
  },

  hydrateFromApi(journal) {
    if (!journal || typeof journal !== 'object') return;
    if (journal.id !== undefined) this.state.journalId = journal.id;
    if (journal.number !== undefined) this.state.journalNumber = journal.number || '';
    if (journal.status) this.state.status = journal.status;
    if (journal.journalTypeCode) this.state.journalTypeCode = journal.journalTypeCode;
    if (typeof journal.notes === 'string') this.state.notes = journal.notes;
    if (journal.header) {
      const h = journal.header;
      this.state.header = {
        ...this.state.header,
        date: h.date || this.state.header.date,
        currency: h.currency || this.state.header.currency,
        exRate: h.exRate !== undefined ? asNum(h.exRate, this.state.header.exRate) : this.state.header.exRate,
        branch: h.branch || this.state.header.branch,
        reference: h.reference ?? this.state.header.reference,
        description: h.description ?? this.state.header.description,
      };
    }
    if (journal.headerUdfValues && typeof journal.headerUdfValues === 'object') {
      Object.entries(journal.headerUdfValues).forEach(([key, value]) => {
        this.state.header[key] = value;
      });
    }
    if (Array.isArray(journal.udfHeaderDefs)) {
      this.state.udfHeaderDefs = journal.udfHeaderDefs;
    }
    if (Array.isArray(journal.udfLineDefs)) {
      this.state.udfLineDefs = journal.udfLineDefs;
    }
    if (Array.isArray(journal.rows)) {
      const rows = journal.rows.map((row) => this.normalizeRow(row));
      // Ensure row-level UDF values are copied to cells
      if (this.state.udfLineDefs?.length) {
        rows.forEach((rowItem) => {
          this.state.udfLineDefs.forEach((def) => {
            if (!def?.id) return;
            if (rowItem.udf && rowItem.udf[def.id] !== undefined) {
              rowItem[def.id] = rowItem.udf[def.id];
            }
          });
        });
      }
      this.state.rows = rows;
      if (!this.state.rows.length) this.resetRows();
    }
    if (journal.totals) {
      this.state.serverTotals = journal.totals;
    }
    if (Array.isArray(journal.charges)) {
      this.state.charges = journal.charges.map((c) => ({
        id: c.id || uid(),
        label: c.label || '',
        mode: c.mode || 'amount',
        value: typeof c.value === 'number' ? c.value : asNum(c.value, 0),
        sign: Number(c.sign || 1),
      }));
    }
    if (Array.isArray(journal.attachments)) {
      this.state.attachments = journal.attachments;
    }
    if (journal.metadata && typeof journal.metadata === 'object') {
      this.state.metadata = journal.metadata;
    }
  },

  fetchJournal(id) {
    const template = this.state.detailUrlTemplate || DETAIL_URL_TEMPLATE;
    if (!template || !id) return;
    const url = template.replace(/0\/?$/, `${id}/`);
    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then((resp) => resp.json().catch(() => ({})).then((data) => ({ status: resp.status, data })))
      .then(({ status, data }) => {
        if (status >= 400 || !data?.ok) {
          notify(data?.error || 'Unable to load journal entry.');
          return;
        }
        this.state.journalId = id;
        this.hydrateFromApi(data.journal);
        this.render();
      })
      .catch((err) => {
        console.error('Failed to fetch journal', err);
        notify('Failed to load journal entry.');
      });
  },

  fetchConfig(journalTypeCode, configId) {
    if (!this.state.configUrl) return;
    const params = new URLSearchParams();
    if (configId) params.set('config_id', configId);
    if (journalTypeCode) params.set('journal_type', journalTypeCode);
    if (!params.has('config_id') && !params.has('journal_type')) return;
    const requestedCode = params.get('journal_type') || '';
    const requestedId = params.get('config_id') || null;
    if (this.lastConfigRequest && this.lastConfigRequest.code === requestedCode && this.lastConfigRequest.id === requestedId) {
      return;
    }
    this.lastConfigRequest = { code: requestedCode, id: requestedId };
    const url = `${this.state.configUrl}?${params.toString()}`;
    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then((resp) => resp.json().catch(() => ({})).then((data) => ({ status: resp.status, data })))
      .then(({ status, data }) => {
        if (status >= 400 || !data?.ok) {
          console.warn('Config fetch failed', status, data);
          if (data?.error) notify(data.error);
          return;
        }
        this.applyConfig(data.config || {});
      })
      .catch((err) => {
        console.error('Failed to fetch voucher configuration', err);
        this.lastConfigRequest = { code: null, id: null };
      });
  },

  applyConfig(config) {
    if (!config || typeof config !== 'object') return;
    const ui = config.uiSchema || config.ui_schema || {};
    const headerSchema = ui.header || {};
    const lineSchema = ui.lines || {};
    const metadata = config.metadata || {};
    this.state.metadata = { ...metadata };\n    if (config.udf) {\n      if (Array.isArray(config.udf.header)) this.state.udfHeaderDefs = config.udf.header;\n      if (Array.isArray(config.udf.line)) this.state.udfLineDefs = config.udf.line;\n    }
    if (Array.isArray(metadata.supportedCurrencies) && metadata.supportedCurrencies.length) {
      this.state.supportedCurrencies = metadata.supportedCurrencies;
    }
    if (Array.isArray(metadata.availableVoucherTypes) && metadata.availableVoucherTypes.length) {
      this.state.availableVoucherTypes = metadata.availableVoucherTypes;
    }
    if (metadata.numbering) {
      this.state.numbering = metadata.numbering;
    }
    if (metadata.journalTypeCode) {
      this.state.journalTypeCode = metadata.journalTypeCode;
      this.state.header.journalTypeCode = metadata.journalTypeCode;
    }
    if (metadata.journalTypeId) {
      this.state.metadata.journalTypeId = metadata.journalTypeId;
    }
    if (metadata.configId) {
      this.state.metadata.configId = metadata.configId;
    }
    if (metadata.defaultCurrency && !this.state.header.currency) {
      this.state.header.currency = metadata.defaultCurrency;
    }
    this.state.headerDefaults = metadata.headerDefaults || {};
    this.state.lineDefaults = metadata.lineDefaults || {};
    Object.entries(this.state.headerDefaults).forEach(([key, value]) => {
      const current = this.state.header[key];
      if (current === undefined || current === null || current === '') {
        this.state.header[key] = value;
      }
    });
    this.state.choiceMaps.header = {};
    this.state.choiceMaps.line = {};
    const headerDefs = [];
    Object.entries(headerSchema).forEach(([key, def]) => {
      const stateKey = HEADER_FIELD_KEY_MAP[key] || key;
      const label = def.label || titleCase(stateKey);
      const choices = normalizeChoiceList(def.choices);
      const choiceMap = {};
      choices.forEach((choice) => { choiceMap[choice.value] = choice; });
      const fieldDef = {
        key,
        stateKey,
        label,
        type: def.type || 'text',
        required: !!def.required,
        placeholder: def.placeholder || '',
        helpText: def.helpText || def.help_text || '',
        choices,
        default: def.default,
      };
      this.state.choiceMaps.header[stateKey] = choiceMap;
      if (fieldDef.default !== undefined) {
        const current = this.state.header[stateKey];
        if (current === undefined || current === null || current === '') {
          this.state.header[stateKey] = fieldDef.default;
        }
      } else if (this.state.header[stateKey] === undefined) {
        this.state.header[stateKey] = '';
      }
      headerDefs.push(fieldDef);
    });
    this.state.headerFieldDefs = headerDefs;
    const baseOverrides = {};
    const extraColumns = [];
    const dynamicKeys = [];
    Object.entries(lineSchema).forEach(([key, def]) => {
      const stateKey = LINE_FIELD_KEY_MAP[key] || key;
      const label = def.label || titleCase(stateKey);
      const choices = normalizeChoiceList(def.choices);
      const choiceMap = {};
      choices.forEach((choice) => { choiceMap[choice.value] = choice; });
      const rawType = def.type || 'text';
      let type = 'text';
      if (rawType === 'decimal' || rawType === 'number') type = 'number';
      else if (rawType === 'date') type = 'date';
      else if (rawType === 'datetime' || rawType === 'datetime-local') type = 'datetime-local';
      else if (rawType === 'select' || rawType === 'multiselect') type = 'select';
      else if (rawType === 'checkbox') type = 'checkbox';
      const columnDef = {
        id: stateKey,
        label,
        type,
        options: choices,
        width: type === 'number' ? 140 : 180,
        align: type === 'number' ? 'right' : 'left',
      };
      this.state.choiceMaps.line[stateKey] = choiceMap;
      if (['account', 'narr', 'dr', 'cr', 'costCenter'].includes(stateKey)) {
        baseOverrides[stateKey] = { label: columnDef.label, type: columnDef.type, options: columnDef.options, align: columnDef.align };
      } else {
        extraColumns.push(columnDef);
        dynamicKeys.push(stateKey);
      }
    });
    this.state.configBaseOverrides = baseOverrides;
    this.state.configLineDefs = extraColumns;
    this.state.dynamicLineKeys = dynamicKeys;
    this.state.currentConfigId = metadata.configId ?? null;
    if (metadata.headerExtras && typeof metadata.headerExtras === 'object') {
      Object.entries(metadata.headerExtras).forEach(([key, value]) => {
        const current = this.state.header[key];
        if (current === undefined || current === null || current === '') {
          this.state.header[key] = value;
        }
      });
    }
    if (!Array.isArray(this.state.rows) || !this.state.rows.length) {
      this.resetRows();
    } else {
      this.state.rows = this.state.rows.map((row) => this.normalizeRow(row));
    }
    this.render();
  },

  renderHeaderForm() {
    if (!this.state.headerFieldDefs.length) {
      return this.renderDefaultHeaderForm();
    }
    const controls = this.state.headerFieldDefs.map((field) => this.renderHeaderField(field)).join('');
    return `<div class="ve-summary-grid grid grid-cols-1 md:grid-cols-3 gap-3">${controls}</div>`;
  },

  renderHeaderField(field) {
    const label = field.label || titleCase(field.stateKey);
    const stateKey = field.stateKey;
    const type = field.type || 'text';
    const rawValue = this.state.header[stateKey];
    const value = rawValue === undefined || rawValue === null ? '' : rawValue;
    const attrs = `data-hkey="${stateKey}"`;
    const placeholder = field.placeholder ? ` placeholder="${escapeHtml(field.placeholder)}"` : '';
    const helpText = field.helpText || '';
    if (type === 'date') {
      return Labeled(label, `<input type="date" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white"${placeholder} ${attrs} value="${escapeHtml(String(value))}">`, helpText);
    }
    if (type === 'datetime-local') {
      return Labeled(label, `<input type="datetime-local" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white"${placeholder} ${attrs} value="${escapeHtml(String(value))}">`, helpText);
    }
    if (type === 'textarea') {
      return Labeled(label, `<textarea class="h-28 px-3 py-2 rounded-xl border border-slate-300 bg-white"${placeholder} ${attrs}>${escapeHtml(String(value))}</textarea>`, helpText);
    }
    if (type === 'checkbox') {
      return Labeled(label, `<div class="h-10 flex items-center"><input type="checkbox" class="rounded border border-slate-300"${placeholder} ${attrs} ${value ? 'checked' : ''}></div>`, helpText);
    }
    if (type === 'select') {
      let options = [];
      if (stateKey === 'currency') {
        options = (this.state.supportedCurrencies || []).map((cur) => ({ value: String(cur), label: String(cur) }));
      } else if (Array.isArray(field.choices)) {
        options = field.choices.map((choice) => {
          if (choice && typeof choice === 'object') {
            const optValue = choice.value === undefined || choice.value === null ? '' : String(choice.value);
            const optLabel = choice.label !== undefined ? choice.label : optValue;
            return { value: optValue, label: optLabel };
          }
          const optValue = choice === undefined || choice === null ? '' : String(choice);
          return { value: optValue, label: optValue };
        });
      }
      if (options.length) {
        const normalized = [{ value: '', label: '' }, ...options];
        const html = normalized.map(({ value: optValue, label: optLabel }) => {
          const valStr = optValue === undefined || optValue === null ? '' : String(optValue);
          const selected = String(value) === valStr;
          return `<option value="${escapeHtml(valStr)}"${selected ? ' selected' : ''}>${escapeHtml(optLabel === undefined || optLabel === null ? valStr : String(optLabel))}</option>`;
        }).join('');
        return Labeled(label, `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white"${placeholder} ${attrs}>${html}</select>`, helpText);
      }
    }
    if (type === 'number') {
      return Labeled(label, `<input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white${field.align === 'right' ? ' text-right' : ''}"${placeholder} ${attrs} value="${escapeHtml(String(value))}">`, helpText);
    }
    return Labeled(label, `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white"${placeholder} ${attrs} value="${escapeHtml(String(value))}">`, helpText);
  },

  renderDefaultHeaderForm() {
    const { voucherType, header, udfHeaderDefs } = this.state;
    const controls = [
      voucherType !== 'Journal'
        ? Labeled('Customer/Supplier', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" placeholder="Search name / phone" value="${escapeHtml(header.party)}" data-hkey="party" title="${escapeHtml(header.party)}">`)
        : '',
      Labeled('Date', `<input type="date" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${escapeHtml(header.date)}" data-hkey="date" title="${escapeHtml(header.date)}">`),
      Labeled('Branch', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" value="${escapeHtml(header.branch)}" data-hkey="branch" title="${escapeHtml(header.branch)}">`),
      Labeled('Currency', `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-hkey="currency" title="${escapeHtml(header.currency)}">${this.state.supportedCurrencies.map(cur => `<option value="${escapeHtml(cur)}" ${cur === header.currency ? 'selected' : ''}>${escapeHtml(cur)}</option>`).join('')}</select>`),
      Labeled('Exchange Rate', `<input type="number" step="0.0001" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white text-right" value="${escapeHtml(header.exRate)}" data-hkey="exRate" title="${escapeHtml(header.exRate)}">`),
      Labeled('Credit Days', `<input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white text-right" value="${escapeHtml(header.creditDays)}" data-hkey="creditDays" title="${escapeHtml(header.creditDays)}">`),
      ...(voucherType !== 'Journal'
        ? [Labeled('Prices are', `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-hkey="priceInclusiveTax" title="${header.priceInclusiveTax ? 'Tax Inclusive' : 'Tax Exclusive'}"><option value="inc" ${header.priceInclusiveTax ? 'selected' : ''}>Tax Inclusive</option><option value="exc" ${!header.priceInclusiveTax ? 'selected' : ''}>Tax Exclusive</option></select>`)]
        : []),
      ...udfHeaderDefs.map((f) => Labeled(`UDF: ${escapeHtml(f.label)}${f.required ? ' *' : ''}`, fieldControl(f, header[f.id] ?? '', 'header'))),
    ].filter(Boolean);
    return `<div class="ve-summary-grid grid grid-cols-1 md:grid-cols-3 gap-3">${controls.join('')}</div>`;
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
    const voucherTypes = this.availableVoucherTypes();
    const statusBadge = this.statusBadgeClass();
    const statusLabel = this.statusLabel();
    const normalizedStatus = (status || '').toLowerCase();
    const isWaitingApproval = normalizedStatus === 'awaiting_approval' || normalizedStatus === 'submitted';
    const isSaving = !!this.state.isSaving;
    const canSaveDraft = !isSaving;
    const canSubmit = PERMISSIONS.submit && normalizedStatus === 'draft' && !isSaving;
    const canApprove = PERMISSIONS.approve && isWaitingApproval && !isSaving;
    const canReject = PERMISSIONS.reject && isWaitingApproval && !isSaving;
    const canPost = PERMISSIONS.post && normalizedStatus === 'approved' && !isSaving;
    const attachmentsCount = Array.isArray(this.state.attachments) ? this.state.attachments.length : 0;

    el.innerHTML = `
      <div class="ve-wrapper">
      <header class="ve-card ve-toolbar flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-semibold tracking-tight">Voucher Entry</h1>
          <span class="ve-pill px-2 py-1 rounded-lg text-xs bg-slate-200 text-slate-800">${voucherType}</span>
          <span class="ve-status-badge ${statusBadge}">${statusLabel}</span>
          <span class="badge">No: <strong>${this.voucherDisplayNumber()}</strong></span>
          <span class="text-xs text-slate-500 ml-2">Excel paste + Sample Excel export</span>
        </div>
        <div class="flex gap-2">
          ${voucherTypes.length > 1 ? `<div class="ve-type-toggle inline-flex rounded-xl p-1 bg-slate-100 text-sm">
            ${voucherTypes.map(v => `
              <button data-action="setType" data-type="${v}"
                class="px-3 py-1.5 rounded-lg transition ${voucherType === v ? 'active text-slate-800 font-medium' : 'text-slate-600 hover:bg-white/60'}">${v}</button>
            `).join('')}
          </div>` : ''}
          <button data-action="saveDraft" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50" ${canSaveDraft ? '' : 'disabled'}>
            ${isSaving ? 'Working…' : 'Save Draft'}
          </button>
          ${PERMISSIONS.submit ? `<button data-action="submit" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50" ${canSubmit ? '' : 'disabled'}>Submit</button>` : ''}
          ${PERMISSIONS.approve ? `<button data-action="approve" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm bg-emerald-600 text-white hover:bg-emerald-700" ${canApprove ? '' : 'disabled'}>Approve</button>` : ''}
          ${PERMISSIONS.reject ? `<button data-action="reject" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50" ${canReject ? '' : 'disabled'}>Reject</button>` : ''}
          ${PERMISSIONS.post ? `<button data-action="post" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50" ${canPost ? '' : 'disabled'}>Post</button>` : ''}
          <button data-action="attach" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">
            Attachments${attachmentsCount ? ` (${attachmentsCount})` : ''}
          </button>
        </div>
      </header>

      <section class="ve-section mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="ve-card col-span-2 rounded-2xl border bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Header</h2>
            <button data-action="toggleSection" data-section="header" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show header">${collapsed.header ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.header ? headerSummary(header, voucherType) : `
          <div class="ve-summary-grid grid grid-cols-2 md:grid-cols-3 gap-3">
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
            <button data-action="openUdf" data-scope="Header" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+ UDF (Header)</button>
            ${udfHeaderDefs.map(f => `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs cursor-pointer hover:bg-slate-200" data-action="removeUdf" data-scope="Header" data-udfid="${f.id}">U:${escapeHtml(f.label)} &times;</span>`).join('')}
          </div>`}
        </div>

        <div class="ve-card rounded-2xl border bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold">Actions</h2>
            <button data-action="toggleSection" data-section="actions" class="text-xs px-2 py-1 rounded-lg border" title="Hide/Show actions">${collapsed.actions ? 'Show' : 'Hide'}</button>
          </div>
          ${collapsed.actions ? actionsSummary(rows, cols) : `
          <div class="flex flex-wrap gap-2">
            <button data-action="addRow" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Add Row</button>
            <button data-action="add10" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+10 Rows</button>
            <button data-action="clearRows" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Clear Rows</button>
            <button data-action="openCols" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Columns</button>
            <button data-action="saveCols" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Save Columns</button>
            <button data-action="resetCols" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Reset Columns</button>
            <button data-action="importCsv" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Import CSV</button>
            <input id="csvFile" type="file" accept=".csv,text/csv" class="hidden" />
            <button data-action="exportCsv" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Export CSV</button>
            <button data-action="sampleXlsx" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Sample Excel (.xlsx)</button>
            <button data-action="exportXlsx" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Export Excel (.xlsx)</button>
            <button data-action="runTests" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">Run Tests</button>
          </div>
          <p class="text-xs text-slate-500 mt-2">Tip: paste cells copied from Excel directly into the grid. Use arrow keys / Tab / Enter. Ctrl+Delete removes row.</p>
          <div class="mt-3 flex gap-2 items-center">
          </div>`}
        </div>
      </section>

      <section class="ve-card mt-5 rounded-2xl border bg-white p-4 shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold">Lines</h2>
          <div class="flex items-center gap-3">
            <button data-action="openUdf" data-scope="Line" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50">+ UDF (Line)</button>
            ${udfLineDefs.map(f => `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs cursor-pointer hover:bg-slate-200" data-action="removeUdf" data-scope="Line" data-udfid="${f.id}">L:${escapeHtml(f.label)} &times;</span>`).join('')}
          </div>
        </div>

        <div id="grid" class="mt-3 overflow-auto border rounded-xl scroll-shadow" style="max-height: 440px">
          <table class="ve-ledger min-w-full text-sm table-fixed">
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

      <section class="ve-section mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="ve-card rounded-2xl border bg-white p-4 shadow-sm lg:col-span-2">
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

        <div class="ve-card rounded-2xl border bg-white p-4 shadow-sm">
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
              ${rowKV('Addl. Charges (+/-)', moneyFmt.format(totals.chargesTotal))}
              ${rowKV('Rounding', moneyFmt.format(totals.roundAdj))}
              <div class="border-t my-1"></div>
              ${rowKV('<strong>Grand Total</strong>', `<strong>${moneyFmt.format(totals.grand)}</strong>`)}
              <div class="mt-2 text-xs text-slate-500">Due Date: <strong>${this.computeDueDate(header.date, header.creditDays)}</strong></div>
            </div>
          `}
          <div class="mt-3 flex gap-2">
            <button data-action="paymentTerms" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50 w-full">Payment Terms</button>
            <button data-action="toggleCharges" class="ve-action-btn inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm border border-slate-300 bg-white hover:bg-slate-50 w-full">Additional Charges</button>
          </div>`}
        </div>
      </section>

      <footer class="ve-footer mt-6 text-center text-xs text-slate-500">
        Data syncs with server on save. Column widths remain stored locally for a personalised layout.
      </footer>

      </div>
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
        if (type === 'Journal') {
          this.state.journalTypeCode = DEFAULT_JOURNAL_TYPE;
        }
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
        this.setSaving(true);
        postJSON(Endpoints.save, payload)
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'draft';
              notify(r.data?.message || 'Draft saved.');
            } else {
              console.warn('Server rejected draft save:', r.status, r.text);
              this.handleServerErrors(r);
            }
          })
          .catch(err => {
            console.error(err);
            notify('Server unreachable. Draft saved locally (console shows payload).');
          })
          .finally(() => this.setSaving(false));
      } else {
        console.log('Draft payload', payload);
        this.state.status = 'draft';
        notify('Draft saved locally (console shows payload).');
        this.render();
      }
      return;
    }
    if (action === 'submit') {
      const errs = this.validate(); 
      if (errs.length) return alert('Fix issues:\n- ' + errs.join('\n- '));
      const payload = this.buildPayload();
      if (Endpoints.submit) {
        this.setSaving(true);
        postJSON(Endpoints.submit, payload)
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'awaiting_approval';
              notify(r.data?.message || 'Submitted for approval.');
            } else {
              console.warn('Server rejected submit:', r.status, r.text);
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Submit not sent.'); })
          .finally(() => this.setSaving(false));
      } else {
        this.state.status = 'awaiting_approval';
        this.render();
        notify('Submitted locally (no backend endpoint configured).');
      }
      return;
    }
    if (action === 'approve') {
      if (!(this.state.status && ['awaiting_approval', 'submitted'].includes(this.state.status.toLowerCase()))) return alert('Submit first');
      const payload = this.buildPayload();
      if (Endpoints.approve) {
        this.setSaving(true);
        postJSON(Endpoints.approve, payload)
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'approved';
              notify(r.data?.message || 'Journal approved.');
            } else {
              console.warn('Server rejected approve:', r.status, r.text);
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Approve not sent.'); })
          .finally(() => this.setSaving(false));
      } else {
        this.state.status = 'approved';
        this.render();
        notify('Approved locally (no backend endpoint configured).');
      }
      return;
    }
    if (action === 'reject') {
      const payload = this.buildPayload();
      if (Endpoints.reject) {
        this.setSaving(true);
        postJSON(Endpoints.reject, payload)
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'rejected';
              notify(r.data?.message || 'Journal rejected.');
            } else {
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Reject not sent.'); })
          .finally(() => this.setSaving(false));
      } else {
        this.state.status = 'rejected';
        this.render();
        notify('Rejected locally (no backend endpoint configured).');
      }
      return;
    }
    if (action === 'post') {
      const payload = this.buildPayload();
      if (Endpoints.post) {
        this.setSaving(true);
        postJSON(Endpoints.post, payload)
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'posted';
              notify(r.data?.message || 'Journal posted.');
            } else {
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Post not sent.'); })
          .finally(() => this.setSaving(false));
      } else {
        this.state.status = 'posted';
        this.render();
        notify('Posted locally (no backend endpoint configured).');
      }
      return;
    }

        if (action === 'attach') {
      notify('Attachment management is coming soon.');
      return;
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
      if (hkey === 'priceInclusiveTax') {
        this.state.header[hkey] = (t.value === 'inc');
      } else if (hkey === 'exRate' || hkey === 'creditDays' || t.type === 'number') {
        this.state.header[hkey] = asNum(t.value, hkey === 'exRate' ? 1 : 0);
      } else if (t.type === 'checkbox') {
        this.state.header[hkey] = !!t.checked;
      } else {
        this.state.header[hkey] = t.value;
      }
      if (!STANDARD_HEADER_KEYS.has(hkey)) {
        const extras = { ...(this.state.metadata.headerExtras || {}) };
        extras[hkey] = this.state.header[hkey];
        this.state.metadata.headerExtras = extras;
      }
      if (t.tagName === 'SELECT') {
        const choice = this.state.choiceMaps.header?.[hkey]?.[t.value];
        if (choice) {
          if (choice.id !== undefined) this.state.metadata[`${hkey}Id`] = choice.id;
          if (choice.code !== undefined) this.state.metadata[`${hkey}Code`] = choice.code;
          if (choice.label !== undefined) this.state.metadata[`${hkey}Label`] = choice.label;
        }
        if (hkey === 'journalTypeCode') {
          this.state.metadata.journalTypeCode = t.value;
          if (choice && choice.id !== undefined) this.state.metadata.journalTypeId = choice.id;
          else delete this.state.metadata.journalTypeId;
          this.state.journalTypeCode = t.value;
          this.state.currentConfigId = null;
          this.state.metadata.configId = null;
          if (this.state.configUrl) {
            this.fetchConfig(t.value);
          }
        }
      }
      this.persistPresets();
      this.render();
      return;
    }
    if (t.getAttribute('data-hudf')) {
      const id = t.getAttribute('data-hudf'); const type = t.getAttribute('data-type');
      if (type === 'checkbox') this.state.header[id] = !!t.checked; else if (type === 'number') this.state.header[id] = asNum(t.value); else this.state.header[id] = t.value;
      this.persistPresets(); this.render(); return;
    }
    if (t.classList.contains('cell-input')) {
      const ri = +t.getAttribute('data-ri');
      const colId = t.getAttribute('data-colid');
      const type = t.getAttribute('data-type');
      const row = this.state.rows[ri];
      if (type === 'checkbox') {
        row[colId] = !!t.checked;
      } else if (type === 'number') {
        row[colId] = asNum(t.value);
      } else if (type === 'select') {
        row[colId] = t.value;
        const choice = this.state.choiceMaps.line?.[colId]?.[t.value];
        if (choice) {
          if (choice.id !== undefined) row[`${colId}Id`] = choice.id;
          else row[`${colId}Id`] = t.value || null;
          if (choice.label !== undefined) row[`${colId}Label`] = choice.label;
          if (choice.code !== undefined) row[`${colId}Code`] = choice.code;
        } else {
          row[`${colId}Id`] = t.value || null;
        }
      } else {
        row[colId] = t.value;
        if (colId === 'account') {
          row.accountCode = (t.value || '').split(/\s+/)[0] || '';
          row.accountId = null;
          this.resolveAccount(row, t.value).finally(() => this.render());
          return;
        }
        if (colId === 'costCenter') {
          row.costCenterId = null;
          this.resolveCostCenter(row, t.value).finally(() => this.render());
          return;
        }
      }
      this.render();
      return;
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
    const {
      voucherType,
      header,
      rows,
      udfHeaderDefs,
      udfLineDefs,
      notes,
      charges,
      numbering,
      journalId,
      journalTypeCode,
      status,
    } = this.state;
    const totals = this.computeTotals();
    const preparedRows = rows.map((row, idx) => {
      const prepared = {
        lineNumber: idx + 1,
        accountId: row.accountId,
        accountCode: row.accountCode,
        account: row.account,
        narr: row.narr,
        dr: asNum(row.dr, 0),
        cr: asNum(row.cr, 0),
        costCenterId: row.costCenterId,
        costCenter: row.costCenter,
        projectId: row.projectId ?? null,
        project: row.project ?? '',
        projectLabel: row.projectLabel ?? '',
        departmentId: row.departmentId ?? null,
        department: row.department ?? '',
        departmentLabel: row.departmentLabel ?? '',
        taxCodeId: row.taxCodeId ?? null,
        taxCode: row.taxCode ?? '',
        taxCodeLabel: row.taxCodeLabel ?? '',
        udf: row.udf || {},
      };
      const dynamicKeys = this.state.dynamicLineKeys || [];
      dynamicKeys.forEach((key) => {
        if (prepared[key] === undefined) prepared[key] = row[key] ?? '';
        const idKey = `${key}Id`;
        if (row[idKey] !== undefined) prepared[idKey] = row[idKey];
        const labelKey = `${key}Label`;
        if (row[labelKey] !== undefined) prepared[labelKey] = row[labelKey];
      });
      return prepared;
    });
    const headerPayload = {
      date: header.date,
      currency: header.currency,
      exRate: asNum(header.exRate, 1),
      creditDays: asNum(header.creditDays, 0),
      reference: header.reference || '',
      description: header.description || notes || '',
      branch: header.branch || '',
    };
    this.state.headerFieldDefs.forEach((field) => {
      const key = field.stateKey;
      if (!(key in headerPayload)) {
        headerPayload[key] = this.state.header[key] ?? '';
      }
    });
    const headerExtras = {};
    Object.keys(headerPayload).forEach((key) => {
      if (!STANDARD_HEADER_KEYS.has(key)) {
        headerExtras[key] = headerPayload[key];
      }
    });
    const sanitizedCharges = (charges || []).map(c => ({
      id: c.id || uid(),
      label: c.label || '',
      mode: c.mode || 'amount',
      value: typeof c.value === 'number' ? c.value : asNum(c.value, 0),
      sign: Number(c.sign ?? 1),
    }));

    const attachmentsPayload = Array.isArray(this.state.attachments) ? this.state.attachments : [];

    const payload = {
      journalId,
      voucherType,
      header: headerPayload,
      rows: preparedRows,
      udfHeaderDefs,
      udfLineDefs,
      columns,
      notes,
      charges: sanitizedCharges,
      numbering,
      totals,
      meta: (() => {
        const meta = {
          ...(this.state.metadata || {}),
          journalTypeCode,
          status,
        };
        if (Object.keys(headerExtras).length) {
          meta.headerExtras = headerExtras;
        }
        return meta;
      })(),
    };
    if (attachmentsPayload.length) {
      payload.attachments = attachmentsPayload;
    }
    return payload;
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
function Labeled(label, inner, help) {
  const lbl = escapeHtml(label);
  const helpBlock = help ? `<span class="text-xs text-slate-400">${escapeHtml(help)}</span>` : '';
  return `<label class="flex flex-col gap-1 text-sm"><span class="text-slate-600">${lbl}</span>${helpBlock}${inner}</label>`;
}
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
  if (col.type === 'select') {
    const options = Array.isArray(col.options) ? col.options : [];
    const normalized = [{ value: '', label: '' }].concat(options.map((opt) => {
      if (opt && typeof opt === 'object') {
        const optValue = opt.value === undefined || opt.value === null ? '' : String(opt.value);
        const optLabel = opt.label !== undefined ? opt.label : optValue;
        return { value: optValue, label: optLabel };
      }
      const optValue = opt === undefined || opt === null ? '' : String(opt);
      return { value: optValue, label: optValue };
    }));
    const currentValue = value === undefined || value === null ? '' : String(value);
    const html = normalized.map(({ value: optValue, label: optLabel }) => {
      const valStr = optValue === undefined || optValue === null ? '' : String(optValue);
      const selected = currentValue === valStr;
      return `<option value="${escapeHtml(valStr)}"${selected ? ' selected' : ''}>${escapeHtml(optLabel === undefined || optLabel === null ? valStr : String(optLabel))}</option>`;
    }).join('');
    return `<select ${base}>${html}</select>`;
  }
  if (col.type === 'checkbox') return `<input type="checkbox" ${base} ${value ? 'checked' : ''}>`;
  return `<input ${base} value="${escapeHtml(value ?? '')}">`;
}
function fieldControl(def, value) {
  const title = def.type === 'number' ? String(value ?? '') : escapeHtml(value ?? '');
  const base = `class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white ${def.type === 'number' ? 'text-right' : ''}" data-hudf="${def.id}" data-type="${def.type}" title="${title}"`;
  if (def.type === 'number') return `<input type="number" ${base} value="${value}">`;
  if (def.type === 'date') return `<input type="date" ${base} value="${value}">`;
  if (def.type === 'select') {
    const options = Array.isArray(def.options) ? def.options : [];
    const normalized = [{ value: '', label: '' }].concat(options.map((opt) => {
      if (opt && typeof opt === 'object') {
        const optValue = opt.value === undefined || opt.value === null ? '' : String(opt.value);
        const optLabel = opt.label !== undefined ? opt.label : optValue;
        return { value: optValue, label: optLabel };
      }
      const optValue = opt === undefined || opt === null ? '' : String(opt);
      return { value: optValue, label: optValue };
    }));
    const currentValue = value === undefined || value === null ? '' : String(value);
    const html = normalized.map(({ value: optValue, label: optLabel }) => {
      const valStr = optValue === undefined || optValue === null ? '' : String(optValue);
      const selected = currentValue === valStr;
      return `<option value="${escapeHtml(valStr)}"${selected ? ' selected' : ''}>${escapeHtml(optLabel === undefined || optLabel === null ? valStr : String(optLabel))}</option>`;
    }).join('');
    return `<select ${base}>${html}</select>`;
  }
  if (def.type === 'checkbox') return `<div class="h-10 flex items-center"><input type="checkbox" ${base} ${value ? 'checked' : ''}></div>`;
  return `<input ${base} value="${escapeHtml(value || '')}">`;
}
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }
function cellTitle(val, col) { return col.type === 'number' ? String(val ?? '') : escapeHtml(val ?? ''); }

function headerSummary(h, vt) {
  return `<div class="text-sm flex flex-wrap gap-2">
    ${vt !== 'Journal' ? chip('Party', escapeHtml(h.party || 'N/A')) : ''}
    ${chip('Date', escapeHtml(h.date || 'N/A'))}
    ${chip('Branch', escapeHtml(h.branch || 'N/A'))}
    ${chip('Currency', escapeHtml(h.currency || 'N/A'))}
    ${vt !== 'Journal' ? chip('Pricing', h.priceInclusiveTax ? 'Tax Inclusive' : 'Tax Exclusive') : ''}
  </div>`;
}
function actionsSummary(rows, cols) {
  const visible = cols.filter(c => c.visible !== false).length;
  return `<div class="text-sm flex flex-wrap gap-2">${chip('Rows', rows.length)}${chip('Visible Cols', visible)}${chip('Hidden Cols', Math.max(0, cols.length - visible))}</div>`;
}
function notesSummary(notes, status) {
  const short = (notes || '').trim().slice(0, 80) || 'N/A';
  return `<div class="text-sm">${chip('Notes', escapeHtml(short))}${chip('Status', escapeHtml(status))}</div>`;
}
function totalsSummary(vt, totals) {
  if (vt === 'Journal') return `<div class="text-sm">${chip('Dr', moneyFmt.format(totals.dr))}${chip('Cr', moneyFmt.format(totals.cr))}${chip('Diff', moneyFmt.format(totals.diff))}</div>`;
  return `<div class="text-sm">${chip('Subtotal', moneyFmt.format(totals.sub))}${chip('Tax', moneyFmt.format(totals.tax))}${chip('Grand', moneyFmt.format(totals.grand))}</div>`;
}
function chip(k, v) { return `<span class="ve-pill inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 text-slate-700"><span class="text-slate-500">${k}:</span> <span class="font-medium">${v}</span></span>`; }

/** Modals */
function udfModalHtml(state) {
  const d = state.udfDraft; const scope = state.udfScope;
  return `
  <div class="modal-backdrop" data-action="udfCancel">
    <div class="bg-white rounded-2xl shadow-xl w-[560px] max-w-[95vw] p-4" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold">Add UDF - ${scope} level</h3>
        <button class="text-slate-500 hover:text-black" data-action="udfCancel">&times;</button>
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
        <button class="text-slate-500 hover:text-black" data-action="cmCancel">&times;</button>
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
                  <button class="px-2 py-1 rounded border" data-action="cmMove" data-col="${r.id}" data-dir="-1">&uarr;</button>
                  <button class="px-2 py-1 rounded border" data-action="cmMove" data-col="${r.id}" data-dir="1">&darr;</button>
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
        <button class="text-slate-500 hover:text-black" data-action="chgClose">&times;</button>
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
