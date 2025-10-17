"""
Fiscal year period generator service.
"""
from datetime import date, timedelta
from accounting.models import AccountingPeriod

def generate_periods(fiscal_year, period_count=12):
    start = fiscal_year.start_date
    end = fiscal_year.end_date
    delta = (end - start) // period_count
    periods = []
    for i in range(period_count):
        period_start = start + i * delta
        period_end = period_start + delta - timedelta(days=1)
        if i == period_count - 1:
            period_end = end
        periods.append(AccountingPeriod(
            fiscal_year=fiscal_year,
            name=f"Period {i+1}",
            period_number=i+1,
            start_date=period_start,
            end_date=period_end,
            status='open',
            is_current=(i == 0)
        ))
    return periods
