"""
Tax calculation helper functions.
"""
from typing import Union

def calculate_tax(amount: float, tax_rate: Union[float, int]) -> float:
    """
    Calculate tax for a given amount and tax rate.

    Args:
        amount (float): The base amount.
        tax_rate (float|int): The tax rate as a percentage (e.g., 5 for 5%).

    Returns:
        float: The calculated tax.
    """
    if not isinstance(amount, (int, float)):
        raise ValueError("Amount must be a number.")
    if not isinstance(tax_rate, (int, float)):
        raise ValueError("Tax rate must be a number.")
    return float(amount) * float(tax_rate) / 100
