from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.services.vendor_service import VendorService
from inventory.services.product_service import ProductService
from accounting.services.pricing_service import PricingService


class ValidationService:
    """
    Centralized validation service for forms and transactions.
    """

    @staticmethod
    def validate_purchase_invoice_data(organization, data):
        """
        Validate complete purchase invoice data before saving.
        """
        errors = {}

        # Validate vendor
        if 'vendor_id' in data:
            try:
                vendor_details = VendorService.get_vendor_details(organization, data['vendor_id'])
                if not vendor_details['is_active']:
                    errors['vendor'] = 'Vendor is inactive'
            except ValidationError as e:
                errors['vendor'] = str(e)

        # Validate credit limit
        if 'vendor_id' in data and 'total_amount' in data:
            credit_check = VendorService.validate_vendor_credit_limit(
                organization, data['vendor_id'], data['total_amount']
            )
            if not credit_check['valid']:
                errors['credit_limit'] = credit_check['message']

        # Validate line items
        if 'line_items' in data:
            for i, item in enumerate(data['line_items']):
                item_errors = ValidationService.validate_line_item(
                    item,
                    data.get('vendor_id'),
                    organization=organization,
                )
                if item_errors:
                    errors[f'line_item_{i}'] = item_errors

        # Validate totals
        if 'calculated_total' in data and 'expected_total' in data:
            calculated = Decimal(data['calculated_total'])
            expected = Decimal(data['expected_total'])
            if abs(calculated - expected) > Decimal('0.01'):
                errors['totals'] = 'Calculated total does not match expected total'

        if 'grand_total' in data and 'payments_total' in data:
            grand_total = Decimal(data['grand_total'])
            payments_total = Decimal(data['payments_total'])
            if payments_total > grand_total:
                errors['payments'] = 'Payment total exceeds invoice total'

        return errors

    @staticmethod
    def validate_line_item(item_data, vendor_id=None, organization=None):
        """
        Validate individual line item data.
        """
        errors = {}

        # Validate product
        if 'product_id' in item_data:
            try:
                if organization:
                    product_details = ProductService.get_product_details(organization, item_data['product_id'])
                    if not product_details['is_active']:
                        errors['product'] = 'Product is inactive'
            except ValidationError as e:
                errors['product'] = str(e)
            except TypeError:
                errors['product'] = 'Product validation failed.'

        # Validate quantity and rate
        if 'quantity' in item_data and item_data['quantity'] <= 0:
            errors['quantity'] = 'Quantity must be positive'

        if 'rate' in item_data and item_data['rate'] < 0:
            errors['rate'] = 'Rate cannot be negative'

        # Validate pricing
        if vendor_id and 'product_id' in item_data and 'rate' in item_data and organization:
            pricing = PricingService.get_pricing_for_party(organization, item_data['product_id'], vendor_id)
            if item_data['rate'] < pricing['party_price'] * 0.9:  # Allow 10% variance
                errors['rate'] = 'Rate significantly below party price'

        # Validate stock if warehouse specified
        if 'product_id' in item_data and 'quantity' in item_data and 'warehouse_id' in item_data:
            stock_check = ProductService.validate_product_for_transaction(
                item_data['product_id'], item_data['quantity'], item_data['warehouse_id']
            )
            if not stock_check['valid']:
                errors['stock'] = stock_check['message']

        return errors

    @staticmethod
    def validate_form_field(field_name, value, context=None):
        """
        Validate individual form fields with context.
        """
        errors = []

        if field_name == 'voucher_no':
            if not value or not value.strip():
                errors.append('Voucher number is required')
            # Add uniqueness check if needed

        elif field_name == 'date_ad':
            from datetime import date
            if isinstance(value, str):
                try:
                    date.fromisoformat(value)
                except ValueError:
                    errors.append('Invalid date format')
            elif isinstance(value, date):
                if value > date.today():
                    errors.append('Date cannot be in the future')

        elif field_name == 'party_invoice_no':
            if len(value) > 50:
                errors.append('Party invoice number too long')

        # Add more field validations as needed

        return errors

    @staticmethod
    def validate_business_rules(data):
        """
        Validate business-specific rules.
        """
        errors = []

        # Example: High-value transaction requires approval
        if 'total_amount' in data and data['total_amount'] > 100000:  # Configurable threshold
            if not data.get('approval_required', False):
                errors.append('High-value transaction requires approval')

        # Example: Certain products require quality check
        if 'line_items' in data:
            for item in data['line_items']:
                if item.get('product_category') == 'raw_material':
                    if not item.get('quality_checked', False):
                        errors.append(f'Product {item["product_id"]} requires quality check')

        return errors
