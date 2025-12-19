import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import JournalType, VoucherModeConfig

# Get first journal type
jt = JournalType.objects.first()
if not jt:
    print("ERROR: No JournalType found")
    exit(1)

print(f"Using JournalType ID: {jt.journal_type_id} - {jt.name}")

# Update all 17 vouchers
voucher_codes = [
    'sales-invoice-vm-si', 'VM08', 'journal-entry-vm-je',
    'VM-SI', 'VM-PI', 'VM-SO', 'VM-PO', 'VM-GR',
    'VM-SCN', 'VM-SDN', 'VM-SR', 'VM-SQ', 'VM-SD',
    'VM-PCN', 'VM-PDN', 'VM-PR', 'VM-LC'
]

updated = 0
for code in voucher_codes:
    try:
        config = VoucherModeConfig.objects.filter(code=code).first()
        if config:
            config.journal_type_id = jt.journal_type_id
            config.save()
            updated += 1
            print(f"OK {code:30} | journal_type_id={jt.journal_type_id}")
        else:
            print(f"SKIP {code:30} | Not found")
    except Exception as e:
        print(f"FAIL {code:30} | Error: {e}")

print(f"\nUpdated {updated}/{len(voucher_codes)} voucher configs")
