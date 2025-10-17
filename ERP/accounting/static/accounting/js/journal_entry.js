document.addEventListener('DOMContentLoaded', function() {
    const gridBody = document.getElementById('journal-grid-body');
    const journalForm = document.getElementById('journal-form');
    const journalIdInput = document.getElementById('journal-id');

    if (!gridBody || !journalForm) {
        return;
    }

    // Debounce function to limit the rate of function calls
    const debounce = (func, delay) => {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    };

    const triggerValidation = debounce(() => {
        if (journalIdInput && journalIdInput.value) {
            htmx.trigger(document.getElementById('validation-panel'), 'change');
        }
    }, 500); // Trigger validation 500ms after the last change

    const initializeGrid = async () => {
        await fetchRowTemplate();
        gridBody.addEventListener('paste', handlePaste);
        gridBody.addEventListener('htmx:afterSwap', (event) => {
            const newRow = event.detail.elt;
            if (newRow.tagName === 'TR') {
                setupRowListeners(newRow);
                 htmx.process(newRow);
            }
            triggerValidation(); // Trigger validation after any HTMX swap in the grid
        });
        gridBody.querySelectorAll('tr').forEach(setupRowListeners);
        if (gridBody.rows.length > 0) {
            showRowDetails(gridBody.rows[0]);
        }
        initializeSidePanel();
        makeColumnsResizable();
        initializeColumnPicker();
        initializeDragAndDrop(gridBody);
        initializeDarkMode();
        initializeDistractionFreeMode();
    };

    const setupRowListeners = (row) => {
        row.addEventListener('click', () => showRowDetails(row));
        row.querySelectorAll('input.grid-cell, select.grid-cell').forEach(cell => {
            cell.addEventListener('input', () => {
                updateTotals();
                validateRow(row);
                triggerValidation(); // Trigger validation on cell input
            });
            cell.addEventListener('keydown', (e) => handleCellNavigation(e, gridBody));
            cell.addEventListener('focus', () => row.classList.add('table-active'));
            cell.addEventListener('blur', () => row.classList.remove('table-active'));
        });

        const referenceInput = document.getElementById('id_reference');
        if (referenceInput) {
            referenceInput.addEventListener('input', debounce(validateReference, 300));
            referenceInput.addEventListener('input', triggerValidation); // Trigger validation on reference input
        }

        const descriptionInput = row.querySelector('input[name$="-description"]');
        if (descriptionInput) {
            descriptionInput.addEventListener('input', debounce((e) => getLineSuggestions(e.target), 300));
        }
    };

    const validateRow = (row) => {
        const debitInput = row.querySelector('input[name$="-debit_amount"]');
        const creditInput = row.querySelector('input[name$="-credit_amount"]');
        const accountInput = row.querySelector('select[name$="-account"]');

        const debit = parseFloat(debitInput?.value || 0);
        const credit = parseFloat(creditInput?.value || 0);

        // Reset errors
        debitInput.classList.remove('is-invalid');
        creditInput.classList.remove('is-invalid');
        accountInput.classList.remove('is-invalid');

        // Check for simultaneous debit and credit
        if (debit > 0 && credit > 0) {
            debitInput.classList.add('is-invalid');
            creditInput.classList.add('is-invalid');
            setRowError(row, "A line cannot have both a debit and a credit.");
        } else {
            clearRowError(row);
        }

        // Check for missing account
        if (!accountInput.value) {
            accountInput.classList.add('is-invalid');
        }
    };

    const setRowError = (row, message) => {
        const errorRow = row.nextElementSibling; // Assuming error row is the next sibling
        if (errorRow && errorRow.classList.contains('journal-line-error-row')) {
            const errorCell = errorRow.querySelector('.line-error-cell');
            if (errorCell) {
                errorCell.textContent = message;
                errorRow.classList.remove('d-none'); // Show the error row
            }
        }
    };

    const clearRowError = (row) => {
        const errorRow = row.nextElementSibling; // Assuming error row is the next sibling
        if (errorRow && errorRow.classList.contains('journal-line-error-row')) {
            const errorCell = errorRow.querySelector('.line-error-cell');
            if (errorCell) {
                errorCell.textContent = '';
                errorRow.classList.add('d-none'); // Hide the error row
            }
        }
    };

    const getLineSuggestions = async (descriptionInput) => {
        const description = descriptionInput.value;
        if (description.length < 3) {
            removeSuggestionBox(descriptionInput);
            return;
        }

        try {
            const response = await fetch('/accounting/api/v1/journals/line-suggest/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ description: description })
            });
            const data = await response.json();
            if (data.suggestions) {
                displaySuggestions(descriptionInput, data.suggestions);
            }
        } catch (error) {
            console.error('Error fetching line suggestions:', error);
        }
    };

    const displaySuggestions = (descriptionInput, suggestions) => {
        removeSuggestionBox(descriptionInput);

        if (suggestions.length === 0) {
            return;
        }

        const suggestionBox = document.createElement('div');
        suggestionBox.className = 'list-group position-absolute';
        suggestionBox.style.zIndex = 1000;

        suggestions.forEach(suggestion => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action';
            item.textContent = `${suggestion.account_code} - ${suggestion.account_name}`;
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const row = descriptionInput.closest('tr');
                const accountInput = row.querySelector('select[name$="-account"]');
                if (accountInput) {
                    // Check if option exists, if not, create it.
                    let option = Array.from(accountInput.options).find(opt => opt.value == suggestion.account_id);
                    if (!option) {
                        option = new Option(`${suggestion.account_code} - ${suggestion.account_name}`, suggestion.account_id, true, true);
                        accountInput.appendChild(option);
                    }
                    accountInput.value = suggestion.account_id;
                    // Trigger change event for any dependent logic
                    accountInput.dispatchEvent(new Event('change'));
                }
                removeSuggestionBox(descriptionInput);
            });
            suggestionBox.appendChild(item);
        });

        descriptionInput.parentNode.appendChild(suggestionBox);

        // Clicking outside the suggestion box should close it
        document.addEventListener('click', function handler(event) {
            if (!suggestionBox.contains(event.target) && event.target !== descriptionInput) {
                removeSuggestionBox(descriptionInput);
                document.removeEventListener('click', handler);
            }
        }, true);
    };

    const removeSuggestionBox = (descriptionInput) => {
        const oldSuggestionBox = descriptionInput.parentNode.querySelector('.list-group');
        if (oldSuggestionBox) {
            oldSuggestionBox.remove();
        }
    };

    const handleCellNavigation = (e, gridBody) => {
        const cell = e.target;
        const row = cell.closest('tr');
        const cells = Array.from(row.querySelectorAll('.grid-cell'));
        const currentIndex = cells.indexOf(cell);
        const currentRowIndex = Array.from(gridBody.rows).indexOf(row);

        let nextRow, nextCell;

        switch (e.key) {
            case 'ArrowUp':
                e.preventDefault();
                nextRow = gridBody.rows[currentRowIndex - 1];
                if (nextRow) {
                    nextCell = nextRow.querySelectorAll('.grid-cell')[currentIndex];
                    if (nextCell) nextCell.focus();
                }
                break;
            case 'ArrowDown':
                e.preventDefault();
                nextRow = gridBody.rows[currentRowIndex + 1];
                if (nextRow) {
                    nextCell = nextRow.querySelectorAll('.grid-cell')[currentIndex];
                    if (nextCell) nextCell.focus();
                }
                break;
            case 'ArrowLeft':
                e.preventDefault();
                if (currentIndex > 0) {
                    nextCell = cells[currentIndex - 1];
                    if (nextCell) nextCell.focus();
                }
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (currentIndex < cells.length - 1) {
                    nextCell = cells[currentIndex + 1];
                    if (nextCell) nextCell.focus();
                }
                break;
            case 'Enter':
                if (!e.ctrlKey) {
                    e.preventDefault();
                    beginCellEdit(cell);
                }
                break;
            case 'Escape':
                e.preventDefault();
                cancelCellEdit(cell);
                break;
            case 'Tab':
                if (!e.shiftKey && currentIndex === cells.length - 1) {
                    const nextRow = gridBody.rows[currentRowIndex + 1];
                    if (!nextRow) {
                        e.preventDefault();
                        document.getElementById('add-row').click();
                    }
                }
                break;
        }
    };

    const beginCellEdit = (cell) => {
        cell.setAttribute('data-original-value', cell.value);
        cell.removeAttribute('readonly');
        cell.focus();
    };

    const cancelCellEdit = (cell) => {
        const originalValue = cell.getAttribute('data-original-value');
        if (originalValue !== null) {
            cell.value = originalValue;
        }
        cell.setAttribute('readonly', true);
        cell.removeAttribute('data-original-value');
    };


    let rowTemplate = '';
    const fetchRowTemplate = async () => {
        try {
            const response = await fetch('/accounting/journal-entry/htmx/get_row_template/');
            if(response.ok) {
                rowTemplate = await response.text();
            } else {
                console.error('Failed to fetch row template.');
            }
        } catch (error) {
            console.error('Error fetching row template:', error);
        }
    };
    const handlePaste = async (e) => {
        e.preventDefault();
        const pasteData = e.clipboardData.getData('text');
        const rows = pasteData.split(/\r\n|\n|\r/).filter(row => row.trim() !== '').map(row => row.split('\t'));
        
        const targetCell = e.target;
        if (!targetCell.classList.contains('grid-cell')) return;

        const startRow = targetCell.closest('tr');
        if (!startRow) return;

        let allGridRows = Array.from(gridBody.rows);
        let startRowIndex = allGridRows.indexOf(startRow);
        const allCellsInRow = Array.from(startRow.querySelectorAll('.grid-cell'));
        let startCellIndex = allCellsInRow.indexOf(targetCell);

        for (let i = 0; i < rows.length; i++) {
            let currentRow;
            let currentRowIndex = startRowIndex + i;

            if (currentRowIndex < allGridRows.length) {
                currentRow = allGridRows[currentRowIndex];
            } else {
                // Add a new row if needed
                const addRowButton = document.getElementById('add-row');
                if (addRowButton) {
                    addRowButton.click();
                    await new Promise(resolve => setTimeout(resolve, 100)); // Wait for the new row to be added
                    allGridRows = Array.from(gridBody.rows);
                    currentRow = allGridRows[allGridRows.length - 1];
                } else {
                    break;
                }
            }
            
            const cellsToUpdate = Array.from(currentRow.querySelectorAll('.grid-cell'));
            const rowData = rows[i];

            rowData.forEach((cellData, j) => {
                let currentCellIndex = startCellIndex + j;
                if (currentCellIndex < cellsToUpdate.length) {
                    const cell = cellsToUpdate[currentCellIndex];
                    cell.value = cellData.trim();
                }
            });
        }
        
        updateTotals();
    };

    const updateTotals = () => {
        let totalDebit = 0;
        let totalCredit = 0;
        gridBody.querySelectorAll('tr').forEach(row => {
            const debitInput = row.querySelector('input[name$="-debit_amount"]');
            const creditInput = row.querySelector('input[name$="-credit_amount"]');
            const debit = parseFloat(debitInput?.value || 0);
            const credit = parseFloat(creditInput?.value || 0);
            totalDebit += debit;
            totalCredit += credit;
        });

        const totalDebitEl = document.getElementById('total-debit');
        const totalCreditEl = document.getElementById('total-credit');
        const imbalanceContainer = document.getElementById('imbalance-container');

        if(totalDebitEl) totalDebitEl.textContent = totalDebit.toFixed(2);
        if(totalCreditEl) totalCreditEl.textContent = totalCredit.toFixed(2);

        const imbalance = totalDebit - totalCredit;
        
        if (imbalanceContainer) {
            if (Math.abs(imbalance) < 0.005) {
                imbalanceContainer.innerHTML = '<span class="text-success fw-bold">Balanced</span>';
            } else {
                imbalanceContainer.innerHTML = `<span class="text-danger fw-bold">Imbalance: ${imbalance.toFixed(2)}</span>`;
            }
        }
    };

    const showRowDetails = (row) => {
        gridBody.querySelectorAll('tr').forEach(r => r.classList.remove('table-info'));
        row.classList.add('table-info');
        const panel = document.getElementById('side-panel');
        if (window.innerWidth > 991.98 && panel.classList.contains('panel-collapsed')) {
            panel.classList.remove('panel-collapsed');
            updateToggleIcons();
        }

        // Load line details into the side panel via HTMX
        const journalId = document.getElementById('journal-id')?.value;
        const rowIndex = Array.from(gridBody.children).indexOf(row);

        if (journalId && rowIndex !== -1) {
            const sidePanelContent = document.getElementById('side-panel-content');
            if (sidePanelContent) {
                htmx.ajax('GET', `/accounting/journal/${journalId}/line/${rowIndex}/details/`, {
                    target: '#side-panel-content',
                    swap: 'innerHTML',
                    onSuccess: function() {
                        // Remove the empty state message if details are loaded
                        const emptyState = document.getElementById('empty-state');
                        if (emptyState) {
                            emptyState.classList.add('d-none');
                        }
                    },
                    onError: function() {
                        const emptyState = document.getElementById('empty-state');
                        if (emptyState) {
                            emptyState.classList.remove('d-none');
                            emptyState.innerHTML = '<i class="fas fa-exclamation-triangle fs-3 mb-3"></i><p>Failed to load line details.</p>';
                        }
                    }
                });
            }
        } else {
            // If no journalId or rowIndex, show empty state
            const emptyState = document.getElementById('empty-state');
            if (emptyState) {
                emptyState.classList.remove('d-none');
                emptyState.innerHTML = '<i class="fas fa-mouse-pointer fs-3 mb-3"></i><p>Select a row to view details.</p>';
            }
        }
    };

    const initializeSidePanel = () => {
        const panel = document.getElementById('side-panel');
        if (window.innerWidth >= 992) { // For desktop, ensure it's not collapsed initially
            panel.classList.remove('panel-collapsed');
        } else { // For mobile, ensure it's collapsed initially
            panel.classList.add('panel-collapsed');
        }
        updateToggleIcons();
    };


    const updateToggleIcons = () => {
        const panel = document.getElementById('side-panel');
        const isCollapsed = panel.classList.contains('panel-collapsed');
        const desktopToggle = document.getElementById('side-panel-toggle');
        if (desktopToggle) {
            const desktopIcon = desktopToggle.querySelector('i');
            if (desktopIcon) {
                desktopIcon.classList.toggle('fa-bars', isCollapsed);
                desktopIcon.classList.toggle('fa-times', !isCollapsed);
            }
        }
        const fabToggle = document.getElementById('side-panel-fab');
        if (fabToggle) {
            const fabIcon = fabToggle.querySelector('i');
            if (fabIcon) {
                fabIcon.classList.toggle('fa-bars', isCollapsed);
                fabIcon.classList.toggle('fa-times', !isCollapsed);
            }
        }
    };

    const makeColumnsResizable = () => {
        const headers = document.querySelectorAll('#journal-grid th.position-relative');
        headers.forEach(header => {
            const handle = header.querySelector('.resize-handle');
            if(!handle) return;
            let startX, startWidth;
            
            handle.addEventListener('mousedown', (e) => {
                startX = e.pageX;
                startWidth = header.offsetWidth;
                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
            });

            const onMouseMove = (e) => {
                const newWidth = startWidth + (e.pageX - startX);
                if (newWidth > 50) {
                    header.style.width = `${newWidth}px`;
                }
            };


            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };
        });
    };

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    const aiAssistInput = {
        setupAutoComplete: () => {
            $('#ai-assist-input').on('input', debounce(async function() {
                const input = $(this).val();
                if (input.length > 3) {
                    const suggestions = await fetchAISuggestions(input);
                    displaySmartSuggestions(suggestions);
                }
            }, 300));
        },
        
        attachQuickFill: () => {
            $('#smart-suggestions').on('click', '.suggestion-item', function() {
                const template = $(this).data('template');
                populateJournalLines(template);
            });
        }
    };

    const toggleSidePanel = () => {
        document.getElementById('side-panel').classList.toggle('panel-collapsed');
        updateToggleIcons();
    };
    const keyboardShortcuts = {
        init: () => {
            const commandPaletteModal = new bootstrap.Modal(document.getElementById('command-palette-modal'));
            const commandPaletteInput = document.getElementById('command-palette-input');
            const commandPaletteResults = document.getElementById('command-palette-results');
            const commands = [
                { name: 'Save Journal', shortcut: 'Ctrl+S', action: () => document.getElementById('journal-form').submit() },
                { name: 'Add New Line', shortcut: 'Ctrl+N', action: () => document.getElementById('add-row').click() },
                { name: 'Open Command Palette', shortcut: 'Ctrl+K', action: () => commandPaletteModal.toggle() },
                { name: 'Auto Balance', shortcut: 'Alt+B', action: () => document.getElementById('auto-balance').click() },
                { name: 'Post Journal', shortcut: 'Ctrl+Enter', action: () => document.getElementById('journal-form').submit() }
            ];

            document.addEventListener('keydown', (e) => {
                const command = commands.find(c => {
                    const keys = c.shortcut.split('+');
                    const isCtrl = keys.includes('Ctrl') ? e.ctrlKey : !keys.includes('Ctrl');
                    const isShift = keys.includes('Shift') ? e.shiftKey : !keys.includes('Shift');
                    const isAlt = keys.includes('Alt') ? e.altKey : !keys.includes('Alt');
                    const isKey = keys.some(k => ['Ctrl', 'Shift', 'Alt'].indexOf(k) === -1 && e.key.toLowerCase() === k.toLowerCase());
                    
                    return isCtrl && isShift && isAlt && isKey;
                });

                if (command) {
                    e.preventDefault();
                    command.action();
                }

                // Handle Command Palette (Ctrl+K) separately for modal display
                if (e.ctrlKey && e.key === 'k') {
                    e.preventDefault();
                    commandPaletteModal.show();
                }
            });

            if (commandPaletteInput) {
                commandPaletteInput.addEventListener('input', () => {
                    const query = commandPaletteInput.value.toLowerCase();
                    const filteredCommands = commands.filter(c => c.name.toLowerCase().includes(query));
                    if (commandPaletteResults) {
                        commandPaletteResults.innerHTML = '';
                        filteredCommands.forEach(c => {
                            const li = document.createElement('li');
                            li.className = 'list-group-item list-group-item-action';
                            li.textContent = c.name;
                            li.addEventListener('click', () => {
                                c.action();
                                commandPaletteModal.hide();
                            });
                            commandPaletteResults.appendChild(li);
                        });
                    }
                });
            }
        }
    };
    // Odoo-style "Hold Ctrl" Shortcut Overlay
    const shortcutOverlay = document.getElementById('shortcut-overlay');
    let ctrlPressed = false;
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Control' && !ctrlPressed) {
            ctrlPressed = true;
            if (shortcutOverlay) {
                shortcutOverlay.classList.add('show');
            }
        }
    });
    document.addEventListener('keyup', (e) => {
        if (e.key === 'Control') {
            ctrlPressed = false;
            if (shortcutOverlay) {
                shortcutOverlay.classList.remove('show');
            }
        }
    });
    // Initial setup
    initializeGrid();
    updateTotals();
    triggerValidation(); // Initial validation on page load
    keyboardShortcuts.init();
    initializeAttachmentHandling();
    initializeReceiptDropzone();
    initializeDensityToggle();
    const desktopToggle = document.getElementById('side-panel-toggle');
    if (desktopToggle) {
        desktopToggle.addEventListener('click', toggleSidePanel);
    }
    const fabToggle = document.getElementById('side-panel-fab');
    if (fabToggle) {
        fabToggle.addEventListener('click', toggleSidePanel);
    }
    const showOverlay = () => { if (shortcutOverlay) shortcutOverlay.classList.add('show'); };
    const hideOverlay = () => { if (shortcutOverlay) shortcutOverlay.classList.remove('show'); };
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && (e.key === '?' || e.key === '/')) {
            e.preventDefault();
            if (shortcutOverlay) {
                shortcutOverlay.classList.toggle('show');
            }
        }
        if (e.key === 'Escape') hideOverlay();
    });
    if (shortcutOverlay) {
        shortcutOverlay.addEventListener('click', (e) => {
            if (e.target === shortcutOverlay) hideOverlay();
        });
    }
    if (journalForm) {
        const debouncedValidation = debounce(validateJournal, 500);
        journalForm.addEventListener('input', debouncedValidation);
        validateJournal(); // Initial validation on page load
        const debouncedBackgroundValidation = debounce(triggerBackgroundValidation, 500);
        journalForm.addEventListener('input', debouncedBackgroundValidation);
        triggerBackgroundValidation(); // Initial validation
    }
    handleFormErrors();
});
const validateReference = async () => {
    const referenceInput = document.getElementById('id_reference');
    const journalTypeInput = document.getElementById('id_journal_type');
    const journalId = document.getElementById('journal-id')?.value; // Assuming you have a hidden input for journal ID
    const feedbackEl = document.getElementById('reference-feedback');

    const reference = referenceInput.value;
    const journalTypeId = journalTypeInput.value;

    if (!reference || !journalTypeId) {
        if(feedbackEl) feedbackEl.style.display = 'none';
        return;
    }

    try {
        const params = new URLSearchParams({
            reference,
            journal_type: journalTypeId,
        });
        if(journalId) {
            params.append('journal_id', journalId);
        }

        const response = await fetch(`/accounting/api/validate-reference/?${params.toString()}`);
        const data = await response.json();

        if (data.is_duplicate) {
            referenceInput.classList.add('is-invalid');
            if(feedbackEl) {
                feedbackEl.textContent = 'This reference number is already in use for this journal type.';
                feedbackEl.style.display = 'block';
            }
        } else {
            referenceInput.classList.remove('is-invalid');
            if(feedbackEl) {
                feedbackEl.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Reference validation error:', error);
        if(feedbackEl) {
            feedbackEl.textContent = 'Could not validate reference.';
            feedbackEl.style.display = 'block';
        }
    }
};
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}
const validateJournal = async () => {
    const form = document.getElementById('journal-form');
    const formData = new FormData(form);
    const journalId = document.getElementById('journal-id')?.value;
    
    let data = Object.fromEntries(formData.entries());
    data['journal_id'] = journalId;

    try {
        const response = await fetch('/accounting/journals/validate-journal/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': data.csrfmiddlewaretoken
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        const errorPanel = document.getElementById('validation-panel');
        
        if (response.ok) {
            errorPanel.innerHTML = '';
            if (Object.keys(result.errors).length === 0) {
                errorPanel.innerHTML = '<p>No errors found.</p>';
            } else {
                const ul = document.createElement('ul');
                for (const [field, message] of Object.entries(result.errors)) {
                    const li = document.createElement('li');
                    li.textContent = message;
                    ul.appendChild(li);
                }
                errorPanel.appendChild(ul);
            }
        } else {
            errorPanel.innerHTML = '<p class="text-danger">An error occurred during validation.</p>';
        }
    } catch (error) {
        console.error('Validation request failed:', error);
        const errorPanel = document.getElementById('validation-panel');
        errorPanel.innerHTML = '<p class="text-danger">Could not connect to the server for validation.</p>';
    }
};

const triggerBackgroundValidation = async () => {
    const form = document.getElementById('journal-form');
    const journalData = {
        date: form.querySelector('#id_date')?.value,
        description: form.querySelector('#id_description')?.value,
    };
    const lines = [];
    form.querySelectorAll('#journal-grid-body tr').forEach(row => {
        const line = {
            account: row.querySelector('select[name$="-account"]')?.value,
            debit: row.querySelector('input[name$="-debit_amount"]')?.value,
            credit: row.querySelector('input[name$="-credit_amount"]')?.value,
        };
        lines.push(line);
    });

    const data = {
        journal: journalData,
        lines: lines,
    };

    htmx.ajax('POST', '/accounting/journals/background-validate/', {
        target: '#validation-panel',
        swap: 'innerHTML',
        values: data,
        headers: {
            'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value
        },
        onSuccess: function(evt) {
            clearValidationFeedback();
            const responseData = JSON.parse(evt.detail.xhr.responseText);
            applyValidationFeedback(responseData.errors);
        }
    });
};

const clearValidationFeedback = () => {
    // Clear header errors
    document.querySelectorAll('#journal-form .is-invalid').forEach(el => {
        el.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    // Clear line errors
    document.querySelectorAll('#journal-grid-body tr').forEach(row => {
        row.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        clearRowError(row);
    });
};

const applyValidationFeedback = (errors) => {
    if (!errors) return;

    // Apply header errors
    if (errors.header) {
        for (const fieldName in errors.header) {
            const input = document.getElementById(`id_${fieldName}`);
            if (input) {
                input.classList.add('is-invalid');
                const feedbackEl = document.getElementById(`${fieldName}-feedback`);
                if (feedbackEl) {
                    feedbackEl.textContent = errors.header[fieldName];
                    feedbackEl.style.display = 'block';
                }
            }
        }
    }

    // Apply line errors
    if (errors.lines) {
        errors.lines.forEach(lineError => {
            const rowIndex = lineError.index;
            const row = document.querySelectorAll('#journal-grid-body tr')[rowIndex];
            if (row) {
                for (const fieldName in lineError.errors) {
                    const input = row.querySelector(`[name$="-${fieldName}"]`);
                    if (input) {
                        input.classList.add('is-invalid');
                        // Create or update an inline feedback element for the specific field
                        let feedbackEl = row.querySelector(`#${input.id}-feedback`);
                        if (!feedbackEl) {
                            feedbackEl = document.createElement('div');
                            feedbackEl.id = `${input.id}-feedback`;
                            feedbackEl.className = 'invalid-feedback d-block'; // d-block to ensure visibility
                            input.parentNode.appendChild(feedbackEl);
                        }
                        feedbackEl.textContent = lineError.errors[fieldName];
                    }
                }
                // Also update the general row error if needed
                setRowError(row, Object.values(lineError.errors).join('; '));
            }
        });
    }
};

const handleFormErrors = () => {
    const form = document.getElementById('journal-form');
    form.addEventListener('htmx:afterRequest', (event) => {
        if (event.detail.failed) {
            const errorPanel = document.getElementById('validation-errors');
            if (errorPanel) {
                errorPanel.focus();
            }
            const firstErrorField = form.querySelector('.is-invalid');
            if (firstErrorField) {
                firstErrorField.focus();
            }
        }
    });
};


// Initialize on page load
function initializeJournalEntry(config) {
    JournalEntry.init(config);
}
const initializeAttachmentHandling = () => {
        const dropZone = document.getElementById('attachment-drop-zone');
        const fileInput = document.getElementById('file-upload');
        const previewsContainer = document.getElementById('attachment-previews');
        const attachmentList = document.getElementById('attachment-list');
        let uploadedFiles = [];

        if (!dropZone || !fileInput || !previewsContainer || !attachmentList) {
            return;
        }

        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-primary');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-primary');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-primary');
            const files = e.dataTransfer.files;
            handleFiles(files);
        });

        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            handleFiles(files);
        });

        const handleFiles = (files) => {
            for (const file of files) {
                uploadedFiles.push(file);
                const fileId = `file-${Date.now()}`;

                const listItem = document.createElement('li');
                listItem.className = 'list-group-item d-flex justify-content-between align-items-center';
                listItem.id = fileId;
                listItem.innerHTML = `
                    <span>${file.name}</span>
                    <button type="button" class="btn-close" aria-label="Remove"></button>
                `;
                attachmentList.appendChild(listItem);

                listItem.querySelector('.btn-close').addEventListener('click', () => {
                    uploadedFiles = uploadedFiles.filter(f => f !== file);
                    listItem.remove();
                    const preview = document.getElementById(`${fileId}-preview`);
                    if (preview) {
                        preview.remove();
                    }
                });

                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const previewHtml = `
                            <div class="attachment-preview" id="${fileId}-preview">
                                <img src="${e.target.result}" alt="${file.name}" class="img-thumbnail" width="100">
                            </div>
                        `;
                        previewsContainer.innerHTML += previewHtml;
                    };
                    reader.readAsDataURL(file);
                }
            }
            updateFileInput();
        };

        const updateFileInput = () => {
            const dataTransfer = new DataTransfer();
            uploadedFiles.forEach(file => {
                dataTransfer.items.add(file);
            });
            fileInput.files = dataTransfer.files;
        };
    };
const initializeReceiptDropzone = () => {
    const dropzone = document.getElementById('receipt-dropzone');
    const fileInput = document.getElementById('receipt-upload');

    if (!dropzone || !fileInput) {
        return;
    }

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-primary');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-primary');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-primary');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleReceiptFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            handleReceiptFile(files[0]);
        }
    });
};

const handleReceiptFile = (file) => {
    const formData = new FormData();
    formData.append('receipt', file);

    // Add CSRF token to the request
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/accounting/journal-entry/upload-receipt/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            populateJournalLinesFromOCR(data.extracted_data);
        } else {
            console.error('OCR processing failed:', data.error);
        }
    })
    .catch(error => console.error('Error uploading receipt:', error));
};

const populateJournalLinesFromOCR = (extractedData) => {
    const gridBody = document.getElementById('journal-grid-body');
    if (!gridBody || !rowTemplate) return;

    // Create a new row for the expense
    const expenseRowIndex = gridBody.rows.length;
    const expenseRowHTML = rowTemplate
        .replace(/__prefix__/g, expenseRowIndex)
        .replace(/__prefix_plus_1__/g, expenseRowIndex + 1);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = expenseRowHTML;
    const expenseRow = tempDiv.firstElementChild;

    // Populate the expense line
    const expenseDesc = expenseRow.querySelector('input[name$="-description"]');
    const expenseDebit = expenseRow.querySelector('input[name$="-debit_amount"]');
    if(expenseDesc) expenseDesc.value = extractedData.vendor || 'Scanned Expense';
    if(expenseDebit) expenseDebit.value = extractedData.total || 0;
    
    gridBody.appendChild(expenseRow);
    setupRowListeners(expenseRow);
    htmx.process(expenseRow);

    updateTotals();
};


// Bind side panel toggles (desktop button and mobile FAB)

const initializeDensityToggle = () => {
    const densityToggle = document.getElementById('density-toggle');
    const journalGrid = document.getElementById('journal-grid');

    if (!densityToggle || !journalGrid) {
        return;
    }

    const setDensity = (isCompact) => {
        const icon = densityToggle.querySelector('i');
        if (isCompact) {
            journalGrid.classList.add('compact-mode');
            icon.classList.remove('fa-compress');
            icon.classList.add('fa-expand');
            localStorage.setItem('journalDensity', 'compact');
        } else {
            journalGrid.classList.remove('compact-mode');
            icon.classList.remove('fa-expand');
            icon.classList.add('fa-compress');
            localStorage.setItem('journalDensity', 'comfortable');
        }
    };

    densityToggle.addEventListener('click', () => {
        const isCompact = !journalGrid.classList.contains('compact-mode');
        setDensity(isCompact);
    });

    // Apply saved preference on page load
    const savedDensity = localStorage.getItem('journalDensity');
    if (savedDensity === 'compact') {
        setDensity(true);
    }
};

const initializeColumnPicker = () => {
    const columnPickerMenu = document.getElementById('column-picker-menu');
    const table = document.getElementById('journal-grid');
    const headers = table.querySelectorAll('thead th');
    const columnVisibility = JSON.parse(localStorage.getItem('journalColumnVisibility')) || {};

    headers.forEach((header, index) => {
        const columnName = header.textContent.trim();
        if (columnName) {
            const isVisible = columnVisibility[columnName] !== false;
            const listItem = document.createElement('li');
            listItem.innerHTML = `
                <a class="dropdown-item" href="#">
                    <input type="checkbox" class="form-check-input" ${isVisible ? 'checked' : ''}>
                    ${columnName}
                </a>
            `;
            if (columnPickerMenu) {
                columnPickerMenu.appendChild(listItem);
            }

            const checkbox = listItem.querySelector('input');
            checkbox.addEventListener('change', () => {
                toggleColumn(index, checkbox.checked);
                columnVisibility[columnName] = checkbox.checked;
                localStorage.setItem('journalColumnVisibility', JSON.stringify(columnVisibility));
            });

            if (!isVisible) {
                toggleColumn(index, false);
            }
        }
    });
};

const toggleColumn = (index, isVisible) => {
    const table = document.getElementById('journal-grid');
    const rows = table.querySelectorAll('tr');
    rows.forEach(row => {
        const cell = row.children[index];
        if (cell) {
            cell.style.display = isVisible ? '' : 'none';
        }
    });
};

const initializeDragAndDrop = (gridBody) => {
    if (gridBody) {
        const sortable = new Sortable(gridBody, {
            animation: 150,
            handle: '.fa-grip-vertical',
        });
    }
};

const initializeDarkMode = () => {
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
        });
    }
};

const initializeDistractionFreeMode = () => {
    const distractionFreeToggle = document.getElementById('distraction-free-toggle');
    if (distractionFreeToggle) {
        distractionFreeToggle.addEventListener('click', () => {
            document.body.classList.toggle('distraction-free-mode');
        });
    }
};
