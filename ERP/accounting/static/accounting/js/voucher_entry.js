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
  periodValidate: __root?.dataset?.endpointPeriodValidate || null,
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
const PREFS_ENDPOINT = __root?.dataset?.prefsUrl || null;
const PREFS_SAVE_ENDPOINT = __root?.dataset?.prefsSaveUrl || __root?.dataset?.prefsUrl || null;
const ATTACH_UPLOAD_ENDPOINT = __root?.dataset?.attachUpload || null;
const ATTACH_DELETE_ENDPOINT = __root?.dataset?.attachDelete || null;
const PAYMENT_TERMS_ENDPOINT = __root?.dataset?.paymentTerms || null;
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
const DEBUG_ENABLED = __root?.dataset?.debugEnabled === 'true';

const cloneForDebug = (payload) => {
  if (!DEBUG_ENABLED || payload === undefined) return undefined;
  try {
    return JSON.parse(JSON.stringify(payload));
  } catch (err) {
    console.warn('Unable to clone payload for debug log', err);
    return payload;
  }
};

const DebugPanel = (() => {
  if (!DEBUG_ENABLED) {
    return { enabled: false, record() {}, clear() {} };
  }
  const panel = document.getElementById('journal-debug-panel');
  if (!panel) {
    return { enabled: false, record() {}, clear() {} };
  }
  const entriesEl = document.getElementById('journal-debug-entries');
  const copyBtn = document.getElementById('journal-debug-copy');
  const downloadBtn = document.getElementById('journal-debug-download');
  const clearBtn = document.getElementById('journal-debug-clear');
  const buffer = [];
  const MAX_ENTRIES = 50;

  const toDuration = (start, end) => {
    if (!start || !end) return '';
    const diff = new Date(end) - new Date(start);
    if (Number.isNaN(diff)) return '';
    return `${diff} ms`;
  };

  const render = () => {
    if (!entriesEl) return;
    entriesEl.innerHTML = '';
    buffer.slice().reverse().forEach((entry) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'mb-3 pb-2 border-bottom';

      const header = document.createElement('div');
      header.className = 'd-flex flex-wrap justify-content-between align-items-center gap-2';

      const left = document.createElement('div');
      left.innerHTML = `<strong>${entry.action || entry.url || 'Request'}</strong>
        <div class="small text-muted">${entry.startedAt || ''}</div>`;

      const right = document.createElement('div');
      right.className = 'd-flex flex-wrap align-items-center gap-2';
      if (entry.debugToken) {
        const tokenBadge = document.createElement('span');
        tokenBadge.className = 'badge bg-secondary';
        tokenBadge.textContent = entry.debugToken;
        tokenBadge.title = 'Share this token with support to correlate backend logs';
        right.appendChild(tokenBadge);
      }
      if (entry.status !== undefined) {
        const statusBadge = document.createElement('span');
        statusBadge.className = `badge ${entry.ok ? 'bg-success' : 'bg-danger'}`;
        statusBadge.textContent = entry.status ?? 'ERR';
        right.appendChild(statusBadge);
      }
      const duration = toDuration(entry.startedAt, entry.finishedAt);
      if (duration) {
        const durBadge = document.createElement('span');
        durBadge.className = 'badge bg-light text-dark border';
        durBadge.textContent = duration;
        right.appendChild(durBadge);
      }

      header.appendChild(left);
      header.appendChild(right);

      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(entry, null, 2);

      wrapper.appendChild(header);
      wrapper.appendChild(pre);
      entriesEl.appendChild(wrapper);
    });
  };

  const feedback = (btn, label) => {
    if (!btn) return;
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = label;
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = original;
    }, 1200);
  };

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      if (!buffer.length) return;
      const text = JSON.stringify(buffer, null, 2);
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(text).then(() => feedback(copyBtn, 'Copied'), () => feedback(copyBtn, 'Copy failed'));
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        try {
          document.execCommand('copy');
          feedback(copyBtn, 'Copied');
        } catch {
          feedback(copyBtn, 'Copy failed');
        }
        document.body.removeChild(textarea);
      }
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      if (!buffer.length) return;
      const blob = new Blob([JSON.stringify(buffer, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `journal-debug-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      feedback(downloadBtn, 'Ready');
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      buffer.length = 0;
      render();
      feedback(clearBtn, 'Cleared');
    });
  }

  return {
    enabled: true,
    record(entry) {
      if (!entry) return;
      const normalized = {
        action: entry.action,
        url: entry.url,
        status: entry.status,
        ok: entry.ok,
        startedAt: entry.startedAt,
        finishedAt: entry.finishedAt,
        debugToken: entry.debugToken,
        request: entry.request,
        response: entry.response,
        error: entry.error,
      };
      buffer.push(normalized);
      if (buffer.length > MAX_ENTRIES) buffer.shift();
      render();
    },
    clear() {
      buffer.length = 0;
      render();
    },
  };
})();

async function postJSON(url, payload, meta = {}) {
  const startedAt = new Date().toISOString();
  const requestCopy = cloneForDebug(payload);
  try {
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
    try { data = JSON.parse(text); } catch (e) { /* non-JSON response */ }
    const finishedAt = new Date().toISOString();
    const debugToken = data?.debugToken || data?.debug_token || null;
    DebugPanel.record({
      action: meta.action || payload?.action || null,
      url,
      status: res.status,
      ok: res.ok,
      startedAt,
      finishedAt,
      debugToken,
      request: requestCopy,
      response: cloneForDebug(data ?? text)
    });
    return { ok: res.ok, status: res.status, data, text, debugToken };
  } catch (error) {
    const finishedAt = new Date().toISOString();
    DebugPanel.record({
      action: meta.action || payload?.action || null,
      url,
      status: null,
      ok: false,
      startedAt,
      finishedAt,
      request: requestCopy,
      error: String(error)
    });
    throw error;
  }
}

async function fetchJSON(url, options = {}, meta = {}) {
  const startedAt = new Date().toISOString();
  const method = options?.method || 'GET';
  const normalizedOptions = {
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  };
  const requestBody = normalizedOptions.body;
  try {
    const res = await fetch(url, normalizedOptions);
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch (err) { /* response not JSON */ }
    const finishedAt = new Date().toISOString();
    DebugPanel.record({
      action: meta.action || `${method} ${url}`,
      url,
      status: res.status,
      ok: res.ok,
      startedAt,
      finishedAt,
      request: requestBody ? cloneForDebug(requestBody) : undefined,
      response: cloneForDebug(data ?? text),
    });
    return { ok: res.ok, status: res.status, data, text };
  } catch (error) {
    const finishedAt = new Date().toISOString();
    DebugPanel.record({
      action: meta.action || `${method} ${url}`,
      url,
      status: null,
      ok: false,
      startedAt,
      finishedAt,
      error: String(error),
      request: requestBody ? cloneForDebug(requestBody) : undefined,
    });
    throw error;
  }
}

function notify(msg, level = 'success') {
  try {
    const alerts = document.getElementById('app-alerts');
    const asText = (typeof msg === 'string') ? msg : (msg?.message || msg?.error || String(msg));
    const plainMessage = String(asText ?? '').trim();
    const sanitized = plainMessage.replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

    if (alerts) {
      // Render an in-page Bootstrap alert just below top bar without trusting HTML from the server
      alerts.textContent = '';
      const cls = level === 'error' ? 'alert-danger' : (level === 'warning' ? 'alert-warning' : 'alert-success');
      const wrapper = document.createElement('div');
      wrapper.className = `alert ${cls} d-flex align-items-center`;
      wrapper.setAttribute('role', 'alert');

      const icon = document.createElement('i');
      icon.className = `mdi ${level === 'error' ? 'mdi-alert-octagon-outline' : 'mdi-check-circle-outline'} me-2`;
      const textNode = document.createElement('div');
      textNode.textContent = plainMessage;

      wrapper.appendChild(icon);
      wrapper.appendChild(textNode);
      alerts.appendChild(wrapper);
    }
    // Also show toast if available (escape to guard against HTML execution)
    if (typeof toastr !== 'undefined') {
      if (level === 'error') toastr.error(sanitized); else if (level === 'warning') toastr.warning(sanitized); else toastr.success(sanitized);
    } else if (!alerts && plainMessage) {
      alert(plainMessage);
    }
  } catch (e) {
    console.error('Notification error:', e);
    try { alert(typeof msg === 'string' ? msg : JSON.stringify(msg)); } catch {}
  }
}
// ---- End Django Integration Header ----


/** Local persistence + utils */
const LS_KEY = 'voucherEntryPresets_v5';
const moneyFmt = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const asNum = (v, d = 0) => { if (v === null || v === undefined) return d; const x = parseFloat(String(v).replace(/,/g, '')); return Number.isNaN(x) ? d : x; };
const uid = () => Math.random().toString(36).slice(2, 10);
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const debounce = (fn, delay = 200) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};
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

const AccountSuggest = (() => {
  let container;
  let listEl;
  let anchor = null;
  let activeIndex = 0;
  let items = [];
  let termText = '';
  let onSelect = null;
  let onAddNew = null;
  let outsideHandler = null;

  const ensure = () => {
    if (container) return;
    container = document.createElement('div');
    container.className = 've-suggest';
    container.innerHTML = '<div class="ve-suggest-list"></div>';
    listEl = container.querySelector('.ve-suggest-list');
    document.body.appendChild(container);
  };

  const position = () => {
    if (!container || !anchor) return;
    const rect = anchor.getBoundingClientRect();
    container.style.minWidth = Math.max(260, rect.width) + 'px';
    container.style.left = `${window.scrollX + rect.left}px`;
    container.style.top = `${window.scrollY + rect.bottom + 6}px`;
  };

  const close = () => {
    if (!container) return;
    container.classList.remove('open');
    items = [];
    anchor = null;
    termText = '';
    activeIndex = 0;
    if (outsideHandler) {
      document.removeEventListener('click', outsideHandler, true);
      outsideHandler = null;
    }
    window.removeEventListener('resize', position);
    window.removeEventListener('scroll', position, true);
  };

  const highlight = (idx) => {
    activeIndex = idx;
    render();
  };

  const select = (idx) => {
    if (idx === items.length) {
      close();
      if (typeof onAddNew === 'function') onAddNew();
      return;
    }
    const choice = items[idx];
    if (choice && typeof onSelect === 'function') {
      onSelect(choice);
    }
    close();
  };

  const render = () => {
    if (!container || !listEl) return;
    listEl.innerHTML = '';
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 've-suggest-empty';
      empty.textContent = termText ? `No matches for "${termText}"` : 'No matches found';
      listEl.appendChild(empty);
    }
    items.forEach((item, idx) => {
      const row = document.createElement('div');
      row.className = `ve-suggest-item${idx === activeIndex ? ' active' : ''}`;
      row.dataset.index = idx;
      row.innerHTML = `
        <div>
          <div class="ve-suggest-label">${escapeHtml([item.code, item.name].filter(Boolean).join(' - ') || item.label || '')}</div>
          <div class="ve-suggest-meta">${escapeHtml(item.name || item.code || '')}</div>
        </div>
        ${item.badge ? `<span class="ve-suggest-chip">${escapeHtml(item.badge)}</span>` : ''}
      `;
      row.onmouseenter = () => highlight(idx);
      row.onmousedown = (ev) => { ev.preventDefault(); select(idx); };
      listEl.appendChild(row);
    });
    const addIdx = items.length;
    const addRow = document.createElement('div');
    addRow.className = `ve-suggest-item add-new${activeIndex === addIdx ? ' active' : ''}`;
    addRow.dataset.index = addIdx;
    addRow.innerHTML = `
      <div>
        <div class="ve-suggest-label">+ Add New Account</div>
        <div class="ve-suggest-meta">Opens Chart of Accounts in a new tab</div>
      </div>
    `;
    addRow.onmouseenter = () => highlight(addIdx);
    addRow.onmousedown = (ev) => { ev.preventDefault(); select(addIdx); };
    listEl.appendChild(addRow);
    position();
  };

  return {
    open(target, suggestions = [], handlers = {}) {
      close();
      ensure();
      anchor = target;
      items = Array.isArray(suggestions) ? suggestions : [];
      onSelect = handlers.onSelect || null;
      onAddNew = handlers.onAddNew || null;
      termText = handlers.term || '';
      activeIndex = items.length ? 0 : 0;
      container.classList.add('open');
      render();
      outsideHandler = (ev) => {
        if (!container.contains(ev.target) && ev.target !== anchor) {
          close();
        }
      };
      document.addEventListener('click', outsideHandler, true);
      window.addEventListener('resize', position);
      window.addEventListener('scroll', position, true);
    },
    close,
    move(delta) {
      if (!container || !container.classList.contains('open')) return;
      const total = items.length + 1; // +1 for Add New
      activeIndex = (activeIndex + delta + total) % total;
      render();
    },
    selectCurrent() { select(activeIndex); },
    isOpenFor(target) {
      return !!container && container.classList.contains('open') && anchor === target;
    },
    highlight,
  };
})();

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
    isLocked: false,
    isEditable: true,
    postedAt: null,
    postedBy: null,
    postedByName: '',
    isReversal: false,
    reversalOfId: null,
    configUrl: __root?.dataset?.configUrl || null,
    supportedCurrencies: SUPPORTED_CURRENCIES,
    header: {
      date: new Date().toISOString().slice(0, 10),
      branch: 'Main',
      currency: SUPPORTED_CURRENCIES[0] || 'NPR',
      exRate: 1,
      reference: '',
      description: '',
    },
    notes: '',
    collapsed: { header: false, actions: false, notes: false, totals: false },
    udfHeaderDefs: [],
    udfLineDefs: [],
    colPrefsByType: {},
    rows: [],
    charges: [],
    numbering: { prefix: { Journal: 'JV' }, nextSeq: { Journal: 1 }, width: 4 },
    focus: { r: 0, c: 0 },
    showUdfModal: false,
    udfScope: 'Header',
    udfDraft: { label: '', type: 'text', required: false, options: '' },
    showColManager: false,
    colManagerDraft: [],
    showCharges: false,
    showKeyboardHelp: false,
    availableVoucherTypes: ['Journal'],
    detailUrlTemplate: DETAIL_URL_TEMPLATE,
    serverTotals: null,
    attachments: [],
    metadata: {},
    density: 'compact',
    frozenColumns: 0,
    showFilters: false,
    columnFilters: {},
    quickSearch: '',
    showAttachmentsModal: false,
    showPaymentTermsModal: false,
    paymentTerms: { termId: null, termCode: '', dueDate: '', discountDueDate: '', discountPercent: 0, netDueDays: 0 },
    paymentTermOptions: [],
    showCoaModal: false,
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

  async init() {
    const presets = loadPresets();
    this.applyPreferencesFromStore(presets);

    if (!Array.isArray(this.state.rows) || !this.state.rows.length) {
      this.resetRows();
    }
    this.render();
    
    // Check URL parameters for config_id
    const urlParams = new URLSearchParams(window.location.search);
    const urlConfigId = urlParams.get('config_id');
    const urlJournalType = urlParams.get('journal_type');
    
    const initialType = urlJournalType || this.state.journalTypeCode || DEFAULT_JOURNAL_TYPE;
    const initialConfigId = urlConfigId || this.state.metadata?.configId || null;
    
    // Always fetch config if we have URL params
    if (this.state.configUrl && (urlConfigId || urlJournalType)) {
      this.fetchConfig(initialType, initialConfigId);
    } else if (this.state.journalId) {
      // Only fetch journal if no config params
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

    this.loadRemotePreferences();
  },

  getColumns() {
    const { udfLineDefs, colPrefsByType, configLineDefs, configBaseOverrides } = this.state;
    const voucherType = 'Journal'; // Always use Journal
    let cols = buildColumns(voucherType, udfLineDefs, colPrefsByType[voucherType]);
    
    // Apply config-based overrides to base columns
    if (configBaseOverrides) {
      cols = cols.map((col) => {
        if (configBaseOverrides[col.id]) {
          return { ...col, ...configBaseOverrides[col.id] };
        }
        return col;
      });
    }
    
    // Add extra columns from config
    if (Array.isArray(configLineDefs) && configLineDefs.length) {
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
  blankRow() {
    // Always return journal row structure
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
  },
  resetRows(n = 5) {
    this.state.rows = Array.from({ length: n }, () => this.blankRow());
    this.state.isEditable = true;
    this.state.isLocked = false;
    this.state.postedAt = null;
    this.state.postedBy = null;
    this.state.postedByName = '';
    this.state.isReversal = false;
    this.state.reversalOfId = null;
  },

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
      notify('Fix issues:\n- ' + details.errors.join('\n- '), 'error');
    } else if (response?.data?.error) {
      notify(response.data.error, 'error');
    } else {
      notify('Server rejected the request.', 'error');
    }
  },

  async _preflightDate() {
    const d = (this.state.header?.date || '').trim();
    if (!d || !Endpoints.periodValidate) return true;
    try {
      const url = `${Endpoints.periodValidate}?date=${encodeURIComponent(d)}`;
      const { ok, data } = await fetchJSON(url, {}, { action: 'Validate Period' });
      if (!ok || !data?.ok) {
        const msg = (data?.error) || 'Selected date is not in an open accounting period.';
        notify(msg, 'error');
        return false;
      }
      return true;
    } catch (e) {
      console.warn('Preflight date validation failed', e);
      return true; // fail-open to avoid blocking if endpoint unreachable
    }
  },

  lookupAccount(query) {
    const token = (query || '').trim();
    if (!LOOKUPS.account || !token) return Promise.resolve(null);
    const code = token.split(/\s|-/)[0];
    const url = `${LOOKUPS.account}?q=${encodeURIComponent(code)}`;
    return fetchJSON(url, {}, { action: `Lookup Account ${code}` })
      .then(({ data }) => {
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
    return fetchJSON(url, {}, { action: `Lookup Cost Center ${code}` })
      .then(({ data }) => {
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

  queueCostCenterSuggestions(inputEl, ri, ci) {
    if (!inputEl || !inputEl.classList.contains('cell-input')) return;
    this.state.rows[ri].costCenter = inputEl.value;
    this.state.rows[ri].costCenterId = null;
    const term = (inputEl.value || '').trim();
    if (!term) {
      AccountSuggest.close();
      return;
    }
    if (!this._debouncedCostCenterLookup) {
      this._debouncedCostCenterLookup = debounce((value, anchor, rowIdx, colIdx) => {
        this.fetchCostCenterSuggestions(value, anchor, rowIdx, colIdx);
      }, 180);
    }
    this._debouncedCostCenterLookup(term, inputEl, ri, ci);
  },

  async fetchCostCenterSuggestions(term, inputEl, ri, ci) {
    if (!LOOKUPS.costCenter || !inputEl) return;
    const queryToken = `${term}:${ri}:${Date.now()}`;
    this._latestCostCenterQuery = queryToken;
    try {
      const { data } = await fetchJSON(`${LOOKUPS.costCenter}?q=${encodeURIComponent(term)}`, {}, { action: `Search Cost Center ${term}` });
      if (this._latestCostCenterQuery !== queryToken) return;
      const results = Array.isArray(data?.results) ? data.results : [];
      const suggestions = results.map((r) => ({ id: r.id, code: r.code || '', name: r.name || '' }));
      AccountSuggest.open(inputEl, suggestions, {
        term,
        onSelect: (choice) => this.applyCostCenterSelection(choice, ri, ci),
      });
    } catch (err) {
      console.error('Cost center lookup failed', err);
    }
  },

  applyCostCenterSelection(choice, ri, ci) {
    if (!choice || !this.state.rows[ri]) return;
    const row = this.state.rows[ri];
    row.costCenterId = choice.id ?? null;
    row.costCenter = choice.code || '';
    this.state.focus = { r: ri, c: ci };
    AccountSuggest.close();
    this.render();
  },

  async fetchPaymentTerms() {
    if (!PAYMENT_TERMS_ENDPOINT) return;
    const date = this.state.header?.date;
    const url = date ? `${PAYMENT_TERMS_ENDPOINT}?date=${encodeURIComponent(date)}` : PAYMENT_TERMS_ENDPOINT;
    try {
      const { ok, data } = await fetchJSON(url, {}, { action: 'Load Payment Terms' });
      if (ok && Array.isArray(data?.results)) {
        this.state.paymentTermOptions = data.results;
      }
    } catch (err) {
      console.warn('Unable to load payment terms', err);
    }
  },

  updatePaymentTerm(term) {
    if (!term) {
      this.state.paymentTerms = { termId: null, termCode: '', dueDate: '', discountDueDate: '', discountPercent: 0, netDueDays: 0 };
      this.render();
      return;
    }
    const net = Number(term.netDueDays || term.net_due_days || 0);
    const dueDate = this.computeDueDate(this.state.header?.date, net);
    const discountDue = term.discountDays ? this.computeDueDate(this.state.header?.date, Number(term.discountDays)) : '';
    this.state.paymentTerms = {
      termId: term.id ?? null,
      termCode: term.code || term.name || '',
      netDueDays: net,
      dueDate,
      discountDueDate: discountDue,
      discountPercent: term.discountPercent ?? 0,
    };
    this.render();
  },

  applyPaymentTerms() {
    const pt = this.state.paymentTerms || {};
    if (pt.netDueDays !== undefined) {
      this.state.header.creditDays = pt.netDueDays;
    }
    if (pt.dueDate) {
      this.state.header.dueDate = pt.dueDate;
    }
    if (pt.termId) {
      this.state.header.paymentTermId = pt.termId;
      this.state.header.paymentTermCode = pt.termCode || '';
    }
    this.state.showPaymentTermsModal = false;
    this.persistPresets();
    this.render();
  },

  async ensureJournalId() {
    if (this.state.journalId) return this.state.journalId;
    if (!Endpoints.save) {
      notify('Configure the draft save endpoint before uploading attachments.', 'error');
      return null;
    }
    const okDate = await this._preflightDate();
    if (!okDate) return null;
    this.state.isSaving = true;
    this.render();
    try {
      const payload = this.buildPayload();
      const res = await postJSON(Endpoints.save, payload, { action: 'Auto-save for attachments' });
      if (res.ok && res.data?.journal) {
        this.hydrateFromApi(res.data.journal);
        this.state.status = res.data?.journal?.status || 'draft';
        return this.state.journalId;
      }
      this.handleServerErrors(res);
    } catch (err) {
      console.error('Auto-save failed', err);
      notify('Could not save draft before uploading attachments.', 'error');
    } finally {
      this.state.isSaving = false;
      this.render();
    }
    return null;
  },

  async uploadAttachments(fileList) {
    if (!ATTACH_UPLOAD_ENDPOINT) {
      notify('Attachment upload endpoint is not configured.', 'error');
      return;
    }
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;
    const journalId = await this.ensureJournalId();
    if (!journalId) return;
    const form = new FormData();
    form.append('journal_id', journalId);
    files.forEach((f) => form.append('files', f));
    const startedAt = new Date().toISOString();
    try {
      const res = await fetch(ATTACH_UPLOAD_ENDPOINT, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': CSRFTOKEN || '' },
        body: form,
      });
      const text = await res.text();
      let data = null;
      try { data = JSON.parse(text); } catch { data = null; }
      DebugPanel.record({
        action: 'Upload Attachments',
        url: ATTACH_UPLOAD_ENDPOINT,
        status: res.status,
        ok: res.ok,
        startedAt,
        finishedAt: new Date().toISOString(),
        request: { journalId, files: files.map((f) => f.name) },
        response: cloneForDebug(data ?? text),
      });
      if (!res.ok || !data?.ok) {
        notify(data?.error || 'Attachment upload failed.', 'error');
        return;
      }
      if (Array.isArray(data.attachments)) {
        const merged = [...(this.state.attachments || []), ...data.attachments];
        const seen = new Set();
        this.state.attachments = merged.filter((att) => {
          if (!att?.id) return true;
          if (seen.has(att.id)) return false;
          seen.add(att.id);
          return true;
        });
        notify('Attachment uploaded.', 'success');
        this.render();
      }
    } catch (err) {
      console.error('Attachment upload failed', err);
      notify('Attachment upload failed.', 'error');
    }
  },

  deleteAttachment(attId) {
    if (!attId) {
      this.render();
      return;
    }
    this.state.attachments = (this.state.attachments || []).filter((att) => String(att.id) !== String(attId));
    if (!ATTACH_DELETE_ENDPOINT) {
      this.render();
      return;
    }
    const form = new FormData();
    form.append('attachment_id', attId);
    fetch(ATTACH_DELETE_ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': CSRFTOKEN || '' },
      body: form,
    })
      .then((res) => res.json().catch(() => ({})).then((data) => ({ res, data })))
      .then(({ res, data }) => {
        if (!res.ok || !data?.ok) {
          notify(data?.error || 'Failed to delete attachment.', 'error');
        }
      })
      .catch((err) => console.warn('Attachment delete failed', err));
    this.render();
  },

  queueAccountSuggestions(inputEl, ri, ci) {
    if (!inputEl || !inputEl.classList.contains('cell-input')) return;
    this.state.rows[ri].account = inputEl.value;
    this.state.rows[ri].accountId = null;
    this.state.focus = { r: ri, c: ci };

    const term = (inputEl.value || '').trim();
    if (!term) {
      AccountSuggest.close();
      return;
    }

    if (!this._debouncedAccountLookup) {
      this._debouncedAccountLookup = debounce((value, anchor, rowIdx, colIdx) => {
        this.fetchAccountSuggestions(value, anchor, rowIdx, colIdx);
      }, 180);
    }
    this._debouncedAccountLookup(term, inputEl, ri, ci);
  },

  async fetchAccountSuggestions(term, inputEl, ri, ci) {
    if (!LOOKUPS.account || !inputEl) return;
    const queryToken = `${term}:${ri}:${Date.now()}`;
    this._latestAccountQuery = queryToken;
    try {
      const { data } = await fetchJSON(`${LOOKUPS.account}?q=${encodeURIComponent(term)}`, {}, { action: `Search Account ${term}` });
      if (this._latestAccountQuery !== queryToken) return;
      const results = Array.isArray(data?.results) ? data.results : [];
      const suggestions = results.map((r, idx) => ({
        id: r.id,
        code: r.code || '',
        name: r.name || '',
        badge: idx === 0 ? 'AI' : '',
      }));
      AccountSuggest.open(inputEl, suggestions, {
        term,
        onSelect: (choice) => this.applyAccountSelection(choice, ri, ci),
        onAddNew: () => this.handleAddNewAccount(),
      });
    } catch (err) {
      console.error('Account lookup failed', err);
    }
  },

  applyAccountSelection(choice, ri, ci) {
    if (!choice || !this.state.rows[ri]) return;
    const row = this.state.rows[ri];
    row.accountId = choice.id ?? null;
    row.accountCode = choice.code || '';
    row.accountName = choice.name || '';
    row.account = [choice.code, choice.name].filter(Boolean).join(' - ');
    this.state.focus = { r: ri, c: ci };
    AccountSuggest.close();
    this.render();
  },

  handleAddNewAccount() {
    AccountSuggest.close();
    const url = '/accounting/chart-of-accounts/create/';
    window.open(url, '_blank');
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
    if (typeof journal.isLocked === 'boolean') this.state.isLocked = journal.isLocked;
    if (journal.editable !== undefined) {
      this.state.isEditable = !!journal.editable;
    } else if (journal.status) {
      const lockedStatuses = ['posted', 'awaiting_approval', 'approved'];
      this.state.isEditable = !lockedStatuses.includes(journal.status);
    }
    this.state.postedAt = journal.postedAt || null;
    this.state.postedBy = journal.postedBy ?? null;
    this.state.postedByName = journal.postedByName || '';
    this.state.isReversal = !!journal.isReversal;
    this.state.reversalOfId = journal.reversalOfId ?? null;
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
      const extras = journal.metadata.headerExtras || {};
      if (extras.dueDate) {
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), dueDate: extras.dueDate };
        this.state.header.dueDate = extras.dueDate;
      }
      if (extras.paymentTermId) {
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), termId: extras.paymentTermId, termCode: extras.paymentTermCode || extras.paymentTerm || this.state.paymentTerms.termCode };
      }
      if (extras.creditDays !== undefined) {
        this.state.header.creditDays = extras.creditDays;
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), netDueDays: extras.creditDays, dueDate: this.state.paymentTerms?.dueDate || this.computeDueDate(this.state.header?.date, extras.creditDays) };
      }
    }
  },

  fetchJournal(id) {
    const template = this.state.detailUrlTemplate || DETAIL_URL_TEMPLATE;
    if (!template || !id) return;
    const url = template.replace(/0\/?$/, `${id}/`);
    fetchJSON(url, {}, { action: `Fetch Journal ${id}` })
      .then(({ status, data, ok }) => {
        if (!ok || status >= 400 || !data?.ok) {
          notify(data?.error || 'Unable to load journal entry.', 'error');
          return;
        }
        this.state.journalId = id;
        this.hydrateFromApi(data.journal);
        this.render();
      })
      .catch((err) => {
        console.error('Failed to fetch journal', err);
        notify('Failed to load journal entry.', 'error');
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
    fetchJSON(url, {}, { action: `Fetch Config ${requestedCode || requestedId || ''}` })
      .then(({ status, data, ok }) => {
        if (!ok || status >= 400 || !data?.ok) {
          console.warn('Config fetch failed', status, data);
          if (data?.error) notify(data.error, 'error');
          this.lastConfigRequest = { code: null, id: null };
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
    this.state.metadata = { ...metadata };
    if (config.udf) {
      if (Array.isArray(config.udf.header)) this.state.udfHeaderDefs = config.udf.header;
      if (Array.isArray(config.udf.line)) this.state.udfLineDefs = config.udf.line;
    }
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
    const { header, udfHeaderDefs } = this.state;
    const controls = [
      Labeled('Date', `<input type="date" class="form-control" value="${escapeHtml(header.date)}" data-hkey="date" title="${escapeHtml(header.date)}">`),
      Labeled('Branch', `<input class="form-control" value="${escapeHtml(header.branch || '')}" data-hkey="branch" title="${escapeHtml(header.branch || '')}">`),
      Labeled('Currency', `<select class="form-select" data-hkey="currency" title="${escapeHtml(header.currency)}">${this.state.supportedCurrencies.map(cur => `<option value="${escapeHtml(cur)}" ${cur === header.currency ? 'selected' : ''}>${escapeHtml(cur)}</option>`).join('')}</select>`),
      Labeled('Exchange Rate', `<input type="number" step="0.0001" class="form-control text-end" value="${escapeHtml(header.exRate)}" data-hkey="exRate" title="${escapeHtml(header.exRate)}">`),
      Labeled('Reference', `<input class="form-control" value="${escapeHtml(header.reference || '')}" data-hkey="reference" placeholder="Reference Number">`),
      Labeled('Description', `<textarea class="form-control" rows="2" data-hkey="description" placeholder="Description">${escapeHtml(header.description || '')}</textarea>`),
      ...udfHeaderDefs.map((f) => Labeled(`${escapeHtml(f.label)}${f.required ? ' *' : ''}`, fieldControl(f, header[f.id] ?? '', 'header'))),
    ].filter(Boolean);
    return `<div class="row g-3">${controls.join('')}</div>`;
  },


  /** Totals engine for journal entries */
  computeTotals() {
    const { rows } = this.state;
    // For journal entries, compute debit/credit totals
    const dr = rows.reduce((s, r) => s + asNum(r.dr), 0);
    const cr = rows.reduce((s, r) => s + asNum(r.cr), 0);
    return { dr, cr, diff: +(dr - cr).toFixed(2) };
  },

  filteredRows() {
    const visibleCols = this.getColumns().filter((c) => c.visible !== false);
    const filters = this.state.columnFilters || {};
    const quick = (this.state.quickSearch || '').toLowerCase();
    return this.state.rows
      .map((row, index) => ({ row, index }))
      .filter(({ row }) => {
        if (quick) {
          const haystack = visibleCols.map((c) => (row[c.id] ?? '')).join(' ').toLowerCase();
          if (!haystack.includes(quick)) return false;
        }
        for (const [colId, value] of Object.entries(filters)) {
          if (!value && value !== 0) continue;
          const term = String(value ?? '').toLowerCase();
          if (!term) continue;
          const cell = row[colId];
          const hay = String(cell ?? '').toLowerCase();
          if (!hay.includes(term)) return false;
        }
        return true;
      });
  },

  visibleRowOrder() {
    if (Array.isArray(this._visibleRowOrder) && this._visibleRowOrder.length) return this._visibleRowOrder;
    return this.state.rows.map((_, idx) => idx);
  },

  persistPresets() {
    const {
      colPrefsByType,
      udfHeaderDefs,
      udfLineDefs,
      collapsed,
      charges,
      numbering,
      density,
      frozenColumns,
      showFilters,
      columnFilters,
    } = this.state;
    const current = loadPresets();
    current.colPrefsByType = colPrefsByType;
    current.udfHeaderDefs = udfHeaderDefs;
    current.udfLineDefs = udfLineDefs;
    current.collapsed = collapsed;
    current.charges = charges;
    current.numbering = numbering;
    current.density = density;
    current.frozenColumns = frozenColumns;
    current.showFilters = showFilters;
    current.columnFilters = columnFilters;
    savePresets(current);
    this.persistRemotePrefs({
      colPrefsByType,
      collapsed,
      numbering,
      density,
      frozenColumns,
      showFilters,
      columnFilters,
    });
  },

  applyPreferences(preferences = {}) {
    if (!preferences || typeof preferences !== 'object') return;
    if (preferences.colPrefsByType) {
      this.state.colPrefsByType = preferences.colPrefsByType;
    }
    if (preferences.collapsed) {
      this.state.collapsed = { ...this.state.collapsed, ...preferences.collapsed };
    }
    if (preferences.numbering) {
      this.state.numbering = { ...this.state.numbering, ...preferences.numbering };
    }
    if (preferences.density) {
      this.state.density = preferences.density;
    }
    if (preferences.frozenColumns !== undefined) {
      this.state.frozenColumns = Number(preferences.frozenColumns) || 0;
    }
    if (preferences.showFilters !== undefined) {
      this.state.showFilters = !!preferences.showFilters;
    }
    if (preferences.columnFilters) {
      this.state.columnFilters = preferences.columnFilters;
    }
  },

  applyPreferencesFromStore(presets = {}) {
    this.applyPreferences(presets);
    if (presets.udfHeaderDefs) this.state.udfHeaderDefs = presets.udfHeaderDefs;
    if (presets.udfLineDefs) this.state.udfLineDefs = presets.udfLineDefs;
    if (presets.charges) this.state.charges = presets.charges;
  },

  persistRemotePrefs(preferences) {
    if (!PREFS_SAVE_ENDPOINT) return;
    if (!this._debouncedSavePrefs) {
      this._debouncedSavePrefs = debounce((prefsPayload) => {
        postJSON(PREFS_SAVE_ENDPOINT, { preferences: prefsPayload }, { action: 'Save UI Preferences' }).catch((err) => {
          console.warn('Failed to save remote preferences', err);
        });
      }, 400);
    }
    this._debouncedSavePrefs(preferences);
  },

  async loadRemotePreferences() {
    if (!PREFS_ENDPOINT) return;
    try {
      const { ok, data } = await fetchJSON(PREFS_ENDPOINT, {}, { action: 'Load UI Preferences' });
      if (ok && data?.preferences) {
        this.applyPreferences(data.preferences);
        this.render();
      }
    } catch (err) {
      console.warn('Unable to load remote preferences', err);
    }
  },

  /** UI */
  render() {
    const el = document.getElementById('app');
    AccountSuggest.close();
    const { voucherType, status, header, udfHeaderDefs, udfLineDefs, collapsed, notes, charges } = this.state;
    const cols = this.getColumns();
    const visibleCols = cols.filter(c => c.visible !== false);
    const visibleRows = this.filteredRows();
    this._visibleRowOrder = visibleRows.map((entry) => entry.index);
    const totals = this.computeTotals();
    const voucherTypes = this.availableVoucherTypes();
    const statusBadge = this.statusBadgeClass();
    const statusLabel = this.statusLabel();
    const normalizedStatus = (status || '').toLowerCase();
    const isWaitingApproval = normalizedStatus === 'awaiting_approval' || normalizedStatus === 'submitted';
    const isSaving = !!this.state.isSaving;
    const readOnly = !this.state.isEditable;
    const densityClass = this.state.density === 'compact' ? ' ve-density-compact' : '';
    const wrapperClasses = `ve-wrapper${readOnly ? ' ve-readonly' : ''}${densityClass}`;
    const canSaveDraft = !isSaving && this.state.isEditable;
    const canSubmit = PERMISSIONS.submit && normalizedStatus === 'draft' && !isSaving && this.state.isEditable;
    const canApprove = PERMISSIONS.approve && isWaitingApproval && !isSaving;
    const canReject = PERMISSIONS.reject && isWaitingApproval && !isSaving;
    const canPost = PERMISSIONS.post && normalizedStatus === 'approved' && !isSaving;
    const attachmentsCount = Array.isArray(this.state.attachments) ? this.state.attachments.length : 0;
    const paymentTermBadge = this.state.paymentTerms?.termCode ? ` (${escapeHtml(this.state.paymentTerms.termCode)})` : '';
    const dueDateBadge = this.state.paymentTerms?.dueDate ? `<span class="badge bg-light text-dark">Due ${escapeHtml(this.state.paymentTerms.dueDate)}</span>` : '';
    const postedBadge = this.state.postedAt
      ? `<span class="ve-pill px-2 py-1 rounded-lg text-xs bg-blue-100 text-blue-700">Posted ${escapeHtml(this.state.postedAt.slice(0, 10))}${this.state.postedByName ? ` · ${escapeHtml(this.state.postedByName)}` : ''}</span>`
      : '';
    const lockBadge = readOnly ? '<span class="ve-pill px-2 py-1 rounded-lg text-xs bg-slate-100 text-slate-600">Read only</span>' : '';
    const reversalBadge = this.state.isReversal ? '<span class="ve-pill px-2 py-1 rounded-lg text-xs bg-purple-100 text-purple-700">Reversal</span>' : '';
    const frozenCount = Math.max(0, Math.min(this.state.frozenColumns || 0, visibleCols.length));
    const frozenOffsets = [];
    if (frozenCount) {
      let offset = 40; // initial index col width
      visibleCols.forEach((c, idx) => {
        if (idx < frozenCount) {
          frozenOffsets[idx] = offset;
          offset += (c.width || 140);
        }
      });
    }

    el.innerHTML = `
      <div class="${wrapperClasses}">
      <div class="card mb-3 ve-sticky-bar">
        <div class="card-body">
          <div class="d-sm-flex align-items-center justify-content-between">
            <div class="d-flex align-items-center flex-wrap gap-2 mb-2 mb-sm-0">
              <h5 class="mb-0">Voucher Entry</h5>
              <span class="badge bg-secondary">${voucherType}</span>
              <span class="voucher-status-badge ${statusBadge}">${statusLabel}</span>
              <span class="badge bg-light text-dark">No: <strong>${this.voucherDisplayNumber()}</strong></span>
              ${postedBadge}
              ${lockBadge}
              ${reversalBadge}
            </div>
            <div class="d-flex flex-wrap gap-2 voucher-actions">
              ${!this.state.metadata?.configId && voucherTypes.length > 1 ? `<div class="btn-group btn-group-sm" role="group">
                ${voucherTypes.map(v => `
                  <button type="button" data-action="setType" data-type="${v}"
                    class="btn ${voucherType === v ? 'btn-primary' : 'btn-outline-primary'}">${v}</button>
                `).join('')}
              </div>` : ''}
              <button data-action="saveDraft" class="btn btn-sm btn-info btn-icon" ${canSaveDraft ? '' : 'disabled'}>
                <i class="mdi mdi-content-save-outline"></i>${isSaving ? 'Working…' : 'Save Draft'}
              </button>
              ${PERMISSIONS.submit ? `<button data-action="submit" class="btn btn-sm btn-primary btn-icon" ${canSubmit ? '' : 'disabled'}><i class="mdi mdi-send"></i>Submit</button>` : ''}
              ${PERMISSIONS.approve ? `<button data-action="approve" class="btn btn-sm btn-success btn-icon" ${canApprove ? '' : 'disabled'}><i class="mdi mdi-check-circle-outline"></i>Approve</button>` : ''}
              ${PERMISSIONS.reject ? `<button data-action="reject" class="btn btn-sm btn-danger btn-icon" ${canReject ? '' : 'disabled'}><i class="mdi mdi-close-circle-outline"></i>Reject</button>` : ''}
              ${PERMISSIONS.post ? `<button data-action="post" class="btn btn-sm btn-success btn-icon" ${canPost ? '' : 'disabled'}><i class="mdi mdi-publish"></i>Post</button>` : ''}
              <button data-action="openPaymentTerms" class="btn btn-sm btn-outline-secondary btn-icon">
                <i class="mdi mdi-calendar-range"></i>Payment Terms${paymentTermBadge}
              </button>
              ${dueDateBadge}
              <button data-action="openAttachments" class="btn btn-sm btn-secondary btn-icon">
                <i class="mdi mdi-paperclip"></i>Attachments${attachmentsCount ? ` (${attachmentsCount})` : ''}
              </button>
              <button data-action="openKeyboardHelp" class="btn btn-sm btn-outline-secondary" title="Keyboard Shortcuts (Ctrl+/)">
                <i class="mdi mdi-keyboard-outline"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="col-lg-8">
          <div class="card mb-3">
            <div class="card-header">
              <div class="d-flex justify-content-between align-items-center">
                <h5 class="card-title mb-0">Header</h5>
                <button data-action="toggleSection" data-section="header" class="btn btn-sm btn-outline-secondary" title="Hide/Show header">
                  <i class="mdi mdi-${collapsed.header ? 'eye' : 'eye-off'}"></i>
                  ${collapsed.header ? 'Show' : 'Hide'}
                </button>
              </div>
            </div>
            <div class="card-body">
              ${collapsed.header ? headerSummary(header, voucherType) : this.renderDefaultHeaderForm()}
            </div>
          </div>
        </div>

        <div class="col-lg-4">
          <div class="card mb-3">
            <div class="card-header">
              <div class="d-flex justify-content-between align-items-center">
                <h5 class="card-title mb-0">Actions</h5>
                <button data-action="toggleSection" data-section="actions" class="btn btn-sm btn-outline-secondary" title="Hide/Show actions">
                  <i class="mdi mdi-${collapsed.actions ? 'eye' : 'eye-off'}"></i>
                  ${collapsed.actions ? 'Show' : 'Hide'}
                </button>
              </div>
            </div>
            <div class="card-body">
              ${collapsed.actions ? actionsSummary(this.state.rows, cols) : `
              <div class="d-flex flex-wrap gap-2">
                <button data-action="addRow" class="btn btn-sm btn-primary btn-icon"><i class="mdi mdi-plus"></i>Add Row</button>
                <button data-action="add10" class="btn btn-sm btn-outline-primary">+10 Rows</button>
                <button data-action="clearRows" class="btn btn-sm btn-outline-danger">Clear Rows</button>
                <button data-action="openCols" class="btn btn-sm btn-outline-secondary">Columns</button>
                <button data-action="importCsv" class="btn btn-sm btn-outline-info"><i class="mdi mdi-file-import"></i>Import CSV</button>
                <input id="csvFile" type="file" accept=".csv,text/csv" class="d-none" />
                <button data-action="exportCsv" class="btn btn-sm btn-outline-info"><i class="mdi mdi-file-export"></i>Export CSV</button>
                <button data-action="sampleXlsx" class="btn btn-sm btn-outline-success"><i class="mdi mdi-file-excel-outline"></i>Sample Excel</button>
                <button data-action="exportXlsx" class="btn btn-sm btn-outline-success"><i class="mdi mdi-file-excel"></i>Export Excel</button>
              </div>
              <p class="text-muted small mt-2 mb-0">Tip: paste cells copied from Excel directly into the grid. Use arrow keys / Tab / Enter.</p>
              `}
            </div>
          </div>
        </div>
      </div>

      <div class="card mb-3">
        <div class="card-header">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
            <div class="d-flex align-items-center gap-2">
              <h5 class="card-title mb-0">Journal Lines</h5>
              <span class="badge bg-light text-dark">${visibleRows.length}/${this.state.rows.length} shown</span>
            </div>
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <div class="input-group input-group-sm" style="min-width:220px">
                <span class="input-group-text bg-light border-end-0"><i class="mdi mdi-magnify"></i></span>
                <input type="search" class="form-control border-start-0" placeholder="Quick search" value="${escapeHtml(this.state.quickSearch)}" data-action="setQuickSearch">
              </div>
              <button data-action="toggleFilters" class="btn btn-sm ${this.state.showFilters ? 'btn-primary' : 'btn-outline-secondary'}">
                <i class="mdi mdi-filter-menu"></i>${this.state.showFilters ? 'Filters On' : 'Filters'}
              </button>
              <button data-action="toggleDensity" class="btn btn-sm btn-outline-secondary">
                <i class="mdi mdi-format-line-spacing"></i>${this.state.density === 'compact' ? 'Compact' : 'Comfort'}
              </button>
              <div class="btn-group btn-group-sm" role="group">
                <button data-action="setFrozen" data-count="0" class="btn ${frozenCount ? 'btn-outline-secondary' : 'btn-secondary'}" title="Unfreeze columns">Unfreeze</button>
                <button data-action="setFrozen" data-count="2" class="btn ${frozenCount === 2 ? 'btn-secondary' : 'btn-outline-secondary'}" title="Freeze first 2 columns">Freeze 2</button>
              </div>
              <button data-action="openUdf" data-scope="Line" class="btn btn-sm btn-outline-secondary btn-icon">
                <i class="mdi mdi-plus"></i>UDF (Line)
              </button>
              ${udfLineDefs.map(f => `<span class="badge bg-secondary" style="cursor:pointer" data-action="removeUdf" data-scope="Line" data-udfid="${f.id}">L:${escapeHtml(f.label)} &times;</span>`).join('')}
            </div>
          </div>
        </div>
        <div class="card-body p-0">
          <div class="table-responsive voucher-grid-wrapper" style="max-height: 500px">
            <table class="table table-bordered table-hover voucher-grid mb-0">
              <colgroup>
                <col style="width:40px">
                ${visibleCols.map(c => `<col data-colid="${c.id}" style="width:${c.width || 140}px">`).join('')}
                <col style="width:48px">
              </colgroup>
              <thead class="table-light">
                <tr>
                  <th class="text-center">#</th>
                  ${visibleCols.map((c, idx) => `
                    <th class="th-resizable${frozenCount && frozenOffsets[idx] !== undefined && idx < frozenCount ? ' ve-frozen' : ''}" data-colid="${c.id}" ${frozenCount && frozenOffsets[idx] !== undefined && idx < frozenCount ? `style="left:${frozenOffsets[idx]}px"` : ''}>
                      <div class="position-relative">${escapeHtml(c.label)}<span class="resize-handle" data-colid="${c.id}"></span></div>
                    </th>`).join('')}
                  <th></th>
                </tr>
                ${this.state.showFilters ? `
                <tr class="ve-filter-row">
                  <th></th>
                  ${visibleCols.map((c, idx) => `
                    <th class="${idx < frozenCount ? 've-frozen' : ''}" ${idx < frozenCount ? `style="left:${frozenOffsets[idx]}px"` : ''}>
                      <input class="form-control form-control-sm" data-action="setColumnFilter" data-colid="${c.id}" value="${escapeHtml(this.state.columnFilters?.[c.id] || '')}" placeholder="Filter ${escapeHtml(c.label)}">
                    </th>`).join('')}
                  <th></th>
                </tr>` : ''}
              </thead>
              <tbody>
                ${visibleRows.map(({ row, index: ri }, displayIdx) => `
                  <tr class="ve-row" draggable="true" data-ri="${ri}">
                    <td class="text-center text-muted small">
                      <span class="ve-drag-handle" title="Drag to reorder" data-ri="${ri}"><i class="mdi mdi-drag"></i></span>
                      <span>${displayIdx + 1}</span>
                    </td>
                    ${visibleCols.map((col, vi) => `
                      <td title="${cellTitle(row[col.id], col)}" class="${vi < frozenCount ? 've-frozen' : ''}" ${vi < frozenCount ? `style="left:${frozenOffsets[vi]}px"` : ''}>
                        ${col.type === 'calc'
        ? `<div class="text-end fw-medium" title="${moneyFmt.format(row[col.id] || 0)}">${moneyFmt.format(row[col.id] || 0)}</div>`
        : gridCell(row[col.id], col, ri, vi)}
                      </td>`).join('')}
                    <td class="text-center">
                      <button data-action="delRow" data-ri="${ri}" class="btn btn-sm btn-link text-danger p-0">
                        <i class="mdi mdi-delete-outline"></i>
                      </button>
                    </td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="col-lg-8">
          <div class="card mb-3">
            <div class="card-header">
              <div class="d-flex justify-content-between align-items-center">
                <h5 class="card-title mb-0">Notes & Audit</h5>
                <button data-action="toggleSection" data-section="notes" class="btn btn-sm btn-outline-secondary">
                  <i class="mdi mdi-${collapsed.notes ? 'eye' : 'eye-off'}"></i>
                  ${collapsed.notes ? 'Show' : 'Hide'}
                </button>
              </div>
            </div>
            <div class="card-body">
              ${collapsed.notes ? notesSummary(notes, status) : `
              <textarea class="form-control mb-3" rows="3" placeholder="Internal note / customer note / delivery note ..." data-action="bindNotes">${escapeHtml(notes)}</textarea>
              <div class="row g-3 text-muted small">
                <div class="col-md-3">Created: <strong>you</strong></div>
                <div class="col-md-3">Created On: <strong>${new Date().toLocaleString()} </strong></div>
                <div class="col-md-3">Last Edited: <strong>${new Date().toLocaleTimeString()} </strong></div>
                <div class="col-md-3">Status: <strong>${status} </strong></div>
              </div>
              `}
            </div>
          </div>
        </div>

        <div class="col-lg-4">
          <div class="card mb-3 ve-sticky-footer">
            <div class="card-header">
              <div class="d-flex justify-content-between align-items-center">
                <h5 class="card-title mb-0">Totals</h5>
                <button data-action="toggleSection" data-section="totals" class="btn btn-sm btn-outline-secondary">
                  <i class="mdi mdi-${collapsed.totals ? 'eye' : 'eye-off'}"></i>
                  ${collapsed.totals ? 'Show' : 'Hide'}
                </button>
              </div>
            </div>
            <div class="card-body">
              ${collapsed.totals ? totalsSummary(this.state.voucherType, totals) : `
              <div class="voucher-totals">
                ${voucherType === 'Journal' ? `
                  <div class="voucher-totals-row">
                    <span class="voucher-totals-label">Total Dr</span>
                    <span class="voucher-totals-value">${moneyFmt.format(totals.dr)}</span>
                  </div>
                  <div class="voucher-totals-row">
                    <span class="voucher-totals-label">Total Cr</span>
                    <span class="voucher-totals-value">${moneyFmt.format(totals.cr)}</span>
                  </div>
                  <div class="voucher-totals-row">
                    <span class="voucher-totals-label">Difference</span>
                    <span class="voucher-totals-value ${Math.abs(totals.diff) < 0.001 ? 'text-success' : 'text-danger'}">${moneyFmt.format(totals.diff)}</span>
                  </div>
                  ${Math.abs(totals.diff) >= 0.001 ? `
                    <div class="voucher-totals-mismatch">
                      <i class="mdi mdi-alert-circle-outline"></i>
                      <span>Debit and Credit must balance!</span>
                    </div>
                  ` : ''}
                ` : ''}
              </div>
              `}
            </div>
          </div>
        </div>
      </div>

      <div class="text-center text-muted small mt-3">
        <p class="mb-0">Data syncs with server on save. Layout tweaks (columns, density, collapses) are saved to your profile.</p>
      </div>

      </div>
      ${this.state.showUdfModal ? udfModalHtml(this.state) : ''}
      ${this.state.showColManager ? colManagerHtml(this.getColumns(), this.state.colManagerDraft) : ''}
      ${this.state.showCharges ? chargesModalHtml(charges) : ''}
      ${this.state.showAttachmentsModal ? attachmentsModalHtml(this.state) : ''}
      ${this.state.showPaymentTermsModal ? paymentTermsModalHtml(this.state) : ''}
      ${this.state.showKeyboardHelp ? keyboardHelpModalHtml() : ''}
    `;

    setTimeout(() => { this.focusCurrent(); this.bindResizeHandles(); this.bindCsv(); this.bindRowDrag(); }, 0);
    const grid = document.querySelector('.voucher-grid-wrapper');
    if (grid) {
      grid.addEventListener('paste', (e) => this.handlePaste(e));
    }
    el.onclick = (ev) => this.handleClick(ev);
    el.onchange = (ev) => this.handleChange(ev);
    el.onkeydown = (ev) => this.handleKeydown(ev);
    el.onfocusin = (ev) => this.handleFocusIn(ev);
    el.oninput = (ev) => {
      const target = ev.target;
      if (target && target.getAttribute('data-action') === 'setQuickSearch') {
        this.state.quickSearch = target.value;
        this.render();
        return;
      }
      if (target && target.getAttribute('data-action') === 'setColumnFilter') {
        const colId = target.getAttribute('data-colid');
        this.state.columnFilters = { ...(this.state.columnFilters || {}), [colId]: target.value };
        this.persistPresets();
        this.render();
        return;
      }
      if (target && target.getAttribute('data-action') === 'bindNotes') {
        this.state.notes = target.value;
        this.persistPresets();
        return;
      }
      if (target && target.classList.contains('cell-input') && target.getAttribute('data-colid') === 'account') {
        const ri = +target.getAttribute('data-ri');
        const ci = +target.getAttribute('data-ci');
        this.queueAccountSuggestions(target, ri, ci);
      }
      if (target && target.classList.contains('cell-input') && target.getAttribute('data-colid') === 'costCenter') {
        const ri = +target.getAttribute('data-ri');
        const ci = +target.getAttribute('data-ci');
        this.queueCostCenterSuggestions(target, ri, ci);
      }
    };
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

  /** Row drag/drop */
  bindRowDrag() {
    const rows = document.querySelectorAll('.ve-row');
    rows.forEach((row) => {
      row.ondragstart = (e) => {
        if (!e.target.closest('.ve-drag-handle')) {
          e.preventDefault();
          return;
        }
        this._dragIndex = Number(row.getAttribute('data-ri'));
        row.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      };
      row.ondragend = () => {
        row.classList.remove('dragging');
        this._dragIndex = null;
        document.querySelectorAll('.ve-row.drag-over').forEach((r) => r.classList.remove('drag-over'));
      };
      row.ondragover = (e) => {
        e.preventDefault();
        row.classList.add('drag-over');
      };
      row.ondragleave = () => row.classList.remove('drag-over');
      row.ondrop = (e) => {
        e.preventDefault();
        row.classList.remove('drag-over');
        const targetIdx = Number(row.getAttribute('data-ri'));
        if (Number.isInteger(this._dragIndex)) {
          this.reorderRows(this._dragIndex, targetIdx);
        }
      };
    });
  },

  reorderRows(fromIdx, toIdx) {
    if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) return;
    const rows = [...this.state.rows];
    if (!rows[fromIdx] || !rows[toIdx]) return;
    const [moved] = rows.splice(fromIdx, 1);
    rows.splice(toIdx, 0, moved);
    this.state.rows = rows;
    this.state.focus = { r: toIdx, c: 0 };
    this.persistPresets();
    this.render();
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
  async handleClick(e) {
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
        const okDate = await this._preflightDate();
        if (!okDate) return;
        this.state.isSaving = true;
        this.render();
        postJSON(Endpoints.save, payload, { action: 'Save Draft' })
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'draft';
              notify(r.data?.message || 'Draft saved.', 'success');
            } else {
              console.warn('Server rejected draft save:', r.status, r.text);
              this.handleServerErrors(r);
            }
          })
          .catch(err => {
            console.error(err);
            notify('Server unreachable. Draft saved locally (console shows payload).', 'warning');
          })
          .finally(() => { this.state.isSaving = false; this.render(); });
      } else {
        console.log('Draft payload', payload);
        this.state.status = 'draft';
        notify('Draft saved locally (console shows payload).', 'success');
        this.render();
      }
      return;
    }
    if (action === 'submit') {
      const errs = this.validate(); 
      if (errs.length) return alert('Fix issues:\n- ' + errs.join('\n- '));
      const payload = this.buildPayload();
      if (Endpoints.submit) {
        const okDate = await this._preflightDate();
        if (!okDate) return;
        this.state.isSaving = true;
        this.render();
        postJSON(Endpoints.submit, payload, { action: 'Submit Journal' })
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'awaiting_approval';
              notify(r.data?.message || 'Submitted for approval.', 'success');
            } else {
              console.warn('Server rejected submit:', r.status, r.text);
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Submit not sent.', 'error'); })
          .finally(() => { this.state.isSaving = false; this.render(); });
      } else {
        this.state.status = 'awaiting_approval';
        this.render();
        notify('Submitted locally (no backend endpoint configured).', 'success');
      }
      return;
    }
    if (action === 'approve') {
      if (!(this.state.status && ['awaiting_approval', 'submitted'].includes(this.state.status.toLowerCase()))) return alert('Submit first');
      const payload = this.buildPayload();
      if (Endpoints.approve) {
        this.state.isSaving = true;
        this.render();
        postJSON(Endpoints.approve, payload, { action: 'Approve Journal' })
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
          .catch(err => { console.error(err); notify('Server unreachable. Approve not sent.', 'error'); })
          .finally(() => { this.state.isSaving = false; this.render(); });
      } else {
        this.state.status = 'approved';
        this.render();
  notify('Approved locally (no backend endpoint configured).', 'success');
      }
      return;
    }
    if (action === 'reject') {
      const payload = this.buildPayload();
      if (Endpoints.reject) {
        this.state.isSaving = true;
        this.render();
        postJSON(Endpoints.reject, payload, { action: 'Reject Journal' })
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'rejected';
              notify(r.data?.message || 'Journal rejected.');
            } else {
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Reject not sent.', 'error'); })
          .finally(() => { this.state.isSaving = false; this.render(); });
      } else {
        this.state.status = 'rejected';
        this.render();
  notify('Rejected locally (no backend endpoint configured).', 'success');
      }
      return;
    }
    if (action === 'post') {
      const payload = this.buildPayload();
      if (Endpoints.post) {
        this.state.isSaving = true;
        this.render();
        postJSON(Endpoints.post, payload, { action: 'Post Journal' })
          .then(r => {
            if (r.ok) {
              if (r.data?.journal) this.hydrateFromApi(r.data.journal);
              this.state.status = (r.data?.journal?.status) || 'posted';
              notify(r.data?.message || 'Journal posted.');
            } else {
              this.handleServerErrors(r);
            }
          })
          .catch(err => { console.error(err); notify('Server unreachable. Post not sent.', 'error'); })
          .finally(() => { this.state.isSaving = false; this.render(); });
      } else {
        this.state.status = 'posted';
        this.render();
  notify('Posted locally (no backend endpoint configured).', 'success');
      }
      return;
    }

    if (action === 'openAttachments') { this.state.showAttachmentsModal = true; this.render(); return; }
    if (action === 'closeAttachments') { this.state.showAttachmentsModal = false; this.render(); return; }
    if (action === 'removeAttachment') {
      const attId = t.getAttribute('data-id');
      this.deleteAttachment(attId);
      return;
    }
    if (action === 'openPaymentTerms') {
      if (!this.state.paymentTerms?.netDueDays && this.state.header?.creditDays !== undefined) {
        const days = asNum(this.state.header.creditDays, 0);
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), netDueDays: days, dueDate: this.computeDueDate(this.state.header?.date, days) };
      }
      this.state.showPaymentTermsModal = true;
      this.fetchPaymentTerms();
      this.render();
      return;
    }
    if (action === 'closePaymentTerms') { this.state.showPaymentTermsModal = false; this.render(); return; }
    if (action === 'applyPaymentTerms') { this.applyPaymentTerms(); return; }

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
    
    if (action === 'closeKeyboardHelp') { this.state.showKeyboardHelp = false; this.render(); }
    if (action === 'openKeyboardHelp') { this.state.showKeyboardHelp = true; this.render(); }

    if (action === 'openCols') { const cols = this.getColumns(); this.state.colManagerDraft = cols.map((c, i) => ({ ...c, order: i })); this.state.showColManager = true; this.render(); }
    if (action === 'cmCancel') { this.state.showColManager = false; this.render(); }
    if (action === 'cmToggle') { const id = t.getAttribute('data-col'); this.state.colManagerDraft = this.state.colManagerDraft.map(x => x.id === id ? { ...x, visible: !(x.visible !== false) } : x); this.render(); }
    if (action === 'cmMove') { const id = t.getAttribute('data-col'); const dir = +t.getAttribute('data-dir'); const arr = this.state.colManagerDraft; const idx = arr.findIndex(x => x.id === id); const j = clamp(idx + dir, 0, arr.length - 1); const [x] = arr.splice(idx, 1); arr.splice(j, 0, x); this.render(); }
    if (action === 'cmApply') { const vt = this.state.voucherType; this.state.colPrefsByType[vt] = this.state.colManagerDraft.map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width, order })); this.state.showColManager = false; this.persistPresets(); this.render(); }
    if (action === 'saveCols') { const vt = this.state.voucherType; const cols = this.getColumns(); this.state.colPrefsByType[vt] = cols.map(({ id, visible, width, order }) => ({ id, visible: visible !== false, width, order })); this.persistPresets(); alert('Column prefs saved.'); }
    if (action === 'resetCols') { const vt = this.state.voucherType; delete this.state.colPrefsByType[vt]; this.persistPresets(); this.render(); }
    if (action === 'toggleFilters') { this.state.showFilters = !this.state.showFilters; this.persistPresets(); this.render(); }
    if (action === 'toggleDensity') { this.state.density = this.state.density === 'compact' ? 'normal' : 'compact'; this.persistPresets(); this.render(); }
    if (action === 'setFrozen') { const count = Number(t.getAttribute('data-count')) || 0; this.state.frozenColumns = count; this.persistPresets(); this.render(); }

    if (action === 'importCsv') { const el = document.getElementById('csvFile'); if (el) el.click(); }
    if (action === 'exportCsv') { this.exportCsv(); }
    if (action === 'sampleXlsx') { this.sampleXlsx(); }
    if (action === 'exportXlsx') { this.exportXlsx(); }

    if (action === 'toggleCharges') { this.state.showCharges = true; this.render(); }
    if (action === 'chgClose') { this.state.showCharges = false; this.render(); }
    if (action === 'chgAdd') { this.state.charges.push({ id: uid(), label: 'New Charge', mode: 'amount', value: 0, sign: 1 }); this.persistPresets(); this.render(); }
    if (action === 'chgDel') { const id = t.getAttribute('data-id'); this.state.charges = this.state.charges.filter(c => c.id !== id); this.persistPresets(); this.render(); }

    if (action === 'runTests') { this.selfTests(); alert('Self-tests executed. Check console for assertions.'); }
  },

  handleChange(e) {
    const t = e.target;
    const actionAttr = t.getAttribute('data-action');
    if (actionAttr === 'attachFiles') {
      const files = t.files || [];
      this.uploadAttachments(files);
      t.value = '';
      return;
    }
    if (actionAttr === 'setPaymentTerm') {
      const termId = t.value;
      const selected = (this.state.paymentTermOptions || []).find((opt) => String(opt.id) === String(termId));
      this.updatePaymentTerm(selected || { id: null, code: '', netDueDays: this.state.paymentTerms?.netDueDays || 0 });
      return;
    }
    if (actionAttr === 'setPaymentCreditDays') {
      const days = asNum(t.value, 0);
      this.state.paymentTerms = { ...(this.state.paymentTerms || {}), netDueDays: days, dueDate: this.computeDueDate(this.state.header?.date, days) };
      this.render();
      return;
    }
    if (actionAttr === 'setPaymentDueDate') {
      this.state.paymentTerms = { ...(this.state.paymentTerms || {}), dueDate: t.value };
      this.render();
      return;
    }
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
      if (hkey === 'creditDays') {
        const daysVal = asNum(t.value, 0);
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), netDueDays: daysVal, dueDate: this.computeDueDate(this.state.header?.date, daysVal) };
      }
      if (hkey === 'date' && this.state.paymentTerms && this.state.paymentTerms.netDueDays !== undefined) {
        const daysVal = this.state.paymentTerms.netDueDays || 0;
        this.state.paymentTerms = { ...(this.state.paymentTerms || {}), dueDate: this.computeDueDate(t.value, daysVal) };
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
          AccountSuggest.close();
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
    // Escape key - close modals
    if (e.key === 'Escape') {
      if (this.state.showKeyboardHelp) {
        e.preventDefault();
        this.state.showKeyboardHelp = false;
        this.render();
        return;
      }
      if (this.state.showUdfModal) {
        e.preventDefault();
        this.state.showUdfModal = false;
        this.render();
        return;
      }
      if (this.state.showCharges) {
        e.preventDefault();
        this.state.showCharges = false;
        this.render();
        return;
      }
      if (this.state.showCoaModal) {
        e.preventDefault();
        this.state.showCoaModal = false;
        this.render();
        return;
      }
      if (this.state.showAttachmentsModal) {
        e.preventDefault();
        this.state.showAttachmentsModal = false;
        this.render();
        return;
      }
      if (this.state.showPaymentTermsModal) {
        e.preventDefault();
        this.state.showPaymentTermsModal = false;
        this.render();
        return;
      }
    }

    const target = e.target;
    if (AccountSuggest.isOpenFor(target)) {
      if (e.key === 'ArrowDown') { e.preventDefault(); AccountSuggest.move(1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); AccountSuggest.move(-1); return; }
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft' || e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        AccountSuggest.selectCurrent();
        return;
      }
      if (e.key === 'Escape') {
        AccountSuggest.close();
        return;
      }
    }

    // Global keyboard shortcuts - directly trigger actions (don't use button.click())
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
      const normalizedStatus = (this.state.status || '').toLowerCase();
      switch(e.key.toLowerCase()) {
        case 's':
          e.preventDefault();
          if (this.state.isEditable && !this.state.isSaving) {
            // Trigger saveDraft action directly
            const payload = this.buildPayload();
            this.persistPresets();
            if (Endpoints.save) {
              this.state.isSaving = true;
              this.render();
              postJSON(Endpoints.save, payload, { action: 'Save Draft (Hotkey)' })
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
                .finally(() => { this.state.isSaving = false; this.render(); });
            } else {
              console.log('Draft payload', payload);
              this.state.status = 'draft';
              notify('Draft saved locally (console shows payload).');
              this.render();
            }
          }
          return;
        case 'enter':
          e.preventDefault();
          if (PERMISSIONS.submit && normalizedStatus === 'draft' && !this.state.isSaving && this.state.isEditable) {
            // Trigger submit action directly
            const errs = this.validate(); 
            if (errs.length) {
              alert('Fix issues:\n- ' + errs.join('\n- '));
              return;
            }
            const payload = this.buildPayload();
            if (Endpoints.submit) {
              this.state.isSaving = true;
              this.render();
              postJSON(Endpoints.submit, payload, { action: 'Submit Journal (Hotkey)' })
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
                .finally(() => { this.state.isSaving = false; this.render(); });
            } else {
              this.state.status = 'awaiting_approval';
              this.render();
              notify('Submitted locally (no backend endpoint configured).');
            }
          }
          return;
        case 'a':
          e.preventDefault();
          const isWaitingApproval = normalizedStatus === 'awaiting_approval' || normalizedStatus === 'submitted';
          if (PERMISSIONS.approve && isWaitingApproval && !this.state.isSaving) {
            // Trigger approve action directly
            const payload = this.buildPayload();
            if (Endpoints.approve) {
              this.state.isSaving = true;
              this.render();
              postJSON(Endpoints.approve, payload, { action: 'Approve Journal (Hotkey)' })
                .then(r => {
                  if (r.ok) {
                    if (r.data?.journal) this.hydrateFromApi(r.data.journal);
                    this.state.status = (r.data?.journal?.status) || 'approved';
                    notify(r.data?.message || 'Journal approved.');
                  } else {
                    console.warn('Server rejected approval:', r.status, r.text);
                    this.handleServerErrors(r);
                  }
                })
                .catch(err => { console.error(err); notify('Server unreachable. Approval not sent.'); })
                .finally(() => { this.state.isSaving = false; this.render(); });
            } else {
              this.state.status = 'approved';
              this.render();
              notify('Approved locally (no backend endpoint configured).');
            }
          }
          return;
        case 'p':
          e.preventDefault();
          if (PERMISSIONS.post && normalizedStatus === 'approved' && !this.state.isSaving) {
            // Trigger post action directly
            const payload = this.buildPayload();
            if (Endpoints.post) {
                this.state.isSaving = true;
                this.render();
              postJSON(Endpoints.post, payload, { action: 'Post Journal (Hotkey)' })
                .then(r => {
                  if (r.ok) {
                    if (r.data?.journal) this.hydrateFromApi(r.data.journal);
                    this.state.status = (r.data?.journal?.status) || 'posted';
                    this.state.isEditable = false;
                    notify(r.data?.message || 'Journal posted to ledger.');
                  } else {
                    console.warn('Server rejected post:', r.status, r.text);
                    this.handleServerErrors(r);
                  }
                })
                .catch(err => { console.error(err); notify('Server unreachable. Post not sent.'); })
                  .finally(() => { this.state.isSaving = false; this.render(); });
            } else {
              this.state.status = 'posted';
              this.state.isEditable = false;
              this.render();
              notify('Posted locally (no backend endpoint configured).');
            }
          }
          return;
        case '/':
          e.preventDefault();
          this.state.showKeyboardHelp = !this.state.showKeyboardHelp;
          this.render();
          return;
      }
    }
    
    // Grid navigation shortcuts
    const t = e.target;
    if (!t.classList.contains('cell-input')) return;
    const ri = +t.getAttribute('data-ri');
    const ci = +t.getAttribute('data-ci');
    const editableCols = this.getColumns().filter(c => c.visible !== false && c.type !== 'calc');
    const visibleOrder = this.visibleRowOrder();
    const pos = visibleOrder.indexOf(ri);
    const currentPos = pos >= 0 ? pos : 0;
    const maxR = visibleOrder.length - 1; const maxC = editableCols.length - 1;
    const rowAt = (idx) => visibleOrder[clamp(idx, 0, maxR)] ?? ri;
    if (e.key === 'ArrowDown') { e.preventDefault(); this.state.focus = { r: rowAt(currentPos + 1), c: ci }; this.focusCurrent(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); this.state.focus = { r: rowAt(currentPos - 1), c: ci }; this.focusCurrent(); }
    if (e.key === 'ArrowRight' || (e.key === 'Tab' && !e.shiftKey)) { e.preventDefault(); this.state.focus = { r: ri, c: clamp(ci + 1, 0, maxC) }; this.focusCurrent(); }
    if (e.key === 'ArrowLeft' || (e.key === 'Tab' && e.shiftKey)) { e.preventDefault(); this.state.focus = { r: ri, c: clamp(ci - 1, 0, maxC) }; this.focusCurrent(); }
    if (e.key === 'Enter') { e.preventDefault(); this.state.rows.splice(ri + 1, 0, this.blankRow()); this.state.focus = { r: ri + 1, c: 0 }; this.render(); }
    if (e.key === 'Delete' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.state.rows.splice(ri, 1); this.state.focus = { r: clamp(rowAt(currentPos), 0, Math.max(0, this.state.rows.length - 1)), c: 0 }; this.render(); }
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
    if (header.dueDate) headerPayload.dueDate = header.dueDate;
    if (header.paymentTermId) headerPayload.paymentTermId = header.paymentTermId;
    if (header.paymentTermCode) headerPayload.paymentTermCode = header.paymentTermCode;
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
  const helpBlock = help ? `<small class="form-text text-muted">${escapeHtml(help)}</small>` : '';
  return `<div class="col-md-6 col-lg-4 mb-3"><label class="form-label">${lbl}</label>${inner}${helpBlock}</div>`;
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

function attachmentsModalHtml(state) {
  const attachments = Array.isArray(state.attachments) ? state.attachments : [];
  return `
  <div class="ve-modal-backdrop" data-action="closeAttachments">
    <div class="ve-modal" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold mb-0">Attachments</h3>
        <button class="text-slate-500 hover:text-black" data-action="closeAttachments">&times;</button>
      </div>
      <div class="mb-3">
        <label class="btn btn-sm btn-outline-secondary mb-2">
          <i class="mdi mdi-upload"></i> Upload files
          <input type="file" class="d-none" data-action="attachFiles" multiple>
        </label>
        <p class="text-muted small mb-0">Files are uploaded to this journal. A draft will be auto-saved if needed.</p>
      </div>
      <div class="border rounded p-2 bg-light-subtle max-h-[45vh] overflow-auto">
        ${attachments.length ? attachments.map(att => `
          <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
            <div>
              <div class="fw-semibold">${escapeHtml(att.name || 'Attachment')}</div>
              <div class="text-muted small">${att.uploadedAt ? `Uploaded ${escapeHtml(att.uploadedAt.slice(0, 10))}` : ''}</div>
            </div>
            <button data-action="removeAttachment" data-id="${att.id}" class="btn btn-link text-danger btn-sm">Remove</button>
          </div>
        `).join('') : '<div class="text-muted small">No attachments yet.</div>'}
      </div>
      <div class="d-flex justify-content-end gap-2 mt-3">
        <button data-action="closeAttachments" class="btn btn-secondary">Close</button>
      </div>
    </div>
  </div>`;
}

function paymentTermsModalHtml(state) {
  const pt = state.paymentTerms || {};
  const options = Array.isArray(state.paymentTermOptions) ? state.paymentTermOptions : [];
  const optionHtml = ['<option value="">Select a term</option>', ...options.map(opt => `<option value="${opt.id}" ${String(pt.termId) === String(opt.id) ? 'selected' : ''}>${escapeHtml(opt.code || opt.name || '')}</option>`)].join('');
  return `
  <div class="ve-modal-backdrop" data-action="closePaymentTerms">
    <div class="ve-modal ve-modal-lg" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold mb-0">Payment Terms</h3>
        <button class="text-slate-500 hover:text-black" data-action="closePaymentTerms">&times;</button>
      </div>
      <div class="row g-3">
        ${Labeled('Term', `<select class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-action="setPaymentTerm">${optionHtml}</select>`)}
        ${Labeled('Credit Days', `<input type="number" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-action="setPaymentCreditDays" value="${pt.netDueDays ?? ''}">`)}
        ${Labeled('Due Date', `<input type="date" class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" data-action="setPaymentDueDate" value="${escapeHtml(pt.dueDate || '')}">`)}
        ${Labeled('Discount', `<input class="h-10 px-3 py-2 rounded-xl border border-slate-300 bg-white" disabled value="${pt.discountPercent ? `${pt.discountPercent}%${pt.discountDueDate ? ` until ${pt.discountDueDate}` : ''}` : 'N/A'}">`)}
      </div>
      <div class="d-flex justify-content-end gap-2 mt-4">
        <button data-action="closePaymentTerms" class="btn btn-outline-secondary">Cancel</button>
        <button data-action="applyPaymentTerms" class="btn btn-primary">Apply</button>
      </div>
    </div>
  </div>`;
}


function keyboardHelpModalHtml() {
  const key = (label) => `<span class="ve-key">${label}</span>`;
  const row = (combo, desc) => `<div class="d-flex align-items-center justify-content-between py-1"><div class="d-flex align-items-center gap-2 flex-wrap">${combo}</div><div>${desc}</div></div>`;
  return `
  <div class="ve-modal-backdrop" data-action="closeKeyboardHelp">
    <div class="ve-modal ve-modal-lg" onclick="event.stopPropagation()">
      <div class="d-flex align-items-start justify-content-between mb-3">
        <h5 class="mb-0"><i class="mdi mdi-keyboard-outline me-2"></i>Keyboard Shortcuts</h5>
        <button type="button" class="btn-close" data-action="closeKeyboardHelp"></button>
      </div>
      <div class="row g-4">
        <div class="col-md-6">
          <h6 class="text-primary fw-bold mb-2"><i class="mdi mdi-cog-outline me-1"></i>Global Actions</h6>
          ${row(`${key('Ctrl')} + ${key('S')}`, 'Save Draft')}
          ${row(`${key('Ctrl')} + ${key('Enter')}`, 'Submit Voucher')}
          ${row(`${key('Ctrl')} + ${key('A')}`, 'Approve Voucher')}
          ${row(`${key('Ctrl')} + ${key('P')}`, 'Post Voucher')}
          ${row(key('Esc'), 'Close Modals')}
          ${row(`${key('Ctrl')} + ${key('/')}`, 'Show This Help')}
        </div>
        <div class="col-md-6">
          <h6 class="text-success fw-bold mb-2"><i class="mdi mdi-table-edit me-1"></i>Grid Navigation</h6>
          ${row(`${key('↑')} ${key('↓')}`, 'Navigate Rows')}
          ${row(`${key('←')} ${key('→')}`, 'Navigate Columns')}
          ${row(key('Tab'), 'Next Cell')}
          ${row(`${key('Shift')} + ${key('Tab')}`, 'Previous Cell')}
          ${row(key('Enter'), 'Insert Row Below')}
          ${row(`${key('Ctrl')} + ${key('Del')}`, 'Delete Current Row')}
        </div>
      </div>
      <div class="alert alert-info d-flex align-items-center mt-3 mb-0" role="alert">
        <i class="mdi mdi-apple me-2"></i>
        <div>Use <strong>Cmd</strong> instead of <strong>Ctrl</strong> on macOS.</div>
      </div>
      <div class="d-flex justify-content-end gap-2 mt-3">
        <button type="button" class="btn btn-secondary" data-action="closeKeyboardHelp">Close</button>
      </div>
    </div>
  </div>`;
}

/** Boot */
window.App = App;
window.addEventListener('DOMContentLoaded', () => App.init());
