document.addEventListener('DOMContentLoaded', function() {
    function updateAccountCode() {
        const orgInput = document.querySelector('[name="organization"]');
        const accountTypeInput = document.querySelector('[name="account_type"]');
        const parentInput = document.querySelector('[name="parent_account"]');
        const codeInput = document.querySelector('[name="account_code"]');
        if (!orgInput || !accountTypeInput || !codeInput) return;

        const orgId = orgInput.value;
        const accountTypeId = accountTypeInput.value;
        const parentId = parentInput ? parentInput.value : null;

        if (!orgId || (!accountTypeId && !parentId)) {
            codeInput.value = '';
            return;
        }

        let params = `?organization=${orgId}`;
        if (parentId) {
            params += `&parent_account=${parentId}`;
        } else if (accountTypeId) {
            params += `&account_type=${accountTypeId}`;
        }

        fetch('/accounting/ajax/get-next-account-code/' + params)
            .then(response => response.json())
            .then(data => {
                if (data.next_code) {
                    codeInput.value = data.next_code;
                } else {
                    codeInput.value = '';
                }
            })
            .catch(() => {
                codeInput.value = '';
            });
    }

    const accountTypeInput = document.querySelector('[name="account_type"]');
    const parentInput = document.querySelector('[name="parent_account"]');
    if (accountTypeInput) accountTypeInput.addEventListener('change', updateAccountCode);
    if (parentInput) parentInput.addEventListener('change', updateAccountCode);

    // Optionally, update on page load if editing
    updateAccountCode();
});
