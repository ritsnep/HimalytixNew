/**
 * Forms Designer - UDF Manager
 * Handles creating, editing, and deleting UDF fields
 */

class UDFManager {
    constructor(engine) {
        this.engine = engine;
        this.configId = engine.configId;
        this.init();
    }
    
    init() {
        // Add UDF button
        document.getElementById('btn-add-udf')?.addEventListener('click', () => {
            this.showUDFModal();
        });
    }
    
    showUDFModal() {
        // TODO: Implement UDF creation modal
        this.engine.showToast('UDF Manager - Coming in next update', 'info');
    }
}

// Initialize when engine is ready
document.addEventListener('DOMContentLoaded', () => {
    const checkEngine = setInterval(() => {
        if (window.designerEngine) {
            window.udfManager = new UDFManager(window.designerEngine);
            clearInterval(checkEngine);
        }
    }, 100);
});
