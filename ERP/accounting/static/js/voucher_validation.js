/**
 * Voucher Validation Module
 * Client-side form validation before submission
 */

(function() {
    'use strict';

    class VoucherValidation {
        constructor() {
            this.form = document.querySelector('form');
            this.formset = document.getElementById('line-formset');
            this.initialized = false;

            this.init();
        }

        /**
         * Initialize validation
         */
        init() {
            if (!this.form) return;

            // Real-time validation on input
            this.form.addEventListener('blur', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
                    this.validateField(e.target);
                }
            }, true);

            // Submit validation
            this.form.addEventListener('submit', (e) => {
                if (!this.validateForm()) {
                    e.preventDefault();
                    this.focusFirstError();
                }
            });

            this.initialized = true;
            console.log('✓ VoucherValidation initialized');
        }

        /**
         * Validate entire form
         * @returns {Boolean}
         */
        validateForm() {
            let isValid = true;

            // Validate journal header
            const headerValid = this.validateJournalHeader();
            if (!headerValid) isValid = false;

            // Validate lines
            const linesValid = this.validateLineItems();
            if (!linesValid) isValid = false;

            // Validate balance
            if (window.voucherTotals) {
                const balance = window.voucherTotals.getBalance();
                if (!balance.isBalanced) {
                    this.showError('Journal entries must balance (Debit = Credit)');
                    isValid = false;
                }
            }

            return isValid;
        }

        /**
         * Validate journal header fields
         * @returns {Boolean}
         */
        validateJournalHeader() {
            let isValid = true;

            const requiredFields = [
                { name: 'journal_type', label: 'Journal Type' },
                { name: 'period', label: 'Period' },
                { name: 'journal_date', label: 'Journal Date' },
                { name: 'currency', label: 'Currency' }
            ];

            requiredFields.forEach(field => {
                const input = this.form.querySelector(`[name="${field.name}"]`);
                if (input && !input.value) {
                    this.markFieldInvalid(input, `${field.label} is required`);
                    isValid = false;
                } else if (input) {
                    this.markFieldValid(input);
                }
            });

            return isValid;
        }

        /**
         * Validate line items
         * @returns {Boolean}
         */
        validateLineItems() {
            let isValid = true;

            if (!this.formset) return isValid;

            const rows = this.formset.querySelectorAll('tr');
            let activeLines = 0;

            rows.forEach((row, index) => {
                // Skip if marked for deletion
                const deleteCheckbox = row.querySelector('input[name*="DELETE"]');
                if (deleteCheckbox && deleteCheckbox.checked) {
                    return;
                }

                activeLines++;

                // Validate account selection
                const accountSelect = row.querySelector('select[name*="account"]');
                if (accountSelect && !accountSelect.value) {
                    this.markFieldInvalid(accountSelect, 'Account is required');
                    isValid = false;
                } else if (accountSelect) {
                    this.markFieldValid(accountSelect);
                }

                // Validate debit/credit
                const debitInput = row.querySelector('input[name*="debit_amount"]');
                const creditInput = row.querySelector('input[name*="credit_amount"]');

                if (debitInput && creditInput) {
                    const debit = parseFloat(debitInput.value) || 0;
                    const credit = parseFloat(creditInput.value) || 0;

                    if (debit > 0 && credit > 0) {
                        this.markFieldInvalid(debitInput, 'Cannot have both debit and credit');
                        this.markFieldInvalid(creditInput, 'Cannot have both debit and credit');
                        isValid = false;
                    } else if (debit === 0 && credit === 0) {
                        this.markFieldInvalid(debitInput, 'Must have debit or credit amount');
                        this.markFieldInvalid(creditInput, 'Must have debit or credit amount');
                        isValid = false;
                    } else {
                        this.markFieldValid(debitInput);
                        this.markFieldValid(creditInput);
                    }
                }
            });

            if (activeLines === 0) {
                this.showError('Journal must have at least one line item');
                isValid = false;
            }

            return isValid;
        }

        /**
         * Validate single field
         * @param {HTMLElement} field
         */
        validateField(field) {
            const name = field.name;
            let isValid = true;
            let errorMsg = '';

            if (name.includes('debit_amount') || name.includes('credit_amount')) {
                const row = field.closest('tr');
                const debitInput = row.querySelector('input[name*="debit_amount"]');
                const creditInput = row.querySelector('input[name*="credit_amount"]');

                const debit = parseFloat(debitInput.value) || 0;
                const credit = parseFloat(creditInput.value) || 0;

                if (debit < 0 || credit < 0) {
                    isValid = false;
                    errorMsg = 'Amount cannot be negative';
                } else if (debit > 0 && credit > 0) {
                    isValid = false;
                    errorMsg = 'Cannot have both debit and credit';
                } else if (debit === 0 && credit === 0) {
                    isValid = false;
                    errorMsg = 'Must enter debit or credit amount';
                }

                if (isValid) {
                    this.markFieldValid(field);
                } else {
                    this.markFieldInvalid(field, errorMsg);
                }
            }

            if (name.includes('tax_rate')) {
                const value = parseFloat(field.value) || 0;
                if (value < 0 || value > 100) {
                    isValid = false;
                    errorMsg = 'Tax rate must be between 0 and 100';
                }

                if (isValid) {
                    this.markFieldValid(field);
                } else {
                    this.markFieldInvalid(field, errorMsg);
                }
            }
        }

        /**
         * Mark field as valid
         * @param {HTMLElement} field
         */
        markFieldValid(field) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');

            const errorDiv = field.parentElement.querySelector('.invalid-feedback');
            if (errorDiv) {
                errorDiv.remove();
            }
        }

        /**
         * Mark field as invalid
         * @param {HTMLElement} field
         * @param {String} message
         */
        markFieldInvalid(field, message) {
            field.classList.remove('is-valid');
            field.classList.add('is-invalid');

            let errorDiv = field.parentElement.querySelector('.invalid-feedback');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback d-block';
                field.parentElement.appendChild(errorDiv);
            }
            errorDiv.textContent = message;
        }

        /**
         * Show general form error
         * @param {String} message
         */
        showError(message) {
            const alertDiv = document.querySelector('.alert-danger');
            if (alertDiv) {
                alertDiv.style.display = 'block';
            } else {
                const alert = document.createElement('div');
                alert.className = 'alert alert-danger alert-dismissible fade show';
                alert.innerHTML = `
                    <strong>Error:</strong> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                this.form.insertBefore(alert, this.form.firstChild);
            }
        }

        /**
         * Focus on first invalid field
         */
        focusFirstError() {
            const firstError = document.querySelector('.is-invalid');
            if (firstError) {
                firstError.focus();
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        /**
         * Clear all validation messages
         */
        clearValidation() {
            this.form.querySelectorAll('.is-invalid, .is-valid').forEach(field => {
                field.classList.remove('is-invalid', 'is-valid');
            });

            this.form.querySelectorAll('.invalid-feedback').forEach(div => {
                div.remove();
            });
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.voucherValidation = new VoucherValidation();
    });

    // Expose globally
    window.VoucherValidation = VoucherValidation;
})();
