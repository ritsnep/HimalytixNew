from accounting.models import FiscalYear, AccountingPeriod
from datetime import date

def get_current_fiscal_year_and_period(organization, target_date=None):
    """
    Determines the current fiscal year and accounting period for a given organization and date.
    If target_date is None, it defaults to today's date.
    """
    if target_date is None:
        target_date = date.today()

    fiscal_year = FiscalYear.objects.filter(
        organization=organization,
        start_date__lte=target_date,
        end_date__gte=target_date,
        status='open'
    ).first()

    accounting_period = None
    if fiscal_year:
        accounting_period = AccountingPeriod.objects.filter(
            fiscal_year=fiscal_year,
            start_date__lte=target_date,
            end_date__gte=target_date,
            is_open=True
        ).first()
    
    return fiscal_year, accounting_period