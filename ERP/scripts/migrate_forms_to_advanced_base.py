#!/usr/bin/env python
"""
Advanced Form Base Migration Script
Automatically updates form views and generates migration checklist.

Usage:
    python scripts/migrate_forms_to_advanced_base.py [--app accounting] [--dry-run]
"""

import os
import re
import sys
from pathlib import Path

# Add ERP to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
import django
django.setup()

from django.apps import apps
from django.urls import reverse


class FormMigrator:
    """Migrates forms to use Advanced Form Base"""
    
    FORM_CONFIGS = {
        # Accounting forms configuration
        'accounting': {
            'currency': {
                'priority': 'high',
                'enable_tabs': False,
                'enable_bulk_import': False,
                'enable_templates': False,
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'tax_type': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'tax_code': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'fiscal_year': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'cost_center': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'department': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'journal_type': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'project': {
                'priority': 'high',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'tax_authority': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'currency_exchange_rate': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'accounting_period': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'voucher_mode_config': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'voucher_mode_default': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'voucher_udf_config': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
            'general_ledger': {
                'priority': 'medium',
                'enable_shortcuts': True,
                'enable_save_and_new': True,
            },
        },
    }
    
    def __init__(self, app_name='accounting', dry_run=False):
        self.app_name = app_name
        self.dry_run = dry_run
        self.base_dir = BASE_DIR
        
    def generate_settings_config(self):
        """Generate ADVANCED_FORM_FEATURES configuration"""
        print("\n" + "="*80)
        print("SETTINGS CONFIGURATION TO ADD")
        print("="*80)
        print("\nAdd this to dashboard/settings.py → ADVANCED_FORM_FEATURES:\n")
        
        for app, models in self.FORM_CONFIGS.items():
            if app != self.app_name:
                continue
                
            print(f"    '{app}': {{")
            for model, config in sorted(models.items()):
                priority = config.pop('priority', 'medium')
                print(f"        # Priority: {priority}")
                print(f"        '{model}': {{")
                for key, value in config.items():
                    print(f"            '{key}': {value},")
                print(f"        }},")
            print(f"    }},\n")
    
    def generate_view_updates(self):
        """Generate view update instructions"""
        print("\n" + "="*80)
        print("VIEW UPDATES NEEDED")
        print("="*80)
        
        views_create_path = self.base_dir / self.app_name / 'views' / 'views_create.py'
        views_update_path = self.base_dir / self.app_name / 'views' / 'views_update.py'
        
        print(f"\n1. Update imports in {views_create_path}")
        print("   Add: from accounting.mixins import AdvancedFormMixin\n")
        
        print("2. Update CreateView classes:\n")
        
        for model_name in self.FORM_CONFIGS.get(self.app_name, {}).keys():
            class_name = self._to_class_name(model_name)
            print(f"   class {class_name}CreateView(AdvancedFormMixin, ...existing mixins...):")
            print(f"       app_name = '{self.app_name}'")
            print(f"       model_name = '{model_name}'")
            print(f"       # Add to get_context_data:")
            print(f"       context['page_title'] = '{class_name}'")
            print(f"       context['list_url'] = reverse('{self.app_name}:{model_name}_list')")
            print()
        
        print(f"\n3. Update {views_update_path} (same pattern as CreateView)\n")
    
    def generate_template_checklist(self):
        """Generate template migration checklist"""
        print("\n" + "="*80)
        print("TEMPLATE MIGRATION CHECKLIST")
        print("="*80)
        
        for model_name, config in self.FORM_CONFIGS.get(self.app_name, {}).items():
            template_path = self.base_dir / self.app_name / 'templates' / self.app_name / f'{model_name}_form.html'
            
            print(f"\n{'─'*80}")
            print(f"📄 {model_name}_form.html")
            print(f"{'─'*80}")
            
            if template_path.exists():
                print("✅ Template exists")
                print(f"📍 Location: {template_path}")
            else:
                print("❌ Template not found (may use different naming)")
            
            priority = config.get('priority', 'medium')
            print(f"🎯 Priority: {priority.upper()}")
            
            print("\n✓ Tasks:")
            print("  [ ] Change extends to 'accounting/_coa_form_base.html'")
            print("  [ ] Wrap form in <div class='tab-content'> and <div class='tab-pane fade show active' id='single-entry'>")
            print("  [ ] Update form ID to follow pattern: '{}-form'".format(model_name.replace('_', '-')))
            print("  [ ] Add 'novalidate' attribute to form")
            print("  [ ] Convert fields to enhanced pattern (see MIGRATION_GUIDE.md)")
            print("  [ ] Add required field indicators (data-pristine-required-message)")
            print("  [ ] Update form actions to include Save & New button")
            print("  [ ] Add keyboard shortcut hint")
            print("  [ ] Add extra_form_js block for custom JS")
            print("  [ ] Test all functionality")
            
    def generate_migration_order(self):
        """Generate recommended migration order"""
        print("\n" + "="*80)
        print("RECOMMENDED MIGRATION ORDER")
        print("="*80)
        
        high_priority = []
        medium_priority = []
        low_priority = []
        
        for model, config in self.FORM_CONFIGS.get(self.app_name, {}).items():
            priority = config.get('priority', 'medium')
            if priority == 'high':
                high_priority.append(model)
            elif priority == 'medium':
                medium_priority.append(model)
            else:
                low_priority.append(model)
        
        print("\n🔴 HIGH PRIORITY (Do these first):")
        for i, model in enumerate(high_priority, 1):
            status = "✅" if model in ['chart_of_accounts', 'account_type'] else "⏳"
            print(f"  {i}. {status} {model}")
        
        print("\n🟡 MEDIUM PRIORITY:")
        for i, model in enumerate(medium_priority, 1):
            print(f"  {i}. ⏳ {model}")
        
        if low_priority:
            print("\n🟢 LOW PRIORITY:")
            for i, model in enumerate(low_priority, 1):
                print(f"  {i}. ⏳ {model}")
    
    def _to_class_name(self, model_name):
        """Convert model_name to ClassName"""
        return ''.join(word.capitalize() for word in model_name.split('_'))
    
    def run(self):
        """Run the migration analysis"""
        print("\n")
        print("╔" + "="*78 + "╗")
        print("║" + " "*20 + "ADVANCED FORM BASE MIGRATION" + " "*30 + "║")
        print("╚" + "="*78 + "╝")
        
        if self.dry_run:
            print("\n🔍 DRY RUN MODE - No files will be modified\n")
        
        self.generate_migration_order()
        self.generate_settings_config()
        self.generate_view_updates()
        self.generate_template_checklist()
        
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("""
1. Review the migration guide: docs/ADVANCED_FORM_MIGRATION_GUIDE.md
2. Add settings configuration to dashboard/settings.py
3. Start with HIGH PRIORITY forms
4. Update views (CreateView and UpdateView)
5. Update templates one by one
6. Test each form thoroughly before moving to next

For detailed examples, see:
- accounting/templates/accounting/account_type_form.html
- accounting/views/views_create.py (AccountTypeCreateView)
        """)
        print("="*80 + "\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate forms to Advanced Form Base')
    parser.add_argument('--app', default='accounting', help='App name (default: accounting)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    migrator = FormMigrator(app_name=args.app, dry_run=args.dry_run)
    migrator.run()
