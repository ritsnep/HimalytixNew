"""
Document sequence service for generating sequential document numbers.
"""
from accounting.services.auto_numbering import generate_auto_number
from accounting.models import PurchaseInvoice


class DocumentSequenceService:
    """Service for generating document sequence numbers."""

    @staticmethod
    def get_next_number(organization, document_type, prefix):
        """
        Get the next document number for the given type and prefix.

        Args:
            organization: Organization instance
            document_type: Type of document (e.g., 'purchase_invoice')
            prefix: Prefix for the document number

        Returns:
            Next available document number as string
        """
        if document_type == 'purchase_invoice':
            return generate_auto_number(
                model=PurchaseInvoice,
                field='invoice_number',
                prefix=prefix,
                suffix=''
            )

        # For other document types, return a simple incremented number
        # This could be enhanced to use TransactionTypeConfig
        return f"{prefix}001"