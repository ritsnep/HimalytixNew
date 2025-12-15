document.addEventListener('DOMContentLoaded', function() {
    const orgInput = document.querySelector('[name="organization"]');
    const accountTypeInput = document.querySelector('[name="account_type"]');
    const parentInput = document.querySelector('[name="parent_account"]');
    const codeInput = document.querySelector('[name="account_code"]');

    if (!orgInput || !accountTypeInput || !codeInput) {
        console.warn('Required account form fields not found for autofill.');
        return;
    }

    async function updateAccountCode() {
        const orgId = orgInput.value;
        const accountTypeId = accountTypeInput.value;
        const parentId = parentInput ? parentInput.value : null;

        if (!orgId || (!accountTypeId && !parentId)) {
            codeInput.value = '';
            return;
        }

        const params = new URLSearchParams();
        params.append('organization', orgId);

        if (parentId) {
            params.append('parent_account', parentId);
        } else if (accountTypeId) {
            params.append('account_type', accountTypeId);
        }

        try {
            const response = await fetch(`/accounting/ajax/get-next-account-code/?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            codeInput.value = data.next_code || '';
        } catch (error) {
            console.error('Error fetching next account code:', error);
            codeInput.value = '';
        }
    }

    orgInput.addEventListener('change', updateAccountCode);
    accountTypeInput.addEventListener('change', updateAccountCode);
    if (parentInput) {
        parentInput.addEventListener('change', updateAccountCode);
    }

    // Optionally, update on page load if editing
    updateAccountCode();
});
