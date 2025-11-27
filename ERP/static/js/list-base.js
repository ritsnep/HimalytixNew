(function (window, document, $) {
  'use strict';

  if (!$ || !$.fn || !$.fn.DataTable) {
    console.warn('[ListBase] DataTables dependency missing.');
    return;
  }

  var DEFAULT_OPTIONS = {
    dom: 'Blfrtip',
    buttons: [
      {
        extend: 'copy',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-content-copy"></i>',
        titleAttr: 'Copy'
      },
      {
        extend: 'csv',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-file-delimited"></i>',
        titleAttr: 'CSV'
      },
      {
        extend: 'excel',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-file-excel"></i>',
        titleAttr: 'Excel'
      },
      {
        extend: 'pdf',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-file-pdf"></i>',
        titleAttr: 'PDF'
      },
      {
        extend: 'print',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-printer"></i>',
        titleAttr: 'Print'
      },
      {
        extend: 'colvis',
        className: 'btn btn-light btn-sm',
        text: '<i class="mdi mdi-view-column"></i>',
        titleAttr: 'Columns'
      }
    ],
    responsive: true,
    fixedHeader: true,
    lengthMenu: [[10, 20, 40, 50, -1], [10, 20, 40, 50, 'All']],
    pageLength: 20
  };

  function readJSONScript(id) {
    var node = document.getElementById(id);
    if (!node) {
      return {};
    }
    try {
      var text = node.textContent || node.innerText || '{}';
      return text ? JSON.parse(text) : {};
    } catch (err) {
      console.warn('[ListBase] Failed to parse JSON config', err);
      return {};
    }
  }

  function isEditable(el) {
    if (!el) return false;
    var tag = el.tagName;
    if (!tag) return false;
    var name = tag.toLowerCase();
    return (
      name === 'input' ||
      name === 'textarea' ||
      name === 'select' ||
      el.isContentEditable
    );
  }

  function normalizeKey(key) {
    if (!key) return '';
    var map = {
      'arrowup': 'up',
      'arrowdown': 'down',
      'arrowleft': 'left',
      'arrowright': 'right',
      ' ': 'space',
      'escape': 'esc'
    };
    key = key.toLowerCase();
    return map[key] || key;
  }

  function matchesShortcut(evt, combo) {
    if (!combo) return false;
    var parts = combo.toLowerCase().replace(/\s+/g, '').split('+');
    var key = parts.pop();
    var needCtrl = parts.indexOf('ctrl') !== -1;
    var needMeta = parts.indexOf('meta') !== -1 || parts.indexOf('cmd') !== -1;
    var needShift = parts.indexOf('shift') !== -1;
    var needAlt = parts.indexOf('alt') !== -1 || parts.indexOf('option') !== -1;

    var actualKey = normalizeKey(evt.key);
    if (needCtrl && !(evt.ctrlKey || evt.metaKey)) return false;
    if (!needCtrl && !needMeta && (evt.ctrlKey || evt.metaKey)) return false;
    if (needMeta && !evt.metaKey) return false;
    if (!needMeta && evt.metaKey && !needCtrl) return false;
    if (needShift !== evt.shiftKey) return false;
    if (needAlt !== evt.altKey) return false;
    return actualKey === key;
  }

  function createToast(message, type) {
    var container = document.getElementById('list-toast-container');
    if (!container || typeof bootstrap === 'undefined' || !message) {
      return;
    }
    var toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-' + (type || 'info') + ' border-0';
    toast.innerHTML = [
      '<div class="d-flex">',
      '<div class="toast-body">',
      message,
      '</div>',
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>',
      '</div>'
    ].join('');
    container.appendChild(toast);
    var instance = new bootstrap.Toast(toast);
    instance.show();
  }

  function setupShortcuts(root, shortcuts, context) {
    if (!shortcuts || !Array.isArray(shortcuts)) return;
    shortcuts.forEach(function (shortcut) {
      if (!shortcut || !shortcut.keys) return;
      document.addEventListener('keydown', function (evt) {
        if (shortcut.allowInInputs !== true && isEditable(evt.target)) {
          return;
        }
        if (!matchesShortcut(evt, shortcut.keys)) {
          return;
        }
        evt.preventDefault();
        if (shortcut.target) {
          var target =
            root.querySelector(shortcut.target) ||
            document.querySelector(shortcut.target);
          if (target) {
            if (shortcut.action === 'focus') {
              target.focus();
              if (target.select) target.select();
            } else if (shortcut.action === 'toggle' && shortcut.toggleClass) {
              target.classList.toggle(shortcut.toggleClass);
            } else {
              target.click();
            }
          }
        }
        if (shortcut.message) {
          createToast(shortcut.message, shortcut.messageType);
        }
        if (typeof shortcut.handler === 'string') {
          var handlerFn = window[shortcut.handler];
          if (typeof handlerFn === 'function') {
            handlerFn.call(context || window, evt, shortcut);
          }
        }
      });
    });
  }

  function toggleCollapse(targetId) {
    if (!targetId) return;
    var node = document.getElementById(targetId);
    if (!node || typeof bootstrap === 'undefined' || !bootstrap.Collapse) return;
    var instance = bootstrap.Collapse.getOrCreateInstance(node, { toggle: false });
    if (node.classList.contains('show')) {
      instance.hide();
    } else {
      instance.show();
    }
  }

  function mount(selector) {
    var root = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!root || root.__listBaseMounted) {
      return;
    }
    root.__listBaseMounted = true;

    var tableId = root.getAttribute('data-datatable-id') || 'datatable-buttons';
    var tableEl = document.getElementById(tableId);
    if (!tableEl) {
      console.warn('[ListBase] Table not found:', tableId);
      return;
    }

    var configId = root.getAttribute('data-config-target') || 'datatable-config';
    var config = readJSONScript(configId);
    var options = Object.assign({}, DEFAULT_OPTIONS, config || {});
    var table = $(tableEl).DataTable(options);
    root.__datatable = table;
    window.DT_MAIN = table;

    var overlay = root.querySelector('[data-list-loading-indicator]');
    if (overlay) {
      table.on('processing.dt', function (_e, _settings, processing) {
        overlay.classList.toggle('d-none', !processing);
      });
    }

    table.columns().every(function () {
      var column = this;
      var footer = $(column.footer());
      if (!footer.length) return;
      $('input', footer).on('keyup change clear', function () {
        if (column.search() !== this.value) {
          column.search(this.value).draw();
        }
      });
    });

    var wrapper = $(tableEl).closest('.dataTables_wrapper');
    wrapper.find('.dataTables_filter').addClass('d-none');
    var exportHost = root.querySelector('[data-list-export]');
    if (exportHost) {
      var buttonContainer = wrapper.find('.dt-buttons');
      if (buttonContainer.length) {
        exportHost.appendChild(buttonContainer.get(0));
      }
    }

    var searchInput = root.querySelector('[data-list-search-input]');
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        table.search(this.value).draw();
      });
    }

    document.addEventListener('keydown', function (evt) {
      if (isEditable(evt.target)) return;
      if (evt.key === '/' && !evt.ctrlKey && !evt.metaKey && !evt.altKey) {
        if (searchInput) {
          evt.preventDefault();
          searchInput.focus();
          searchInput.select();
        }
      }
    });

    var filterTarget = root.getAttribute('data-filter-target');
    document.addEventListener('keydown', function (evt) {
      if (isEditable(evt.target)) return;
      if (matchesShortcut(evt, 'ctrl+shift+f')) {
        evt.preventDefault();
        toggleCollapse(filterTarget);
      }
    });

    var expandBtn = root.querySelector('[data-list-expand]');
    function setExpanded(forceValue) {
      var newState = typeof forceValue === 'boolean'
        ? forceValue
        : !root.classList.contains('list-shell--expanded');
      root.classList.toggle('list-shell--expanded', newState);
      if (expandBtn) {
        expandBtn.setAttribute('aria-pressed', newState ? 'true' : 'false');
        var icon = expandBtn.querySelector('i');
        if (icon) {
          icon.classList.toggle('mdi-arrow-expand-all', !newState);
          icon.classList.toggle('mdi-arrow-collapse-all', newState);
        }
      }
    }
    if (expandBtn) {
      expandBtn.addEventListener('click', function () {
        setExpanded();
      });
    }
    document.addEventListener('keydown', function (evt) {
      if (isEditable(evt.target)) return;
      if (matchesShortcut(evt, 'ctrl+shift+e')) {
        evt.preventDefault();
        setExpanded();
      }
    });

    var shortcutsId = root.getAttribute('data-shortcuts-target') || 'list-shortcuts';
    var shortcutConfig = readJSONScript(shortcutsId);
    setupShortcuts(root, shortcutConfig.shortcuts || shortcutConfig, root);

    var htmxTargetId = root.getAttribute('data-htmx-target');
    if (htmxTargetId && window.htmx) {
      document.body.addEventListener('htmx:beforeRequest', function (evt) {
        if (evt.detail && evt.detail.target && evt.detail.target.id === htmxTargetId && overlay) {
          overlay.classList.remove('d-none');
        }
      });
      document.body.addEventListener('htmx:afterRequest', function (evt) {
        if (evt.detail && evt.detail.target && evt.detail.target.id === htmxTargetId && overlay) {
          overlay.classList.add('d-none');
        }
      });
    }
  }

  window.ListBase = {
    mount: mount
  };
})(window, document, window.jQuery);
