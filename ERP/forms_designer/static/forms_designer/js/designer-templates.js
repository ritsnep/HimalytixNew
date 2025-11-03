/**
 * Forms Designer - Template Manager
 * Handles loading and applying templates
 */

class TemplateManager {
    constructor(engine) {
        this.engine = engine;
        this.init();
    }
    
    init() {
        document.getElementById('btn-templates')?.addEventListener('click', () => {
            this.showTemplatesModal();
        });
    }
    
    showTemplatesModal() {
        // TODO: Implement template browser modal
        this.engine.showToast('Template Manager - Coming in next update', 'info');
    }
}

// Initialize when engine is ready
document.addEventListener('DOMContentLoaded', () => {
    const checkEngine = setInterval(() => {
        if (window.designerEngine) {
            window.templateManager = new TemplateManager(window.designerEngine);
            clearInterval(checkEngine);
        }
    }, 100);
});
