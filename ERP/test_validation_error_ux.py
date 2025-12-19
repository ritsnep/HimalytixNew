"""
Test script to verify validation error UX improvements for inventory vouchers.

This script will:
1. Navigate to an inventory voucher entry page
2. Create a voucher with a line that has validation errors
3. Verify that the error display is prominent and user-friendly
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from accounting.models import VoucherModeConfig, Organization, JournalType

User = get_user_model()

def test_validation_error_display():
    """Test that validation errors are displayed prominently."""
    
    # Create test client
    client = Client()
    
    # Create or get test user
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'is_active': True,
            'is_staff': True
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()
    
    # Login
    client.login(username='testuser', password='testpass123')
    
    # Get inventory voucher config
    try:
        inventory_config = VoucherModeConfig.objects.filter(
            code__icontains='inventory'
        ).first()
        
        if not inventory_config:
            print("❌ No inventory voucher configuration found")
            return
        
        print(f"✅ Found inventory config: {inventory_config.name} ({inventory_config.code})")
        
        # Navigate to voucher entry page
        url = f'/accounting/vouchers/generic/{inventory_config.code}/'
        response = client.get(url)
        
        if response.status_code == 200:
            print(f"✅ Successfully loaded voucher entry page")
            
            # Submit form with invalid data (no debit or credit)
            post_data = {
                # Header form data
                'voucher_number': 'TEST-001',
                'date': '2024-01-15',
                'description': 'Test voucher with validation error',
                
                # Line formset management form
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '0',
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
                
                # Line 0 - intentionally missing debit AND credit
                'form-0-account': '1',
                'form-0-description': 'Test line',
                'form-0-debit_amount': '',  # Missing
                'form-0-credit_amount': '',  # Missing
            }
            
            response = client.post(url, data=post_data)
            
            if response.status_code == 200:
                content = response.content.decode('utf-8')
                
                # Check for error display improvements
                checks = [
                    ('error-row' in content, "Error row class found"),
                    ('table-danger' in content, "Row highlighting class found"),
                    ('alert-danger' in content, "Alert box found"),
                    ('Line must have either debit or credit' in content, "Validation error message found"),
                    ('fa-exclamation-triangle' in content, "Error icon found"),
                ]
                
                print("\n" + "="*60)
                print("VALIDATION ERROR DISPLAY TEST RESULTS")
                print("="*60)
                
                for check, description in checks:
                    status = "✅" if check else "❌"
                    print(f"{status} {description}")
                
                all_passed = all(check for check, _ in checks)
                
                if all_passed:
                    print("\n🎉 All validation error UX improvements are working!")
                    print("\nExpected behavior:")
                    print("  1. Error message appears ABOVE the problematic line")
                    print("  2. Row is highlighted with red background")
                    print("  3. Alert box with icon is prominent")
                    print("  4. Error message clearly states the issue")
                else:
                    print("\n⚠️  Some improvements may not be working as expected")
                
                print("="*60)
            else:
                print(f"❌ Form submission returned status {response.status_code}")
        else:
            print(f"❌ Failed to load voucher entry page: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Testing Validation Error UX Improvements")
    print("="*60)
    test_validation_error_display()
