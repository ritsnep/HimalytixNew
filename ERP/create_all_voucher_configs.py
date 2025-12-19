#!/usr/bin/env python
"""
Create missing VoucherModeConfig records and standardize all ui_schemas
"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, JournalType
from usermanagement.models import Organization
from django.db import transaction

# Get the first organization (or create one)
try:
    org = Organization.objects.first()
    if not org:
        print("ERROR: No organization found. Please create an organization first.")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Define the 17 target vouchers with their configurations
VOUCHER_CONFIGS = [
    {
        'code': 'sales-invoice-vm-si',
        'name': 'Sales Invoice',
        'description': 'Sales invoice for recording customer sales',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['voucher_date', 'customer', 'reference_no', 'due_date', 'payment_terms', 'notes', 'status'],
                    'fields': {
                        'voucher_date': {'order_no': 1, 'autofocus': True, 'label': 'Invoice Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'reference_no': {'order_no': 3, 'label': 'Reference No', 'widget': 'text'},
                        'due_date': {'order_no': 4, 'label': 'Due Date', 'widget': 'date'},
                        'payment_terms': {'order_no': 5, 'label': 'Payment Terms', 'widget': 'text'},
                        'notes': {'order_no': 6, 'label': 'Notes', 'widget': 'textarea'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'journal-entry-vm-je',
        'name': 'Journal Entry',
        'description': 'General journal entry for manual accounting transactions',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['voucher_date', 'reference_no', 'narration', 'status'],
                    'fields': {
                        'voucher_date': {'order_no': 1, 'autofocus': True, 'label': 'Entry Date', 'widget': 'date', 'required': True},
                        'reference_no': {'order_no': 2, 'label': 'Reference No', 'widget': 'text'},
                        'narration': {'order_no': 3, 'label': 'Narration', 'widget': 'textarea', 'required': True},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SI',
        'name': 'Sales Invoice (VM)',
        'description': 'Voucher mode configuration for sales invoices',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['voucher_date', 'customer', 'invoice_no', 'total_amount', 'status'],
                    'fields': {
                        'voucher_date': {'order_no': 1, 'autofocus': True, 'label': 'Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'invoice_no': {'order_no': 3, 'label': 'Invoice No', 'widget': 'text', 'required': True},
                        'total_amount': {'order_no': 4, 'label': 'Total Amount', 'widget': 'number', 'read_only': True},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-PI',
        'name': 'Purchase Invoice',
        'description': 'Purchase invoice for recording supplier purchases',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['voucher_date', 'vendor', 'invoice_no', 'total_amount', 'status'],
                    'fields': {
                        'voucher_date': {'order_no': 1, 'autofocus': True, 'label': 'Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'invoice_no': {'order_no': 3, 'label': 'Invoice No', 'widget': 'text', 'required': True},
                        'total_amount': {'order_no': 4, 'label': 'Total Amount', 'widget': 'number', 'read_only': True},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SO',
        'name': 'Sales Order',
        'description': 'Sales order for customer orders',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['order_date', 'customer', 'order_no', 'delivery_date', 'status'],
                    'fields': {
                        'order_date': {'order_no': 1, 'autofocus': True, 'label': 'Order Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'order_no': {'order_no': 3, 'label': 'Order No', 'widget': 'text', 'required': True},
                        'delivery_date': {'order_no': 4, 'label': 'Expected Delivery', 'widget': 'date'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-PO',
        'name': 'Purchase Order',
        'description': 'Purchase order for supplier orders',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['order_date', 'vendor', 'order_no', 'delivery_date', 'status'],
                    'fields': {
                        'order_date': {'order_no': 1, 'autofocus': True, 'label': 'Order Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'order_no': {'order_no': 3, 'label': 'Order No', 'widget': 'text', 'required': True},
                        'delivery_date': {'order_no': 4, 'label': 'Expected Delivery', 'widget': 'date'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-GR',
        'name': 'Goods Receipt',
        'description': 'Goods receipt for inventory receiving',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['receipt_date', 'vendor', 'receipt_no', 'purchase_order', 'status'],
                    'fields': {
                        'receipt_date': {'order_no': 1, 'autofocus': True, 'label': 'Receipt Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'receipt_no': {'order_no': 3, 'label': 'Receipt No', 'widget': 'text', 'required': True},
                        'purchase_order': {'order_no': 4, 'label': 'PO Reference', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SCN',
        'name': 'Sales Credit Note',
        'description': 'Credit note for sales returns and adjustments',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['note_date', 'customer', 'note_no', 'invoice_reference', 'status'],
                    'fields': {
                        'note_date': {'order_no': 1, 'autofocus': True, 'label': 'Note Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'note_no': {'order_no': 3, 'label': 'Credit Note No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SDN',
        'name': 'Sales Debit Note',
        'description': 'Debit note for additional charges to customers',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['note_date', 'customer', 'note_no', 'invoice_reference', 'status'],
                    'fields': {
                        'note_date': {'order_no': 1, 'autofocus': True, 'label': 'Note Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'note_no': {'order_no': 3, 'label': 'Debit Note No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SR',
        'name': 'Sales Return',
        'description': 'Sales return for returned goods',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['return_date', 'customer', 'return_no', 'invoice_reference', 'status'],
                    'fields': {
                        'return_date': {'order_no': 1, 'autofocus': True, 'label': 'Return Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'return_no': {'order_no': 3, 'label': 'Return No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SQ',
        'name': 'Sales Quotation',
        'description': 'Sales quotation for customer inquiries',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['quote_date', 'customer', 'quote_no', 'valid_until', 'status'],
                    'fields': {
                        'quote_date': {'order_no': 1, 'autofocus': True, 'label': 'Quote Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'quote_no': {'order_no': 3, 'label': 'Quotation No', 'widget': 'text', 'required': True},
                        'valid_until': {'order_no': 4, 'label': 'Valid Until', 'widget': 'date'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-SD',
        'name': 'Sales Delivery',
        'description': 'Delivery note for shipped goods',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['delivery_date', 'customer', 'delivery_no', 'order_reference', 'status'],
                    'fields': {
                        'delivery_date': {'order_no': 1, 'autofocus': True, 'label': 'Delivery Date', 'widget': 'date', 'required': True},
                        'customer': {'order_no': 2, 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx', 'required': True},
                        'delivery_no': {'order_no': 3, 'label': 'Delivery No', 'widget': 'text', 'required': True},
                        'order_reference': {'order_no': 4, 'label': 'Sales Order', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-PCN',
        'name': 'Purchase Credit Note',
        'description': 'Credit note for purchase returns',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['note_date', 'vendor', 'note_no', 'invoice_reference', 'status'],
                    'fields': {
                        'note_date': {'order_no': 1, 'autofocus': True, 'label': 'Note Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'note_no': {'order_no': 3, 'label': 'Credit Note No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-PDN',
        'name': 'Purchase Debit Note',
        'description': 'Debit note for additional charges from suppliers',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['note_date', 'vendor', 'note_no', 'invoice_reference', 'status'],
                    'fields': {
                        'note_date': {'order_no': 1, 'autofocus': True, 'label': 'Note Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'note_no': {'order_no': 3, 'label': 'Debit Note No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-PR',
        'name': 'Purchase Return',
        'description': 'Purchase return for returned goods to suppliers',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['return_date', 'vendor', 'return_no', 'invoice_reference', 'status'],
                    'fields': {
                        'return_date': {'order_no': 1, 'autofocus': True, 'label': 'Return Date', 'widget': 'date', 'required': True},
                        'vendor': {'order_no': 2, 'label': 'Vendor', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_vendor_lookup_hx', 'required': True},
                        'return_no': {'order_no': 3, 'label': 'Return No', 'widget': 'text', 'required': True},
                        'invoice_reference': {'order_no': 4, 'label': 'Original Invoice', 'widget': 'text'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
    {
        'code': 'VM-LC',
        'name': 'Letter of Credit',
        'description': 'Letter of credit for international trade',
        'ui_schema': {
            'sections': {
                'header': {
                    '__order__': ['lc_date', 'bank', 'lc_no', 'beneficiary', 'amount', 'expiry_date', 'status'],
                    'fields': {
                        'lc_date': {'order_no': 1, 'autofocus': True, 'label': 'LC Date', 'widget': 'date', 'required': True},
                        'bank': {'order_no': 2, 'label': 'Issuing Bank', 'widget': 'text', 'required': True},
                        'lc_no': {'order_no': 3, 'label': 'LC Number', 'widget': 'text', 'required': True},
                        'beneficiary': {'order_no': 4, 'label': 'Beneficiary', 'widget': 'text', 'required': True},
                        'amount': {'order_no': 5, 'label': 'Amount', 'widget': 'number', 'required': True},
                        'expiry_date': {'order_no': 6, 'label': 'Expiry Date', 'widget': 'date'},
                        'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                    }
                }
            }
        }
    },
]

# Also update VM08 with proper ui_schema
VM08_UPDATE = {
    'code': 'VM08',
    'ui_schema': {
        'sections': {
            'header': {
                '__order__': ['voucher_date', 'reference_no', 'adjustment_type', 'narration', 'status'],
                'fields': {
                    'voucher_date': {'order_no': 1, 'autofocus': True, 'label': 'Adjustment Date', 'widget': 'date', 'required': True},
                    'reference_no': {'order_no': 2, 'label': 'Reference No', 'widget': 'text'},
                    'adjustment_type': {'order_no': 3, 'label': 'Adjustment Type', 'widget': 'select', 'choices': [('stock', 'Stock Adjustment'), ('gl', 'GL Adjustment')]},
                    'narration': {'order_no': 4, 'label': 'Narration', 'widget': 'textarea', 'required': True},
                    'status': {'order_no': 99, 'label': 'Status', 'widget': 'select', 'read_only': True, 'default': 'draft'}
                }
            }
        }
    }
}


def create_or_update_vouchers():
    """Create missing vouchers and update existing ones"""
    created = 0
    updated = 0
    skipped = 0
    
    # Update VM08
    try:
        with transaction.atomic():
            vm08 = VoucherModeConfig.objects.get(code='VM08', organization=org)
            vm08.ui_schema = VM08_UPDATE['ui_schema']
            vm08.save()
            print(f"✓ Updated: VM08 - {vm08.name}")
            updated += 1
    except VoucherModeConfig.DoesNotExist:
        print(f"✗ VM08 not found - skipping update")
    except Exception as e:
        print(f"✗ Error updating VM08: {e}")
    
    # Create or update target vouchers
    for config_data in VOUCHER_CONFIGS:
        code = config_data['code']
        
        try:
            with transaction.atomic():
                # Check if exists
                existing = VoucherModeConfig.objects.get(code=code, organization=org)
                # Update ui_schema
                existing.ui_schema = config_data['ui_schema']
                existing.name = config_data['name']
                existing.description = config_data['description']
                existing.save()
                print(f"✓ Updated: {code} - {existing.name}")
                updated += 1
        except VoucherModeConfig.DoesNotExist:
            try:
                with transaction.atomic():
                    # Create new
                    new_config = VoucherModeConfig(
                        organization=org,
                        code=code,
                        name=config_data['name'],
                        description=config_data['description'],
                        ui_schema=config_data['ui_schema'],
                        is_active=True
                    )
                    new_config.save()
                    print(f"✓ Created: {code} - {new_config.name}")
                    created += 1
            except Exception as e:
                print(f"✗ Error creating {code}: {e}")
                skipped += 1
        except Exception as e:
            print(f"✗ Error processing {code}: {e}")
            skipped += 1
    
    return created, updated, skipped


if __name__ == '__main__':
    print("\n" + "="*80)
    print("CREATING/UPDATING VOUCHERMODECONFIG RECORDS")
    print("="*80)
    print(f"Organization: {org.name}")
    print(f"Target vouchers: 17 (16 new + 1 update)")
    print("="*80 + "\n")
    
    created, updated, skipped = create_or_update_vouchers()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total processed: {created + updated + skipped}")
    print("="*80 + "\n")
    
    # Verify total count
    total = VoucherModeConfig.objects.filter(organization=org).count()
    print(f"Total VoucherModeConfig records in database: {total}\n")
