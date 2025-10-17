(function() {
    const FORM_PREFIX = 'pending_form_';
    function getFormKey(form) {
        const id = form.getAttribute('id') || form.getAttribute('name') || 'form';
        return FORM_PREFIX + id + '_' + window.location.pathname.replace(/\//g, '_');
    }

    function serializeForm(form) {
        const data = {};
        new FormData(form).forEach((v, k) => {
            if (data[k]) {
                if (!Array.isArray(data[k])) data[k] = [data[k]];
                data[k].push(v);
            } else {
                data[k] = v;
            }
        });
        return data;
    }

    function saveFormToStorage(form) {
        const data = serializeForm(form);
        data['__path__'] = window.location.pathname;
        localStorage.setItem(getFormKey(form), JSON.stringify(data));
    }

    // function restoreFormFromStorage(form) {
    //     const raw = localStorage.getItem(getFormKey(form));
    //     if (!raw) return;
    //     const data = JSON.parse(raw);
    //     if (data['__path__'] !== window.location.pathname) return;
    //     for (const [k, v] of Object.entries(data)) {
    //         if (k === '__path__') continue;
    //         const el = form.elements[k];
    //         if (!el) continue;
    //         if (el.type === 'checkbox' || el.type === 'radio') {
    //             el.checked = !!v;
    //         } else {
    //             el.value = v;
    //         }
    //     }
    // }

    function clearFormStorage(form) {
        localStorage.removeItem(getFormKey(form));
    }

    window.addEventListener('beforeunload', function() {
        document.querySelectorAll('form.session-preserve').forEach(form => saveFormToStorage(form));
    });

    document.body.addEventListener('htmx:responseError', function(evt) {
        if (evt.detail.xhr.status === 401) {
            const form = evt.target.closest('form.session-preserve');
            if (form) saveFormToStorage(form);
            window.location.href = '/accounts/login/?next=' + encodeURIComponent(window.location.pathname);
        }
    });

    window.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('form.session-preserve').forEach(form => restoreFormFromStorage(form));
    });

    document.body.addEventListener('clearFormStorage', function() {
        document.querySelectorAll('form.session-preserve').forEach(form => clearFormStorage(form));
    });
})();
