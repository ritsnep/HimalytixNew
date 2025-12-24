"""
Dynamic date field utilities for Nepali/AD dual calendar support.

This module provides schema-aware utilities to automatically configure
date fields across all models with appropriate Nepali date support.
"""

import datetime
from typing import Any, Dict, List, Optional, Set, Type, Tuple

from django import forms
from django.apps import apps
from django.db import models
from django.utils import timezone

from utils.calendars import (
    CalendarMode,
    ad_to_bs_string,
    bs_to_ad_string,
    get_calendar_mode,
)
from utils.widgets import DualCalendarWidget, set_default_date_initial, dual_date_widget


# Schema definitions: maps model name to list of date fields that should use dual calendar
SCHEMA_DATE_FIELDS: Dict[str, List[str]] = {
    # Accounting module
    "FiscalYear": ["start_date", "end_date"],
    "AccountingPeriod": ["start_date", "end_date"],
    "Journal": ["posting_date"],
    "JournalLine": ["posting_date"],
    "ChartOfAccount": ["effective_from", "effective_to"],
    "GeneralLedger": ["posting_date", "transaction_date"],
    "VoucherModeDefault": ["effective_date"],
    "BankStatement": ["statement_date"],
    "BankTransaction": ["transaction_date"],
    "Budget": ["start_date", "end_date", "fiscal_year__start_date"],
    "BudgetLine": ["start_date", "end_date"],
    "Asset": ["acquisition_date", "disposal_date"],
    "AssetEvent": ["event_date"],
    "CurrencyExchangeRate": ["rate_date"],
    "CostCenter": ["effective_from", "effective_to"],
    "PurchaseInvoice": ["invoice_date", "due_date", "delivery_date"],
    "PurchaseInvoiceLine": ["delivery_date"],
    "SalesInvoice": ["invoice_date", "due_date", "delivery_date"],
    "SalesInvoiceLine": ["delivery_date"],
    "SalesOrder": ["order_date", "due_date"],
    "SalesOrderLine": ["promised_date"],
    "Quotation": ["quote_date", "valid_until"],
    "QuotationLine": ["delivery_date"],
    "ARReceipt": ["receipt_date"],
    "ARReceiptLine": ["receipt_date"],
    "APPayment": ["payment_date", "due_date"],
    "APPaymentLine": ["payment_date"],
    "PaymentBatch": ["batch_date"],
    "PaymentApproval": ["approval_date"],
    "TaxCode": ["effective_from", "effective_to"],
    "PaymentTerm": ["start_date", "end_date"],
    
    # Inventory module
    "Product": ["manufacture_date", "expiry_date"],
    "Batch": ["manufacture_date", "expiry_date"],
    "ProductUnit": [],  # No date fields
    "Warehouse": [],
    "Location": [],
    "InventoryItem": [],
    "StockLedger": ["txn_date"],
    "PriceList": ["valid_from", "valid_to"],
    "InwardGatePass": ["expected_date"],
    "PickList": ["pick_date", "completed_date"],
    "PackingList": ["packed_date"],
    "Shipment": ["estimated_delivery", "actual_delivery"],
    "ReceiveAgainstPurchaseOrder": ["expected_date"],
    "IssuanceRequest": ["requested_date", "approved_date"],
    
    # Service Management module
    "DeviceCategory": [],
    "DeviceModel": [],
    "DeviceLifecycle": ["deployed_date"],
    "ServiceContract": ["start_date", "end_date", "renewal_date"],
    "ServiceTicket": ["assigned_date", "created_date", "first_response_date", "resolution_date", "closed_date"],
    "WarrantyPool": [],
    "RMAHardware": [],
    "DeviceProvisioningLog": ["provisioning_date"],
}

# Fields that should NOT use dual calendar (timestamps, audit fields, etc.)
EXCLUDE_FIELD_PATTERNS: Set[str] = {
    "created_at",
    "updated_at",
    "deleted_at",
    "created_date",
    "updated_date",
    "deleted_date",
    "last_modified",
    "last_updated",
    "timestamp",
    "created_on",
    "modified_on",
}


def get_date_fields_for_model(model: Type[models.Model]) -> List[Tuple[str, models.Field]]:
    """
    Get all date/datetime fields for a model that should use dual calendar widget.
    
    Respects SCHEMA_DATE_FIELDS configuration and excludes audit/timestamp fields.
    
    Args:
        model: Django model class
        
    Returns:
        List of (field_name, field_instance) tuples
    """
    model_name = model.__name__
    configured_fields = SCHEMA_DATE_FIELDS.get(model_name, [])
    
    date_fields = []
    
    for field in model._meta.get_fields():
        # Skip non-date fields
        if not isinstance(field, (models.DateField, models.DateTimeField)):
            continue
            
        # Skip excluded patterns
        if field.name in EXCLUDE_FIELD_PATTERNS:
            continue
            
        # If schema is configured, only include explicitly listed fields
        if configured_fields:
            if field.name not in configured_fields:
                continue
        
        date_fields.append((field.name, field))
    
    return date_fields


def get_widget_for_field(
    field: models.Field,
    organization: Optional[Any] = None,
    default_view: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> forms.Widget:
    """
    Get appropriate widget for a date field with Nepali support.
    
    Args:
        field: Django model field
        organization: Organization instance for calendar mode detection
        default_view: Explicit calendar mode (AD, BS, DUAL)
        attrs: Additional widget attributes
        
    Returns:
        Widget instance (DualCalendarWidget for date fields)
    """
    if not isinstance(field, (models.DateField, models.DateTimeField)):
        raise ValueError(f"Field {field.name} is not a date field")
    
    return dual_date_widget(attrs=attrs, organization=organization, default_view=default_view)


def apply_date_widgets_to_form(
    form_class: Type[forms.ModelForm],
    organization: Optional[Any] = None,
    exclude_fields: Optional[Set[str]] = None,
) -> Type[forms.ModelForm]:
    """
    Dynamically apply DualCalendarWidget to all date fields in a form.
    
    This modifies the form's Meta.widgets to use DualCalendarWidget for
    all configured date fields.
    
    Args:
        form_class: ModelForm class to modify
        organization: Organization instance for calendar mode detection
        exclude_fields: Set of field names to exclude from date widget treatment
        
    Returns:
        Modified form class
    """
    exclude_fields = exclude_fields or set()
    
    # Get model from form
    model = getattr(form_class.Meta, "model", None)
    if not model:
        return form_class
    
    # Get date fields for this model
    date_fields = get_date_fields_for_model(model)
    
    # Ensure Meta.widgets exists
    if not hasattr(form_class.Meta, "widgets"):
        form_class.Meta.widgets = {}
    
    # Apply widget to each date field
    for field_name, field in date_fields:
        if field_name in exclude_fields:
            continue
        
        if field_name not in form_class.Meta.widgets:
            form_class.Meta.widgets[field_name] = get_widget_for_field(
                field,
                organization=organization,
            )
    
    return form_class


def configure_form_date_fields(
    form_instance: forms.ModelForm,
    organization: Optional[Any] = None,
) -> None:
    """
    Configure date fields on a form instance (post-instantiation).
    
    Sets default dates and applies field initialization for all date fields.
    
    Args:
        form_instance: ModelForm instance
        organization: Organization instance for calendar mode detection
    """
    model = getattr(form_instance.Meta, 'model', None)
    date_fields = get_date_fields_for_model(model)
    
    # Store organization for widget access
    if organization:
        form_instance.organization = organization
    
    # Set default dates for each field
    for field_name, field in date_fields:
        if hasattr(form_instance, field_name):
            form_field = form_instance.fields.get(field_name)
            if form_field:
                set_default_date_initial(form_instance, field_name, form_field)


def get_all_models_with_date_fields() -> Dict[str, List[str]]:
    """
    Get all models that have date fields configured for dual calendar.
    
    Returns:
        Dict mapping model names to their date field names
    """
    return SCHEMA_DATE_FIELDS.copy()


def register_date_field_schema(model_name: str, field_names: List[str]) -> None:
    """
    Register or update date field schema for a model.
    
    Useful for third-party apps adding date fields to existing models.
    
    Args:
        model_name: Model class name
        field_names: List of date field names to configure
    """
    if model_name not in SCHEMA_DATE_FIELDS:
        SCHEMA_DATE_FIELDS[model_name] = []
    
    # Add new fields, avoid duplicates
    existing = set(SCHEMA_DATE_FIELDS[model_name])
    for field_name in field_names:
        if field_name not in existing:
            SCHEMA_DATE_FIELDS[model_name].append(field_name)


def get_date_field_display_value(
    value: Any,
    calendar_mode: str = CalendarMode.DEFAULT,
    include_both: bool = False,
) -> str:
    """
    Format a date value for display with Nepali support.
    
    Args:
        value: Date/datetime value
        calendar_mode: Calendar mode (AD, BS, DUAL)
        include_both: If True, return both AD and BS representations
        
    Returns:
        Formatted date string
    """
    if not value:
        return ""
    
    # Convert datetime to date if needed
    if isinstance(value, datetime.datetime):
        value = value.date()
    elif isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value).date()
        except (ValueError, TypeError):
            return str(value)
    
    # Format for display
    ad_str = value.isoformat()
    
    if calendar_mode == CalendarMode.BS:
        bs_str = ad_to_bs_string(ad_str)
        return bs_str or ad_str
    elif calendar_mode == CalendarMode.DUAL and include_both:
        bs_str = ad_to_bs_string(ad_str)
        return f"{ad_str} (BS: {bs_str})" if bs_str else ad_str
    else:
        return ad_str


def batch_configure_forms(
    form_classes: List[Type[forms.ModelForm]],
    organization: Optional[Any] = None,
) -> Dict[str, Type[forms.ModelForm]]:
    """
    Configure multiple form classes for date field support.
    
    Args:
        form_classes: List of ModelForm classes
        organization: Organization instance for calendar mode detection
        
    Returns:
        Dict mapping form class names to modified classes
    """
    results = {}
    for form_class in form_classes:
        results[form_class.__name__] = apply_date_widgets_to_form(
            form_class,
            organization=organization,
        )
    return results


# Auto-discovery: Find all ModelForm classes that should be enhanced
def autodiscover_forms() -> Dict[str, Type[forms.ModelForm]]:
    """
    Autodiscover and return all ModelForm classes that use models with date fields.
    
    Returns:
        Dict mapping app_label.FormClassName to form class
    """
    from django.forms import ModelForm
    
    forms_dict = {}
    
    # Get all installed apps
    for app_config in apps.get_app_configs():
        try:
            forms_module = __import__(f"{app_config.name}.forms", fromlist=[""])
        except (ImportError, ModuleNotFoundError):
            continue
        
        # Find all ModelForm subclasses
        for attr_name in dir(forms_module):
            attr = getattr(forms_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ModelForm)
                and attr is not ModelForm
            ):
                model = getattr(attr.Meta, "model", None)
                if model and hasattr(model, "_meta"):
                    date_fields = get_date_fields_for_model(model)
                    if date_fields:
                        forms_dict[f"{app_config.label}.{attr_name}"] = attr
    
    return forms_dict
