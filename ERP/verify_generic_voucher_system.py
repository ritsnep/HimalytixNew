#!/usr/bin/env python
"""
Comprehensive Generic Voucher Entry System Verification
Tests all 17 standardized vouchers for proper configuration and accessibility
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from accounting.models import VoucherModeConfig  # Using existing table
from accounting.forms_factory import VoucherFormFactory
from django.urls import reverse
from django.test import RequestFactory
from accounting.views.generic_voucher_views import VoucherTypeSelectionView, GenericVoucherCreateView
from usermanagement.models import Organization
import json


# List of 17 standardized voucher codes
STANDARDIZED_VOUCHERS = [
    'sales-invoice-vm-si',
    'VM08',
    'journal-entry-vm-je',
    'VM-SI',
    'VM-PI',
    'VM-SO',
    'VM-PO',
    'VM-GR',
    'VM-SCN',
    'VM-SDN',
    'VM-SR',
    'VM-SQ',
    'VM-SD',
    'VM-PCN',
    'VM-PDN',
    'VM-PR',
    'VM-LC'
]


def test_database_configs():
    """Test 1: Verify all voucher configurations exist in database"""
    print("\n" + "="*80)
    print("TEST 1: DATABASE CONFIGURATION CHECK")
    print("="*80)
    
    results = []
    for code in STANDARDIZED_VOUCHERS:
        try:
            # Don't filter by organization since we want to find any matching code
            config = VoucherModeConfig.objects.filter(code=code).first()
            if not config:
                raise VoucherModeConfig.DoesNotExist
            results.append({
                'code': code,
                'name': config.name,
                'exists': True,
                'is_active': config.is_active,
                'has_ui_schema': bool(config.schema_definition),
                'module': 'accounting'  # VoucherModeConfig is accounting-only
            })
        except VoucherModeConfig.DoesNotExist:
            results.append({
                'code': code,
                'exists': False,
                'error': 'Configuration not found'
            })
    
    # Print results
    passed = sum(1 for r in results if r.get('exists') and r.get('is_active'))
    print(f"\nOK Found: {passed}/{len(STANDARDIZED_VOUCHERS)} active configurations")
    
    for result in results:
        if result.get('exists'):
            status = "OK" if result['is_active'] else "FAIL (INACTIVE)"
            print(f"  {status} {result['code']:25} | {result.get('name', 'N/A'):30} | {result.get('module', 'N/A')}")
        else:
            print(f"  FAIL {result['code']:25} | ERROR: {result.get('error', 'Unknown')}")
    
    return results


def test_ui_schema_compliance():
    """Test 2: Verify UI schema has proper ordering, autofocus, and status fields"""
    print("\n" + "="*80)
    print("TEST 2: UI SCHEMA COMPLIANCE CHECK")
    print("="*80)
    
    results = []
    for code in STANDARDIZED_VOUCHERS:
        try:
            config = VoucherModeConfig.objects.filter(code=code).first()
            if not config:
                raise VoucherModeConfig.DoesNotExist
            ui_schema = config.resolve_ui_schema() or {}
            
            # Check for __order__ or order_no in header fields
            has_ordering = False
            has_autofocus = False
            has_status = False
            
            header_section = ui_schema.get('sections', {}).get('header', {})
            header_fields = header_section.get('fields', {})
            
            # Check __order__ at section level
            if '__order__' in header_section:
                has_ordering = True
            
            # Check order_no in individual fields
            for field_name, field_config in header_fields.items():
                if isinstance(field_config, dict):
                    if 'order_no' in field_config:
                        has_ordering = True
                    if field_config.get('autofocus'):
                        has_autofocus = True
                    if field_name == 'status':
                        has_status = True
            
            results.append({
                'code': code,
                'name': config.name,
                'has_ordering': has_ordering,
                'has_autofocus': has_autofocus,
                'has_status': has_status,
                'compliant': has_ordering and has_autofocus and has_status,
                'field_count': len(header_fields)
            })
            
        except VoucherModeConfig.DoesNotExist:
            results.append({
                'code': code,
                'error': 'Configuration not found'
            })
    
    # Print results
    compliant = sum(1 for r in results if r.get('compliant'))
    print(f"\nOK Compliant: {compliant}/{len(STANDARDIZED_VOUCHERS)} vouchers")
    print("\nCompliance Breakdown:")
    print(f"  {'Voucher Code':<25} | {'Order':<6} | {'Focus':<6} | {'Status':<7} | {'Fields':<7} | {'Result'}")
    print(f"  {'-'*25}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*7}-+-{'-'*10}")
    
    for result in results:
        if 'error' not in result:
            order_mark = "OK" if result['has_ordering'] else "NO"
            focus_mark = "OK" if result['has_autofocus'] else "NO"
            status_mark = "OK" if result['has_status'] else "NO"
            result_mark = "OK PASS" if result['compliant'] else "FAIL"
            
            print(f"  {result['code']:<25} | {order_mark:<6} | {focus_mark:<6} | {status_mark:<7} | {result['field_count']:<7} | {result_mark}")
    
    return results


def test_form_generation():
    """Test 3: Verify forms can be generated from all configurations"""
    print("\n" + "="*80)
    print("TEST 3: FORM GENERATION CHECK")
    print("="*80)
    
    # Get organization
    org = Organization.objects.first()
    if not org:
        print("ERROR: No organization found")
        return []
    
    results = []
    for code in STANDARDIZED_VOUCHERS:
        try:
            config = VoucherModeConfig.objects.filter(code=code).first()
            if not config:
                raise VoucherModeConfig.DoesNotExist
            
            # Try to generate form (returns class, need to instantiate)
            form_class = VoucherFormFactory.get_generic_voucher_form(config, org)
            form = form_class()  # Instantiate to access fields
            
            # Check form properties
            has_fields = len(form.fields) > 0
            has_autofocus = any(field.widget.attrs.get('autofocus') for field in form.fields.values())
            
            results.append({
                'code': code,
                'name': config.name,
                'form_generated': True,
                'field_count': len(form.fields),
                'has_autofocus': has_autofocus,
                'success': True
            })
            
        except VoucherModeConfig.DoesNotExist:
            results.append({
                'code': code,
                'error': 'Configuration not found'
            })
        except Exception as e:
            results.append({
                'code': code,
                'error': f'Form generation failed: {str(e)}'
            })
    
    # Print results
    successful = sum(1 for r in results if r.get('success'))
    print(f"\nOK Generated: {successful}/{len(STANDARDIZED_VOUCHERS)} forms")
    
    for result in results:
        if result.get('success'):
            focus_mark = "OK" if result['has_autofocus'] else "NO"
            print(f"  OK {result['code']:25} | Fields: {result['field_count']:3} | Autofocus: {focus_mark}")
        else:
            print(f"  FAIL {result['code']:25} | ERROR: {result.get('error', 'Unknown')}")
    
    return results


def test_url_routing():
    """Test 4: Verify URL routing for all vouchers"""
    print("\n" + "="*80)
    print("TEST 4: URL ROUTING CHECK")
    print("="*80)
    
    results = []
    for code in STANDARDIZED_VOUCHERS:
        try:
            # Test selection view URL
            select_url = reverse('accounting:generic_voucher_select')
            
            # Test create view URL
            create_url = reverse('accounting:generic_voucher_create', kwargs={'voucher_code': code})
            
            # Test line view URL
            line_url = reverse('accounting:generic_voucher_line')
            
            # Test lookup URLs
            vendor_lookup_url = reverse('accounting:generic_voucher_vendor_lookup_hx')
            customer_lookup_url = reverse('accounting:generic_voucher_customer_lookup_hx')
            product_lookup_url = reverse('accounting:generic_voucher_product_lookup_hx')
            
            results.append({
                'code': code,
                'select_url': select_url,
                'create_url': create_url,
                'routing_ok': True
            })
            
        except Exception as e:
            results.append({
                'code': code,
                'error': f'URL routing failed: {str(e)}'
            })
    
    # Print results
    successful = sum(1 for r in results if r.get('routing_ok'))
    print(f"\nOK Routable: {successful}/{len(STANDARDIZED_VOUCHERS)} vouchers")
    
    for result in results:
        if result.get('routing_ok'):
            print(f"  OK {result['code']:25} | URL: {result['create_url']}")
        else:
            print(f"  FAIL {result['code']:25} | ERROR: {result.get('error', 'Unknown')}")
    
    # Print common URLs
    print("\n  Common URLs:")
    print(f"    Selection: {reverse('accounting:generic_voucher_select')}")
    print(f"    Line View: {reverse('accounting:generic_voucher_line')}")
    print(f"    Vendor Lookup: {reverse('accounting:generic_voucher_vendor_lookup_hx')}")
    print(f"    Customer Lookup: {reverse('accounting:generic_voucher_customer_lookup_hx')}")
    print(f"    Product Lookup: {reverse('accounting:generic_voucher_product_lookup_hx')}")
    
    return results


def test_menu_integration():
    """Test 5: Verify menu integration"""
    print("\n" + "="*80)
    print("TEST 5: MENU INTEGRATION CHECK")
    print("="*80)
    
    try:
        # Check if left-sidebar.html contains generic voucher link
        sidebar_path = Path(__file__).parent / 'templates' / 'partials' / 'left-sidebar.html'
        
        if sidebar_path.exists():
            content = sidebar_path.read_text(encoding='utf-8')
            has_link = 'generic_voucher_select' in content
            has_text = 'Generic Voucher Entry' in content
            
            if has_link and has_text:
                print("  OK Menu link found in left-sidebar.html")
                print("  OK Menu displays 'Generic Voucher Entry'")
                print("  OK Link points to 'accounting:generic_voucher_select'")
                return True
            else:
                print("  FAIL Menu link not properly configured")
                return False
        else:
            print("  FAIL left-sidebar.html not found")
            return False
            
    except Exception as e:
        print(f"  FAIL Menu check failed: {str(e)}")
        return False


def print_summary(test_results):
    """Print final summary"""
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    all_tests = [
        ("Database Configurations", test_results['db']),
        ("UI Schema Compliance", test_results['schema']),
        ("Form Generation", test_results['forms']),
        ("URL Routing", test_results['urls']),
        ("Menu Integration", test_results['menu'])
    ]
    
    print("\nTest Results:")
    for test_name, result in all_tests:
        if isinstance(result, list):
            passed = sum(1 for r in result if r.get('success') or r.get('compliant') or r.get('routing_ok') or (r.get('exists') and r.get('is_active')))
            status = "OK PASS" if passed == len(STANDARDIZED_VOUCHERS) else f"PARTIAL ({passed}/{len(STANDARDIZED_VOUCHERS)})"
        else:
            status = "OK PASS" if result else "FAIL"
        
        print(f"  {test_name:<30} | {status}")
    
    print("\n" + "="*80)
    print("GENERIC VOUCHER ENTRY SYSTEM STATUS")
    print("="*80)
    
    # Calculate overall compliance
    db_ok = all(r.get('exists') and r.get('is_active') for r in test_results['db'])
    schema_ok = all(r.get('compliant') for r in test_results['schema'])
    forms_ok = all(r.get('success') for r in test_results['forms'])
    urls_ok = all(r.get('routing_ok') for r in test_results['urls'])
    menu_ok = test_results['menu']
    
    if db_ok and schema_ok and forms_ok and urls_ok and menu_ok:
        print("\n  OK SYSTEM FULLY OPERATIONAL")
        print("     All 17 standardized vouchers are properly configured")
        print("     and accessible through the generic voucher entry system.")
    else:
        print("\n  WARN SYSTEM PARTIALLY OPERATIONAL")
        print("     Some vouchers may have configuration issues.")
        if not db_ok:
            print("     - Database configuration needs attention")
        if not schema_ok:
            print("     - UI schema compliance needs improvement")
        if not forms_ok:
            print("     - Form generation has errors")
        if not urls_ok:
            print("     - URL routing needs fixing")
        if not menu_ok:
            print("     - Menu integration incomplete")
    
    print("\n  Access Points:")
    print(f"    • Menu: 'Generic Voucher Entry' in left sidebar")
    print(f"    • URL: /accounting/generic-voucher/select/")
    print(f"    • Permission: 'accounting_journal_add'")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("GENERIC VOUCHER ENTRY SYSTEM - COMPREHENSIVE VERIFICATION")
    print("="*80)
    print(f"Testing {len(STANDARDIZED_VOUCHERS)} standardized voucher configurations")
    print("="*80)
    
    # Run all tests
    test_results = {
        'db': test_database_configs(),
        'schema': test_ui_schema_compliance(),
        'forms': test_form_generation(),
        'urls': test_url_routing(),
        'menu': test_menu_integration()
    }
    
    # Print summary
    print_summary(test_results)
    
    print("\n" + "="*80)
    print("Verification complete!")
    print("="*80 + "\n")
