describe('Journal Entry Keyboard Navigation', () => {
    beforeEach(() => {
        // For a real test, you would visit the actual journal entry page.
        // cy.visit('/accounting/journal-entry/new/');
        // For this example, we'll use a static HTML fixture.
        cy.visit('cypress/fixtures/journal_entry.html');
    });

    it('navigates up and down the grid with arrow keys', () => {
        // Focus the first cell of the first row
        cy.get('#journal-grid-body tr:first-child .grid-cell:first-child').focus();
        
        // Navigate down
        cy.focused().type('{downarrow}');
        cy.focused().should('have.closest', 'tr:nth-child(2)');

        // Navigate back up
        cy.focused().type('{uparrow}');
        cy.focused().should('have.closest', 'tr:first-child');
    });

    it('makes a line editable on Enter key press', () => {
        // Get the first row
        const firstRow = cy.get('#journal-grid-body tr:first-child');

        // Press enter on the row (by targeting a cell within it)
        firstRow.find('.grid-cell:first-child').focus().type('{enter}');

        // Assert that the row is now in editing mode
        firstRow.should('have.class', 'editing');
        firstRow.find('.grid-cell').each(cell => {
            cy.wrap(cell).should('not.have.attr', 'readonly');
        });
    });

    it('opens the command palette with Ctrl+K', () => {
        // Ensure the modal is not visible initially
        cy.get('#command-palette-modal').should('not.be.visible');

        // Send Ctrl+K shortcut
        cy.get('body').type('{ctrl}k');

        // Assert that the modal is now visible
        cy.get('#command-palette-modal').should('be.visible');
    });
});