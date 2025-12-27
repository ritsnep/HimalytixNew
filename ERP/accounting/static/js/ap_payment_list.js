/**
 * AP Payment Enhanced JavaScript Functionality
 * 
 * This file provides enhanced interactivity for the AP Payment list page
 * including advanced filtering, bulk operations, and real-time updates.
 */

class APPaymentManager {
    constructor() {
        this.selectedPayments = new Set();
        this.filterTimeout = null;
        this.isProcessing = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeComponents();
        this.loadInitialState();
    }

    bindEvents() {
        // Filter events
        $('#filterForm input, #filterForm select').on('change', () => {
            this.debounceFilter();
        });

        // Table selection events
        $('#selectAll').on('change', (e) => {
            this.handleSelectAll(e.target.checked);
        });

        $('.payment-checkbox').on('change', (e) => {
            this.handlePaymentSelection(e.target);
        });

        // Keyboard shortcuts
        $(document).on('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
    }

    initializeComponents() {
        // Initialize Select2 for vendor dropdown
        if ($('#vendor').length) {
            $('#vendor').select2({
                theme: 'bootstrap-5',
                placeholder: 'All Vendors',
                allowClear: true,
                width: '100%'
            });
        }

        // Initialize Bootstrap tooltips
        document.querySelectorAll('[title]').forEach(function (element) {
            new bootstrap.Tooltip(element);
        });

        // Initialize date pickers if needed
        this.initializeDatePickers();

        // Setup auto-refresh
        this.setupAutoRefresh();
    }

    initializeDatePickers() {
        // Add date picker functionality if not using HTML5 date inputs
        const dateInputs = ['#date_from', '#date_to'];
        dateInputs.forEach(selector => {
            const element = $(selector);
            if (element.length && element.attr('type') !== 'date') {
                element.datepicker({
                    format: 'yyyy-mm-dd',
                    autoclose: true,
                    todayHighlight: true
                });
            }
        });
    }

    setupAutoRefresh() {
        // Auto-refresh summary every 30 seconds
        setInterval(() => {
            this.refreshSummary();
        }, 30000);
    }

    loadInitialState() {
        // Load any saved filter states from localStorage
        this.loadSavedFilters();
        
        // Initialize bulk actions visibility
        this.updateBulkActions();
    }

    debounceFilter() {
        clearTimeout(this.filterTimeout);
        this.filterTimeout = setTimeout(() => {
            this.applyFilters();
        }, 500);
    }

    applyFilters() {
        const formData = new FormData($('#filterForm')[0]);
        const params = new URLSearchParams(formData);
        
        // Add pagination info if present
        const currentPage = new URLSearchParams(window.location.search).get('page');
        if (currentPage) {
            params.set('page', currentPage);
        }

        // Update URL without reload
        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.history.replaceState({}, '', newUrl);
        
        // Submit form
        $('#filterForm')[0].submit();
    }

    handleSelectAll(isChecked) {
        $('.payment-checkbox').prop('checked', isChecked);
        this.updateSelectedPayments();
        this.updateBulkActions();
    }

    handlePaymentSelection(checkbox) {
        const paymentId = parseInt(checkbox.value);
        
        if (checkbox.checked) {
            this.selectedPayments.add(paymentId);
        } else {
            this.selectedPayments.delete(paymentId);
            $('#selectAll').prop('checked', false);
        }
        
        this.updateBulkActions();
    }

    updateSelectedPayments() {
        this.selectedPayments.clear();
        $('.payment-checkbox:checked').each((index, checkbox) => {
            this.selectedPayments.add(parseInt(checkbox.value));
        });
    }

    updateBulkActions() {
        const count = this.selectedPayments.size;
        const bulkCard = $('#bulkActionsCard');
        const selectedCount = $('#selectedCount');

        if (count > 0) {
            bulkCard.removeClass('d-none');
            selectedCount.text(count);
        } else {
            bulkCard.addClass('d-none');
        }
    }

    handleKeyboardShortcuts(e) {
        // Ctrl+A: Select all visible payments
        if (e.ctrlKey && e.key === 'a' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
            e.preventDefault();
            $('#selectAll').prop('checked', true).trigger('change');
        }
        
        // Escape: Clear selections
        if (e.key === 'Escape') {
            $('.payment-checkbox').prop('checked', false);
            $('#selectAll').prop('checked', false);
            this.updateSelectedPayments();
            this.updateBulkActions();
        }
        
        // Delete: Cancel selected payments
        if (e.key === 'Delete' && this.selectedPayments.size > 0) {
            e.preventDefault();
            this.bulkAction('cancel');
        }
    }

    clearFilters() {
        // Reset form
        $('#filterForm')[0].reset();
        
        // Clear Select2
        if ($('#vendor').data('select2')) {
            $('#vendor').val(null).trigger('change');
        }
        
        // Clear localStorage
        localStorage.removeItem('apPaymentFilters');
        
        // Submit form
        window.location.href = window.location.pathname;
    }

    exportData() {
        const params = new URLSearchParams(window.location.search);
        params.set('export', 'csv');
        
        // Show loading
        this.showLoading('Exporting data...');
        
        // Create temporary link and trigger download
        const link = document.createElement('a');
        link.href = `${window.location.pathname}?${params.toString()}`;
        link.download = 'ap-payments.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        setTimeout(() => {
            this.hideLoading();
        }, 1000);
    }

    bulkAction(action) {
        if (this.selectedPayments.size === 0) {
            this.showAlert('Please select at least one payment.', 'warning');
            return;
        }

        const paymentIds = Array.from(this.selectedPayments);
        this.showBulkActionModal(action, paymentIds);
    }

    singleAction(paymentId, action) {
        this.showBulkActionModal(action, [paymentId]);
    }

    showBulkActionModal(action, paymentIds) {
        const actionText = action.charAt(0).toUpperCase() + action.slice(1);
        const count = paymentIds.length;
        
        let confirmationText = '';
        let warningColor = 'warning';
        
        switch (action) {
            case 'approve':
                confirmationText = `approve ${count} payment(s). This will mark them as approved for execution.`;
                break;
            case 'execute':
                confirmationText = `execute ${count} payment(s). This will post the journal entries and cannot be undone.`;
                warningColor = 'danger';
                break;
            case 'reconcile':
                confirmationText = `reconcile ${count} payment(s). This will mark them as fully reconciled.`;
                break;
            case 'cancel':
                confirmationText = `cancel ${count} payment(s). This action cannot be undone.`;
                warningColor = 'danger';
                break;
        }

        const content = `
            <div class="alert alert-${warningColor}">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Warning:</strong> You are about to ${confirmationText}
            </div>
            <p>Are you sure you want to proceed?</p>
            <div class="mb-3">
                <label for="actionNotes" class="form-label">Notes (Optional):</label>
                <textarea class="form-control" id="actionNotes" rows="3" 
                          placeholder="Add notes for this action..."></textarea>
            </div>
        `;

        $('#bulkActionContent').html(content);
        $('#bulkActionModal').modal('show');

        // Handle confirm button
        $('#confirmBulkAction').off('click').on('click', () => {
            const notes = $('#actionNotes').val();
            this.executeBulkAction(action, paymentIds, notes);
            $('#bulkActionModal').modal('hide');
        });
    }

    async executeBulkAction(action, paymentIds, notes) {
        if (this.isProcessing) return;
        
        this.isProcessing = true;
        this.showLoading(`Processing ${action} operation...`);

        try {
            const response = await this.makeAjaxRequest({
                url: '/accounting/ap-payments/bulk-action/',
                method: 'POST',
                data: {
                    action: action,
                    payment_ids: paymentIds,
                    notes: notes
                }
            });

            this.handleBulkActionResponse(response, action);
        } catch (error) {
            this.handleBulkActionError(error);
        } finally {
            this.isProcessing = false;
            this.hideLoading();
        }
    }

    async makeAjaxRequest(options) {
        return new Promise((resolve, reject) => {
            $.ajax({
                url: options.url,
                method: options.method,
                contentType: 'application/json',
                data: JSON.stringify(options.data),
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                },
                success: resolve,
                error: reject
            });
        });
    }

    handleBulkActionResponse(response, action) {
        if (response.success) {
            const successCount = response.successful_count || 0;
            const failedCount = response.failed_count || 0;
            
            if (failedCount > 0) {
                this.showAlert(`${action} completed with ${failedCount} errors. Check results for details.`, 'warning');
            } else {
                this.showAlert(`Successfully ${action}d ${successCount} payment(s).`, 'success');
            }

            // Clear selections
            $('.payment-checkbox').prop('checked', false);
            $('#selectAll').prop('checked', false);
            this.selectedPayments.clear();
            this.updateBulkActions();

            // Refresh page after delay
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            this.showAlert(response.error || 'Operation failed.', 'danger');
        }
    }

    handleBulkActionError(error) {
        let errorMessage = 'An error occurred during the operation.';
        
        try {
            const response = JSON.parse(error.responseText);
            errorMessage = response.error || errorMessage;
        } catch (e) {
            console.error('Error parsing response:', e);
        }
        
        this.showAlert(errorMessage, 'danger');
    }

    async refreshSummary() {
        try {
            const response = await fetch('/accounting/ap-payments/summary-ajax/?organization_id=' + this.getCurrentOrganizationId());
            const data = await response.json();
            
            if (data.success) {
                this.updateSummaryCards(data.summary);
            }
        } catch (error) {
            console.error('Failed to refresh summary:', error);
        }
    }

    updateSummaryCards(summary) {
        // Update summary card values with animation
        Object.keys(summary).forEach(key => {
            const element = $(`.${key.replace('_count', '')}-count`);
            if (element.length) {
                this.animateNumber(element, parseInt(element.text()) || 0, summary[key]);
            }
        });
    }

    animateNumber(element, start, end) {
        const duration = 1000;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            const current = Math.floor(start + (end - start) * progress);
            element.text(current.toLocaleString());
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    showLoading(message = 'Processing...') {
        $('#loadingOverlay').removeClass('d-none');
        $('.loading-spinner p').text(message);
    }

    hideLoading() {
        $('#loadingOverlay').addClass('d-none');
    }

    showAlert(message, type) {
        const alertClass = `alert-${type}`;
        const iconClass = type === 'success' ? 'fa-check-circle' : 
                         type === 'warning' ? 'fa-exclamation-triangle' : 
                         type === 'danger' ? 'fa-times-circle' : 'fa-info-circle';
        
        const alertHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                <i class="fas ${iconClass} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Remove existing alerts
        $('.alert').remove();
        
        // Add new alert
        $('.container-fluid').prepend(alertHtml);
        
        // Auto-hide success messages
        if (type === 'success') {
            setTimeout(() => {
                $('.alert-success').fadeOut();
            }, 5000);
        }
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
               '';
    }

    getCurrentOrganizationId() {
        // Extract organization ID from URL or data attribute
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('organization_id') || 
               document.querySelector('[data-organization-id]')?.getAttribute('data-organization-id') ||
               '';
    }

    saveFilters() {
        const filters = {};
        $('#filterForm').serializeArray().forEach(item => {
            filters[item.name] = item.value;
        });
        localStorage.setItem('apPaymentFilters', JSON.stringify(filters));
    }

    loadSavedFilters() {
        const saved = localStorage.getItem('apPaymentFilters');
        if (saved) {
            try {
                const filters = JSON.parse(saved);
                Object.keys(filters).forEach(name => {
                    const element = $(`[name="${name}"]`);
                    if (element.length) {
                        element.val(filters[name]);
                    }
                });
            } catch (e) {
                console.error('Failed to load saved filters:', e);
            }
        }
    }

    // Utility method to format currency
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }

    // Utility method to format date
    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
}

// Initialize when document is ready
$(document).ready(function() {
    // Only initialize on the AP payment list page
    if ($('#paymentsTable').length) {
        window.apPaymentManager = new APPaymentManager();
    }
});

// Global wrapper functions for onclick handlers
function bulkAction(action) {
    if (window.apPaymentManager) {
        window.apPaymentManager.bulkAction(action);
    }
}

function singleAction(paymentId, action) {
    if (window.apPaymentManager) {
        window.apPaymentManager.singleAction(paymentId, action);
    }
}

function clearFilters() {
    if (window.apPaymentManager) {
        window.apPaymentManager.clearFilters();
    }
}

function exportData() {
    if (window.apPaymentManager) {
        window.apPaymentManager.exportData();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = APPaymentManager;
}
