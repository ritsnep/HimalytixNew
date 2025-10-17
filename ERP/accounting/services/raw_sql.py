"""
Raw-SQL functions for year-end close and trial balance.
"""
from django.db import connection

def run_trial_balance(fiscal_year_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT account_id, SUM(debit) as total_debit, SUM(credit) as total_credit
            FROM general_ledger
            WHERE fiscal_year_id = %s
            GROUP BY account_id
        """, [fiscal_year_id])
        return cursor.fetchall()

def run_year_end_close(fiscal_year_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            -- Example: Close all open periods for the fiscal year
            UPDATE accounting_period SET status='closed' WHERE fiscal_year_id=%s AND status='open'
        """, [fiscal_year_id])
