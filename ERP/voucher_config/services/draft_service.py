from django.db import transaction
from django.core.exceptions import ValidationError
from accounting.models import VoucherProcess, Journal, JournalLine
from .models import VoucherConfigMaster


def save_draft(voucher_config_code, data, user):
    config = VoucherConfigMaster.objects.get(code=voucher_config_code, organization=user.organization)
    
    with transaction.atomic():
        # Pre-validation
        _validate_draft(data, config, user)
        
        # Create header
        voucher = Journal.objects.create(
            organization=user.organization,
            journal_type=config.journal_type_mapping,
            voucher_date=data.get('voucher_date'),
            reference=data.get('reference'),
            description=data.get('description'),
            status='draft',
            created_by=user,
        )
        
        # Normalize and persist lines
        lines_data = data.getlist('lines')
        for line_data in lines_data:
            JournalLine.objects.create(
                journal=voucher,
                account_id=line_data.get('account'),
                debit=line_data.get('debit', 0),
                credit=line_data.get('credit', 0),
                description=line_data.get('description'),
            )
        
        # Build inventory metadata (stub)
        inventory_metadata = {}
        
        # Create VoucherProcess
        VoucherProcess.objects.create(
            voucher=voucher,
            current_step='saved',
            actor=user,
            correlation_id=data.get('correlation_id'),
        )
        
        return {'success': True, 'voucher_id': voucher.id}


def _validate_draft(data, config, user):
    # Fiscal period, back-date, duplicate number, credit limit checks
    if not data.get('voucher_date'):
        raise ValidationError("Voucher date required")
    # Add more validations