// ERP/static/js/htmx-autofill.js

export function setupAutoFill({
    triggerSelectors,
    targetSelector,
    url,
    paramsCallback,
    valueCallback,
}) {
    function update() {
        const params = paramsCallback();
        // Only send if organization is present and not undefined/empty
        if (!params || !params.organization || params.organization === 'undefined' || params.organization === '') return;
        fetch(url + "?" + new URLSearchParams(params))
            .then(r => r.json())
            .then(data => valueCallback(data));
    }
    triggerSelectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            el.removeEventListener("change", update); // Prevent duplicate listeners
            el.addEventListener("change", update);
        });
    });
    update();
}

// Re-initialize after HTMX swaps
document.body.addEventListener("htmx:afterSwap", function () {
    if (window.initAutoFills) window.initAutoFills();
});