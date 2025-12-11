/**
 * Forms Designer - Properties Panel
 * Handles field property editing
 */

class DesignerProperties {
    constructor(engine) {
        this.engine = engine;
        this.currentField = null;
        this.currentSection = null;
        this.init();
    }
    
    init() {
        // Properties panel is loaded dynamically when a field is selected
    }
    
    /**
     * Load field properties into the properties panel
     */
    loadFieldProperties(field, section) {
        this.currentField = field;
        this.currentSection = section;
        
        const content = document.getElementById('properties-content');
        content.innerHTML = this.generatePropertiesHTML(field, section);
        
        // Attach event listeners
        this.attachPropertyListeners();
    }
    
    /**
     * Generate HTML for properties panel
     */
    generatePropertiesHTML(field, section) {
        return `
            <div class="property-group">
                <div class="property-group-title">
                    <i class="fas fa-info-circle"></i>
                    Basic Properties
                </div>
                
                <div class="property-field">
                    <label class="property-label">Field Name</label>
                    <input type="text" 
                           class="property-input" 
                           data-property="name"
                           value="${field.name}" 
                           ${field.locked ? 'disabled' : ''}>
                </div>
                
                <div class="property-field">
                    <label class="property-label">Label</label>
                    <input type="text" 
                           class="property-input" 
                           data-property="label"
                           value="${field.label || ''}" 
                           ${field.locked ? 'disabled' : ''}>
                </div>
                
                <div class="property-field">
                    <label class="property-label">Help Text</label>
                    <textarea class="property-textarea" 
                              data-property="help_text" 
                              ${field.locked ? 'disabled' : ''}>${field.help_text || ''}</textarea>
                </div>
                
                <div class="property-field">
                    <label class="property-label">Placeholder</label>
                    <input type="text" 
                           class="property-input" 
                           data-property="placeholder"
                           value="${field.placeholder || ''}" 
                           ${field.locked ? 'disabled' : ''}>
                </div>
                
                <div class="property-field">
                    <label class="property-label">Default Value</label>
                    <input type="text" 
                           class="property-input" 
                           data-property="default_value"
                           value="${field.default_value || ''}" 
                           ${field.locked ? 'disabled' : ''}>
                </div>
                
                <div class="property-checkbox">
                    <input type="checkbox" 
                           id="prop-required" 
                           data-property="required"
                           ${field.required ? 'checked' : ''}
                           ${field.locked ? 'disabled' : ''}>
                    <label for="prop-required" class="property-label">Required Field</label>
                </div>
            </div>
            
            <div class="property-group">
                <div class="property-group-title">
                    <i class="fas fa-th"></i>
                    Layout & Grid
                </div>
                
                <div class="grid-layout-control">
                    <div class="property-field">
                        <label class="property-label">Column Width</label>
                        <select class="property-select" data-property="grid_column_width" ${field.locked ? 'disabled' : ''}>
                            <option value="3" ${field.grid_column_width === 3 ? 'selected' : ''}>3/12 (25%)</option>
                            <option value="4" ${field.grid_column_width === 4 ? 'selected' : ''}>4/12 (33%)</option>
                            <option value="6" ${field.grid_column_width === 6 ? 'selected' : ''}>6/12 (50%)</option>
                            <option value="8" ${field.grid_column_width === 8 ? 'selected' : ''}>8/12 (66%)</option>
                            <option value="9" ${field.grid_column_width === 9 ? 'selected' : ''}>9/12 (75%)</option>
                            <option value="12" ${(field.grid_column_width === 12 || !field.grid_column_width) ? 'selected' : ''}>12/12 (100%)</option>
                        </select>
                    </div>
                    
                    <div class="property-field">
                        <label class="property-label">Offset</label>
                        <select class="property-select" data-property="grid_column_offset" ${field.locked ? 'disabled' : ''}>
                            <option value="0" ${!field.grid_column_offset ? 'selected' : ''}>None</option>
                            <option value="1" ${field.grid_column_offset === 1 ? 'selected' : ''}>1 Column</option>
                            <option value="2" ${field.grid_column_offset === 2 ? 'selected' : ''}>2 Columns</option>
                            <option value="3" ${field.grid_column_offset === 3 ? 'selected' : ''}>3 Columns</option>
                            <option value="4" ${field.grid_column_offset === 4 ? 'selected' : ''}>4 Columns</option>
                        </select>
                    </div>
                </div>
                
                <div class="property-field">
                    <label class="property-label">CSS Class</label>
                    <input type="text" 
                           class="property-input" 
                           data-property="css_class"
                           value="${field.css_class || ''}" 
                           ${field.locked ? 'disabled' : ''}>
                </div>
            </div>
            
            <div class="property-group">
                <div class="property-group-title property-group-toggle" data-toggle="validation">
                    <i class="fas fa-chevron-right" style="font-size: 0.75rem; transition: transform 0.2s;"></i>
                    <i class="fas fa-check-circle"></i>
                    Validation Rules
                </div>
                <div class="property-group-content" data-content="validation" style="display: none;">
                    ${this.generateValidationHTML(field)}
                </div>
            </div>
            
            <div class="property-group">
                <div class="property-group-title property-group-toggle" data-toggle="visibility">
                    <i class="fas fa-chevron-right" style="font-size: 0.75rem; transition: transform 0.2s;"></i>
                    <i class="fas fa-eye"></i>
                    Visibility Conditions
                </div>
                <div class="property-group-content" data-content="visibility" style="display: none;">
                    ${this.generateVisibilityHTML(field)}
                </div>
            </div>
            
            ${!field.locked ? `
            <div class="property-group">
                <button type="button" class="btn-toolbar btn-primary" id="apply-properties" style="width: 100%;">
                    <i class="fas fa-check"></i>
                    Apply Changes
                </button>
            </div>
            ` : ''}
        `;
    }
    
    /**
     * Generate validation rules HTML
     */
    generateValidationHTML(field) {
        const validation = field.validation_rules || {};
        
        if (field.type === 'number' || field.type === 'decimal') {
            return `
                <div class="property-field">
                    <label class="property-label">Minimum Value</label>
                    <input type="number" 
                           class="property-input" 
                           data-validation="min_value"
                           value="${validation.min_value || ''}" 
                           step="any">
                </div>
                
                <div class="property-field">
                    <label class="property-label">Maximum Value</label>
                    <input type="number" 
                           class="property-input" 
                           data-validation="max_value"
                           value="${validation.max_value || ''}" 
                           step="any">
                </div>
            `;
        } else if (field.type === 'text' || field.type === 'textarea') {
            return `
                <div class="property-field">
                    <label class="property-label">Minimum Length</label>
                    <input type="number" 
                           class="property-input" 
                           data-validation="min_length"
                           value="${validation.min_length || ''}" 
                           min="0">
                </div>
                
                <div class="property-field">
                    <label class="property-label">Maximum Length</label>
                    <input type="number" 
                           class="property-input" 
                           data-validation="max_length"
                           value="${validation.max_length || ''}" 
                           min="0">
                </div>
                
                <div class="property-field">
                    <label class="property-label">Regex Pattern</label>
                    <input type="text" 
                           class="property-input" 
                           data-validation="regex"
                           value="${validation.regex || ''}" 
                           placeholder="e.g., ^[A-Z]{3}-[0-9]{4}$">
                </div>
            `;
        }
        
        return '<p style="color: #6b7280; font-size: 0.875rem;">No validation rules available for this field type.</p>';
    }
    
    /**
     * Generate visibility conditions HTML
     */
    generateVisibilityHTML(field) {
        const visibility = field.visibility_rules || { enabled: false, conditions: [], action: 'show' };
        
        return `
            <div class="property-checkbox">
                <input type="checkbox" 
                       id="prop-visibility-enabled" 
                       data-visibility="enabled"
                       ${visibility.enabled ? 'checked' : ''}>
                <label for="prop-visibility-enabled" class="property-label">Enable Conditional Visibility</label>
            </div>
            
            <div id="visibility-conditions" style="display: ${visibility.enabled ? 'block' : 'none'};">
                <div class="property-field">
                    <label class="property-label">Action</label>
                    <select class="property-select" data-visibility="action">
                        <option value="show" ${visibility.action === 'show' ? 'selected' : ''}>Show</option>
                        <option value="hide" ${visibility.action === 'hide' ? 'selected' : ''}>Hide</option>
                        <option value="enable" ${visibility.action === 'enable' ? 'selected' : ''}>Enable</option>
                        <option value="disable" ${visibility.action === 'disable' ? 'selected' : ''}>Disable</option>
                    </select>
                </div>
                
                <p style="color: #6b7280; font-size: 0.875rem; margin-top: 0.5rem;">
                    <i class="fas fa-info-circle"></i>
                    Advanced condition builder coming soon. For now, conditions can be configured via schema JSON.
                </p>
            </div>
        `;
    }
    
    /**
     * Attach event listeners to property inputs
     */
    attachPropertyListeners() {
        // Toggle groups
        document.querySelectorAll('.property-group-toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                const contentId = toggle.dataset.toggle;
                const content = document.querySelector(`[data-content="${contentId}"]`);
                const icon = toggle.querySelector('.fa-chevron-right');
                
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    icon.style.transform = 'rotate(90deg)';
                } else {
                    content.style.display = 'none';
                    icon.style.transform = 'rotate(0deg)';
                }
            });
        });
        
        // Visibility enabled checkbox
        const visibilityEnabledCheckbox = document.getElementById('prop-visibility-enabled');
        if (visibilityEnabledCheckbox) {
            visibilityEnabledCheckbox.addEventListener('change', (e) => {
                const conditionsDiv = document.getElementById('visibility-conditions');
                conditionsDiv.style.display = e.target.checked ? 'block' : 'none';
            });
        }
        
        // Apply button
        const applyBtn = document.getElementById('apply-properties');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyProperties();
            });
        }
        
        // Real-time updates for certain properties
        document.querySelectorAll('[data-property]').forEach(input => {
            input.addEventListener('blur', () => {
                this.applyProperties();
            });
        });
    }
    
    /**
     * Apply property changes to the field
     */
    applyProperties() {
        if (!this.currentField) return;
        
        // Track styling changes (width, padding, background)
        const stylingProperties = ['custom_width', 'padding', 'background', 'background_color', 'css_class'];
        let hasStylingChanges = false;
        
        // Collect all property values
        document.querySelectorAll('[data-property]').forEach(input => {
            const property = input.dataset.property;
            let value;
            
            if (input.type === 'checkbox') {
                value = input.checked;
            } else if (input.type === 'number') {
                value = parseInt(input.value, 10);
            } else {
                value = input.value;
            }
            
            // Check if this is a styling property with a new value
            if (stylingProperties.includes(property) && value && value !== this.currentField[property]) {
                hasStylingChanges = true;
            }
            
            this.currentField[property] = value;
        });
        
        // Collect validation rules
        const validationRules = {};
        document.querySelectorAll('[data-validation]').forEach(input => {
            const rule = input.dataset.validation;
            if (input.value) {
                validationRules[rule] = input.type === 'number' ? parseFloat(input.value) : input.value;
            }
        });
        this.currentField.validation_rules = validationRules;
        
        // Collect visibility rules
        const visibilityRules = {
            enabled: document.getElementById('prop-visibility-enabled')?.checked || false,
            conditions: this.currentField.visibility_rules?.conditions || [],
            action: document.querySelector('[data-visibility="action"]')?.value || 'show'
        };
        this.currentField.visibility_rules = visibilityRules;
        
        // Update the field element in DOM
        const fieldElement = document.querySelector(
            `.field-item[data-field-name="${this.currentField.name}"][data-section="${this.currentSection}"]`
        );
        
        if (fieldElement) {
            // Update grid width
            fieldElement.style.gridColumn = `span ${this.currentField.grid_column_width || 12}`;
            fieldElement.dataset.gridWidth = this.currentField.grid_column_width || 12;
            
            // Update label
            const labelEl = fieldElement.querySelector('.field-item-label');
            if (labelEl) {
                const icon = this.engine.getFieldIcon(this.currentField.type);
                const requiredBadge = this.currentField.required ? '<span class="field-required-badge">Required</span>' : '';
                labelEl.innerHTML = `
                    <i class="${icon}" style="margin-right: 0.5rem; color: var(--primary-color);"></i>
                    ${this.currentField.label}
                    ${requiredBadge}
                `;
            }
            
            // Update preview
            const previewEl = fieldElement.querySelector('.field-item-preview');
            if (previewEl) {
                previewEl.textContent = this.currentField.help_text || 'No help text';
            }
        }
        
        // Mark as dirty and save state
        this.engine.markDirty();
        this.engine.saveState();
        
        // Show feedback
        this.engine.showToast('Properties updated', 'success');
        
        // If styling properties changed, ask to refresh
        if (hasStylingChanges) {
            this.showRefreshConfirmation();
        }
    }
    
    /**
     * Show SweetAlert confirmation to refresh page for styling changes
     */
    showRefreshConfirmation() {
        Swal.fire({
            title: 'Custom width, padding, background.',
            html: '<p style="margin: 1rem 0; color: #666; font-size: 0.95rem;">Styling changes have been detected. Refresh the page to see the updates applied to your components.</p>',
            icon: 'info',
            width: 600,
            padding: '100px',
            background: 'rgb(224, 225, 243)',
            confirmButtonText: 'Refresh Page',
            confirmButtonColor: '#1c84ee',
            showCancelButton: true,
            cancelButtonText: 'Later',
            cancelButtonColor: '#6b7280',
            didOpen: (modal) => {
                // Apply additional styling to the modal if needed
                modal.style.display = 'grid';
            }
        }).then((result) => {
            if (result.isConfirmed) {
                // Refresh the page
                window.location.reload();
            }
        });
    }
}

// Initialize when engine is ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait for engine to be initialized
    const checkEngine = setInterval(() => {
        if (window.designerEngine) {
            window.designerProperties = new DesignerProperties(window.designerEngine);
            clearInterval(checkEngine);
        }
    }, 100);
});
