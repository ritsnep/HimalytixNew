/**
 * Voucher Totals Calculation Module
 * Real-time calculation of journal line totals and balances
 */

(function() {
    'use strict';

    class VoucherTotals {
        constructor() {
            this.formset = document.getElementById('line-formset');
            this.totalDebitElement = document.getElementById('total-debit');
            this.totalCreditElement = document.getElementById('total-credit');
            this.balanceStatusElement = document.getElementById('balance-status');
            this.initialized = false;

            this.init();
        }

        /**
         * Initialize event listeners
         */
        init() {
            if (!this.formset) return;

            // Listen for input changes on amount fields
            this.formset.addEventListener('change', (e) => {
                if (e.target.name.includes('debit_amount') || 
                    e.target.name.includes('credit_amount') ||
                    e.target.name.includes('DELETE')) {
                    this.updateTotals();
                }
            });

            // Initial calculation
            this.updateTotals();
            this.initialized = true;

            console.log('✓ VoucherTotals initialized');
        }

        /**
         * Calculate and update totals
         */
        updateTotals() {
            const totals = this.calculateTotals();
            
            // Update display
            if (this.totalDebitElement) {
                this.totalDebitElement.textContent = totals.debit.toFixed(2);
            }
            if (this.totalCreditElement) {
                this.totalCreditElement.textContent = totals.credit.toFixed(2);
            }

            // Update balance status
            this.updateBalanceStatus(totals);

            console.log(`Totals updated - Debit: ${totals.debit}, Credit: ${totals.credit}`);
        }

        /**
         * Calculate totals from all line items
         * @returns {Object} {debit, credit}
         */
        calculateTotals() {
            let totalDebit = 0;
            let totalCredit = 0;

            if (!this.formset) return { debit: 0, credit: 0 };

            // Get all rows
            const rows = this.formset.querySelectorAll('tr');

            rows.forEach(row => {
                // Skip if row is marked for deletion
                const deleteCheckbox = row.querySelector('input[name*="DELETE"]');
                if (deleteCheckbox && deleteCheckbox.checked) {
                    return;
                }

                // Get amount fields
                const debitInput = row.querySelector('input[name*="debit_amount"]');
                const creditInput = row.querySelector('input[name*="credit_amount"]');

                if (debitInput) {
                    const value = parseFloat(debitInput.value) || 0;
                    totalDebit += Math.max(0, value); // Ignore negatives
                }

                if (creditInput) {
                    const value = parseFloat(creditInput.value) || 0;
                    totalCredit += Math.max(0, value); // Ignore negatives
                }
            });

            return { debit: totalDebit, credit: totalCredit };
        }

        /**
         * Update balance status display
         * @param {Object} totals - {debit, credit}
         */
        updateBalanceStatus(totals) {
            const isBalanced = Math.abs(totals.debit - totals.credit) < 0.01;
            const difference = Math.abs(totals.debit - totals.credit);

            if (this.balanceStatusElement) {
                const statusClass = isBalanced ? 'bg-success' : 'bg-danger';
                const statusText = isBalanced ? 
                    'Balanced ✓' : 
                    `Unbalanced (Diff: ${difference.toFixed(2)})`;
                const iconClass = isBalanced ? 
                    'bi-check-circle' : 
                    'bi-x-circle';

                this.balanceStatusElement.innerHTML = `
                    <span class="badge ${statusClass}">
                        <i class="bi ${iconClass}"></i> ${statusText}
                    </span>
                `;
            }

            // Trigger custom event for other modules
            document.dispatchEvent(new CustomEvent('voucherBalanceChanged', {
                detail: {
                    debit: totals.debit,
                    credit: totals.credit,
                    isBalanced: isBalanced,
                    difference: difference
                }
            }));
        }

        /**
         * Format amount as currency
         * @param {Number} amount
         * @returns {String}
         */
        formatCurrency(amount) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD'
            }).format(amount);
        }

        /**
         * Get current balance
         * @returns {Object} {debit, credit, isBalanced, difference}
         */
        getBalance() {
            const totals = this.calculateTotals();
            return {
                ...totals,
                isBalanced: Math.abs(totals.debit - totals.credit) < 0.01,
                difference: Math.abs(totals.debit - totals.credit)
            };
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.voucherTotals = new VoucherTotals();
    });

    // Expose globally
    window.VoucherTotals = VoucherTotals;
})();
