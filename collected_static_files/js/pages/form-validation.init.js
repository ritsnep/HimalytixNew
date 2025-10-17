!function(){"use strict";window.addEventListener("load",function(){var e=document.getElementsByClassName("needs-validation");Array.prototype.filter.call(e,function(t){t.addEventListener("submit",function(e){!1===t.checkValidity()&&(e.preventDefault(),e.stopPropagation()),t.classList.add("was-validated")},!1)})},!1)}(),window.onload=function(){var e=document.getElementById("pristine-valid-example"),t=new Pristine(e);e.addEventListener("submit",function(e){e.preventDefault();t.validate()});var n=document.getElementById("pristine-valid-common"),i=new Pristine(n);n.addEventListener("submit",function(e){e.preventDefault();i.validate()});var e=document.getElementById("pristine-valid-specificfield"),a=new Pristine(e),n=document.getElementById("specificfield");a.addValidator(n,function(e,t){return!(!e.length||e[0]!==e[0].toUpperCase())},"The first character must be capitalized",2,!1),e.addEventListener("submit",function(e){e.preventDefault();a.validate()})};

// This script applies Pristine.js validation to all forms with the 'needs-validation' class.
document.addEventListener('DOMContentLoaded', function() {
    var forms = document.querySelectorAll('form.needs-validation'); 

    forms.forEach(function(form) {
        var pristine = new Pristine(form, {
            classTo: 'mb-3',          // Parent element to add error/success classes (e.g., div.mb-3)
            errorTextParent: 'mb-3',  // Parent element to append error text to
            errorTextClass: 'invalid-feedback' // Class for error text
        });

        // Handle form submission
        form.addEventListener('submit', function (e) {
            e.preventDefault(); // Prevent default browser submission
            if (pristine.validate()) {
                // If validation passes, allow the form to submit
                form.submit();
            } else {
                console.log("Client-side validation failed for form:", form.id || form.name);
                // Optionally scroll to the first error for better UX
                var firstError = form.querySelector('.has-danger');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    });

    // Datepicker initialization is now handled in _form_base.html, no longer here.
});