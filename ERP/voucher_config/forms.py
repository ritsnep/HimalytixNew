from django import forms
from accounting.forms_factory import VoucherFormFactory
from accounting.services.voucher_errors import VoucherProcessError


class VoucherFormMixin:
    """Utility mixin to build and instantiate header form and line formset

    Usage:
        mixin = VoucherFormMixin()
        header_cls, line_formset_cls = mixin.build_forms(config, organization)
        header = mixin.instantiate_form(header_cls, data=request.POST)
        lines = mixin.instantiate_formset(line_formset_cls, data=request.POST)
    """

    def build_forms(self, voucher_config, organization):
        try:
            build_result = VoucherFormFactory.build(voucher_config=voucher_config, organization=organization)
        except VoucherProcessError as exc:
            raise
        if len(build_result) == 3:
            header_cls, line_formset_cls, additional_charges_formset_cls = build_result
            return header_cls, line_formset_cls, additional_charges_formset_cls
        return build_result

    def instantiate_form(self, form_cls, data=None, files=None, instance=None, prefix=None, initial=None):
        kwargs = {}
        if data is not None:
            kwargs['data'] = data
        if files is not None:
            kwargs['files'] = files
        if instance is not None:
            kwargs['instance'] = instance
        if initial is not None:
            kwargs['initial'] = initial
        if prefix is not None:
            kwargs['prefix'] = prefix
        return form_cls(**kwargs)

    def instantiate_formset(self, formset_cls, data=None, files=None, prefix=None, initial=None):
        kwargs = {}
        if data is not None:
            kwargs['data'] = data
        if files is not None:
            kwargs['files'] = files
        if prefix is not None:
            kwargs['prefix'] = prefix
        if initial is not None:
            kwargs['initial'] = initial
        return formset_cls(**kwargs)
