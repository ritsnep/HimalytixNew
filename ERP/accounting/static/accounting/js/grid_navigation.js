const GridNavigation = {
    init(gridBody) {
        if (!gridBody) return;
        
        this.gridBody = gridBody;
        this.currentCell = null;
        this.copiedRowData = null;
        this.editHistory = [];
        this.historyIndex = -1;
        this.maxHistory = 50;
        
        this.setupKeyboardNavigation();
        this.setupContextMenu();
        this.setupClipboard();
        this.setupUndoRedo();
    },

    setupKeyboardNavigation() {
        this.gridBody.addEventListener('keydown', (e) => {
            const cell = e.target;
            if (!cell.classList.contains('grid-cell')) return;

            const row = cell.closest('tr');
            if (!row) return;

            this.currentCell = cell;
            this.handleNavigationKey(e, cell, row);
        });

        // Focus tracking
        this.gridBody.addEventListener('focusin', (e) => {
            const cell = e.target;
            if (cell.classList.contains('grid-cell')) {
                this.currentCell = cell;
                this.highlightCurrentRow(cell.closest('tr'));
            }
        });
    },

    setupContextMenu() {
        const contextMenu = document.getElementById('context-menu');
        if (!contextMenu) return;

        this.gridBody.addEventListener('contextmenu', (e) => {
            if (!e.target.classList.contains('grid-cell')) return;
            
            e.preventDefault();
            this.currentCell = e.target;
            
            // Position the context menu
            contextMenu.style.display = 'block';
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;
            
            // Handle clicking outside
            const closeMenu = (e) => {
                if (!contextMenu.contains(e.target)) {
                    contextMenu.style.display = 'none';
                    document.removeEventListener('click', closeMenu);
                }
            };
            
            setTimeout(() => {
                document.addEventListener('click', closeMenu);
            }, 0);
        });

        // Handle context menu actions
        contextMenu.addEventListener('click', (e) => {
            const action = e.target.closest('.menu-item')?.dataset.action;
            if (!action || !this.currentCell) return;

            switch (action) {
                case 'edit':
                    this.enterEditMode(this.currentCell);
                    break;
                case 'duplicate':
                    this.duplicateRow();
                    break;
                case 'delete':
                    this.deleteRow();
                    break;
                case 'insert-above':
                    this.insertRow(true);
                    break;
                case 'insert-below':
                    this.insertRow(false);
                    break;
                case 'copy-values':
                    this.copyRow();
                    break;
                case 'paste-values':
                    this.pasteRow();
                    break;
            }
            
            contextMenu.style.display = 'none';
        });
    },

    setupClipboard() {
        document.addEventListener('keydown', (e) => {
            if (!this.currentCell) return;
            
            if (e.ctrlKey && e.key === 'c') {
                this.copyRow();
            } else if (e.ctrlKey && e.key === 'v') {
                this.pasteRow();
            }
        });
    },

    setupUndoRedo() {
        document.addEventListener('keydown', (e) => {
            if (!this.currentCell) return;
            
            if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                if (e.shiftKey) {
                    this.redo();
                } else {
                    this.undo();
                }
            }
        });
    },

    handleNavigationKey(e, cell, row) {
        const cells = Array.from(row.querySelectorAll('.grid-cell'));
        const currentIndex = cells.indexOf(cell);
        const rows = Array.from(this.gridBody.rows);
        const currentRowIndex = rows.indexOf(row);

        switch (e.key) {
            case 'ArrowUp':
                e.preventDefault();
                this.navigateVertical(currentRowIndex - 1, currentIndex);
                break;

            case 'ArrowDown':
                e.preventDefault();
                this.navigateVertical(currentRowIndex + 1, currentIndex);
                break;

            case 'ArrowLeft':
                if (cell.selectionStart === 0 || e.ctrlKey) {
                    e.preventDefault();
                    if (currentIndex > 0) {
                        cells[currentIndex - 1].focus();
                    }
                }
                break;

            case 'ArrowRight':
                if (cell.selectionEnd === cell.value.length || e.ctrlKey) {
                    e.preventDefault();
                    if (currentIndex < cells.length - 1) {
                        cells[currentIndex + 1].focus();
                    }
                }
                break;

            case 'Enter':
                e.preventDefault();
                if (e.shiftKey) {
                    this.navigateVertical(currentRowIndex - 1, currentIndex);
                } else if (e.ctrlKey) {
                    this.enterEditMode(cell);
                } else {
                    this.navigateVertical(currentRowIndex + 1, currentIndex);
                }
                break;

            case 'Escape':
                e.preventDefault();
                if (cell.hasAttribute('data-original-value')) {
                    this.exitEditMode(cell);
                }
                break;

            case 'Tab':
                e.preventDefault();
                if (e.shiftKey) {
                    if (currentIndex > 0) {
                        cells[currentIndex - 1].focus();
                    } else if (currentRowIndex > 0) {
                        const prevRow = rows[currentRowIndex - 1];
                        const prevCells = prevRow.querySelectorAll('.grid-cell');
                        prevCells[prevCells.length - 1].focus();
                    }
                } else {
                    if (currentIndex < cells.length - 1) {
                        cells[currentIndex + 1].focus();
                    } else if (currentRowIndex < rows.length - 1) {
                        const nextRow = rows[currentRowIndex + 1];
                        nextRow.querySelector('.grid-cell').focus();
                    } else {
                        document.getElementById('add-row').click();
                    }
                }
                break;

            case 'Delete':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.deleteRow();
                }
                break;
        }
    },

    navigateVertical(targetRowIndex, cellIndex) {
        const rows = Array.from(this.gridBody.rows);
        const targetRow = rows[targetRowIndex];
        if (!targetRow) return;

        const targetCells = targetRow.querySelectorAll('.grid-cell');
        if (targetCells[cellIndex]) {
            targetCells[cellIndex].focus();
            this.highlightCurrentRow(targetRow);
        }
    },

    highlightCurrentRow(row) {
        const rows = Array.from(this.gridBody.rows);
        rows.forEach(r => r.classList.remove('current-row'));
        row.classList.add('current-row');
    },

    enterEditMode(cell) {
        if (cell.hasAttribute('readonly')) {
            cell.setAttribute('data-original-value', cell.value);
            cell.removeAttribute('readonly');
            cell.focus();
            cell.select();
            
            // Track changes for undo/redo
            const changeData = {
                cell,
                oldValue: cell.value,
                newValue: null
            };
            
            const saveChange = () => {
                changeData.newValue = cell.value;
                if (changeData.oldValue !== changeData.newValue) {
                    this.pushToHistory({
                        type: 'edit',
                        cell,
                        oldValue: changeData.oldValue,
                        newValue: changeData.newValue
                    });
                }
                cell.removeEventListener('change', saveChange);
            };
            
            cell.addEventListener('change', saveChange);
        }
    },

    exitEditMode(cell) {
        const originalValue = cell.getAttribute('data-original-value');
        if (originalValue !== null) {
            // Only revert if Escape was pressed
            if (event?.key === 'Escape') {
                cell.value = originalValue;
            }
            cell.setAttribute('readonly', 'readonly');
            cell.removeAttribute('data-original-value');
            this.validateCell(cell);
        }
    },

    validateCell(cell) {
        const value = cell.value.trim();
        const type = cell.dataset.type;
        let isValid = true;

        switch (type) {
            case 'number':
                isValid = !isNaN(value) && value !== '';
                break;
            case 'date':
                isValid = !isNaN(Date.parse(value));
                break;
            case 'required':
                isValid = value !== '';
                break;
        }

        cell.classList.toggle('invalid', !isValid);
        return isValid;
    },

    insertRow(above = false) {
        const currentRow = this.currentCell.closest('tr');
        const newRow = currentRow.cloneNode(true);
        
        // Clear values
        newRow.querySelectorAll('.grid-cell').forEach(cell => {
            cell.value = '';
            cell.classList.remove('invalid');
        });
        
        if (above) {
            currentRow.parentNode.insertBefore(newRow, currentRow);
        } else {
            currentRow.parentNode.insertBefore(newRow, currentRow.nextSibling);
        }
        
        this.pushToHistory({
            type: 'insert',
            row: newRow,
            position: above ? 'above' : 'below',
            reference: currentRow
        });
        
        // Focus first cell of new row
        newRow.querySelector('.grid-cell').focus();
    },

    deleteRow() {
        const row = this.currentCell.closest('tr');
        const rows = Array.from(this.gridBody.rows);
        
        if (rows.length <= 1) return; // Keep at least one row
        
        const index = rows.indexOf(row);
        const data = this.getRowData(row);
        
        row.remove();
        
        this.pushToHistory({
            type: 'delete',
            data,
            index
        });
        
        // Focus adjacent row
        const newIndex = Math.min(index, rows.length - 2);
        const targetCell = rows[newIndex].querySelector('.grid-cell');
        if (targetCell) targetCell.focus();
    },

    duplicateRow() {
        const row = this.currentCell.closest('tr');
        const newRow = row.cloneNode(true);
        row.parentNode.insertBefore(newRow, row.nextSibling);
        
        this.pushToHistory({
            type: 'duplicate',
            row: newRow,
            original: row
        });
        
        newRow.querySelector('.grid-cell').focus();
    },

    copyRow() {
        const row = this.currentCell.closest('tr');
        this.copiedRowData = this.getRowData(row);
        
        // Visual feedback
        row.classList.add('copied');
        setTimeout(() => row.classList.remove('copied'), 200);
    },

    pasteRow() {
        if (!this.copiedRowData) return;
        
        const row = this.currentCell.closest('tr');
        const oldData = this.getRowData(row);
        
        this.setRowData(row, this.copiedRowData);
        
        this.pushToHistory({
            type: 'paste',
            row,
            oldData,
            newData: this.copiedRowData
        });
        
        // Visual feedback
        row.classList.add('pasted');
        setTimeout(() => row.classList.remove('pasted'), 200);
    },

    getRowData(row) {
        return Array.from(row.querySelectorAll('.grid-cell')).map(cell => ({
            value: cell.value,
            attributes: Array.from(cell.attributes).reduce((attrs, attr) => {
                attrs[attr.name] = attr.value;
                return attrs;
            }, {})
        }));
    },

    setRowData(row, data) {
        const cells = row.querySelectorAll('.grid-cell');
        cells.forEach((cell, i) => {
            if (data[i]) {
                cell.value = data[i].value;
                // Restore attributes
                Object.entries(data[i].attributes).forEach(([name, value]) => {
                    cell.setAttribute(name, value);
                });
                this.validateCell(cell);
            }
        });
    },

    pushToHistory(action) {
        // Remove any future history if we're not at the latest state
        if (this.historyIndex < this.editHistory.length - 1) {
            this.editHistory = this.editHistory.slice(0, this.historyIndex + 1);
        }
        
        this.editHistory.push(action);
        if (this.editHistory.length > this.maxHistory) {
            this.editHistory.shift();
        }
        this.historyIndex = this.editHistory.length - 1;
    },

    undo() {
        if (this.historyIndex < 0) return;
        
        const action = this.editHistory[this.historyIndex];
        this.historyIndex--;
        
        this.applyHistoryAction(action, true);
    },

    redo() {
        if (this.historyIndex >= this.editHistory.length - 1) return;
        
        this.historyIndex++;
        const action = this.editHistory[this.historyIndex];
        
        this.applyHistoryAction(action, false);
    },

    applyHistoryAction(action, isUndo) {
        switch (action.type) {
            case 'edit':
                action.cell.value = isUndo ? action.oldValue : action.newValue;
                this.validateCell(action.cell);
                break;
                
            case 'insert':
                if (isUndo) {
                    action.row.remove();
                } else {
                    action.reference.parentNode.insertBefore(
                        action.row,
                        action.position === 'above' ? action.reference : action.reference.nextSibling
                    );
                }
                break;
                
            case 'delete':
                if (isUndo) {
                    const rows = Array.from(this.gridBody.rows);
                    const referenceRow = rows[Math.min(action.index, rows.length - 1)];
                    const newRow = referenceRow.cloneNode(true);
                    this.setRowData(newRow, action.data);
                    referenceRow.parentNode.insertBefore(newRow, referenceRow);
                }
                break;
                
            case 'duplicate':
                if (isUndo) {
                    action.row.remove();
                } else {
                    action.original.parentNode.insertBefore(
                        action.row.cloneNode(true),
                        action.original.nextSibling
                    );
                }
                break;
                
            case 'paste':
                this.setRowData(action.row, isUndo ? action.oldData : action.newData);
                break;
        }
    }
};

// Initialize Grid Navigation
document.addEventListener('DOMContentLoaded', () => {
    const gridBody = document.getElementById('journal-grid-body');
    if (gridBody) {
        GridNavigation.init(gridBody);
    }
});
