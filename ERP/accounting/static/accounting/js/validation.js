document.addEventListener('DOMContentLoaded', function () {
    const errorPanel = document.getElementById('error-panel');
    const errorList = document.getElementById('error-list');

    function validateField(voucherType, fieldName, fieldValue) {
        fetch('/accounting/api/v1/validate-field/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
                voucher_type: voucherType,
                field_name: fieldName,
                field_value: fieldValue,
            }),
        })
        .then(response => response.json())
        .then(data => {
            clearErrors(fieldName);
            if (data.status === 'error') {
                displayErrors(fieldName, data.errors);
            }
        });
    }

    function displayErrors(fieldName, errors) {
        if (!errors || !errorPanel || !errorList) {
            return;
        }

        errorPanel.style.display = 'block';
        for (const [field, messages] of Object.entries(errors)) {
            messages.forEach(message => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = `${field}: ${message}`;
                li.setAttribute('data-field', field);
                errorList.appendChild(li);
            });
        }
    }

    function clearErrors(fieldName) {
        if (!errorList) {
            return;
        }
        const items = errorList.querySelectorAll(`[data-field="${fieldName}"]`);
        items.forEach(item => item.remove());

        if (errorList.children.length === 0) {
            errorPanel.style.display = 'none';
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const voucherTypeInput = document.querySelector('input[name="voucher_type"]');
    if (voucherTypeInput) {
        const voucherType = voucherTypeInput.value;
        const fields = document.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            field.addEventListener('blur', (e) => {
                validateField(voucherType, e.target.name, e.target.value);
            });
        });
    }
});