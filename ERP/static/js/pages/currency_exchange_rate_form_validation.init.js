document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('currency-exchange-rate-form');

    if (form) {
        var pristine = new Pristine(form, {
            classTo: 'mb-3', // Parent element to add error/success classes to
            errorTextParent: 'mb-3', // Parent element to append error text to
            errorTextClass: 'invalid-feedback' // Class for error text
        });

        // Pristine.js will now pick up 'required' attributes and 'data-pristine-required-message'
        // directly from the HTML rendered by Django forms.
        // No need for explicit pristine.addValidator for 'required' if configured on widgets.

        form.addEventListener('submit', function (e) {
            e.preventDefault(); // Prevent default form submission
            if (pristine.validate()) {
                // If Pristine validation passes, then allow form submission
                form.submit();
            } else {
                console.log("Client-side validation failed.");
                // Optionally scroll to the first error
                var firstError = document.querySelector('.has-danger');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }

    // Initialize date picker
    // Ensure this part is separate and runs even if Pristine.js fails to initialize for some reason.
    $('.datepicker').datepicker({
        format: 'yyyy-mm-dd',
        autoclose: true,
        todayHighlight: true,
        clearBtn: true,
        orientation: "bottom auto"
    });
}); 