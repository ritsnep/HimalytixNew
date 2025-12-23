from accounting.models import Vendor, Pricing
from inventory.models import Product
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models


class PricingService:
    """
    Service for managing pricing logic, including standard and party-specific prices.
    """

    @staticmethod
    @staticmethod
    def get_pricing_for_party(organization, product_id, party_id):
        """
        Get pricing details for a specific product and party (vendor/customer).
        Returns party-specific pricing if available, otherwise standard price.
        """
        try:
            product = Product.objects.get(organization=organization, id=product_id)
            standard_price = product.standard_price or 0.0

            party_price = standard_price
            discount_percentage = 0.0

            if party_id:
                # Get active pricing for this party and product
                today = timezone.now().date()
                pricing = Pricing.objects.filter(
                    organization=organization,
                    product_id=product_id,
                    party_id=party_id,
                    is_active=True,
                    effective_from__lte=today,
                ).filter(
                    models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
                ).order_by('-priority').first()

                if pricing:
                    party_price = pricing.unit_price
                    if pricing.discount_type == 'percentage':
                        discount_percentage = pricing.discount_value
                    else:
                        # Fixed amount discount
                        discount_percentage = (pricing.discount_value / pricing.unit_price) * 100 if pricing.unit_price > 0 else 0

            return {
                'standard_price': standard_price,
                'party_price': party_price,
                'discount_percentage': discount_percentage,
            }
        except Product.DoesNotExist:
            raise ValidationError(f"Product with ID {product_id} does not exist.")

    @staticmethod
    def set_party_pricing(product_id, party_id, price, discount_type='percentage', discount_value=0, **kwargs):
        """
        Set or update party-specific pricing for a product.
        """
        from accounting.models import Organization

        try:
            product = Product.objects.get(id=product_id)
            party = Vendor.objects.get(id=party_id)

            # Get organization from product (assuming product has organization field)
            organization = getattr(product, 'organization', None)
            if not organization:
                raise ValidationError("Product must belong to an organization.")

            pricing, created = Pricing.objects.get_or_create(
                organization=organization,
                product=product,
                party=party,
                price_type=kwargs.get('price_type', 'special'),
                defaults={
                    'unit_price': price,
                    'discount_type': discount_type,
                    'discount_value': discount_value,
                    'currency': kwargs.get('currency', product.currency if hasattr(product, 'currency') else None),
                    'effective_from': kwargs.get('effective_from', timezone.now().date()),
                    'effective_to': kwargs.get('effective_to'),
                    'priority': kwargs.get('priority', 1),
                }
            )

            if not created:
                # Update existing pricing
                pricing.unit_price = price
                pricing.discount_type = discount_type
                pricing.discount_value = discount_value
                if 'effective_from' in kwargs:
                    pricing.effective_from = kwargs['effective_from']
                if 'effective_to' in kwargs:
                    pricing.effective_to = kwargs['effective_to']
                if 'priority' in kwargs:
                    pricing.priority = kwargs['priority']
                pricing.save()

            return {
                'pricing_id': pricing.pricing_id,
                'product_id': product_id,
                'party_id': party_id,
                'unit_price': pricing.unit_price,
                'discount_type': pricing.discount_type,
                'discount_value': pricing.discount_value,
                'created': created,
            }
        except Product.DoesNotExist:
            raise ValidationError(f"Product with ID {product_id} does not exist.")
        except Vendor.DoesNotExist:
            raise ValidationError(f"Vendor with ID {party_id} does not exist.")

    @staticmethod
    def get_bulk_pricing(products, party_id):
        """
        Get pricing for multiple products for a party.
        """
        product_ids = [p['id'] for p in products]
        standard_prices = {p.id: p.standard_price for p in Product.objects.filter(id__in=product_ids)}

        result = []
        for prod in products:
            std_price = standard_prices.get(prod['id'], 0)
            # For now, party price = standard price
            party_price = std_price
            result.append({
                'product_id': prod['id'],
                'standard_price': std_price,
                'party_price': party_price,
            })

        return result

    @staticmethod
    def calculate_discounted_price(base_price, discount_type, discount_value):
        """
        Calculate price after applying discount.
        """
        if discount_type == 'percentage':
            return base_price * (1 - discount_value / 100)
        elif discount_type == 'amount':
            return max(0, base_price - discount_value)
        else:
            return base_price

    @staticmethod
    def validate_pricing_rules(product_id, party_id, proposed_price):
        """
        Validate pricing against business rules (e.g., minimum margins).
        """
        product = Product.objects.get(id=product_id)
        min_price = product.min_price or 0

        if proposed_price < min_price:
            return {
                'valid': False,
                'message': f"Price below minimum allowed: {min_price}"
            }

        # Additional rules can be added here
        return {'valid': True, 'message': 'OK'}