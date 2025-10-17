window.addEventListener('DOMContentLoaded', () => {
    const tabBar = document.getElementById('open-tabs');
    let contentArea = document.querySelector('.main-content');
    if (!tabBar || !contentArea) return;

    function getTabs() {
        return JSON.parse(sessionStorage.getItem('openTabs') || '[]');
    }
    function saveTabs(tabs) {
        sessionStorage.setItem('openTabs', JSON.stringify(tabs));
    }

    function addTab(title, url) {
        const tabs = getTabs();
        if (!tabs.find(t => t.url === url)) {
            tabs.push({ title, url });
            saveTabs(tabs);
        }
    }

    function renderTabs(activeUrl = window.location.pathname) {
        tabBar.innerHTML = '';
        getTabs().forEach(tab => {
            const li = document.createElement('li');
            li.className = 'nav-item';
            const a = document.createElement('a');
            a.className = 'nav-link' + (tab.url === activeUrl ? ' active' : '');
            a.href = tab.url;
            // Use span for tab title for styling
            const titleSpan = document.createElement('span');
            titleSpan.className = 'tab-title';
            titleSpan.textContent = tab.title;
            a.appendChild(titleSpan);
            // Close button
            const closeBtn = document.createElement('button');
            closeBtn.innerHTML = '&times;';
            closeBtn.className = 'btn-close';
            closeBtn.title = 'Close tab';
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                closeTab(tab.url);
            });
            a.appendChild(closeBtn);
            li.appendChild(a);
            tabBar.appendChild(li);
        });
    }

    function closeTab(url) {
        const tabs = getTabs().filter(t => t.url !== url);
        saveTabs(tabs);
        // Remove cached form data for closed tab
        sessionStorage.removeItem('formData:' + url);
        if (url === window.location.pathname) {
            const next = tabs[tabs.length - 1];
            if (next) {
                htmx.ajax('GET', next.url, '#main-container');
            } else {
                renderTabs();
            }
        } else {
            renderTabs();
        }
    }

    // Save form data for the current tab
    function cacheFormData(url) {
        if (!contentArea) return;
        const forms = contentArea.querySelectorAll('form');
        if (!forms.length) return;
        const data = [];
        forms.forEach(form => {
            const fd = new FormData(form);
            const obj = {};
            for (const [k, v] of fd.entries()) obj[k] = v;
            data.push({ action: form.action, data: obj });
        });
        sessionStorage.setItem('formData:' + url, JSON.stringify(data));
    }

    // Restore form data for the current tab
    function restoreFormData(url) {
        if (!contentArea) return;
        const forms = contentArea.querySelectorAll('form');
        const saved = sessionStorage.getItem('formData:' + url);
        if (!saved) return;
        const dataArr = JSON.parse(saved);
        forms.forEach((form, idx) => {
            const data = dataArr[idx]?.data || {};
            for (const [k, v] of Object.entries(data)) {
                const el = form.elements[k];
                if (!el) continue;
                if (el.type === 'checkbox' || el.type === 'radio') {
                    el.checked = !!v;
                } else {
                    el.value = v;
                }
            }
        });
    }

    function navigate(url, push = true) {
        // Cache form data before navigating away
        cacheFormData(window.location.pathname);
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(resp => resp.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContent = doc.querySelector('.main-content');
                if (!newContent) {
                    window.location.href = url;
                    return;
                }
                contentArea.replaceWith(newContent);
                contentArea = newContent;
                document.title = doc.title;
                const path = new URL(url, window.location.origin).pathname;
                addTab(doc.title, path);
                renderTabs(path);
                if (push) history.pushState({}, '', path);
                if (window.feather) feather.replace();
                // Restore form data for this tab if available
                restoreFormData(path);
            });
    }

    // Initial tab
    addTab(document.title, window.location.pathname);
    renderTabs();

    if (!window.htmx) {
        document.body.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (!link || link.target || link.hasAttribute('download') || link.getAttribute('href').startsWith('#')) return;
            if (link.origin !== location.origin) return;
            e.preventDefault();
            navigate(link.href);
        });

        window.addEventListener('popstate', () => {
            navigate(location.href, false);
        });
    } else {
        htmx.on('htmx:beforeRequest', () => {
            cacheFormData(window.location.pathname);
        });

        htmx.on('htmx:afterSwap', (e) => {
            if (e.detail.target.id === 'main-container') {
                contentArea = document.getElementById('main-container');
                addTab(document.title, window.location.pathname);
                renderTabs(window.location.pathname);
                restoreFormData(window.location.pathname);
                if (window.feather) feather.replace();
            }
        });
    }

    // Global controls
    window.closeCurrentTab = () => closeTab(window.location.pathname);
    window.closeAllTabs = () => {
        saveTabs([]);
        renderTabs();
    };
    window.closeOtherTabs = () => {
        saveTabs([{ title: document.title, url: window.location.pathname }]);
        renderTabs(window.location.pathname);
    };
});