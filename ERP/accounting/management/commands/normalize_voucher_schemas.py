from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import json
import os

from accounting.models import VoucherModeConfig, VoucherConfiguration


class Command(BaseCommand):
    help = "Normalize voucher ui_schema: add __order__, display_order and toggle flags (hidden/disabled)"

    def _normalize_section_dict(self, section_dict: dict) -> dict:
        # Preserve existing __order__ if present, otherwise create from keys order
        explicit = section_dict.get('__order__') if isinstance(section_dict, dict) else None
        keys = [k for k in section_dict.keys() if k != '__order__']
        if not isinstance(explicit, list) or not explicit:
            section_dict['__order__'] = keys
        # Ensure each field config is a dict and has toggles + display_order
        for idx, name in enumerate(section_dict['__order__']):
            cfg = section_dict.get(name)
            if cfg is None:
                cfg = {}
            if not isinstance(cfg, dict):
                # migrate simple values into dict
                cfg = {'type': 'char', 'label': str(cfg)}
            cfg.setdefault('hidden', False)
            cfg.setdefault('disabled', False)
            cfg.setdefault('display_order', idx)
            cfg.setdefault('order_no', idx)
            section_dict[name] = cfg
        return section_dict

    def _normalize_section_list(self, section_list: list) -> list:
        for idx, item in enumerate(section_list):
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            item.setdefault('hidden', False)
            item.setdefault('disabled', False)
            item.setdefault('display_order', idx)
            item.setdefault('order_no', idx)
        return section_list

    def _normalize_ui(self, ui: dict) -> dict:
        if not isinstance(ui, dict):
            return ui
        changed = False
        for section_key in ('header', 'lines'):
            section = ui.get(section_key)
            if section is None:
                continue
            if isinstance(section, dict):
                before = dict(section)
                ui[section_key] = self._normalize_section_dict(section)
                if ui[section_key] != before:
                    changed = True
            elif isinstance(section, list):
                before = list(section)
                ui[section_key] = self._normalize_section_list(section)
                if ui[section_key] != before:
                    changed = True
        return ui

    def handle(self, *args, **options):
        total = 0
        updated = 0
        self.stdout.write("Starting normalization of voucher ui_schema entries...")
        # backup current ui_schema values
        backup = {'voucher_mode_configs': {}, 'voucher_configurations': {}}
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        with transaction.atomic():
            # VoucherModeConfig
            for cfg in VoucherModeConfig.objects.select_for_update().all():
                total += 1
                ui = cfg.ui_schema or {}
                backup['voucher_mode_configs'][str(cfg.pk)] = ui
                new_ui = self._normalize_ui(ui)
                if new_ui != ui:
                    cfg.ui_schema = new_ui
                    cfg.save(update_fields=['ui_schema', 'updated_at'])
                    updated += 1
                    self.stdout.write(f"Updated VoucherModeConfig {cfg.pk} ({cfg.code})")

            # VoucherConfiguration
            for cfg in VoucherConfiguration.objects.select_for_update().all():
                total += 1
                ui = cfg.ui_schema or {}
                backup['voucher_configurations'][str(cfg.pk)] = ui
                new_ui = self._normalize_ui(ui)
                if new_ui != ui:
                    cfg.ui_schema = new_ui
                    cfg.save(update_fields=['ui_schema', 'updated_at'])
                    updated += 1
                    self.stdout.write(f"Updated VoucherConfiguration {cfg.pk} ({cfg.code})")

        # write backup file
        backup_dir = os.path.join(os.getcwd(), 'accounting', 'schema_backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f'voucher_ui_schema_backup_{timestamp}.json')
        try:
            with open(backup_path, 'w', encoding='utf-8') as bf:
                json.dump(backup, bf, indent=2, ensure_ascii=False)
            self.stdout.write(f'Backup written to {backup_path}')
        except Exception as e:
            self.stdout.write(f'Failed to write backup: {e}')

        self.stdout.write(f"Completed. Scanned {total} configs, updated {updated}.")