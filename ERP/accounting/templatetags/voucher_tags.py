from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def total_debit(lines):
    """Calculate total debit amount from journal lines."""
    if not lines:
        return Decimal('0.00')
    return sum(Decimal(str(getattr(line, 'debit_amount', 0) or 0)) for line in lines)

@register.filter
def total_credit(lines):
    """Calculate total credit amount from journal lines."""
    if not lines:
        return Decimal('0.00')
        # Handle empty or None values gracefully
        return sum(Decimal(str(getattr(line, 'credit_amount', 0) or 0)) for line in lines)