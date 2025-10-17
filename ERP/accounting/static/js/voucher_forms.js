/**
 * Voucher Forms Module
 * Dynamic form interactions and line management
 */

(function() {
    'use strict';

    class VoucherForms {
        constructor() {
            this.formset = document.getElementById('line-formset');
            this.addLineBtn = document.querySelector('[hx-get*="create_line"]');
            this.initialized = false;

            this.init();
        }

        /**
         * Initialize form interactions
         */
        init() {
            if (!this.formset) return;

            // Intercept HTMX add line
            document.addEventListener('htmx:afterSettle', (e) => {
                if (e.detail.target.id === 'line-formset') {
                    this.onLineAdded();
                }
            });

            // Line deletion handlers
            this.formset.addEventListener('click', (e) => {
                if (e.target.closest('[hx-delete*="line_delete"]')) {
                    this.onLineDeleted();
                }
            });

            // Focus management
            this.formset.addEventListener('change', (e) => {
                if (e.target.name.includes('account')) {
                    this.onAccountChanged(e.target);
                }
            });

            this.initialized = true;
            console.log('✓ VoucherForms initialized');
        }

        /**
         * Called when new line is added
         */
        onLineAdded() {
            const lineCount = this.formset.querySelectorAll('tr').length;
            console.log(`Line added - Total rows: ${lineCount}`);

            // Update management form
            this.updateManagementForm();

            // Re-initialize any new inputs
            this.initializeNewInputs();

            // Trigger total update
            document.dispatchEvent(new Event('voucherLinesChanged'));

            if (window.voucherTotals) {
                window.voucherTotals.updateTotals();
            }
        }

        /**
         * Called when line is deleted
         */
        onLineDeleted() {
            setTimeout(() => {
                this.updateManagementForm();

                if (window.voucherTotals) {
                    window.voucherTotals.updateTotals();
                }

                document.dispatchEvent(new Event('voucherLinesChanged'));
            }, 500);
        }

        /**
         * Called when account is selected
         * @param {HTMLElement} accountField
         */
        onAccountChanged(accountField) {
            const row = accountField.closest('tr');
            const selectedOption = accountField.options[accountField.selectedIndex];

            if (selectedOption && selectedOption.dataset.type) {
                const accountType = selectedOption.dataset.type;
                console.log(`Account selected - Type: ${accountType}`);

                // Set focus to next field (description)
                const descField = row.querySelector('input[name*="description"]');
                if (descField) {
                    descField.focus();
                }
            }
        }

        /**
         * Update formset management form
         */
        updateManagementForm() {
            const managementForm = document.querySelector('[id*="-TOTAL_FORMS"]');
            if (!managementForm) return;

            const totalForms = this.formset.querySelectorAll('tr').length;
            managementForm.value = totalForms;

            console.log(`Management form updated - Total forms: ${totalForms}`);
        }

        /**
         * Initialize inputs for new lines
         */
        initializeNewInputs() {
            const newRows = this.formset.querySelectorAll('tr:last-child');

            newRows.forEach(row => {
                const inputs = row.querySelectorAll('input[type="number"], input[type="text"], select');

                inputs.forEach(input => {
                    // Add focus handlers
                    input.addEventListener('focus', () => {
                        row.classList.add('table-active');
                    });

                    input.addEventListener('blur', () => {
                        row.classList.remove('table-active');
                    });

                    // Add change handlers
                    input.addEventListener('change', () => {
                        if (window.voucherTotals) {
                            window.voucherTotals.updateTotals();
                        }
                    });
                });
            });
        }

        /**
         * Add new line to formset
         */
        addLine() {
            if (this.addLineBtn) {
                this.addLineBtn.click();
            }
        }

        /**
         * Remove line from formset
         * @param {Number} lineIndex
         */
        removeLine(lineIndex) {
            const rows = this.formset.querySelectorAll('tr');
            if (rows[lineIndex]) {
                const deleteCheckbox = rows[lineIndex].querySelector('input[name*="DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                    rows[lineIndex].classList.add('table-secondary', 'opacity-50');

                    if (window.voucherTotals) {
                        window.voucherTotals.updateTotals();
                    }
                }
            }
        }

        /**
         * Get line data
         * @param {Number} lineIndex
         * @returns {Object}
         */
        getLineData(lineIndex) {
            const rows = this.formset.querySelectorAll('tr');
            if (!rows[lineIndex]) return null;

            const row = rows[lineIndex];
            const accountSelect = row.querySelector('select[name*="account"]');
            const debitInput = row.querySelector('input[name*="debit_amount"]');
            const creditInput = row.querySelector('input[name*="credit_amount"]');
            const descInput = row.querySelector('input[name*="description"]');

            return {
                account_id: accountSelect?.value,
                account_text: accountSelect?.options[accountSelect.selectedIndex]?.text,
                debit_amount: parseFloat(debitInput?.value) || 0,
                credit_amount: parseFloat(creditInput?.value) || 0,
                description: descInput?.value,
                index: lineIndex
            };
        }

        /**
         * Get all line data
         * @returns {Array}
         */
        getAllLinesData() {
            const lines = [];
            const rows = this.formset.querySelectorAll('tr');

            rows.forEach((row, index) => {
                const deleteCheckbox = row.querySelector('input[name*="DELETE"]');
                if (deleteCheckbox && deleteCheckbox.checked) {
                    return; // Skip deleted lines
                }

                const lineData = this.getLineData(index);
                if (lineData) {
                    lines.push(lineData);
                }
            });

            return lines;
        }

        /**
         * Validate line count
         * @returns {Boolean}
         */
        validateLineCount() {
            const activeLines = this.formset.querySelectorAll('tr').length;
            return activeLines > 0;
        }

        /**
         * Clear all lines
         */
        clearAllLines() {
            const deleteCheckboxes = this.formset.querySelectorAll('input[name*="DELETE"]');
            deleteCheckboxes.forEach(checkbox => {
                checkbox.checked = true;
                checkbox.closest('tr').classList.add('table-secondary', 'opacity-50');
            });

            if (window.voucherTotals) {
                window.voucherTotals.updateTotals();
            }
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.voucherForms = new VoucherForms();
    });

    // Expose globally
    window.VoucherForms = VoucherForms;
})();
