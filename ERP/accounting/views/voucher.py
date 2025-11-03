from django.forms import formset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views import View
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

from accounting.models import Journal, JournalLine, VoucherModeConfig
from accounting.forms_factory import build_form
from accounting.services.create_voucher import create_voucher
from accounting.validation import JournalValidationService
from accounting.services.post_journal import JournalError
from usermanagement.utils import PermissionUtils
from .views_mixins import VoucherConfigMixin, PermissionRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin

logger = logging.getLogger(__name__)

def _inject_udfs_into_schema(schema, udf_configs):
    """Injects UDF configurations into the header and lines schema."""
    header_schema = schema.get("header", {})
    lines_schema = schema.get("lines", {})

    for udf in udf_configs:
        udf_schema = {
            "name": f"udf_{udf.field_name}",
            "label": udf.field_label,
            "type": udf.field_type,
            "required": udf.is_required,
            "choices": udf.choices or [],
        }
        if udf.scope == 'header':
            header_schema.setdefault('fields', []).append(udf_schema)
        elif udf.scope == 'line':
            lines_schema.setdefault('fields', []).append(udf_schema)
    return schema


class VoucherEntryView(VoucherConfigMixin, PermissionRequiredMixin, LoginRequiredMixin, View):
    template_name = 'accounting/voucher_entry.html'
    permission_required = ('accounting', 'journal', 'add')
    config_pk_kwarg = "config_id"

    def get_user_perms(self, request):
        """
        Return a dict of user permissions for voucher actions.
        """
        organization = request.user.get_active_organization()
        return {
            "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
            "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
            "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
        }

    def _get_voucher_schema(self, config):
        schema = config.resolve_ui()
        warning = None
        if schema:
            # Drop dimensional fields if not shown
            if not config.show_dimensions:
                for field in ["department", "project", "cost_center"]:
                    schema["lines"].pop(field, None)
            
            # Drop tax details if not shown
            if not config.show_tax_details:
                schema["lines"].pop("tax_code", None)

            # Enforce required line description
            if config.require_line_description and "description" in schema["lines"]:
                schema["lines"]["description"]["required"] = True

            # Handle multi-currency
            if not config.allow_multiple_currencies:
                schema["lines"].pop("currency_code", None)
                schema["lines"].pop("exchange_rate", None)

            schema = _inject_udfs_into_schema(schema, list(config.udf_configs.all()))
        return schema, warning

    def _create_voucher_forms(self, schema, organization, user_perms, request=None):
        header_schema_dict = schema.get("header", {})
        lines_schema_dict = schema.get("lines", {})

        # Convert header schema dict to list format expected by FormBuilder
        header_fields = []
        for field_name, field_cfg in header_schema_dict.items():
            field_def = field_cfg.copy()
            field_def["name"] = field_name
            header_fields.append(field_def)
        
        HeaderFormClass = build_form({"fields": header_fields}, model=Journal, prefix="hdr")

        # Convert lines schema dict to list format
        line_fields = []
        for field_name, field_cfg in lines_schema_dict.items():
            field_def = field_cfg.copy()
            field_def["name"] = field_name
            line_fields.append(field_def)
            
        LineFormClass = build_form({"fields": line_fields}, model=JournalLine, prefix="line")
        LineFormset = formset_factory(LineFormClass, extra=1)

        if request:
            header_form = HeaderFormClass(request.POST)
            line_formset = LineFormset(request.POST)
        else:
            header_form = HeaderFormClass(initial={'journal_date': timezone.now().strftime('%Y-%m-%d')})
            line_formset = LineFormset()
        
        return header_form, line_formset

    def get(self, request, *args, **kwargs):
        config_id = kwargs.get("config_id")
        warning = None
        config = None
        
        all_configs = VoucherModeConfig.objects.filter(is_active=True, archived_at__isnull=True)
        
        if not config_id:
            config = all_configs.first()
            if not config:
                return render(request, self.template_name, {
                    "page_title": "Voucher Entry",
                    "user_perms": self.get_user_perms(request),
                    "error": "No voucher configuration available.",
                    "voucher_configs": all_configs,
                })
            config_id = config.pk
        
        try:
            config = self.get_config()
        except Exception as e:
            warning = f"Voucher configuration not found: {e}"

        schema, schema_warning = self._get_voucher_schema(config)
        if schema_warning:
            warning = schema_warning

        if not schema:
            return render(request, self.template_name, {
                "error": warning or "Schema not found for this voucher type.",
                "user_perms": self.get_user_perms(request),
                "config": config,
                "voucher_configs": all_configs,
            })

        organization = request.user.get_active_organization()
        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms)

        defaults = list(getattr(config, 'defaults', []).all())
        
        context = {
            "config": config,
            "header_form": header_form,
            "lines_fs": line_formset,
            "user_perms": user_perms,
            "page_title": "Voucher Entry",
            "voucher_configs": all_configs,
            "defaults": defaults,
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        logger.debug(f"VoucherEntryView.post called by user={request.user} POST={request.POST}")
        
        try:
            config = self.get_config()
        except Exception as e:
            return render(request, self.template_name, {
                "error": f"Voucher configuration not found: {e}",
                "user_perms": self.get_user_perms(request),
            })

        schema, warning = self._get_voucher_schema(config)
        if not schema:
            return render(request, self.template_name, {
                "error": warning or "Schema not found for this voucher type.",
                "user_perms": self.get_user_perms(request),
                "config": config,
            })

        organization = request.user.get_active_organization()
        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms, request=request)

        if header_form.is_valid() and line_formset.is_valid():
            header_data = header_form.cleaned_data
            lines_data = [f.cleaned_data for f in line_formset.forms if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]

            # Custom validation rules
            rules = config.validation_rules or {}
            if rules.get("max_lines") is not None:
                max_lines = int(rules["max_lines"])
                if len(lines_data) > max_lines:
                    line_formset.add_error(None, ValidationError(f"Maximum {max_lines} lines allowed for this voucher."))

            if rules.get("debit_accounts_only"):
                for i, line in enumerate(lines_data):
                    account = line.get("account")
                    if account and account.account_type.nature != 'debit':
                        line_formset.forms[i].add_error('account', "Only debit accounts are allowed.")

            if rules.get("no_tax_without_account"):
                for i, line in enumerate(lines_data):
                    tax = line.get('tax_code')
                    acct = line.get('account')
                    if tax and not acct:
                        line_formset.forms[i].add_error('account', "Account is required if Tax Code is specified.")

            validation_service = JournalValidationService(organization)
            errors = validation_service.validate_journal_entry(header_data, lines_data)

            if not errors and not line_formset.non_form_errors():
                # Single entry auto-balancing
                if config.default_voucher_mode == 'single_entry':
                    total_debit = sum(line.get('debit_amount', 0) for line in lines_data)
                    total_credit = sum(line.get('credit_amount', 0) for line in lines_data)
                    diff = total_debit - total_credit

                    if diff != 0:
                        default_account = config.default_ledger
                        if not default_account:
                            line_formset.add_error(None, ValidationError("This voucher must balance to a default ledger, but none is configured."))
                        else:
                            offset_line = {
                                "account": default_account.pk,
                                "description": config.name + " Offset",
                                "debit_amount": 0, "credit_amount": 0,
                                "department": None, "project": None, "cost_center": None, "tax_code": None
                            }
                            if diff > 0:
                                offset_line["credit_amount"] = diff
                            else:
                                offset_line["debit_amount"] = -diff
                            lines_data.append(offset_line)

                with transaction.atomic():
                    try:
                        journal = create_voucher(
                            user=request.user,
                            config_id=config.pk,
                            header_data=header_data,
                            lines_data=lines_data,
                        )
                        messages.success(request, "Voucher created successfully.")
                        return redirect('accounting:journal_list')
                    except (JournalError, ValidationError) as e:
                        logger.error(
                            "Error creating voucher: %s", e,
                            exc_info=True,
                            extra={'user_id': request.user.pk, 'organization_id': request.organization.pk}
                        )
                        messages.error(request, f"Error creating voucher: {e}")
                    except Exception as e:
                        logger.exception(
                            "An unexpected error occurred while creating voucher: %s", e,
                            extra={'user_id': request.user.pk, 'organization_id': request.organization.pk}
                        )
                        messages.error(request, "An unexpected error occurred while creating the voucher.")
            else:
                if 'general' in errors:
                    for error in errors['general']:
                        header_form.add_error(None, error)
                if 'header' in errors:
                    for field, error in errors['header'].items():
                        header_form.add_error(field, error)
                if 'lines' in errors:
                    for error_info in errors['lines']:
                        index = error_info['index']
                        for field, error in error_info['errors'].items():
                            line_formset.forms[index].add_error(field, error)
                logger.warning(
                    "Voucher validation failed for user %s, organization %s. Errors: %s",
                    request.user.pk, request.organization.pk, errors,
                    extra={'user_id': request.user.pk, 'organization_id': request.organization.pk, 'validation_errors': errors}
                )
        else:
            logger.error(
                'Header form errors: %s, Line formset errors: %s for user %s, organization %s',
                header_form.errors, line_formset.errors, request.user.pk, request.organization.pk,
                extra={'user_id': request.user.pk, 'organization_id': request.organization.pk, 'header_errors': header_form.errors, 'line_errors': line_formset.errors}
            )
        
        context = {
            "config": config,
            "header_form": header_form,
            "lines_fs": line_formset,
            "user_perms": user_perms,
            "page_title": "Voucher Entry",
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)


def htmx_voucher_line(request):
    config_id = request.GET.get('config_id')
    index = request.GET.get('index', '0')
    organization = request.user.get_active_organization()
    
    config = get_object_or_404(VoucherModeConfig, pk=config_id)
    schema = config.resolve_ui()
    
    if not schema or 'lines' not in schema:
        return HttpResponse("Error: Schema not found or invalid.", status=400)

    lines_schema_dict = schema.get("lines", {})
    line_fields = []
    for field_name, field_cfg in lines_schema_dict.items():
        field_def = field_cfg.copy()
        field_def["name"] = field_name
        line_fields.append(field_def)
        
    LineFormClass = build_form({"fields": line_fields}, model=JournalLine, prefix=f"line-{index}")
    form = LineFormClass()
    
    return render(request, 'accounting/partials/voucher_line_row.html', {
        'form': form,
        'index': index,
    })
