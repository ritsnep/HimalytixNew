from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from django.core.management.base import BaseCommand

from accounting.models import VoucherModeConfig
from accounting.schema_validation import validate_ui_schema
from accounting.voucher_schema import definition_to_ui_schema


class Command(BaseCommand):
    help = "Validate voucher UI schemas against JSON Schema with optional strict type checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--code",
            action="append",
            dest="codes",
            help="Validate only these voucher codes (repeatable).",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive voucher configurations.",
        )
        parser.add_argument(
            "--schema-path",
            type=str,
            default=None,
            help="Path to JSON Schema file (defaults to accounting/schemas/voucher_ui_schema.json).",
        )
        parser.add_argument(
            "--no-strict-types",
            action="store_true",
            help="Disable strict type validation (unsupported types are allowed).",
        )

    def handle(self, *args, **options):
        codes = set([c.strip() for c in options.get("codes") or [] if c.strip()])
        include_inactive = options.get("include_inactive", False)
        schema_path = options.get("schema_path")
        strict_types = not options.get("no_strict_types", False)

        schema_file = Path(schema_path) if schema_path else None

        mode_qs = VoucherModeConfig.objects.all()
        if not include_inactive:
            mode_qs = mode_qs.filter(is_active=True)
        if codes:
            mode_qs = mode_qs.filter(code__in=codes)

        total = 0
        total_errors = 0

        def _validate(label: str, ui_schema: dict | None) -> List[str]:
            return validate_ui_schema(ui_schema or {}, schema_path=schema_file, strict_types=strict_types)

        for cfg in mode_qs:
            total += 1
            ui_schema = definition_to_ui_schema(cfg.schema_definition or {})
            errors = _validate(cfg.code, ui_schema)
            if errors:
                total_errors += 1
                self.stdout.write(self.style.ERROR(f"[VoucherModeConfig] {cfg.code}: {len(errors)} issue(s)"))
                for err in errors:
                    self.stdout.write(self.style.ERROR(f"  - {err}"))

        if total == 0:
            self.stdout.write(self.style.WARNING("No voucher configurations found for validation."))
            return

        if total_errors:
            self.stdout.write(self.style.ERROR(f"Validation completed with {total_errors} failing config(s)."))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"Validation completed: {total} config(s) OK."))
