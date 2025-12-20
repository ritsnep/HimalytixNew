from __future__ import annotations

from typing import Iterable, Optional

from django.db import transaction

from accounting.models import JournalType, VoucherModeConfig, VoucherModeDefault
from accounting.voucher_definitions import VOUCHER_DEFINITIONS, journal_type_seed


def seed_journal_types(organization) -> dict:
    created = {}
    for code, name in journal_type_seed().items():
        jt, _ = JournalType.objects.get_or_create(
            organization=organization,
            code=code,
            defaults={
                "name": name,
                "is_system_type": True,
                "requires_approval": False,
                "is_active": True,
            },
        )
        created[code] = jt
    return created


@transaction.atomic
def seed_voucher_configs(organization, *, reset: bool = False, repair: bool = True) -> dict:
    if reset:
        VoucherModeDefault.objects.filter(config__organization=organization).delete()
        VoucherModeConfig.objects.filter(organization=organization).delete()

    journal_types = seed_journal_types(organization)
    stats = {"created": 0, "repaired": 0, "updated": 0}

    for definition in VOUCHER_DEFINITIONS:
        code = definition["code"]
        journal_code = definition.get("journal_type_code")
        journal_type = journal_types.get(journal_code)
        defaults = {
            "name": definition.get("name", code),
            "description": definition.get("description"),
            "module": definition.get("module", "accounting"),
            "journal_type": journal_type,
            "affects_gl": bool(definition.get("affects_gl", True)),
            "affects_inventory": bool(definition.get("affects_inventory", False)),
            "requires_approval": bool(definition.get("requires_approval", False)),
            "schema_definition": definition.get("schema", {}),
            "workflow_definition": definition.get("workflow", {}),
            "is_active": True,
        }
        config, created = VoucherModeConfig.objects.get_or_create(
            organization=organization,
            code=code,
            defaults=defaults,
        )
        if created:
            stats["created"] += 1
            continue

        if repair:
            changed = False
            if not config.name:
                config.name = defaults["name"]
                changed = True
            if not config.description and defaults.get("description"):
                config.description = defaults.get("description")
                changed = True
            if not config.module:
                config.module = defaults["module"]
                changed = True
            if config.journal_type_id is None and journal_type is not None:
                config.journal_type = journal_type
                changed = True
            if not config.schema_definition and defaults.get("schema_definition"):
                config.schema_definition = defaults["schema_definition"]
                changed = True
            if not config.workflow_definition and defaults.get("workflow_definition"):
                config.workflow_definition = defaults["workflow_definition"]
                changed = True
            if config.is_active is False:
                config.is_active = True
                changed = True
            if changed:
                config.save(update_fields=[
                    "name",
                    "description",
                    "module",
                    "journal_type",
                    "schema_definition",
                    "workflow_definition",
                    "is_active",
                ])
                stats["repaired"] += 1
        else:
            stats["updated"] += 1

    return stats
