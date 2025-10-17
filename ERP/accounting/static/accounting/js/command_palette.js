class CommandPalette {
    constructor() {
        this.element = document.getElementById('command-palette');
        this.input = document.getElementById('command-input');
        this.content = document.querySelector('.command-palette-content');
        this.overlay = document.querySelector('.command-palette-overlay');
        this.commands = this.getDefaultCommands();
        this.selectedIndex = 0;
        
        this.initializeEventListeners();
    }

    getDefaultCommands() {
        return [
            {
                group: 'Actions',
                items: [
                    { title: 'Save Journal Entry', shortcut: ['Ctrl', 'S'], action: () => this.saveJournalEntry() },
                    { title: 'Post Journal', shortcut: ['Ctrl', 'Enter'], action: () => this.postJournal() },
                    { title: 'Auto Balance', shortcut: ['Alt', 'B'], action: () => this.autoBalance() },
                    { title: 'Show Keyboard Shortcuts', shortcut: ['?'], action: () => this.toggleShortcutOverlay() }
                ]
            },
            {
                group: 'Navigation',
                items: [
                    { title: 'Focus Grid', shortcut: ['Alt', '1'], action: () => this.focusGrid() },
                    { title: 'Focus Details', shortcut: ['Alt', '2'], action: () => this.focusDetails() },
                    { title: 'Focus Attachments', shortcut: ['Alt', '3'], action: () => this.focusAttachments() }
                ]
            },
            {
                group: 'View',
                items: [
                    { title: 'Toggle Full Screen', shortcut: ['F11'], action: () => this.toggleFullScreen() },
                    { title: 'Toggle Dark Mode', shortcut: ['Ctrl', 'Alt', 'D'], action: () => this.toggleDarkMode() },
                    { title: 'Reset Layout', action: () => this.resetLayout() }
                ]
            }
        ];
    }

    initializeEventListeners() {
        // Toggle command palette
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
        });

        // Close on overlay click
        this.overlay.addEventListener('click', () => this.hide());

        // Search input handling
        this.input.addEventListener('input', () => this.filterCommands());

        // Keyboard navigation
        this.element.addEventListener('keydown', (e) => {
            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    this.selectNext();
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.selectPrevious();
                    break;
                case 'Enter':
                    e.preventDefault();
                    this.executeSelected();
                    break;
                case 'Escape':
                    e.preventDefault();
                    this.hide();
                    break;
            }
        });
    }

    toggle() {
        if (this.element.classList.contains('active')) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        this.element.classList.add('active');
        this.input.value = '';
        this.input.focus();
        this.filterCommands();
    }

    hide() {
        this.element.classList.remove('active');
        this.selectedIndex = 0;
    }

    filterCommands() {
        const query = this.input.value.toLowerCase();
        let filteredHtml = '';
        let totalItems = 0;

        for (const group of this.commands) {
            const filteredItems = group.items.filter(item =>
                item.title.toLowerCase().includes(query)
            );

            if (filteredItems.length > 0) {
                filteredHtml += `
                    <div class="command-group">
                        <div class="command-group-title">${group.group}</div>
                        ${filteredItems.map((item, index) => `
                            <div class="command-item ${totalItems === this.selectedIndex ? 'selected' : ''}" 
                                 data-index="${totalItems++}">
                                <i class="fas fa-${this.getIconForCommand(item.title)}"></i>
                                <span class="command-item-title">${item.title}</span>
                                ${item.shortcut ? `
                                    <div class="command-item-shortcut">
                                        ${item.shortcut.map(key => `<kbd>${key}</kbd>`).join('')}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        }

        this.content.innerHTML = filteredHtml;
    }

    getIconForCommand(title) {
        const iconMap = {
            'Save': 'save',
            'Post': 'paper-plane',
            'Balance': 'balance-scale',
            'Keyboard': 'keyboard',
            'Focus': 'crosshairs',
            'Full': 'expand',
            'Dark': 'moon',
            'Reset': 'undo'
        };

        return Object.keys(iconMap).find(key => title.includes(key))
            ? iconMap[Object.keys(iconMap).find(key => title.includes(key))]
            : 'chevron-right';
    }

    selectNext() {
        const items = this.content.querySelectorAll('.command-item');
        if (items.length === 0) return;

        this.selectedIndex = (this.selectedIndex + 1) % items.length;
        this.updateSelection(items);
    }

    selectPrevious() {
        const items = this.content.querySelectorAll('.command-item');
        if (items.length === 0) return;

        this.selectedIndex = (this.selectedIndex - 1 + items.length) % items.length;
        this.updateSelection(items);
    }

    updateSelection(items) {
        items.forEach(item => item.classList.remove('selected'));
        items[this.selectedIndex].classList.add('selected');
        items[this.selectedIndex].scrollIntoView({ block: 'nearest' });
    }

    executeSelected() {
        const selectedItem = this.content.querySelector('.command-item.selected');
        if (!selectedItem) return;

        const groupIndex = Math.floor(selectedItem.dataset.index / this.commands[0].items.length);
        const itemIndex = selectedItem.dataset.index % this.commands[0].items.length;
        const command = this.commands[groupIndex].items[itemIndex];

        this.hide();
        command.action();
    }

    // Command Actions
    saveJournalEntry() {
        // Implement save functionality
    }

    postJournal() {
        // Implement post functionality
    }

    autoBalance() {
        // Implement auto balance functionality
    }

    toggleShortcutOverlay() {
        const overlay = document.getElementById('shortcut-overlay');
        overlay.classList.toggle('active');
    }

    focusGrid() {
        // Implement grid focus
    }

    focusDetails() {
        // Implement details focus
    }

    focusAttachments() {
        // Implement attachments focus
    }

    toggleFullScreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    toggleDarkMode() {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    }

    resetLayout() {
        // Implement layout reset
    }
}

// Initialize Command Palette
document.addEventListener('DOMContentLoaded', () => {
    window.commandPalette = new CommandPalette();
});
