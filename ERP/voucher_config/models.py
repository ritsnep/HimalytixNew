from __future__ import annotations

from typing import Any, Dict, List

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from usermanagement.models import Organization

logger = logging.getLogger(__name__)


NUMBERING_METHOD_CHOICES = [
    ("auto", "Auto"),
    ("manual", "Manual"),
]

CALCULATION_TYPE_CHOICES = [
    ("rate", "Rate"),
    ("amount", "Amount"),
]


def _decimal_step(decimal_places: int) -> str:
    decimal_places = max(int(decimal_places), 0)
    if decimal_places == 0:
        return "1"
    return "0." + ("0" * (decimal_places - 1)) + "1"


class VoucherConfigMaster(models.Model):
    """Master configuration for config-driven voucher entry."""

    config_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="voucher_config_masters",
        db_column="organization_id",
    )
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=200)

    voucher_date_label = models.CharField(max_length=100, default="Date")
    entry_date_label = models.CharField(max_length=100, blank=True)
    ref_no_label = models.CharField(max_length=100, blank=True)
    use_ref_no = models.BooleanField(default=True)
    show_time = models.BooleanField(default=False)
    show_document_details = models.BooleanField(default=False)

    numbering_method = models.CharField(
        max_length=20, choices=NUMBERING_METHOD_CHOICES, default="auto"
    )
    auto_post = models.BooleanField(default=False)
    prevent_duplicate_voucher_no = models.BooleanField(default=True)

    affects_gl = models.BooleanField(default=True)
    affects_inventory = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)

    journal_type = models.ForeignKey(
        "accounting.JournalType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voucher_config_masters",
    )

    schema_definition = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_voucher_config_masters",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_voucher_config_masters",
    )

    class Meta:
        db_table = "voucher_config_master"
        unique_together = ("organization", "code")
        ordering = ("organization_id", "code")
        indexes = [
            models.Index(fields=("organization", "code"), name="vcm_org_code_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.label}"

    @property
    def name(self) -> str:
        return self.label

    def _base_definition(self) -> Dict[str, Any]:
        from accounting.models import default_ui_schema
        from accounting.voucher_schema import ui_schema_to_definition

        return ui_schema_to_definition(default_ui_schema())

    def _apply_header_overrides(self, header_fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def _key(field: Dict[str, Any]) -> str:
            return field.get("key") or field.get("name") or ""

        def _update_label(field: Dict[str, Any], label: str) -> None:
            if label:
                field["label"] = label

        for field in header_fields:
            key = _key(field)
            if key in {"journal_date", "voucher_date"}:
                _update_label(field, self.voucher_date_label)
            if key in {"entry_date", "entry_date_bs"}:
                _update_label(field, self.entry_date_label)
            if key in {"reference_number", "reference"}:
                _update_label(field, self.ref_no_label)

        if not self.use_ref_no:
            header_fields = [
                field
                for field in header_fields
                if _key(field) not in {"reference_number", "reference"}
            ]
        return header_fields

    def _build_definition(self) -> Dict[str, Any]:
        definition = self._base_definition()
        header_fields = definition.get("header_fields", [])
        line_fields = definition.get("line_fields", [])

        header_fields = self._apply_header_overrides(header_fields)

        if self.affects_inventory and hasattr(self, "inventory_line_config"):
            line_fields = self.inventory_line_config.to_definition_fields()

        definition["header_fields"] = header_fields
        definition["line_fields"] = line_fields

        footer_charges = [
            charge.to_schema_entry()
            for charge in self.footer_charges.filter(is_active=True).order_by("display_order", "footer_charge_id")
        ]
        if footer_charges:
            definition.setdefault("settings", {})["footer_charges"] = footer_charges

        definition.setdefault("settings", {}).update(
            {
                "show_time": self.show_time,
                "show_document_details": self.show_document_details,
                "use_ref_no": self.use_ref_no,
            }
        )

        return definition

    ALLOWED_FIELD_TYPES = {
        "text",
        "number",
        "decimal",
        "date",
        "datetime",
        "select",
        "multiselect",
        "checkbox",
        "textarea",
        "email",
        "phone",
        "url",
        "char",
        "typeahead",
        "bsdate",
        "boolean",
    } 

    FIELD_TYPE_ALIASES = {
        "string": "char",
        "str": "char",
        "bool": "boolean",
    }

    def _normalize_field_type(self, field: Dict[str, Any]) -> str:
        field_type = field.get("field_type") or field.get("type")
        if not field_type:
            field_type = "char"
        if isinstance(field_type, str):
            field_type = field_type.strip().lower()
        else:
            field_type = "char"
        field_type = self.FIELD_TYPE_ALIASES.get(field_type, field_type)
        field["field_type"] = field_type
        return field_type

    def _inject_udfs(self, definition: Dict[str, Any]) -> None:
        """Inject UDF fields into header_fields or line_fields."""
        udfs = self.udf_configs.filter(is_active=True).order_by('display_order')
        for udf in udfs:
            field_def = {
                "name": udf.field_name,
                "label": udf.display_name,
                "field_type": udf.field_type or "text",
                "required": udf.is_required,
                "default": udf.default_value,
                "help_text": udf.help_text,
                "display_order": udf.display_order,
            }
            if udf.choices:
                field_def["choices"] = udf.choices
            if udf.min_value is not None:
                field_def["min_value"] = float(udf.min_value)
            if udf.max_value is not None:
                field_def["max_value"] = float(udf.max_value)
            if udf.min_length is not None:
                field_def["min_length"] = udf.min_length
            if udf.max_length is not None:
                field_def["max_length"] = udf.max_length
            if udf.validation_regex:
                field_def["regex"] = udf.validation_regex

            if udf.scope == "header":
                definition.setdefault("header_fields", []).append(field_def)
            elif udf.scope == "line":
                definition.setdefault("line_fields", []).append(field_def)

    def _validate_schema(self, definition: Dict[str, Any]) -> None:
        """Validate schema for controlled vocabulary and config."""
        errors = []
        for section in ["header_fields", "line_fields"]:
            for field in definition.get(section, []):
                field_type = self._normalize_field_type(field)
                if field_type not in self.ALLOWED_FIELD_TYPES:
                    msg = (
                        "CFG-001: Unknown field_type '%s' in %s; defaulting to 'char'." % (field_type, section)
                    )
                    logger.warning(msg)
                    errors.append(msg)
                    field["field_type"] = "char"

        return errors

    def resolve_ui_schema(self) -> Dict[str, Any]:
        """Return UI schema for voucher entry rendering."""
        from accounting.voucher_schema import definition_to_ui_schema
        from django.core.exceptions import ValidationError

        definition = self.schema_definition or self._build_definition()
        
        # Inject UDFs
        self._inject_udfs(definition)

        # Validate schema (collect errors)
        validation_errors = self._validate_schema(definition)
        if validation_errors:
            return {"error": "; ".join(validation_errors)}

        ui = definition_to_ui_schema(definition)

        # Backwards compatibility: some callers/tests expect `header_fields` and
        # `line_fields` keys (legacy naming). Mirror `header`/`lines` into
        # these aliases so both shapes are supported.
        if isinstance(ui, dict):
            if "header" in ui and "header_fields" not in ui:
                ui["header_fields"] = ui["header"]
            if "lines" in ui and "line_fields" not in ui:
                ui["line_fields"] = ui["lines"]

        return ui


class InventoryLineConfig(models.Model):
    """Configures the inventory line grid for a voucher type."""

    config_id = models.BigAutoField(primary_key=True)
    voucher_config = models.OneToOneField(
        VoucherConfigMaster,
        on_delete=models.CASCADE,
        related_name="inventory_line_config",
    )

    show_rate = models.BooleanField(default=True)
    show_amount = models.BooleanField(default=True)
    allow_free_qty = models.BooleanField(default=False)
    show_alternate_unit = models.BooleanField(default=False)
    show_discount = models.BooleanField(default=False)

    show_batch_no = models.BooleanField(default=False)
    show_mfg_date = models.BooleanField(default=False)
    show_exp_date = models.BooleanField(default=False)
    show_serial_no = models.BooleanField(default=False)

    qty_decimal_places = models.PositiveSmallIntegerField(default=2)
    rate_decimal_places = models.PositiveSmallIntegerField(default=2)

    is_fixed_product = models.BooleanField(default=False)
    allow_batch_in_stock_journal = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voucher_inventory_line_config"

    def __str__(self) -> str:
        return f"{self.voucher_config.code} inventory config"

    def _decimal_field(self, key: str, label: str, *, step: str, required: bool) -> Dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "field_type": "decimal",
            "required": required,
            "validators": {"min": 0, "step": step},
        }

    def _lookup_field(self, key: str, label: str, model_name: str, kind: str, *, required: bool) -> Dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "field_type": "typeahead",
            "required": required,
            "lookup": {"model": model_name, "kind": kind},
        }

    def to_definition_fields(self) -> List[Dict[str, Any]]:
        qty_step = _decimal_step(self.qty_decimal_places)
        rate_step = _decimal_step(self.rate_decimal_places)

        fields: List[Dict[str, Any]] = [
            self._lookup_field("product", "Product", "Product", "product", required=True),
            self._lookup_field("warehouse", "Warehouse", "Warehouse", "warehouse", required=True),
            self._decimal_field("quantity", "Quantity", step=qty_step, required=True),
        ]

        if self.allow_free_qty:
            fields.append(self._decimal_field("free_qty", "Free Qty", step=qty_step, required=False))
        if self.show_alternate_unit:
            fields.append(
                {
                    "key": "alternate_unit",
                    "label": "Alt Unit",
                    "field_type": "char",
                    "required": False,
                }
            )

        if self.show_rate:
            fields.append(self._decimal_field("rate", "Rate", step=rate_step, required=False))
        if self.show_amount:
            fields.append(self._decimal_field("amount", "Amount", step=rate_step, required=False))
        if self.show_discount:
            fields.append(self._decimal_field("discount_amount", "Discount", step=rate_step, required=False))

        if self.show_batch_no:
            fields.append({"key": "batch_no", "label": "Batch No", "field_type": "char", "required": False})
        if self.show_mfg_date:
            fields.append({"key": "mfg_date", "label": "MFG Date", "field_type": "date", "required": False})
        if self.show_exp_date:
            fields.append({"key": "exp_date", "label": "EXP Date", "field_type": "date", "required": False})
        if self.show_serial_no:
            fields.append({"key": "serial_no", "label": "Serial No", "field_type": "char", "required": False})

        if self.is_fixed_product:
            fields.extend(
                [
                    {"key": "engine_no", "label": "Engine No", "field_type": "char", "required": False},
                    {"key": "chassis_no", "label": "Chassis No", "field_type": "char", "required": False},
                ]
            )

        return fields


class FooterChargeSetup(models.Model):
    """Defines footer charges such as taxes or discounts."""

    footer_charge_id = models.BigAutoField(primary_key=True)
    voucher_config = models.ForeignKey(
        VoucherConfigMaster,
        on_delete=models.CASCADE,
        related_name="footer_charges",
    )
    ledger = models.ForeignKey(
        "accounting.ChartOfAccount",
        on_delete=models.PROTECT,
        related_name="voucher_footer_charges",
    )
    calculation_type = models.CharField(
        max_length=20, choices=CALCULATION_TYPE_CHOICES, default="rate"
    )
    rate = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    can_edit = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voucher_footer_charge_setup"
        ordering = ("display_order", "footer_charge_id")

    def __str__(self) -> str:
        return f"{self.voucher_config.code} - {self.ledger.account_name}"

    def to_schema_entry(self) -> Dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "ledger_code": getattr(self.ledger, "account_code", None),
            "ledger_name": getattr(self.ledger, "account_name", None),
            "calculation_type": self.calculation_type,
            "rate": self.rate if self.rate is not None else None,
            "amount": self.amount if self.amount is not None else None,
            "can_edit": self.can_edit,
        }


class VoucherUDFConfig(models.Model):
    """User-Defined Fields configuration for voucher entry forms in voucher_config"""
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'Date & Time'),
        ('select', 'Dropdown'),
        ('multiselect', 'Multi-Select'),
        ('checkbox', 'Checkbox'),
        ('textarea', 'Text Area'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('url', 'URL'),
    ]
    
    SCOPE_CHOICES = [
        ('header', 'Voucher Header'),
        ('line', 'Journal Line'),
    ]
    
    udf_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='voucher_config_udf_configs', db_column='organization_id')
    voucher_config = models.ForeignKey(VoucherConfigMaster, on_delete=models.CASCADE, related_name='udf_configs', db_column='voucher_config_id')
    field_name = models.CharField(max_length=50, help_text="Internal field name (no spaces, lowercase)")
    display_name = models.CharField(max_length=100, help_text="User-friendly display name")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='header')
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    default_value = models.CharField(max_length=255, blank=True, null=True)
    choices = models.JSONField(null=True, blank=True, help_text="For select/multiselect fields")
    min_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    validation_regex = models.CharField(max_length=255, null=True, blank=True)
    help_text = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voucher_config_udf_config'
        unique_together = ('voucher_config', 'field_name')
        ordering = ['scope', 'display_order', 'field_name']
        verbose_name = "Voucher Config UDF Configuration"
        verbose_name_plural = "Voucher Config UDF Configurations"

    def __str__(self):
        return f"{self.voucher_config.code} - {self.display_name}"
