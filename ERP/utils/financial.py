"""
Financial Calculations Utilities

Provides comprehensive financial calculation utilities including tax calculations,
balance computations, depreciation, and other financial formulas for the accounting system.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from django.db import models
from django.db.models import Sum, Q, F, Case, When, Value, DecimalField
from django.utils import timezone

from .organization import OrganizationService
from .currency import CurrencyConverter, CurrencyValidator
from .validation import BusinessValidator


class TaxCalculator:
    """
    Comprehensive tax calculation utilities supporting multiple tax types,
    compound taxes, and tax rules.
    """

    @staticmethod
    def calculate_tax(
        amount: Decimal,
        tax_code: Any,
        date: Optional[date] = None,
        inclusive: bool = False
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate tax amount for a given tax code.

        Args:
            amount: Base amount to calculate tax on
            tax_code: Tax code instance or rate
            date: Date for tax calculation (for historical rates)
            inclusive: Whether the amount already includes tax

        Returns:
            Tuple of (tax_amount, net_amount)

        Usage:
            # Calculate VAT on sales
            tax_amount, net_amount = TaxCalculator.calculate_tax(
                Decimal('1000'), vat_tax_code
            )
        """
        if not amount or amount <= 0:
            return Decimal('0'), amount or Decimal('0')

        # Handle different tax_code formats
        if hasattr(tax_code, 'tax_rate'):
            rate = tax_code.tax_rate
        elif isinstance(tax_code, (int, float, Decimal)):
            rate = Decimal(str(tax_code))
        else:
            raise ValueError(f"Invalid tax code format: {tax_code}")

        rate = rate / Decimal('100')  # Convert percentage to decimal

        if inclusive:
            # Tax-inclusive calculation: extract tax from total
            tax_amount = (amount * rate) / (Decimal('1') + rate)
            net_amount = amount - tax_amount
        else:
            # Tax-exclusive calculation: add tax to base
            tax_amount = amount * rate
            net_amount = amount

        return tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), net_amount

    @staticmethod
    def calculate_compound_tax(
        amount: Decimal,
        tax_codes: List[Any],
        inclusive: bool = False
    ) -> Tuple[Decimal, Decimal, List[Dict[str, Any]]]:
        """
        Calculate compound tax (multiple taxes applied sequentially).

        Args:
            amount: Base amount
            tax_codes: List of tax codes
            inclusive: Whether amounts are tax-inclusive

        Returns:
            Tuple of (total_tax, net_amount, breakdown_list)

        Usage:
            # Calculate GST + PST
            total_tax, net, breakdown = TaxCalculator.calculate_compound_tax(
                Decimal('1000'), [gst_code, pst_code]
            )
        """
        if not tax_codes:
            return Decimal('0'), amount, []

        breakdown = []
        current_amount = amount
        total_tax = Decimal('0')

        for tax_code in tax_codes:
            tax_amount, net_amount = TaxCalculator.calculate_tax(
                current_amount, tax_code, inclusive=inclusive
            )

            breakdown.append({
                'tax_code': getattr(tax_code, 'code', str(tax_code)),
                'rate': getattr(tax_code, 'tax_rate', tax_code),
                'tax_amount': tax_amount,
                'base_amount': current_amount,
            })

            if inclusive:
                current_amount = net_amount
            else:
                current_amount += tax_amount
                total_tax += tax_amount

        if inclusive:
            total_tax = sum(item['tax_amount'] for item in breakdown)

        return total_tax, amount, breakdown

    @staticmethod
    def reverse_tax_calculation(
        total_amount: Decimal,
        tax_codes: List[Any]
    ) -> Tuple[Decimal, Decimal, List[Dict[str, Any]]]:
        """
        Reverse calculate tax components from a tax-inclusive total.

        Args:
            total_amount: Tax-inclusive total amount
            tax_codes: List of tax codes applied

        Returns:
            Tuple of (net_amount, total_tax, breakdown)

        Usage:
            # Extract net amount from invoice total
            net, tax, breakdown = TaxCalculator.reverse_tax_calculation(
                Decimal('1120'), [vat_12_code]
            )
        """
        if not tax_codes:
            return total_amount, Decimal('0'), []

        # For reverse calculation, work backwards from the total
        current_total = total_amount
        breakdown = []
        total_tax = Decimal('0')

        # Reverse order for compound taxes
        for tax_code in reversed(tax_codes):
            if hasattr(tax_code, 'tax_rate'):
                rate = tax_code.tax_rate / Decimal('100')
            else:
                rate = Decimal(str(tax_code)) / Decimal('100')

            # Extract this tax layer
            tax_amount = current_total - (current_total / (Decimal('1') + rate))
            net_amount = current_total - tax_amount

            breakdown.insert(0, {
                'tax_code': getattr(tax_code, 'code', str(tax_code)),
                'rate': getattr(tax_code, 'tax_rate', tax_code),
                'tax_amount': tax_amount,
                'net_amount': net_amount,
            })

            current_total = net_amount
            total_tax += tax_amount

        return current_total, total_tax, breakdown


class BalanceCalculator:
    """
    Account balance calculation utilities with support for different balance types
    and date ranges.
    """

    @staticmethod
    def calculate_account_balance(
        account: Any,
        as_of_date: Optional[date] = None,
        balance_type: str = 'current'
    ) -> Decimal:
        """
        Calculate account balance with different balance types.

        Args:
            account: Account instance
            as_of_date: Date for balance calculation
            balance_type: 'current', 'opening', 'closing', 'reconciled'

        Returns:
            Account balance

        Usage:
            # Get current balance
            balance = BalanceCalculator.calculate_account_balance(account)

            # Get balance as of specific date
            balance = BalanceCalculator.calculate_account_balance(
                account, date(2024, 12, 31)
            )
        """
        if not account:
            return Decimal('0')

        if balance_type == 'opening':
            return account.opening_balance or Decimal('0')
        elif balance_type == 'reconciled':
            return account.reconciled_balance or Decimal('0')
        elif balance_type == 'current':
            return account.current_balance or Decimal('0')
        else:
            # Default to current balance
            return account.current_balance or Decimal('0')

    @staticmethod
    def calculate_trial_balance(
        organization: Any,
        as_of_date: Optional[date] = None,
        include_children: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate trial balance for organization.

        Args:
            organization: Organization instance
            as_of_date: Date for balance calculation
            include_children: Whether to include child account balances

        Returns:
            Trial balance data

        Usage:
            # Generate trial balance
            trial_balance = BalanceCalculator.calculate_trial_balance(
                request.organization, date.today()
            )
        """
        from accounting.models import ChartOfAccount

        accounts = ChartOfAccount.active_accounts.for_org(organization)

        trial_balance = {
            'assets': {'total': Decimal('0'), 'accounts': []},
            'liabilities': {'total': Decimal('0'), 'accounts': []},
            'equity': {'total': Decimal('0'), 'accounts': []},
            'income': {'total': Decimal('0'), 'accounts': []},
            'expenses': {'total': Decimal('0'), 'accounts': []},
            'summary': {'total_debit': Decimal('0'), 'total_credit': Decimal('0')}
        }

        for account in accounts:
            balance = BalanceCalculator.calculate_account_balance(account, as_of_date)
            if balance == 0:
                continue

            account_data = {
                'code': account.account_code,
                'name': account.account_name,
                'balance': balance,
                'type': account.account_type.name if account.account_type else '',
            }

            # Categorize by nature
            nature = account.account_type.nature if account.account_type else ''
            if nature == 'asset':
                trial_balance['assets']['accounts'].append(account_data)
                trial_balance['assets']['total'] += balance
                trial_balance['summary']['total_debit'] += balance
            elif nature == 'liability':
                trial_balance['liabilities']['accounts'].append(account_data)
                trial_balance['liabilities']['total'] += abs(balance)
                trial_balance['summary']['total_credit'] += abs(balance)
            elif nature == 'equity':
                trial_balance['equity']['accounts'].append(account_data)
                trial_balance['equity']['total'] += abs(balance)
                trial_balance['summary']['total_credit'] += abs(balance)
            elif nature == 'income':
                trial_balance['income']['accounts'].append(account_data)
                trial_balance['income']['total'] += abs(balance)
                trial_balance['summary']['total_credit'] += abs(balance)
            elif nature == 'expense':
                trial_balance['expenses']['accounts'].append(account_data)
                trial_balance['expenses']['total'] += balance
                trial_balance['summary']['total_debit'] += balance

        # Calculate imbalances
        imbalance = trial_balance['summary']['total_debit'] - trial_balance['summary']['total_credit']
        trial_balance['summary']['imbalance'] = imbalance
        trial_balance['summary']['balanced'] = imbalance == 0

        return trial_balance

    @staticmethod
    def calculate_balance_sheet(
        organization: Any,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate balance sheet.

        Args:
            organization: Organization instance
            as_of_date: Date for calculation

        Returns:
            Balance sheet data
        """
        trial_balance = BalanceCalculator.calculate_trial_balance(organization, as_of_date)

        balance_sheet = {
            'assets': trial_balance['assets'],
            'liabilities_and_equity': {
                'liabilities': trial_balance['liabilities'],
                'equity': trial_balance['equity'],
                'total': trial_balance['liabilities']['total'] + trial_balance['equity']['total']
            },
            'total_assets': trial_balance['assets']['total'],
            'total_liabilities_equity': trial_balance['liabilities']['total'] + trial_balance['equity']['total'],
            'balanced': trial_balance['summary']['balanced']
        }

        return balance_sheet

    @staticmethod
    def calculate_income_statement(
        organization: Any,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Calculate income statement for period.

        Args:
            organization: Organization instance
            start_date: Period start date
            end_date: Period end date

        Returns:
            Income statement data
        """
        from accounting.models import Journal, JournalLine

        # Get income and expense accounts
        income_accounts = JournalLine.objects.filter(
            journal__organization=organization,
            account__account_type__nature='income',
            journal__journal_date__range=(start_date, end_date)
        )

        expense_accounts = JournalLine.objects.filter(
            journal__organization=organization,
            account__account_type__nature='expense',
            journal__journal_date__range=(start_date, end_date)
        )

        # Calculate totals
        income_total = income_accounts.aggregate(
            total=Sum('credit_amount') - Sum('debit_amount')
        )['total'] or Decimal('0')

        expense_total = expense_accounts.aggregate(
            total=Sum('debit_amount') - Sum('credit_amount')
        )['total'] or Decimal('0')

        net_income = income_total - expense_total

        return {
            'period': {'start': start_date, 'end': end_date},
            'income': {'total': income_total, 'accounts': []},
            'expenses': {'total': expense_total, 'accounts': []},
            'net_income': net_income,
        }


class DepreciationCalculator:
    """
    Fixed asset depreciation calculation utilities.
    """

    METHOD_STRAIGHT_LINE = 'straight_line'
    METHOD_DECLINING_BALANCE = 'declining_balance'

    @staticmethod
    def calculate_depreciation(
        asset: Any,
        calculation_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate depreciation for an asset.

        Args:
            asset: Asset instance
            calculation_date: Date for calculation (defaults to today)

        Returns:
            Depreciation calculation results

        Usage:
            # Calculate monthly depreciation
            dep = DepreciationCalculator.calculate_depreciation(asset, date.today())
        """
        if not asset:
            return {'depreciation': Decimal('0'), 'accumulated': Decimal('0')}

        calculation_date = calculation_date or timezone.localdate()

        if asset.depreciation_method == DepreciationCalculator.METHOD_STRAIGHT_LINE:
            return DepreciationCalculator._straight_line_depreciation(asset, calculation_date)
        elif asset.depreciation_method == DepreciationCalculator.METHOD_DECLINING_BALANCE:
            return DepreciationCalculator._declining_balance_depreciation(asset, calculation_date)
        else:
            return {'depreciation': Decimal('0'), 'accumulated': Decimal('0')}

    @staticmethod
    def _straight_line_depreciation(asset: Any, calculation_date: date) -> Dict[str, Any]:
        """Calculate straight-line depreciation."""
        if not asset.useful_life_years or asset.useful_life_years <= 0:
            return {'depreciation': Decimal('0'), 'accumulated': asset.accumulated_depreciation or Decimal('0')}

        # Calculate annual depreciation
        depreciable_amount = asset.cost - (asset.salvage_value or Decimal('0'))
        annual_depreciation = depreciable_amount / asset.useful_life_years

        # Calculate monthly rate
        monthly_depreciation = annual_depreciation / Decimal('12')

        # Calculate accumulated depreciation up to calculation date
        acquisition_date = asset.acquisition_date
        if acquisition_date > calculation_date:
            return {'depreciation': Decimal('0'), 'accumulated': asset.accumulated_depreciation or Decimal('0')}

        months_elapsed = (calculation_date.year - acquisition_date.year) * 12 + \
                        (calculation_date.month - acquisition_date.month)

        if months_elapsed < 0:
            months_elapsed = 0

        accumulated = min(monthly_depreciation * months_elapsed, depreciable_amount)

        return {
            'depreciation': monthly_depreciation,
            'accumulated': accumulated,
            'remaining': depreciable_amount - accumulated,
            'method': 'straight_line'
        }

    @staticmethod
    def _declining_balance_depreciation(asset: Any, calculation_date: date) -> Dict[str, Any]:
        """Calculate declining balance depreciation."""
        # Simplified implementation - would need more sophisticated logic
        # for different declining balance methods
        return {
            'depreciation': Decimal('0'),
            'accumulated': asset.accumulated_depreciation or Decimal('0'),
            'method': 'declining_balance'
        }


class FinancialRatioCalculator:
    """
    Financial ratio calculation utilities.
    """

    @staticmethod
    def calculate_liquidity_ratios(
        current_assets: Decimal,
        current_liabilities: Decimal,
        cash_equivalents: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate liquidity ratios.

        Args:
            current_assets: Total current assets
            current_liabilities: Total current liabilities
            cash_equivalents: Cash and cash equivalents

        Returns:
            Dictionary of liquidity ratios
        """
        ratios = {}

        # Current Ratio
        if current_liabilities > 0:
            ratios['current_ratio'] = current_assets / current_liabilities

        # Quick Ratio (Acid Test)
        # Assume inventory is 20% of current assets (simplified)
        inventory_estimate = current_assets * Decimal('0.2')
        quick_assets = current_assets - inventory_estimate
        if current_liabilities > 0:
            ratios['quick_ratio'] = quick_assets / current_liabilities

        # Cash Ratio
        if current_liabilities > 0:
            ratios['cash_ratio'] = cash_equivalents / current_liabilities

        return ratios

    @staticmethod
    def calculate_profitability_ratios(
        net_income: Decimal,
        total_assets: Decimal,
        total_equity: Decimal,
        sales: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate profitability ratios.

        Args:
            net_income: Net income for period
            total_assets: Total assets
            total_equity: Total equity
            sales: Total sales/revenue

        Returns:
            Dictionary of profitability ratios
        """
        ratios = {}

        # Return on Assets (ROA)
        if total_assets > 0:
            ratios['roa'] = net_income / total_assets

        # Return on Equity (ROE)
        if total_equity > 0:
            ratios['roe'] = net_income / total_equity

        # Net Profit Margin
        if sales > 0:
            ratios['net_profit_margin'] = net_income / sales

        return ratios


class ForeignExchangeCalculator:
    """
    Foreign exchange impact calculation utilities.
    """

    @staticmethod
    def calculate_fx_impact(
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        original_rate: Decimal,
        new_rate: Decimal
    ) -> Tuple[Decimal, str]:
        """
        Calculate foreign exchange gain/loss.

        Args:
            amount: Amount in foreign currency
            from_currency: Source currency
            to_currency: Target currency
            original_rate: Original exchange rate
            new_rate: New exchange rate

        Returns:
            Tuple of (fx_impact, impact_type)

        Usage:
            # Calculate FX impact on receivable
            impact, type = ForeignExchangeCalculator.calculate_fx_impact(
                Decimal('1000'), 'USD', 'NPR', Decimal('130'), Decimal('135')
            )
        """
        if original_rate == 0 or new_rate == 0:
            return Decimal('0'), 'none'

        original_base = amount * original_rate
        new_base = amount * new_rate
        impact = new_base - original_base

        impact_type = 'gain' if impact > 0 else 'loss' if impact < 0 else 'none'

        return impact, impact_type


class AmortizationCalculator:
    """
    Loan and lease amortization calculation utilities.
    """

    @staticmethod
    def calculate_loan_payment(
        principal: Decimal,
        annual_rate: Decimal,
        term_years: int,
        payment_frequency: str = 'monthly'
    ) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """
        Calculate loan payment schedule.

        Args:
            principal: Loan principal amount
            annual_rate: Annual interest rate (as decimal, e.g., 0.05 for 5%)
            term_years: Term in years
            payment_frequency: 'monthly', 'quarterly', 'annually'

        Returns:
            Tuple of (monthly_payment, payment_schedule)
        """
        # Convert annual rate to periodic rate
        if payment_frequency == 'monthly':
            periods_per_year = 12
        elif payment_frequency == 'quarterly':
            periods_per_year = 4
        elif payment_frequency == 'annually':
            periods_per_year = 1
        else:
            periods_per_year = 12

        periodic_rate = annual_rate / periods_per_year
        total_periods = term_years * periods_per_year

        if periodic_rate == 0:
            # No interest loan
            payment = principal / total_periods
            schedule = AmortizationCalculator._build_schedule_no_interest(
                principal, payment, total_periods
            )
        else:
            # Standard loan formula
            payment = principal * (periodic_rate * (1 + periodic_rate) ** total_periods) / \
                     ((1 + periodic_rate) ** total_periods - 1)

            schedule = AmortizationCalculator._build_amortization_schedule(
                principal, periodic_rate, total_periods, payment
            )

        return payment.quantize(Decimal('0.01')), schedule

    @staticmethod
    def _build_amortization_schedule(
        principal: Decimal,
        periodic_rate: Decimal,
        total_periods: int,
        payment: Decimal
    ) -> List[Dict[str, Any]]:
        """Build amortization schedule."""
        schedule = []
        remaining_balance = principal

        for period in range(1, total_periods + 1):
            interest_payment = remaining_balance * periodic_rate
            principal_payment = payment - interest_payment

            # Adjust for rounding in last payment
            if period == total_periods:
                principal_payment = remaining_balance

            remaining_balance -= principal_payment

            schedule.append({
                'period': period,
                'payment': payment,
                'principal_payment': principal_payment.quantize(Decimal('0.01')),
                'interest_payment': interest_payment.quantize(Decimal('0.01')),
                'remaining_balance': max(Decimal('0'), remaining_balance.quantize(Decimal('0.01')))
            })

        return schedule

    @staticmethod
    def _build_schedule_no_interest(
        principal: Decimal,
        payment: Decimal,
        total_periods: int
    ) -> List[Dict[str, Any]]:
        """Build schedule for no-interest loan."""
        schedule = []
        remaining_balance = principal

        for period in range(1, total_periods + 1):
            principal_payment = min(payment, remaining_balance)
            remaining_balance -= principal_payment

            schedule.append({
                'period': period,
                'payment': payment,
                'principal_payment': principal_payment.quantize(Decimal('0.01')),
                'interest_payment': Decimal('0'),
                'remaining_balance': max(Decimal('0'), remaining_balance.quantize(Decimal('0.01')))
            })

        return schedule


# Financial validation utilities
def validate_financial_amount(amount: Decimal, field_name: str = "amount") -> None:
    """
    Validate financial amount constraints.

    Args:
        amount: Amount to validate
        field_name: Field name for error messages

    Raises:
        ValidationError: If validation fails
    """
    from django.core.exceptions import ValidationError

    if amount is None:
        raise ValidationError({field_name: "Amount cannot be null"})

    if amount < 0:
        raise ValidationError({field_name: "Amount cannot be negative"})

    # Check for reasonable limits (adjust as needed)
    if abs(amount) > Decimal('999999999.99'):
        raise ValidationError({field_name: "Amount exceeds maximum allowed value"})


def validate_currency_conversion(
    from_currency: str,
    to_currency: str,
    amount: Decimal,
    organization: Any = None
) -> Tuple[bool, str]:
    """
    Validate currency conversion is possible.

    Args:
        from_currency: Source currency
        to_currency: Target currency
        amount: Amount to convert
        organization: Organization context

    Returns:
        Tuple of (is_valid, error_message)
    """
    return CurrencyValidator.validate_currency_conversion(
        from_currency, to_currency, amount, organization
    )
