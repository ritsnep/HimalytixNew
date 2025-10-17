class FormPersistence {
    constructor(formId, storageKey) {
        this.form = document.getElementById(formId);
        this.storageKey = storageKey;
        this.setupListeners();
    }

    setupListeners() {
        this.form.addEventListener('input', () => this.saveState());
        window.addEventListener('load', () => this.loadState());
    }

    saveState() {
        const formData = new FormData(this.form);
        const state = Object.fromEntries(formData);
        localStorage.setItem(this.storageKey, JSON.stringify(state));
    }

    loadState() {
        const savedState = localStorage.getItem(this.storageKey);
        if (savedState) {
            const state = JSON.parse(savedState);
            Object.entries(state).forEach(([name, value]) => {
                const field = this.form.elements[name];
                if (field) field.value = value;
            });
        }
    }
}