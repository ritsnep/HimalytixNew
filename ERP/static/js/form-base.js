(function (window, document, $) {
  'use strict';

  function readJSONScript(id) {
    if (!id) return {};
    var node = document.getElementById(id);
    if (!node) return {};
    try {
      var text = node.textContent || node.innerText || '{}';
      return text ? JSON.parse(text) : {};
    } catch (error) {
      console.warn('[FormBase] Failed to parse config', error);
      return {};
    }
  }

  function isEditable(el) {
    if (!el) return false;
    var tag = el.tagName;
    if (!tag) return false;
    var name = tag.toLowerCase();
    return name === 'input' || name === 'textarea' || name === 'select' || el.isContentEditable;
  }

  function normalizeKey(key) {
    if (!key) return '';
    var map = { 'escape': 'esc', ' ': 'space', 'arrowup': 'up', 'arrowdown': 'down' };
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

  function bindShortcut(combo, handler, opts) {
    document.addEventListener('keydown', function (evt) {
      if (!matchesShortcut(evt, combo)) return;
      if (!opts || opts.allowInInputs !== true) {
        if (isEditable(evt.target)) return;
      }
      evt.preventDefault();
      handler(evt);
    });
  }

  function setupCustomShortcuts(root, shortcuts) {
    if (!shortcuts || !Array.isArray(shortcuts)) return;
    shortcuts.forEach(function (shortcut) {
      if (!shortcut || !shortcut.keys) return;
      bindShortcut(shortcut.keys, function () {
        if (shortcut.target) {
          var target = root.querySelector(shortcut.target) || document.querySelector(shortcut.target);
          if (target) {
            if (shortcut.action === 'focus') {
              target.focus();
              if (target.select) target.select();
            } else if (shortcut.action === 'toggle' && shortcut.toggleClass) {
              target.classList.toggle(shortcut.toggleClass);
            } else if (shortcut.action === 'submit' && target.requestSubmit) {
              target.requestSubmit();
            } else {
              target.click();
            }
          }
        }
        if (shortcut.message && typeof bootstrap !== 'undefined') {
          var container = document.getElementById('form-toast-container');
          if (container) {
            var toast = document.createElement('div');
            toast.className = 'toast align-items-center text-bg-' + (shortcut.messageType || 'info') + ' border-0';
            toast.innerHTML = '<div class="d-flex"><div class="toast-body">' +
              shortcut.message +
              '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
            container.appendChild(toast);
            new bootstrap.Toast(toast).show();
          }
        }
        if (shortcut.handler && typeof window[shortcut.handler] === 'function') {
          window[shortcut.handler].call(root, shortcut);
        }
      }, { allowInInputs: shortcut.allowInInputs === true });
    });
  }

  function mount(selector) {
    var root = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!root || root.__formBaseMounted) return;
    root.__formBaseMounted = true;

    var form = root.querySelector('form[data-form-base]') || root.querySelector('form');
    if (!form) {
      console.warn('[FormBase] No form found inside shell.');
      return;
    }

    var configId = root.getAttribute('data-form-config-id') || 'form-config';
    var config = readJSONScript(configId);
    var dirtyIndicator = root.querySelector('[data-form-dirty-indicator]');
    var trackDirty = form.getAttribute('data-form-track-dirty') !== 'false';
    var isDirty = false;
    var warnOnExit = config.warnOnExit !== false && trackDirty;

    function markDirty() {
      if (!trackDirty) return;
      isDirty = true;
      if (dirtyIndicator) {
        dirtyIndicator.classList.add('is-visible');
      }
    }

    function clearDirty() {
      isDirty = false;
      if (dirtyIndicator) {
        dirtyIndicator.classList.remove('is-visible');
      }
    }

    form.addEventListener('input', markDirty, { capture: true });
    form.addEventListener('change', markDirty, { capture: true });
    form.addEventListener('submit', clearDirty);

    if (warnOnExit) {
      window.addEventListener('beforeunload', function (evt) {
        if (!isDirty) return;
        evt.preventDefault();
        evt.returnValue = '';
      });
    }

    function requestSubmit() {
      var submitBtn = form.querySelector('[data-form-submit]');
      if (form.requestSubmit) {
        form.requestSubmit(submitBtn || null);
      } else {
        form.submit();
      }
    }

    bindShortcut('ctrl+s', requestSubmit);
    bindShortcut('meta+s', requestSubmit);
    bindShortcut('ctrl+enter', requestSubmit);
    bindShortcut('meta+enter', requestSubmit);

    var expandBtn = root.querySelector('[data-form-expand]');
    function toggleExpand(forceState) {
      var newState = typeof forceState === 'boolean'
        ? forceState
        : !root.classList.contains('form-shell--expanded');
      root.classList.toggle('form-shell--expanded', newState);
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
        toggleExpand();
      });
    }
    bindShortcut('ctrl+shift+e', toggleExpand);
    bindShortcut('meta+shift+e', toggleExpand);

    var shortcuts = config.shortcuts || [];
    setupCustomShortcuts(root, shortcuts);

    if ($ && $.fn && $.fn.datepicker) {
      $('.datepicker', form).datepicker({
        format: 'yyyy-mm-dd',
        autoclose: true,
        todayHighlight: true
      });
    }
    if (window.flatpickr) {
      window.flatpickr('.flatpickr', {});
    }
    if (window.Pristine) {
      var pristine = new window.Pristine(form, {
        classTo: 'form-group',
        errorClass: 'has-danger',
        successClass: 'has-success',
        errorTextParent: 'form-group',
        errorTextTag: 'div',
        errorTextClass: 'text-danger'
      });
      form.addEventListener('submit', function (evt) {
        if (!pristine.validate()) {
          evt.preventDefault();
        }
      });
    }
  }

  window.FormBase = {
    mount: mount
  };
})(window, document, window.jQuery);
