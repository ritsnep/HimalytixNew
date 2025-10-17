// Utility functions for dynamic components
const ComponentUtils = {
    // Initialize dynamic table
    initTable: function(tableId, options = {}) {
        const defaultOptions = {
            processing: true,
            serverSide: true,
            responsive: true,
            dom: 'Bfrtip',
            buttons: ['copy', 'csv', 'excel', 'pdf', 'print'],
            pageLength: 25,
            order: []
        };

        return $(tableId).DataTable({
            ...defaultOptions,
            ...options
        });
    },

    // Initialize dynamic form
    initForm: function(formId, options = {}) {
        const form = $(formId);
        const defaultOptions = {
            ajax: true,
            resetOnSuccess: true,
            successCallback: null,
            errorCallback: null
        };

        const settings = { ...defaultOptions, ...options };

        form.on('submit', function(e) {
            if (settings.ajax) {
                e.preventDefault();
                ComponentUtils.submitForm(form, settings);
            }
        });

        // Initialize select2 for select elements
        form.find('select').select2();

        // Initialize datepicker for date inputs
        form.find('input[type="date"]').flatpickr();

        return form;
    },

    // Submit form via AJAX
    submitForm: function(form, settings) {
        $.ajax({
            url: form.attr('action'),
            type: 'POST',
            data: new FormData(form[0]),
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.status === 'success') {
                    toastr.success(response.message || 'Success!');
                    if (settings.resetOnSuccess) {
                        form[0].reset();
                    }
                    if (settings.successCallback) {
                        settings.successCallback(response);
                    }
                    if (response.redirect_url) {
                        window.location.href = response.redirect_url;
                    }
                } else {
                    ComponentUtils.handleFormErrors(form, response.errors);
                    if (settings.errorCallback) {
                        settings.errorCallback(response);
                    }
                }
            },
            error: function(xhr) {
                toastr.error('An error occurred. Please try again.');
                if (settings.errorCallback) {
                    settings.errorCallback(xhr);
                }
            }
        });
    },

    // Handle form errors
    handleFormErrors: function(form, errors) {
        form.find('.is-invalid').removeClass('is-invalid');
        form.find('.invalid-feedback').remove();

        $.each(errors, function(field, messages) {
            const input = form.find(`[name="${field}"]`);
            input.addClass('is-invalid');
            input.after(`<div class="invalid-feedback">${messages.join('<br>')}</div>`);
        });
    },

    // Initialize dialog
    initDialog: function(dialogId, options = {}) {
        const dialog = $(dialogId);
        const defaultOptions = {
            onShow: null,
            onHide: null,
            onSubmit: null
        };

        const settings = { ...defaultOptions, ...options };

        // Handle dialog events
        dialog.on('show.bs.modal', function(e) {
            if (settings.onShow) {
                settings.onShow(e);
            }
        });

        dialog.on('hide.bs.modal', function(e) {
            if (settings.onHide) {
                settings.onHide(e);
            }
        });

        // Handle dialog form submission
        dialog.find('form').on('submit', function(e) {
            e.preventDefault();
            if (settings.onSubmit) {
                settings.onSubmit(e, $(this));
            }
        });

        return dialog;
    },

    // Load content into dialog
    loadDialog: function(url, dialogId) {
        $.get(url, function(response) {
            $(dialogId).find('.modal-content').html(response);
            $(dialogId).modal('show');
        });
    }
};

// Export for use in other modules
window.ComponentUtils = ComponentUtils;
