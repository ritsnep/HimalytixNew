/**
 * Forms Designer - UI Utilities
 * Handles preview, history, and other UI features
 */

class DesignerUI {
    constructor(engine) {
        this.engine = engine;
        this.init();
    }
    
    init() {
        // Preview button
        document.getElementById('btn-preview')?.addEventListener('click', () => {
            this.openPreview();
        });
        
        // History button
        document.getElementById('btn-history')?.addEventListener('click', () => {
            this.openHistory();
        });
    }
    
    openPreview() {
        const url = `/forms_designer/preview/${this.engine.configId}/`;
        window.open(url, '_blank', 'width=1200,height=800');
    }
    
    openHistory() {
        const url = `/forms_designer/history/${this.engine.configId}/`;
        window.location.href = url;
    }
}

// Initialize when engine is ready
document.addEventListener('DOMContentLoaded', () => {
    const checkEngine = setInterval(() => {
        if (window.designerEngine) {
            window.designerUI = new DesignerUI(window.designerEngine);
            clearInterval(checkEngine);
        }
    }, 100);
});
