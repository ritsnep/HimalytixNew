document.addEventListener("DOMContentLoaded", function () {
    const DARK = "layout-mode-dark";
    const LIGHT = "layout-mode-light";

    const body = document.getElementById("page-body");
    const modeBtn = document.getElementById("mode-setting-btn");
    const moonIcon = document.getElementById("moon-icon");
    const sunIcon = document.getElementById("sun-icon");

    if (!body || !modeBtn || !moonIcon || !sunIcon) {
        console.warn("Some theme toggle elements are missing.");
        return;
    }

    function applyMode(mode) {
        body.classList.remove(DARK, LIGHT);
        body.classList.add(mode);
        sessionStorage.setItem("themeMode", mode);

        if (mode === DARK) {
            moonIcon.style.display = "none";
            sunIcon.style.display = "inline";
        } else {
            moonIcon.style.display = "inline";
            sunIcon.style.display = "none";
        }

        if (window.feather) {
            feather.replace();
        }
    }

    let savedMode = sessionStorage.getItem("themeMode");

    if (!savedMode) {
        const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        savedMode = prefersDark ? DARK : LIGHT;
        sessionStorage.setItem("themeMode", savedMode);
    }

    applyMode(savedMode);

    modeBtn.addEventListener("click", function () {
        const currentMode = body.classList.contains(DARK) ? DARK : LIGHT;
        const newMode = currentMode === DARK ? LIGHT : DARK;
        applyMode(newMode);
    });
});
