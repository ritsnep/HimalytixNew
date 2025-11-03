/**
 * Forms Designer - Core Engine
 * Handles drag-drop, schema management, undo/redo, and core functionality
 */

class FormsDesignerEngine {
    constructor(config) {
        this.configId = config.configId;
        this.schema = config.schema || { header: [], lines: [] };
        this.undoStack = [];
        this.redoStack = [];
        this.maxUndoStack = 50;
        this.selectedField = null;
        this.isDirty = false;
        this.autoSaveInterval = null;
        
        this.init();
    }
    
    init() {
        this.setupDropzones();
        this.loadSchema();
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.setupAutoSave();
    }
    
    /**
     * Setup Sortable.js for drag and drop
     */
    setupDropzones() {
        const self = this;
        
        // Header dropzone
        this.headerSortable = Sortable.create(document.getElementById('header-dropzone'), {
            group: {
                name: 'fields',
                pull: false,
                put: ['palette', 'fields']
            },
            animation: 150,
            handle: '.field-item-header',
            ghostClass: 'gu-transit',
            chosenClass: 'selected',
            dragClass: 'gu-mirror',
            onAdd: (evt) => self.handleFieldAdd(evt, 'header'),
            onUpdate: (evt) => self.handleFieldReorder(evt, 'header'),
            onRemove: (evt) => self.handleFieldRemove(evt, 'header')
        });
        
        // Lines dropzone
        this.linesSortable = Sortable.create(document.getElementById('lines-dropzone'), {
            group: {
                name: 'fields',
                pull: false,
                put: ['palette', 'fields']
            },
            animation: 150,
            handle: '.field-item-header',
            ghostClass: 'gu-transit',
            chosenClass: 'selected',
            dragClass: 'gu-mirror',
            onAdd: (evt) => self.handleFieldAdd(evt, 'lines'),
            onUpdate: (evt) => self.handleFieldReorder(evt, 'lines'),
            onRemove: (evt) => self.handleFieldRemove(evt, 'lines')
        });
        
        // Make palette items draggable
        this.setupPaletteDrag();
    }
    
    setupPaletteDrag() {
        const palettes = document.querySelectorAll('.field-palette-item:not(.locked)');
        
        palettes.forEach(item => {
            item.draggable = true;
            
            item.addEventListener('dragstart', (e) => {
                const fieldData = {
                    name: item.dataset.fieldName,
                    type: item.dataset.fieldType,
                    label: item.querySelector('.field-name').textContent,
                    udfId: item.dataset.udfId || null,
                    scope: item.dataset.scope || null
                };
                e.dataTransfer.setData('application/json', JSON.stringify(fieldData));
                e.dataTransfer.effectAllowed = 'copy';
            });
        });
        
        // Setup dropzone drag events
        const dropzones = document.querySelectorAll('.dropzone');
        dropzones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
                zone.classList.add('drag-over');
            });
            
            zone.addEventListener('dragleave', (e) => {
                if (e.target === zone) {
                    zone.classList.remove('drag-over');
                }
            });
            
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                
                const fieldData = JSON.parse(e.dataTransfer.getData('application/json'));
                const section = zone.dataset.section;
                
                this.addFieldToCanvas(fieldData, section);
            });
        });
    }
    
    /**
     * Load schema and render fields
     */
    loadSchema() {
        // Render header fields
        if (this.schema.header && Array.isArray(this.schema.header)) {
            this.schema.header.forEach(field => {
                this.renderField(field, 'header', false);
            });
        }
        
        // Render line fields
        if (this.schema.lines && Array.isArray(this.schema.lines)) {
            this.schema.lines.forEach(field => {
                this.renderField(field, 'lines', false);
            });
        }
        
        this.updateEmptyStates();
    }
    
    /**
     * Add field to canvas from palette
     */
    addFieldToCanvas(fieldData, section) {
        // Create field object with defaults
        const field = {
            name: fieldData.name,
            type: fieldData.type,
            label: fieldData.label,
            required: false,
            help_text: '',
            placeholder: '',
            default_value: '',
            grid_column_width: 12,
            grid_column_offset: 0,
            css_class: '',
            visibility_rules: {
                enabled: false,
                conditions: [],
                action: 'show'
            },
            validation_rules: {},
            udf_id: fieldData.udfId,
            locked: fieldData.locked || false
        };
        
        // Add to schema
        this.schema[section].push(field);
        
        // Render field
        this.renderField(field, section);
        
        // Save state for undo
        this.saveState();
        
        // Mark as dirty
        this.markDirty();
        
        // Update UI
        this.updateEmptyStates();
        
        // Show toast
        this.showToast(`Field "${field.label}" added to ${section}`, 'success');
    }
    
    /**
     * Render a field in the canvas
     */
    renderField(field, section, animate = true) {
        const dropzone = section === 'header' ? 
            document.getElementById('header-dropzone') : 
            document.getElementById('lines-dropzone');
        
        const fieldElement = this.createFieldElement(field, section);
        
        if (animate) {
            fieldElement.style.opacity = '0';
            fieldElement.style.transform = 'scale(0.9)';
        }
        
        dropzone.appendChild(fieldElement);
        
        if (animate) {
            setTimeout(() => {
                fieldElement.style.transition = 'all 0.3s ease-out';
                fieldElement.style.opacity = '1';
                fieldElement.style.transform = 'scale(1)';
            }, 10);
        }
        
        // Set grid column width
        fieldElement.style.gridColumn = `span ${field.grid_column_width || 12}`;
        
        return fieldElement;
    }
    
    /**
     * Create DOM element for a field
     */
    createFieldElement(field, section) {
        const div = document.createElement('div');
        div.className = 'field-item';
        div.dataset.fieldName = field.name;
        div.dataset.section = section;
        div.dataset.gridWidth = field.grid_column_width || 12;
        
        if (field.locked) {
            div.classList.add('locked');
        }
        
        const icon = this.getFieldIcon(field.type);
        const requiredBadge = field.required ? '<span class="field-required-badge">Required</span>' : '';
        
        div.innerHTML = `
            <div class="field-item-header">
                <div class="field-item-label">
                    <i class="${icon}" style="margin-right: 0.5rem; color: var(--primary-color);"></i>
                    ${field.label}
                    ${requiredBadge}
                </div>
                <div class="field-item-actions">
                    ${!field.locked ? `
                        <button type="button" class="field-item-action-btn" data-action="edit" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button type="button" class="field-item-action-btn" data-action="clone" title="Clone">
                            <i class="fas fa-copy"></i>
                        </button>
                        <button type="button" class="field-item-action-btn" data-action="delete" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    ` : `
                        <i class="fas fa-lock" style="color: #9ca3af;"></i>
                    `}
                </div>
            </div>
            <div class="field-item-preview">
                ${field.help_text || 'No help text'}
            </div>
        `;
        
        // Add event listeners
        div.addEventListener('click', (e) => {
            if (!e.target.closest('.field-item-action-btn')) {
                this.selectField(div);
            }
        });
        
        // Action buttons
        const editBtn = div.querySelector('[data-action="edit"]');
        const cloneBtn = div.querySelector('[data-action="clone"]');
        const deleteBtn = div.querySelector('[data-action="delete"]');
        
        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectField(div);
            });
        }
        
        if (cloneBtn) {
            cloneBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.cloneField(field, section);
            });
        }
        
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteField(field.name, section);
            });
        }
        
        return div;
    }
    
    /**
     * Get Font Awesome icon for field type
     */
    getFieldIcon(type) {
        const icons = {
            'text': 'fas fa-font',
            'textarea': 'fas fa-align-left',
            'number': 'fas fa-calculator',
            'decimal': 'fas fa-calculator',
            'date': 'fas fa-calendar',
            'datetime': 'fas fa-calendar-alt',
            'select': 'fas fa-list',
            'multiselect': 'fas fa-list-ul',
            'checkbox': 'fas fa-check-square',
            'email': 'fas fa-envelope',
            'phone': 'fas fa-phone',
            'url': 'fas fa-link'
        };
        return icons[type] || 'fas fa-question-circle';
    }
    
    /**
     * Select a field
     */
    selectField(fieldElement) {
        // Deselect previous
        document.querySelectorAll('.field-item.selected').forEach(el => {
            el.classList.remove('selected');
        });
        
        // Select new
        fieldElement.classList.add('selected');
        
        const fieldName = fieldElement.dataset.fieldName;
        const section = fieldElement.dataset.section;
        
        // Find field in schema
        const field = this.schema[section].find(f => f.name === fieldName);
        
        if (field) {
            this.selectedField = { field, section, element: fieldElement };
            // Update properties panel
            if (window.designerProperties) {
                window.designerProperties.loadFieldProperties(field, section);
            }
        }
    }
    
    /**
     * Clone a field
     */
    cloneField(field, section) {
        const clonedField = JSON.parse(JSON.stringify(field));
        clonedField.name = `${field.name}_copy`;
        clonedField.label = `${field.label} (Copy)`;
        
        // Ensure unique name
        let counter = 1;
        while (this.schema[section].find(f => f.name === clonedField.name)) {
            clonedField.name = `${field.name}_copy_${counter}`;
            clonedField.label = `${field.label} (Copy ${counter})`;
            counter++;
        }
        
        this.schema[section].push(clonedField);
        this.renderField(clonedField, section);
        this.saveState();
        this.markDirty();
        this.showToast(`Field "${clonedField.label}" cloned`, 'success');
    }
    
    /**
     * Delete a field
     */
    deleteField(fieldName, section) {
        if (!confirm(`Are you sure you want to delete this field?`)) {
            return;
        }
        
        const index = this.schema[section].findIndex(f => f.name === fieldName);
        if (index !== -1) {
            this.schema[section].splice(index, 1);
            
            // Remove from DOM
            const element = document.querySelector(`.field-item[data-field-name="${fieldName}"][data-section="${section}"]`);
            if (element) {
                element.style.transition = 'all 0.3s ease-out';
                element.style.opacity = '0';
                element.style.transform = 'scale(0.9)';
                setTimeout(() => element.remove(), 300);
            }
            
            this.saveState();
            this.markDirty();
            this.updateEmptyStates();
            this.showToast('Field deleted', 'success');
        }
    }
    
    /**
     * Handle field add event
     */
    handleFieldAdd(evt, section) {
        // This is handled by the drop event
    }
    
    /**
     * Handle field reorder
     */
    handleFieldReorder(evt, section) {
        // Rebuild schema order based on DOM
        const dropzone = section === 'header' ? 
            document.getElementById('header-dropzone') : 
            document.getElementById('lines-dropzone');
        
        const fieldElements = dropzone.querySelectorAll('.field-item');
        const newOrder = [];
        
        fieldElements.forEach(el => {
            const fieldName = el.dataset.fieldName;
            const field = this.schema[section].find(f => f.name === fieldName);
            if (field) {
                newOrder.push(field);
            }
        });
        
        this.schema[section] = newOrder;
        this.saveState();
        this.markDirty();
    }
    
    /**
     * Handle field remove
     */
    handleFieldRemove(evt, section) {
        // This is handled by delete action
    }
    
    /**
     * Update empty states
     */
    updateEmptyStates() {
        const headerZone = document.getElementById('header-dropzone');
        const linesZone = document.getElementById('lines-dropzone');
        
        if (headerZone.children.length === 0) {
            headerZone.classList.add('empty');
            headerZone.innerHTML = '<p>Drag fields here to build your header section</p>';
        } else {
            headerZone.classList.remove('empty');
        }
        
        if (linesZone.children.length === 0) {
            linesZone.classList.add('empty');
            linesZone.innerHTML = '<p>Drag fields here to build your line items section</p>';
        } else {
            linesZone.classList.remove('empty');
        }
    }
    
    /**
     * Save current state for undo
     */
    saveState() {
        const state = JSON.parse(JSON.stringify(this.schema));
        this.undoStack.push(state);
        
        if (this.undoStack.length > this.maxUndoStack) {
            this.undoStack.shift();
        }
        
        this.redoStack = [];
        this.updateUndoRedoButtons();
    }
    
    /**
     * Undo last action
     */
    undo() {
        if (this.undoStack.length > 0) {
            const currentState = JSON.parse(JSON.stringify(this.schema));
            this.redoStack.push(currentState);
            
            const previousState = this.undoStack.pop();
            this.schema = previousState;
            
            this.reloadCanvas();
            this.markDirty();
            this.updateUndoRedoButtons();
            this.showToast('Undo successful', 'info');
        }
    }
    
    /**
     * Redo last undone action
     */
    redo() {
        if (this.redoStack.length > 0) {
            const currentState = JSON.parse(JSON.stringify(this.schema));
            this.undoStack.push(currentState);
            
            const nextState = this.redoStack.pop();
            this.schema = nextState;
            
            this.reloadCanvas();
            this.markDirty();
            this.updateUndoRedoButtons();
            this.showToast('Redo successful', 'info');
        }
    }
    
    /**
     * Reload canvas from schema
     */
    reloadCanvas() {
        document.getElementById('header-dropzone').innerHTML = '';
        document.getElementById('lines-dropzone').innerHTML = '';
        this.loadSchema();
    }
    
    /**
     * Update undo/redo button states
     */
    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('btn-undo');
        const redoBtn = document.getElementById('btn-redo');
        
        undoBtn.disabled = this.undoStack.length === 0;
        redoBtn.disabled = this.redoStack.length === 0;
    }
    
    /**
     * Mark schema as dirty (unsaved changes)
     */
    markDirty() {
        this.isDirty = true;
        const saveBtn = document.getElementById('btn-save');
        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fas fa-save"></i><span>Save Draft *</span>';
        }
    }
    
    /**
     * Mark schema as clean (saved)
     */
    markClean() {
        this.isDirty = false;
        const saveBtn = document.getElementById('btn-save');
        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fas fa-save"></i><span>Save Draft</span>';
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Save button
        document.getElementById('btn-save')?.addEventListener('click', () => {
            this.saveSchema();
        });
        
        // Publish button
        document.getElementById('btn-publish')?.addEventListener('click', () => {
            this.publishSchema();
        });
        
        // Undo/Redo buttons
        document.getElementById('btn-undo')?.addEventListener('click', () => {
            this.undo();
        });
        
        document.getElementById('btn-redo')?.addEventListener('click', () => {
            this.redo();
        });
        
        // Clear buttons
        document.getElementById('btn-clear-header')?.addEventListener('click', () => {
            if (confirm('Clear all header fields?')) {
                this.schema.header = [];
                this.reloadCanvas();
                this.saveState();
                this.markDirty();
            }
        });
        
        document.getElementById('btn-clear-lines')?.addEventListener('click', () => {
            if (confirm('Clear all line fields?')) {
                this.schema.lines = [];
                this.reloadCanvas();
                this.saveState();
                this.markDirty();
            }
        });
        
        // Field search
        document.getElementById('field-search')?.addEventListener('input', (e) => {
            this.filterFields(e.target.value);
        });
        
        // Sidebar tabs
        document.querySelectorAll('.sidebar-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                this.switchTab(tabName);
            });
        });
    }
    
    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+Z - Undo
            if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
            }
            
            // Ctrl+Y or Ctrl+Shift+Z - Redo
            if ((e.ctrlKey && e.key === 'y') || (e.ctrlKey && e.shiftKey && e.key === 'z')) {
                e.preventDefault();
                this.redo();
            }
            
            // Ctrl+S - Save
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveSchema();
            }
            
            // Delete - Delete selected field
            if (e.key === 'Delete' && this.selectedField && !this.selectedField.field.locked) {
                e.preventDefault();
                this.deleteField(this.selectedField.field.name, this.selectedField.section);
                this.selectedField = null;
            }
        });
    }
    
    /**
     * Setup auto-save
     */
    setupAutoSave() {
        this.autoSaveInterval = setInterval(() => {
            if (this.isDirty) {
                this.saveSchema(true); // Silent auto-save
            }
        }, 60000); // Auto-save every 60 seconds
    }
    
    /**
     * Filter fields in palette
     */
    filterFields(query) {
        const items = document.querySelectorAll('.field-palette-item');
        const searchQuery = query.toLowerCase();
        
        items.forEach(item => {
            const fieldName = item.querySelector('.field-name').textContent.toLowerCase();
            const fieldType = item.querySelector('.field-type').textContent.toLowerCase();
            
            if (fieldName.includes(searchQuery) || fieldType.includes(searchQuery)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    /**
     * Switch sidebar tab
     */
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.sidebar-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`.sidebar-tab[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = 'none';
        });
        document.querySelector(`[data-tab-content="${tabName}"]`).style.display = 'block';
    }
    
    /**
     * Save schema
     */
    async saveSchema(silent = false) {
        try {
            const response = await fetch(`/forms_designer/designer/${this.configId}/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(this.schema)
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.markClean();
                if (!silent) {
                    this.showToast('Schema saved successfully', 'success');
                }
            } else {
                throw new Error(data.message || 'Save failed');
            }
        } catch (error) {
            console.error('Save error:', error);
            if (!silent) {
                this.showToast('Error saving schema: ' + error.message, 'error');
            }
        }
    }
    
    /**
     * Publish schema
     */
    async publishSchema() {
        if (!confirm('Publish this schema? This will make it the active version.')) {
            return;
        }
        
        try {
            // First save
            await this.saveSchema(true);
            
            // Then publish via API
            const response = await fetch(`/api/forms-designer/schemas/publish/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    config_id: this.configId
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showToast('Schema published successfully', 'success');
                // Update status badge
                const statusEl = document.getElementById('schema-status');
                statusEl.className = 'toolbar-status status-published';
                statusEl.innerHTML = '<i class="fas fa-circle" style="font-size: 0.5rem;"></i><span>Published</span>';
            } else {
                throw new Error(data.message || 'Publish failed');
            }
        } catch (error) {
            console.error('Publish error:', error);
            this.showToast('Error publishing schema: ' + error.message, 'error');
        }
    }
    
    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <i class="fas ${icons[type]}" style="color: ${colors[type]}; font-size: 1.25rem;"></i>
                <span>${message}</span>
            </div>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    /**
     * Get CSRF token
     */
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               document.getElementById('csrf-token')?.value ||
               '';
    }
    
    /**
     * Cleanup
     */
    destroy() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
        }
        
        if (this.headerSortable) {
            this.headerSortable.destroy();
        }
        
        if (this.linesSortable) {
            this.linesSortable.destroy();
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const configId = document.getElementById('config-id')?.value;
    const schemaData = document.getElementById('schema-data')?.value;
    
    if (configId) {
        let schema = { header: [], lines: [] };
        
        if (schemaData) {
            try {
                schema = JSON.parse(schemaData);
            } catch (e) {
                console.error('Error parsing schema:', e);
            }
        }
        
        window.designerEngine = new FormsDesignerEngine({
            configId,
            schema
        });
    }
});
