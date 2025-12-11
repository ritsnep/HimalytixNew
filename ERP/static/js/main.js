const root = document.body;

function setCookie(name, value) {
  try {
    document.cookie = `${name}=${value};path=/;max-age=${60 * 60 * 24 * 365}`;
  } catch (e) {
    /* non-blocking */
  }
}

function getPersisted(key, fallback) {
  const cookieVal = getCookie(key);
  if (cookieVal) return cookieVal;
  try {
    const ls = localStorage.getItem(key);
    if (ls) return ls;
  } catch (e) { /* ignore */ }
  return fallback;
}

function getCookie(name) {
  const pattern = `; ${document.cookie}`;
  const parts = pattern.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

function setTheme(mode) {
  const next = mode || 'light';
  root.setAttribute('data-layout-mode', next);
  setCookie('theme', next);
  try {
    localStorage.setItem('theme', next);
  } catch (e) {}
}

function setTextScale(scale) {
  const next = scale || 'm';
  root.setAttribute('data-text-scale', next);
  ['ui-scale-xs','ui-scale-s','ui-scale-m','ui-scale-l','ui-scale-xl'].forEach(cls => root.classList.remove(cls));
  root.classList.add(`ui-scale-${next}`);
  setCookie('text_scale', next);
  try { localStorage.setItem('text_scale', next); } catch (e) {}
}

function setLayoutAttr(key, value) {
  const map = {
    'layout': 'data-layout',
    'layout-mode': 'data-layout-mode',
    'layout-width': 'data-layout-size',
    'layout-position': 'data-layout-scrollable',
    'topbar-color': 'data-topbar',
    'sidebar-size': 'data-sidebar-size',
    'sidebar-color': 'data-sidebar',
    'layout-direction': 'dir',
  };
  const attr = map[key];
  if (!attr) return;
  if (attr === 'dir') {
    document.documentElement.setAttribute('dir', value === 'rtl' ? 'rtl' : 'ltr');
    return;
  }
  root.setAttribute(attr, value);
  setCookie(`ui-${key}`, value);
  try { localStorage.setItem(`ui-${key}`, value); } catch (e) {}
}

function applyFontFamily() {
  const font = root.dataset.fontFamily || localStorage.getItem('ui-font-family');
  if (font) {
    root.style.setProperty('--ui-font-family', font);
    setCookie('font_family', font);
    try { localStorage.setItem('ui-font-family', font); } catch (e) {}
  }
}

function setFontFamily(font) {
  if (!font) return;
  root.dataset.fontFamily = font;
  root.style.setProperty('--ui-font-family', font);
  setCookie('font_family', font);
  try { localStorage.setItem('ui-font-family', font); } catch (e) {}
}

function setBrandColor(color) {
  if (!color || !/^#[0-9A-F]{6}$/i.test(color)) return;
  document.documentElement.style.setProperty('--ui-brand-color', color);
  setCookie('brand_color', color);
  try { localStorage.setItem('brand_color', color); } catch (e) {}
}

function applyPersistedBrandColor() {
  const storedColor = getCookie('brand_color') || localStorage.getItem('brand_color');
  if (storedColor && /^#[0-9A-F]{6}$/i.test(storedColor)) {
    setBrandColor(storedColor);
  }
}

function resetBrandColor() {
  const defaultColor = '#1c84ee';
  setBrandColor(defaultColor);
  const picker = document.getElementById('brand-color-picker');
  const input = document.getElementById('brand-color-input');
  if (picker) picker.value = defaultColor;
  if (input) input.value = defaultColor;
  // Also clear from storage
  try {
    localStorage.removeItem('brand_color');
    document.cookie = 'brand_color=;path=/;max-age=0';
  } catch (e) {}
}

function applyPersistedLayout() {
  const theme = getPersisted('theme', root.getAttribute('data-layout-mode') || 'light');
  const topbar = getPersisted('ui-topbar-color', root.getAttribute('data-topbar') || 'light');
  const sidebar = getPersisted('ui-sidebar-color', root.getAttribute('data-sidebar') || 'light');
  const sidebarSize = getPersisted('ui-sidebar-size', root.getAttribute('data-sidebar-size') || 'lg');
  const layout = getPersisted('ui-layout', root.getAttribute('data-layout') || 'vertical');
  const layoutWidth = getPersisted('ui-layout-width', root.getAttribute('data-layout-size') || 'fluid');
  const layoutPos = getPersisted('ui-layout-position', (root.getAttribute('data-layout-scrollable') === 'true') ? 'scrollable' : 'fixed');
  const direction = getPersisted('ui-layout-direction', document.documentElement.getAttribute('dir') || 'ltr');

  root.setAttribute('data-layout-mode', theme);
  root.setAttribute('data-topbar', topbar);
  root.setAttribute('data-sidebar', sidebar);
  root.setAttribute('data-sidebar-size', sidebarSize);
  root.setAttribute('data-layout', layout);
  root.setAttribute('data-layout-size', layoutWidth);
  root.setAttribute('data-layout-scrollable', layoutPos === 'scrollable' ? 'true' : 'false');
  document.documentElement.setAttribute('dir', direction === 'rtl' ? 'rtl' : 'ltr');
}

function startLayoutGuards() {
  const storedTopbar = getPersisted('ui-topbar-color', root.getAttribute('data-topbar') || 'light');
  const storedSidebar = getPersisted('ui-sidebar-color', root.getAttribute('data-sidebar') || 'light');
  const storedSidebarSize = getPersisted('ui-sidebar-size', root.getAttribute('data-sidebar-size') || 'lg');

  const enforce = () => {
    if (root.getAttribute('data-topbar') !== storedTopbar) {
      root.setAttribute('data-topbar', storedTopbar);
    }
    if (root.getAttribute('data-sidebar') !== storedSidebar) {
      root.setAttribute('data-sidebar', storedSidebar);
    }
    if (root.getAttribute('data-sidebar-size') !== storedSidebarSize) {
      root.setAttribute('data-sidebar-size', storedSidebarSize);
    }
  };

  enforce();
  try {
    new MutationObserver(enforce).observe(root, { attributes: true, attributeFilter: ['data-topbar','data-sidebar','data-sidebar-size'] });
  } catch (e) { /* non-blocking */ }
  setTimeout(enforce, 50);
  setTimeout(enforce, 150);
  setTimeout(enforce, 400);
}

function hydratePreferences() {
  const defaultTheme = root.dataset.layoutMode || 'light';
  const storedTheme = getCookie('theme') || localStorage.getItem('theme');
  setTheme(storedTheme || defaultTheme);

  const defaultScale = root.dataset.textScale || 'm';
  const storedScale = getCookie('text_scale') || localStorage.getItem('text_scale');
  setTextScale(storedScale || defaultScale);

  const storedFont = getCookie('font_family') || localStorage.getItem('ui-font-family') || root.dataset.fontFamily;
  if (storedFont) {
    setFontFamily(storedFont);
  } else {
    applyFontFamily();
  }

  // hydrate layout-related attributes
  const layoutDefaults = {
    'layout': root.getAttribute('data-layout') || 'vertical',
    'layout-width': root.getAttribute('data-layout-size') || 'fluid',
    'layout-position': root.getAttribute('data-layout-scrollable') === 'true' ? 'scrollable' : 'fixed',
    'topbar-color': root.getAttribute('data-topbar') || 'light',
    'sidebar-size': root.getAttribute('data-sidebar-size') || 'lg',
    'sidebar-color': root.getAttribute('data-sidebar') || 'light',
    'layout-direction': document.documentElement.getAttribute('dir') || 'ltr'
  };

  Object.entries(layoutDefaults).forEach(([key, fallback]) => {
    const stored = getCookie(`ui-${key}`) || localStorage.getItem(`ui-${key}`);
    const value = stored || fallback;
    setLayoutAttr(key, value);
  });

  applyFontFamily();
  applyPersistedLayout();
  applyPersistedBrandColor();
}

function bindRightBarControls() {
  document.querySelectorAll('[data-setting="layout-mode"]').forEach((input) => {
    input.checked = input.value === (root.getAttribute('data-layout-mode') || 'light');
    input.addEventListener('change', () => setTheme(input.value));
  });

  document.querySelectorAll('[data-setting="text-scale"]').forEach((input) => {
    input.checked = input.value === (root.getAttribute('data-text-scale') || 'm');
    input.addEventListener('change', () => setTextScale(input.value));
  });

  document.querySelectorAll('[data-setting]').forEach((input) => {
    if (['layout-mode','text-scale','font-family'].includes(input.dataset.setting)) return;
    const key = input.dataset.setting;
    // Map setting keys to their data attributes
    const attrMap = {
      'topbar-color': 'data-topbar',
      'sidebar-color': 'data-sidebar',
      'sidebar-size': 'data-sidebar-size',
      'layout': 'data-layout',
      'layout-width': 'data-layout-size',
      'layout-position': 'data-layout-scrollable',
      'layout-direction': 'dir'
    };
    const attrName = attrMap[key] || `data-${key}`;
    const current = localStorage.getItem(`ui-${key}`) || (key === 'layout-direction' ? document.documentElement.getAttribute('dir') || 'ltr' : root.getAttribute(attrName));
    input.checked = input.value === current;
    input.addEventListener('change', () => setLayoutAttr(key, input.value));
  });

  document.querySelectorAll('[data-setting="font-family"]').forEach((input) => {
    const current = getCookie('font_family') || localStorage.getItem('ui-font-family') || root.dataset.fontFamily;
    input.checked = input.value === current;
    input.addEventListener('change', () => setFontFamily(input.value));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  hydratePreferences();
  bindRightBarControls();
  // Re-assert persisted layout after vendor scripts initialize
  applyPersistedLayout();
  startLayoutGuards();
  setTimeout(applyPersistedLayout, 50);
  setTimeout(applyPersistedLayout, 150);
  setTimeout(applyPersistedLayout, 400);

  // Initialize brand color picker
  const colorPicker = document.getElementById('brand-color-picker');
  const colorInput = document.getElementById('brand-color-input');
  const resetBtn = document.getElementById('reset-brand-color');

  if (colorPicker && colorInput) {
    // Sync color picker with text input
    colorPicker.addEventListener('change', (e) => {
      const color = e.target.value;
      colorInput.value = color;
      setBrandColor(color);
    });

    // Sync text input with color picker (validate hex color)
    colorInput.addEventListener('change', (e) => {
      let color = e.target.value.trim();
      if (!/^#[0-9A-F]{6}$/i.test(color)) {
        // Invalid format, revert to current
        const stored = getCookie('brand_color') || localStorage.getItem('brand_color') || '#1c84ee';
        color = stored;
        colorInput.value = color;
      }
      colorPicker.value = color;
      setBrandColor(color);
    });

    colorInput.addEventListener('input', (e) => {
      let color = e.target.value.trim();
      if (/^#[0-9A-F]{6}$/i.test(color)) {
        colorPicker.value = color;
      }
    });
  }

  // Reset brand color button
  if (resetBtn) {
    resetBtn.addEventListener('click', resetBrandColor);
  }
});

if (window.htmx) {
  htmx.on('htmx:beforeSwap', () => setTheme(getCookie('theme') || localStorage.getItem('theme') || 'light'));
}

const overlay = document.getElementById('loading-overlay');
if (overlay && window.htmx) {
  htmx.on('htmx:requestStart', () => overlay.classList.add('show'));
  htmx.on('htmx:responseError', () => overlay.classList.remove('show'));
  htmx.on('htmx:afterSwap', () => overlay.classList.remove('show'));
}