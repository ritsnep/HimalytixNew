from accounting.models import Vendor
from django.core.exceptions import ValidationError
from django.db.models import Sum


class VendorService:
    """
    Service for managing vendor/customer master data and related operations.
    """

    @staticmethod
    @staticmethod
    def get_vendor_details(organization, vendor_id):
        """
        Retrieve detailed vendor information including balance, credit limit, PAN, etc.
        """
        try:
            vendor = Vendor.objects.get(organization=organization, vendor_id=vendor_id)
            balance = 0.0  # TODO: Calculate actual balance from transactions
            credit_limit = vendor.credit_limit or 0.0

            # Get primary address
            primary_address = vendor.primary_address()
            address_str = ""
            if primary_address:
                address_parts = [primary_address.line1]
                if primary_address.line2:
                    address_parts.append(primary_address.line2)
                if primary_address.city:
                    address_parts.append(primary_address.city)
                if primary_address.state_province:
                    address_parts.append(primary_address.state_province)
                address_str = ", ".join(address_parts)

            # Get payment term name
            payment_term_name = ""
            if vendor.payment_term:
                payment_term_name = vendor.payment_term.name

            return {
                'id': vendor.vendor_id,
                'name': vendor.display_name,
                'pan': vendor.tax_id or '',
                'address': address_str,
                'phone': vendor.phone_number or '',
                'email': vendor.email or '',
                'balance': balance,
                'credit_limit': credit_limit,
                'payment_terms': payment_term_name,
                'is_active': vendor.is_active,
            }
        except Vendor.DoesNotExist:
            raise ValidationError(f"Vendor with ID {vendor_id} does not exist.")

    @staticmethod
    def get_vendors_for_dropdown(organization):
        """
        Get active vendors for dropdown selection filtered by organization.
        """
        vendors = Vendor.objects.filter(organization=organization, is_active=True).values('vendor_id', 'display_name')
        return [{'id': v['vendor_id'], 'name': v['display_name']} for v in vendors]

    @staticmethod
    def auto_select_agent_for_vendor(vendor_id):
        """
        Auto-select default agent and area based on vendor.
        """
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            agent_id = vendor.default_agent_id if hasattr(vendor, 'default_agent') else None
            area_id = vendor.area_id if hasattr(vendor, 'area') else None
            return {'agent_id': agent_id, 'area_id': area_id}
        except Vendor.DoesNotExist:
            return {'agent_id': None, 'area_id': None}

    @staticmethod
    def validate_vendor_credit_limit(vendor_id, transaction_amount):
        """
        Check if transaction exceeds vendor's credit limit.
        """
        vendor = Vendor.objects.get(id=vendor_id)
        balance = vendor.get_balance()
        credit_limit = vendor.credit_limit or 0.0
        new_balance = balance + transaction_amount

        if new_balance > credit_limit:
            return {
                'valid': False,
                'message': f"Transaction would exceed credit limit. Current balance: {balance}, Limit: {credit_limit}"
            }
        return {'valid': True, 'message': 'OK'}

    @staticmethod
    def get_vendor_payment_history(vendor_id, limit=10):
        """
        Get recent payment history for vendor.
        """
        # Assuming Payment model exists
        from accounting.models import APPayment
        payments = APPayment.objects.filter(vendor_id=vendor_id).order_by('-date')[:limit]
        return list(payments.values('id', 'date', 'amount', 'reference'))

    @staticmethod
    def update_vendor_balance(vendor_id):
        """
        Recalculate and update vendor balance.
        """
        vendor = Vendor.objects.get(id=vendor_id)
        # Calculate balance from transactions
        balance = 0.0  # Implement calculation logic
        vendor.balance = balance
        vendor.save()