/**
 * Voucher HTMX Event Handlers Module
 * Integrations between HTMX events and form behavior
 */

(function() {
    'use strict';

    class VoucherHtmxHandlers {
        constructor() {
            this.initialized = false;
            this.init();
        }

        /**
         * Initialize HTMX event handlers
         */
        init() {
            // Before request
            document.addEventListener('htmx:beforeRequest', (e) => {
                this.onBeforeRequest(e);
            });

            // After response
            document.addEventListener('htmx:afterSettle', (e) => {
                this.onAfterSettle(e);
            });

            // On error
            document.addEventListener('htmx:responseError', (e) => {
                this.onResponseError(e);
            });

            // On success
            document.addEventListener('htmx:afterSwap', (e) => {
                this.onAfterSwap(e);
            });

            // Confirm before action
            document.addEventListener('htmx:confirm', (e) => {
                this.onConfirm(e);
            });

            this.initialized = true;
            console.log('✓ VoucherHtmxHandlers initialized');
        }

        /**
         * Before HTMX request
         * @param {Event} e
         */
        onBeforeRequest(e) {
            const element = e.detail.xhr.target;

            // Show loading indicator for buttons
            if (element && element.tagName === 'BUTTON') {
                const originalText = element.innerHTML;
                element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
                element.disabled = true;

                // Restore on error/complete
                element.addEventListener('htmx:afterSettle', () => {
                    element.innerHTML = originalText;
                    element.disabled = false;
                }, { once: true });
            }

            console.log('HTMX Request started:', element?.getAttribute('hx-get') || element?.getAttribute('hx-post'));
        }

        /**
         * After HTMX settles
         * @param {Event} e
         */
        onAfterSettle(e) {
            const target = e.detail.target;
            const xhr = e.detail.xhr;

            // Update line totals after adding/removing lines
            if (target.id === 'line-formset' && window.voucherTotals) {
                window.voucherTotals.updateTotals();
                console.log('Totals updated after line change');
            }

            // Reinitialize form listeners for new elements
            if (target.id === 'line-formset' && window.voucherForms) {
                window.voucherForms.initializeNewInputs();
            }

            // Handle success messages
            if (target.classList.contains('alert-success')) {
                setTimeout(() => {
                    target.style.opacity = '1';
                    setTimeout(() => {
                        if (target.parentElement) {
                            target.remove();
                        }
                    }, 3000);
                }, 500);
            }
        }

        /**
         * Handle HTMX response errors
         * @param {Event} e
         */
        onResponseError(e) {
            const xhr = e.detail.xhr;
            const target = e.detail.target;

            console.error(`HTMX Error - Status: ${xhr.status}`, target);

            // Display error message
            const errorMsg = document.createElement('div');
            errorMsg.className = 'alert alert-danger alert-dismissible fade show';
            errorMsg.innerHTML = `
                <strong>Error:</strong> Request failed (${xhr.status})
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;

            target.parentElement?.insertBefore(errorMsg, target);
        }

        /**
         * After HTMX swap
         * @param {Event} e
         */
        onAfterSwap(e) {
            const target = e.detail.target;

            // Reinitialize Bootstrap components
            this.initializeBootstrapComponents(target);

            // Trigger custom event
            document.dispatchEvent(new CustomEvent('voucherHtmxSwapped', {
                detail: { target }
            }));
        }

        /**
         * Confirm action before proceeding
         * @param {Event} e
         */
        onConfirm(e) {
            const element = e.detail.target;
            const message = element.getAttribute('hx-confirm');

            if (!message) return;

            // Use Bootstrap modal for better UX
            const confirmed = confirm(message);

            if (!confirmed) {
                e.preventDefault();
            }

            console.log(`Action confirmed: ${message} - Result: ${confirmed}`);
        }

        /**
         * Initialize Bootstrap components in newly added elements
         * @param {HTMLElement} container
         */
        initializeBootstrapComponents(container) {
            // Reinitialize tooltips
            const tooltips = container.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(tooltip => {
                if (typeof bootstrap !== 'undefined') {
                    new bootstrap.Tooltip(tooltip);
                }
            });

            // Reinitialize popovers
            const popovers = container.querySelectorAll('[data-bs-toggle="popover"]');
            popovers.forEach(popover => {
                if (typeof bootstrap !== 'undefined') {
                    new bootstrap.Popover(popover);
                }
            });

            // Reinitialize dropdowns
            const dropdowns = container.querySelectorAll('[data-bs-toggle="dropdown"]');
            dropdowns.forEach(dropdown => {
                if (typeof bootstrap !== 'undefined') {
                    new bootstrap.Dropdown(dropdown);
                }
            });
        }

        /**
         * Send HTMX request with validation
         * @param {String} url
         * @param {Object} options
         */
        sendRequest(url, options = {}) {
            const method = options.method || 'get';
            const data = options.data || {};
            const target = options.target;
            const swap = options.swap || 'innerHTML';

            htmx.ajax(method, url, {
                target: target,
                swap: swap,
                values: data
            });
        }

        /**
         * Close modal and refresh page
         */
        closeModalAndRefresh() {
            const modal = document.querySelector('.modal.show');
            if (modal && typeof bootstrap !== 'undefined') {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            }

            // Refresh after modal closes
            setTimeout(() => {
                window.location.reload();
            }, 300);
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.voucherHtmxHandlers = new VoucherHtmxHandlers();
    });

    // Expose globally
    window.VoucherHtmxHandlers = VoucherHtmxHandlers;
})();
