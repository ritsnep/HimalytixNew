class KeyboardShortcuts {
    constructor() {
        this.shortcutOverlay = document.getElementById('shortcut-overlay');
        this.registerShortcuts();
    }

    registerShortcuts() {
        // Global shortcuts
        document.addEventListener('keydown', (e) => {
            // Show keyboard shortcuts overlay with '?'
            if (e.key === '?' && !e.ctrlKey && !e.altKey) {
                e.preventDefault();
                this.toggleShortcutOverlay();
            }

            // Toggle command palette
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                window.commandPalette.toggle();
            }

            // Save journal entry
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveJournalEntry();
            }

            // Post journal
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                this.postJournal();
            }

            // Auto balance
            if (e.altKey && e.key === 'b') {
                e.preventDefault();
                this.autoBalance();
            }

            // New row
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                document.getElementById('add-row').click();
            }

            // Focus navigation
            if (e.altKey && /^[1-3]$/.test(e.key)) {
                e.preventDefault();
                this.focusSection(parseInt(e.key));
            }

            // Toggle full screen
            if (e.key === 'F11') {
                e.preventDefault();
                this.toggleFullScreen();
            }
        });
    }

    toggleShortcutOverlay() {
        this.shortcutOverlay.classList.toggle('active');

        if (this.shortcutOverlay.classList.contains('active')) {
            // Close overlay when clicking outside
            const closeOverlay = (e) => {
                if (e.target === this.shortcutOverlay) {
                    this.shortcutOverlay.classList.remove('active');
                    document.removeEventListener('click', closeOverlay);
                }
            };
            document.addEventListener('click', closeOverlay);

            // Close overlay with Escape key
            const handleEscape = (e) => {
                if (e.key === 'Escape') {
                    this.shortcutOverlay.classList.remove('active');
                    document.removeEventListener('keydown', handleEscape);
                }
            };
            document.addEventListener('keydown', handleEscape);
        }
    }

    saveJournalEntry() {
        const form = document.getElementById('journal-form');
        if (form) {
            // Show saving indicator
            const saveButton = document.querySelector('.save-button');
            if (saveButton) {
                const originalText = saveButton.innerHTML;
                saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
                saveButton.disabled = true;

                // Submit the form
                form.dispatchEvent(new Event('submit', { bubbles: true }));

                // Restore button state
                setTimeout(() => {
                    saveButton.innerHTML = originalText;
                    saveButton.disabled = false;
                }, 1000);
            }
        }
    }

    postJournal() {
        // Validate before posting
        if (!this.validateJournal()) {
            this.showError('Please fix validation errors before posting.');
            return;
        }

        const postButton = document.querySelector('.post-button');
        if (postButton) {
            // Show confirmation dialog
            if (confirm('Are you sure you want to post this journal entry? This action cannot be undone.')) {
                const originalText = postButton.innerHTML;
                postButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Posting...';
                postButton.disabled = true;

                // Add posted status to form
                const form = document.getElementById('journal-form');
                const statusInput = document.createElement('input');
                statusInput.type = 'hidden';
                statusInput.name = 'status';
                statusInput.value = 'posted';
                form.appendChild(statusInput);

                // Submit the form
                form.dispatchEvent(new Event('submit', { bubbles: true }));

                // Restore button state
                setTimeout(() => {
                    postButton.innerHTML = originalText;
                    postButton.disabled = false;
                }, 1000);
            }
        }
    }

    autoBalance() {
        const rows = Array.from(document.querySelectorAll('#journal-grid-body tr'));
        let totalDebit = 0;
        let totalCredit = 0;

        // Calculate totals
        rows.forEach(row => {
            const debitCell = row.querySelector('[data-type="debit"]');
            const creditCell = row.querySelector('[data-type="credit"]');

            if (debitCell) totalDebit += parseFloat(debitCell.value) || 0;
            if (creditCell) totalCredit += parseFloat(creditCell.value) || 0;
        });

        // Find the difference
        const difference = Math.abs(totalDebit - totalCredit);
        if (difference === 0) return; // Already balanced

        // Find the last empty cell to balance
        const lastRow = rows[rows.length - 1];
        const debitCell = lastRow.querySelector('[data-type="debit"]');
        const creditCell = lastRow.querySelector('[data-type="credit"]');

        if (totalDebit > totalCredit && creditCell) {
            creditCell.value = difference.toFixed(2);
        } else if (totalDebit < totalCredit && debitCell) {
            debitCell.value = difference.toFixed(2);
        }

        // Trigger change event for validation
        const modifiedCell = totalDebit > totalCredit ? creditCell : debitCell;
        if (modifiedCell) {
            modifiedCell.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    focusSection(sectionNumber) {
        const sections = {
            1: '#journal-grid',
            2: '#journal-details',
            3: '#journal-attachments'
        };

        const section = document.querySelector(sections[sectionNumber]);
        if (section) {
            section.scrollIntoView({ behavior: 'smooth' });
            const focusableElement = section.querySelector('input, select, textarea');
            if (focusableElement) {
                focusableElement.focus();
            }
        }
    }

    toggleFullScreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    validateJournal() {
        let isValid = true;
        const errors = [];

        // Validate required fields
        document.querySelectorAll('[data-required="true"]').forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.classList.add('invalid');
                errors.push(`${field.dataset.label || 'Field'} is required`);
            }
        });

        // Validate numbers
        document.querySelectorAll('[data-type="number"]').forEach(field => {
            if (field.value && isNaN(field.value)) {
                isValid = false;
                field.classList.add('invalid');
                errors.push(`${field.dataset.label || 'Field'} must be a valid number`);
            }
        });

        // Validate dates
        document.querySelectorAll('[data-type="date"]').forEach(field => {
            if (field.value && isNaN(Date.parse(field.value))) {
                isValid = false;
                field.classList.add('invalid');
                errors.push(`${field.dataset.label || 'Field'} must be a valid date`);
            }
        });

        // Check debit/credit balance
        const rows = Array.from(document.querySelectorAll('#journal-grid-body tr'));
        let totalDebit = 0;
        let totalCredit = 0;

        rows.forEach(row => {
            const debitCell = row.querySelector('[data-type="debit"]');
            const creditCell = row.querySelector('[data-type="credit"]');

            if (debitCell) totalDebit += parseFloat(debitCell.value) || 0;
            if (creditCell) totalCredit += parseFloat(creditCell.value) || 0;
        });

        if (Math.abs(totalDebit - totalCredit) > 0.01) {
            isValid = false;
            errors.push('Debits and credits must be equal');
        }

        // Show errors if any
        if (!isValid) {
            this.showError(errors.join('<br>'));
        }

        return isValid;
    }

    showError(message) {
        const errorPanel = document.querySelector('.error-panel');
        if (errorPanel) {
            errorPanel.innerHTML = `<div class="alert alert-danger">${message}</div>`;
            errorPanel.style.display = 'block';
            errorPanel.scrollIntoView({ behavior: 'smooth' });
        }
    }
}

// Initialize Keyboard Shortcuts
document.addEventListener('DOMContentLoaded', () => {
    window.keyboardShortcuts = new KeyboardShortcuts();
});
