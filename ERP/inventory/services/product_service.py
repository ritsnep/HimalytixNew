from django.db import transaction
from inventory.models import Product, InventoryItem
from accounting.models import TaxCode
from django.core.exceptions import ValidationError


class ProductService:
    """
    Service for managing product master data, including retrieval of details
    for purchase/sales transactions.
    """

    @staticmethod
    @staticmethod
    def get_product_details(organization, product_id):
        """
        Retrieve detailed product information including unit, HS code, description,
        VAT applicability, and default pricing.
        """
        try:
            product = Product.objects.get(organization=organization, id=product_id)
            # For now, assume no tax code - this might need to be added to Product model
            vat_applicable = False
            vat_rate = 0.0

            # Get unit name from base_unit foreign key
            unit_name = product.base_unit.name if product.base_unit else 'Nos'

            return {
                'id': product.id,
                'code': product.code,
                'name': product.name,
                'description': product.description or '',
                'hs_code': '',  # Product model doesn't have hs_code field
                'unit': unit_name,
                'vat_applicable': vat_applicable,
                'vat_rate': vat_rate,
                'standard_price': product.cost_price or 0.0,  # Use cost_price as standard_price
                'category': product.category.name if product.category else '',
                'is_active': True,  # Product model doesn't have is_active field, assume all are active
            }
        except Product.DoesNotExist:
            raise ValidationError(f"Product with ID {product_id} does not exist.")

    @staticmethod
    def get_products_for_dropdown(organization):
        """
        Get active products for dropdown selection filtered by organization.
        """
        products = Product.objects.filter(organization=organization).order_by('name')
        return [
            {'id': product.id, 'name': f"{product.code} - {product.name}" if product.code else product.name}
            for product in products
        ]

    @staticmethod
    def validate_product_for_transaction(product_id, quantity, warehouse_id=None):
        """
        Validate product availability and constraints for transactions.
        """
        try:
            product = Product.objects.get(id=product_id)
            if warehouse_id:
                inventory = InventoryItem.objects.filter(
                    product=product,
                    warehouse_id=warehouse_id
                ).first()
                available = None
                if inventory:
                    available = getattr(inventory, "quantity_on_hand", None)
                    if available is None:
                        available = getattr(inventory, "quantity", None)
                if available is not None and available < quantity:
                    return {
                        'valid': False,
                        'message': f"Insufficient stock. Available: {available}"
                    }
            return {'valid': True, 'message': 'OK'}
        except Product.DoesNotExist:
            return {'valid': False, 'message': 'Product not found'}

    @staticmethod
    def update_product_prices(product_id, new_standard_price=None, party_prices=None):
        """
        Update standard and party-specific prices for a product.
        """
        with transaction.atomic():
            product = Product.objects.get(id=product_id)
            if new_standard_price is not None:
                # Product model doesn't expose `standard_price`; use cost_price as standard baseline.
                product.cost_price = new_standard_price
            product.save()

            # Update party prices if provided (assuming a related model)
            if party_prices:
                for party_price in party_prices:
                    # Assuming PartyPrice model exists
                    pass  # Implement based on your model structure

    @staticmethod
    def get_product_vat_details(product_id):
        """
        Get VAT-related details for a product.
        """
        product = Product.objects.get(id=product_id)
        tax_code = product.tax_code if hasattr(product, 'tax_code') else None
        return {
            'vat_applicable': tax_code.vat_applicable if tax_code else False,
            'vat_rate': tax_code.rate if tax_code else 0.0,
            'tax_code': tax_code.code if tax_code else '',
        }
