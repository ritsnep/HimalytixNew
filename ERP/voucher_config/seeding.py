from __future__ import annotations

from typing import Dict

import json

from django.db import transaction

from accounting.services.voucher_seeding import seed_journal_types
from accounting.voucher_definitions import VOUCHER_DEFINITIONS
from voucher_config.models import InventoryLineConfig, VoucherConfigMaster


_INVENTORY_QTY_ONLY = {"STOCK-TRANSFER", "STOCK-JOURNAL"}
_DISCOUNT_DEFAULT = {"SALES-INVOICE", "SALES-RETURN", "PURCHASE-INVOICE", "PURCHASE-RETURN"}
_BATCH_TRACKING = {"PURCHASE-INVOICE", "PURCHASE-RETURN", "GOODS-RECEIPT", "SALES-RETURN"}


def _inventory_defaults_for(definition: Dict[str, object]) -> Dict[str, object]:
    code = str(definition.get("code", ""))
    schema = definition.get("schema") or {}
    settings = schema.get("settings") if isinstance(schema, dict) else {}
    inventory_settings = settings.get("inventory") if isinstance(settings, dict) else {}
    txn_type = inventory_settings.get("txn_type")

    qty_only = code in _INVENTORY_QTY_ONLY or txn_type == "issue" and not definition.get("affects_gl")
    show_discount = code in _DISCOUNT_DEFAULT
    show_rate = not qty_only
    show_amount = not qty_only

    return {
        "show_rate": show_rate,
        "show_amount": show_amount,
        "show_discount": show_discount,
        "show_batch_no": code in _BATCH_TRACKING,
        "show_mfg_date": code in _BATCH_TRACKING,
        "show_exp_date": code in _BATCH_TRACKING,
        "allow_batch_in_stock_journal": code == "STOCK-JOURNAL",
    }


def _schema_signature(schema: object) -> str:
    try:
        return json.dumps(schema, sort_keys=True, default=str)
    except Exception:
        return str(schema)


@transaction.atomic
def seed_voucher_config_master(organization, *, reset: bool = False, repair: bool = True) -> Dict[str, int]:
    if reset:
        InventoryLineConfig.objects.filter(voucher_config__organization=organization).delete()
        VoucherConfigMaster.objects.filter(organization=organization).delete()

    journal_types = seed_journal_types(organization)
    stats = {"created": 0, "repaired": 0}

    for definition in VOUCHER_DEFINITIONS:
        code = definition["code"]
        journal_type = journal_types.get(definition.get("journal_type_code"))

        defaults = {
            "label": definition.get("name", code),
            "affects_gl": bool(definition.get("affects_gl", True)),
            "affects_inventory": bool(definition.get("affects_inventory", False)),
            "requires_approval": bool(definition.get("requires_approval", False)),
            "journal_type": journal_type,
            "use_ref_no": True,
            "voucher_date_label": "Date",
            "ref_no_label": "Reference Number",
            "numbering_method": "auto",
            "auto_post": False,
            "prevent_duplicate_voucher_no": True,
            "schema_definition": definition.get("schema", {}),
            "is_active": True,
        }

        config, created = VoucherConfigMaster.objects.get_or_create(
            organization=organization,
            code=code,
            defaults=defaults,
        )
        if created:
            stats["created"] += 1
        elif repair:
            changed = False
            for key, value in defaults.items():
                if getattr(config, key, None) in (None, "") and value not in (None, ""):
                    setattr(config, key, value)
                    changed = True
            incoming_schema = defaults.get("schema_definition")
            if incoming_schema is not None:
                if _schema_signature(config.schema_definition) != _schema_signature(incoming_schema):
                    config.schema_definition = incoming_schema
                    changed = True
            if config.is_active is False:
                config.is_active = True
                changed = True
            if changed:
                config.save()
                stats["repaired"] += 1

        if config.affects_inventory:
            inv_defaults = _inventory_defaults_for(definition)
            InventoryLineConfig.objects.get_or_create(
                voucher_config=config,
                defaults=inv_defaults,
            )

    return stats
