from django.db import migrations


VIEW_NAME = "accounting_monthly_journalline_mv"

CREATE_VIEW_SQL = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {VIEW_NAME} AS
SELECT
    DATE_TRUNC('month', j.journal_date)::date AS month_start,
    jl.account_id AS account_id,
    SUM(jl.debit_amount) AS total_debit,
    SUM(jl.credit_amount) AS total_credit
FROM accounting_journalline jl
JOIN accounting_journal j ON jl.journal_id = j.journal_id
GROUP BY DATE_TRUNC('month', j.journal_date), jl.account_id;

CREATE INDEX IF NOT EXISTS {VIEW_NAME}_idx
    ON {VIEW_NAME} (month_start, account_id);
"""

DROP_VIEW_SQL = f"DROP MATERIALIZED VIEW IF EXISTS {VIEW_NAME};"


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0135_alter_fiscalyear_id'),
    ]

    operations = [
        migrations.RunSQL(CREATE_VIEW_SQL, reverse_sql=DROP_VIEW_SQL),
    ]
