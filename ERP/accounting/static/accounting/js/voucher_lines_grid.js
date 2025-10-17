document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('voucher-lines-grid');
    if (!container) {
        return;
    }

    const formsetPrefix = 'form';
    const totalFormsInput = document.querySelector('input[name="' + formsetPrefix + '-TOTAL_FORMS"]');
    let initialData = [];
    if (totalFormsInput) {
        const formCount = parseInt(totalFormsinsput.value, 10);
        for (let i = 0; i < formCount; i++) {
            const row = {
                'account': document.querySelector('input[name="' + formsetPrefix + '-' + i + '-account"]').value,
                'debit': document.querySelector('input[name="' + formsetPrefix + '-' + i + '-debit"]').value,
                'credit': document.querySelector('input[name="' + formsetPrefix + '-' + i + '-credit"]').value,
                'description': document.querySelector('input[name="' + formsetPrefix + '-' + i + '-description"]').value,
            };
            initialData.push(row);
        }
    }

    const hot = new Handsontable(container, {
        data: initialData,
        colHeaders: ['Account', 'Debit', 'Credit', 'Description'],
        columns: [
            { data: 'account' },
            { data: 'debit', type: 'numeric' },
            { data: 'credit', type: 'numeric' },
            { data: 'description' },
        ],
        rowHeaders: true,
        colWidths: [200, 100, 100, 300],
        minSpareRows: 1,
        licenseKey: 'non-commercial-and-evaluation',
        afterChange: (changes, source) => {
            if (source === 'loadData') {
                return;
            }
            updateFormset();
            validateTotals();
        },
        afterPaste: (data, coords) => {
            updateFormset();
            validateTotals();
        }
    });

    function updateFormset() {
        const gridData = hot.getData();
        const rowCount = gridData.length;
        totalFormsInput.value = rowCount;

        for (let i = 0; i < rowCount; i++) {
            const row = gridData[i];
            document.querySelector('input[name="' + formsetPrefix + '-' + i + '-account"]').value = row[0] || '';
            document.querySelector('input[name="' + formsetPrefix + '-' + i + '-debit"]').value = row[1] || '';
            document.querySelector('input[name="' + formsetPrefix + '-' + i + '-credit"]').value = row[2] || '';
            document.querySelector('input[name="' + formsetPrefix + '-' + i + '-description"]').value = row[3] || '';
        }
    }

    function validateTotals() {
        let totalDebit = 0;
        let totalCredit = 0;
        const gridData = hot.getData();

        gridData.forEach(row => {
            const debit = parseFloat(row[1]);
            const credit = parseFloat(row[2]);
            if (!isNaN(debit)) {
                totalDebit += debit;
            }
            if (!isNaN(credit)) {
                totalCredit += credit;
            }
        });

        const debitTotalEl = document.getElementById('debit-total');
        const creditTotalEl = document.getElementById('credit-total');
        const nextButton = document.querySelector('button[type="submit"]');

        if (debitTotalEl && creditTotalEl) {
            debitTotalEl.textContent = totalDebit.toFixed(2);
            creditTotalEl.textContent = totalCredit.toFixed(2);

            if (totalDebit !== totalCredit) {
                debitTotalEl.classList.add('text-danger');
                creditTotalEl.classList.add('text-danger');
                if (nextButton) {
                    nextButton.disabled = true;
                }
            } else {
                debitTotalEl.classList.remove('text-danger');
                creditTotalEl.classList.remove('text-danger');
                if (nextButton) {
                    nextButton.disabled = false;
                }
            }
        }
    }
});