from accounting.models import PaymentTerm


class PaymentTermService:
    """
    Service for managing payment terms.
    """

    @staticmethod
    def get_payment_terms_for_dropdown(organization):
        """
        Get active payment terms for dropdown selection filtered by organization.
        """
        payment_terms = PaymentTerm.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('name')
        return [
            {'id': term.payment_term_id, 'name': f"{term.code} - {term.name}"}
            for term in payment_terms
        ]