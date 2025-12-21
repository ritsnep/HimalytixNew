from __future__ import annotations

from typing import Any, Dict, List

from django.conf import settings
from django.db import models

from usermanagement.models import Organization


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

    def resolve_ui_schema(self) -> Dict[str, Any]:
        """Return UI schema for voucher entry rendering."""
        from accounting.voucher_schema import definition_to_ui_schema

        definition = self.schema_definition or self._build_definition()
        return definition_to_ui_schema(definition)


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
