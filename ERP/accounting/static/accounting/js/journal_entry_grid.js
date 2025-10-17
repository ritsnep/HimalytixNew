// accounting/static/accounting/js/journal_entry_grid.js
document.addEventListener('DOMContentLoaded', function () {
    const addRowBtn = document.getElementById('add-row-btn');
    const gridRows = document.getElementById('je-grid-rows');
    
    let nextIndex = parseInt(gridRows.dataset.nextIndex, 10);
    const csrfToken = gridRows.dataset.csrfToken;
    const addRowUrl = gridRows.dataset.addRowUrl;

    addRowBtn.addEventListener('click', function () {
        const formData = new FormData();
        formData.append('next_index', nextIndex);
        formData.append('csrfmiddlewaretoken', csrfToken);

        fetch(addRowUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.text())
        .then(html => {
            gridRows.insertAdjacentHTML('beforeend', html);
            nextIndex++;
            gridRows.dataset.nextIndex = nextIndex;
        })
        .catch(error => console.error('Error adding row:', error));
    });
});