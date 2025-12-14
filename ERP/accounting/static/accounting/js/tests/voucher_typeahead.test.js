import { html, fixture, expect } from '@open-wc/testing';
import sinon from 'sinon';

// Mock htmx if not available
if (!window.htmx) {
    window.htmx = {
        process: () => {}
    };
}

describe('Voucher Typeahead and Keyboard Navigation', () => {
    let mockFetch;

    beforeEach(() => {
        mockFetch = sinon.stub(window, 'fetch');
    });

    afterEach(() => {
        mockFetch.restore();
    });

    it('initializes typeahead on DOMContentLoaded', async () => {
        const el = await fixture(html`
            <div>
                <input type="text" class="account-typeahead" data-list-id="accounts-1" data-hidden-name="lines-0-account">
                <datalist id="accounts-1"></datalist>
                <input type="hidden" name="lines-0-account">
            </div>
        `);

        // Trigger DOMContentLoaded
        const event = new Event('DOMContentLoaded');
        document.dispatchEvent(event);

        const input = el.querySelector('.account-typeahead');
        expect(input._initialized).to.be.true;
    });

    it('fetches account suggestions on input', async () => {
        mockFetch.resolves({
            json: () => Promise.resolve({
                results: [
                    { id: 1, code: '1000', name: 'Cash' },
                    { id: 2, code: '2000', name: 'Bank' }
                ]
            })
        });

        const el = await fixture(html`
            <div>
                <input type="text" class="account-typeahead" data-list-id="accounts-1" data-hidden-name="lines-0-account">
                <datalist id="accounts-1"></datalist>
                <input type="hidden" name="lines-0-account">
            </div>
        `);

        const input = el.querySelector('.account-typeahead');
        const datalist = el.querySelector('#accounts-1');

        // Trigger input
        input.value = 'Ca';
        input.dispatchEvent(new Event('input'));

        await new Promise(resolve => setTimeout(resolve, 100));

        expect(mockFetch.calledOnce).to.be.true;
        expect(datalist.children.length).to.equal(2);
        expect(datalist.children[0].value).to.equal('1000 - Cash');
    });

    it('navigates between inputs with Tab', async () => {
        const el = await fixture(html`
            <div id="line-1" class="row">
                <input type="text" class="account-typeahead">
                <input type="text" name="description">
                <input type="number" name="debit_amount">
            </div>
        `);

        const inputs = el.querySelectorAll('input');
        const firstInput = inputs[0];

        // Focus first input
        firstInput.focus();
        expect(document.activeElement).to.equal(firstInput);

        // Simulate Tab
        const tabEvent = new KeyboardEvent('keydown', { key: 'Tab' });
        firstInput.dispatchEvent(tabEvent);

        expect(document.activeElement).to.equal(inputs[1]);
    });

    it('navigates to next row with Enter', async () => {
        const el = await fixture(html`
            <div>
                <div id="line-1" class="row">
                    <input type="text" class="account-typeahead">
                    <input type="text" name="description">
                </div>
                <div id="line-2" class="row">
                    <input type="text" class="account-typeahead">
                    <input type="text" name="description">
                </div>
            </div>
        `);

        const rows = el.querySelectorAll('.row');
        const firstInput = rows[0].querySelector('input');

        // Focus first input
        firstInput.focus();

        // Simulate Enter
        const enterEvent = new KeyboardEvent('keydown', { key: 'Enter' });
        firstInput.dispatchEvent(enterEvent);

        const secondInput = rows[1].querySelector('input');
        expect(document.activeElement).to.equal(secondInput);
    });

    it('navigates vertically with Arrow keys', async () => {
        const el = await fixture(html`
            <div>
                <div id="line-1" class="row">
                    <input type="text" class="account-typeahead">
                </div>
                <div id="line-2" class="row">
                    <input type="text" class="account-typeahead">
                </div>
            </div>
        `);

        const rows = el.querySelectorAll('.row');
        const firstInput = rows[0].querySelector('input');

        // Focus first input
        firstInput.focus();

        // Simulate ArrowDown
        const downEvent = new KeyboardEvent('keydown', { key: 'ArrowDown' });
        firstInput.dispatchEvent(downEvent);

        const secondInput = rows[1].querySelector('input');
        expect(document.activeElement).to.equal(secondInput);
    });
});