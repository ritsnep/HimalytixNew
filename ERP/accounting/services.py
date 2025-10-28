"""
Service functions for accounting operations.
"""
from django.db import transaction
from accounting.models import Journal, JournalLine


def create_voucher(config, header_data, lines_data, user):
    """
    Create a voucher (journal entry) from wizard data.
    
    Args:
        config: VoucherModeConfig instance
        header_data: Dictionary containing header information
        lines_data: Dictionary or list containing line item information
        user: User creating the voucher
        
    Returns:
        Created Journal instance
    """
    with transaction.atomic():
        # Create the journal entry
        journal = Journal.objects.create(
            organization=user.organization if hasattr(user, 'organization') else None,
            journal_type=config.journal_type if config else None,
            status='draft',
            created_by=user,
            **{k: v for k, v in header_data.items() if hasattr(Journal, k)}
        )
        
        # Create journal lines if provided
        if lines_data:
            # Handle both dict and list formats
            if isinstance(lines_data, dict):
                lines_data = [lines_data]
            
            for line_data in lines_data:
                if line_data:  # Skip empty lines
                    JournalLine.objects.create(
                        journal=journal,
                        **{k: v for k, v in line_data.items() if hasattr(JournalLine, k)}
                    )
        
        return journal
