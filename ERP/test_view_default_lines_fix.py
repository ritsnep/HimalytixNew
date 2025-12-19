import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig
from accounting.views.generic_voucher_views import GenericVoucherCreateView
from usermanagement.models import Organization
from django.test import RequestFactory
from django.contrib.auth import get_user_model

print("="*80)
print("TESTING GenericVoucherCreateView WITH FIXED default_lines")
print("="*80)

try:
    User = get_user_model()
    user = User.objects.get(pk=1)
    org = Organization.objects.get(pk=1)
    config = VoucherModeConfig.objects.get(code='sales-invoice-vm-si', organization=org)
    
    print(f"\nTesting voucher: {config.code} - {config.name}")
    print(f"Has default_lines attribute: {hasattr(config, 'default_lines')}")
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/accounting/generic-voucher/sales-invoice-vm-si/create/')
    request.user = user
    request.organization = org
    
    # Test the view
    print("\nTesting GenericVoucherCreateView.get()...")
    try:
        view = GenericVoucherCreateView()
        view.request = request
        view.kwargs = {'voucher_code': 'sales-invoice-vm-si'}
        
        # Call the get method (this is what triggers the error)
        response = view.get(request, voucher_code='sales-invoice-vm-si')
        
        print(f"   OK View rendered successfully (status: {response.status_code})")
        
    except AttributeError as e:
        print(f"   ERROR: AttributeError - {e}")
        raise
    except Exception as e:
        # Other exceptions are OK (like template not found, etc.)
        print(f"   View executed without AttributeError")
        print(f"   (Other error occurred, but that's OK for this test: {type(e).__name__})")
    
    print("\n" + "="*80)
    print("SUCCESS! No AttributeError on default_lines")
    print("="*80)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
