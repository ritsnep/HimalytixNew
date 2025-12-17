from django.db import migrations


GENERAL_LEDGER_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_general_ledger(
    p_org_id BIGINT,
    p_start_date DATE,
    p_end_date DATE,
    p_account_id BIGINT DEFAULT NULL
)
RETURNS TABLE (
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    transaction_date DATE,
    journal_id BIGINT,
    journal_number VARCHAR,
    journal_line_id BIGINT,
    reference TEXT,
    line_description TEXT,
    debit_amount NUMERIC(19, 4),
    credit_amount NUMERIC(19, 4),
    running_balance NUMERIC(19, 4),
    opening_balance NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH filtered AS (
    SELECT
        gl.gl_entry_id,
        gl.transaction_date,
        gl.journal_id,
        gl.journal_line_id,
        gl.account_id,
        gl.debit_amount,
        gl.credit_amount,
        j.journal_number,
        j.reference,
        jl.description,
        acc.account_code,
        acc.account_name
    FROM accounting_generalledger gl
    JOIN accounting_journal j ON j.journal_id = gl.journal_id
    JOIN accounting_journalline jl ON jl.journal_line_id = gl.journal_line_id
    JOIN chart_of_account acc ON acc.account_id = gl.account_id
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date BETWEEN p_start_date AND p_end_date
      AND (p_account_id IS NULL OR gl.account_id = p_account_id)
    ORDER BY gl.account_id, gl.transaction_date, gl.gl_entry_id
),
opening AS (
    SELECT
        gl.account_id,
        COALESCE(SUM(gl.debit_amount - gl.credit_amount), 0) AS opening_balance
    FROM accounting_generalledger gl
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date < p_start_date
      AND (p_account_id IS NULL OR gl.account_id = p_account_id)
    GROUP BY gl.account_id
)
SELECT
    f.account_id,
    f.account_code,
    f.account_name,
    f.transaction_date,
    f.journal_id,
    f.journal_number,
    f.journal_line_id,
    f.reference,
    f.description,
    f.debit_amount,
    f.credit_amount,
    COALESCE(o.opening_balance, 0)
        + SUM(f.debit_amount - f.credit_amount)
            OVER (PARTITION BY f.account_id ORDER BY f.transaction_date, f.gl_entry_id
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        AS running_balance,
    COALESCE(o.opening_balance, 0) AS opening_balance
FROM filtered f
LEFT JOIN opening o ON o.account_id = f.account_id
ORDER BY f.account_code, f.transaction_date, f.journal_id, f.journal_line_id;
$$;
"""


TRIAL_BALANCE_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_trial_balance(
    p_org_id BIGINT,
    p_as_of DATE
)
RETURNS TABLE (
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    account_nature VARCHAR,
    debit_total NUMERIC(19, 4),
    credit_total NUMERIC(19, 4),
    net_balance NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH balances AS (
    SELECT
        gl.account_id,
        SUM(gl.debit_amount) AS debit_total,
        SUM(gl.credit_amount) AS credit_total
    FROM accounting_generalledger gl
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date <= p_as_of
    GROUP BY gl.account_id
)
SELECT
    acc.account_id,
    acc.account_code,
    acc.account_name,
    at.nature,
    COALESCE(b.debit_total, 0) AS debit_total,
    COALESCE(b.credit_total, 0) AS credit_total,
    COALESCE(b.debit_total, 0) - COALESCE(b.credit_total, 0) AS net_balance
FROM chart_of_account acc
JOIN account_type at ON at.account_type_id = acc.account_type_id
LEFT JOIN balances b ON b.account_id = acc.account_id
WHERE acc.organization_id = p_org_id
  AND acc.is_active = TRUE
ORDER BY at.display_order, acc.account_code;
$$;
"""


PROFIT_LOSS_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_profit_loss(
    p_org_id BIGINT,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    account_nature VARCHAR,
    category VARCHAR,
    debit_total NUMERIC(19, 4),
    credit_total NUMERIC(19, 4),
    net_amount NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH movements AS (
    SELECT
        gl.account_id,
        SUM(gl.debit_amount) AS debit_total,
        SUM(gl.credit_amount) AS credit_total
    FROM accounting_generalledger gl
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date BETWEEN p_start_date AND p_end_date
    GROUP BY gl.account_id
)
SELECT
    acc.account_id,
    acc.account_code,
    acc.account_name,
    at.nature,
    COALESCE(at.income_statement_category, at.name) AS category,
    COALESCE(m.debit_total, 0) AS debit_total,
    COALESCE(m.credit_total, 0) AS credit_total,
    CASE
        WHEN at.nature = 'income'
            THEN COALESCE(m.credit_total, 0) - COALESCE(m.debit_total, 0)
        ELSE COALESCE(m.debit_total, 0) - COALESCE(m.credit_total, 0)
    END AS net_amount
FROM chart_of_account acc
JOIN account_type at ON at.account_type_id = acc.account_type_id
LEFT JOIN movements m ON m.account_id = acc.account_id
WHERE acc.organization_id = p_org_id
  AND at.nature IN ('income', 'expense')
ORDER BY at.display_order, acc.account_code;
$$;
"""


BALANCE_SHEET_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_balance_sheet(
    p_org_id BIGINT,
    p_as_of DATE
)
RETURNS TABLE (
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    nature VARCHAR,
    category VARCHAR,
    balance NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH balances AS (
    SELECT
        gl.account_id,
        SUM(gl.debit_amount) AS debit_total,
        SUM(gl.credit_amount) AS credit_total
    FROM accounting_generalledger gl
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date <= p_as_of
    GROUP BY gl.account_id
)
SELECT
    acc.account_id,
    acc.account_code,
    acc.account_name,
    at.nature,
    COALESCE(at.balance_sheet_category, at.name) AS category,
    COALESCE(b.debit_total, 0) - COALESCE(b.credit_total, 0) AS balance
FROM chart_of_account acc
JOIN account_type at ON at.account_type_id = acc.account_type_id
LEFT JOIN balances b ON b.account_id = acc.account_id
WHERE acc.organization_id = p_org_id
  AND at.nature IN ('asset', 'liability', 'equity')
ORDER BY at.display_order, acc.account_code;
$$;
"""


CASH_FLOW_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_cash_flow(
    p_org_id BIGINT,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    category VARCHAR,
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    cash_movement NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH categorized AS (
    SELECT
        acc.account_id,
        acc.account_code,
        acc.account_name,
        COALESCE(at.cash_flow_category, at.nature) AS category,
        SUM(gl.debit_amount - gl.credit_amount) AS net_change
    FROM accounting_generalledger gl
    JOIN chart_of_account acc ON acc.account_id = gl.account_id
    JOIN account_type at ON at.account_type_id = acc.account_type_id
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date BETWEEN p_start_date AND p_end_date
      AND acc.is_active = TRUE
    GROUP BY acc.account_id, acc.account_code, acc.account_name, category
)
SELECT
    category,
    account_id,
    account_code,
    account_name,
    net_change
FROM categorized
WHERE category IS NOT NULL
ORDER BY category, account_code;
$$;
"""


AR_AGING_FUNCTION = r"""
CREATE OR REPLACE FUNCTION fn_report_ar_aging(
    p_org_id BIGINT,
    p_as_of DATE
)
RETURNS TABLE (
    account_id BIGINT,
    account_code VARCHAR,
    account_name VARCHAR,
    bucket VARCHAR,
    bucket_order INTEGER,
    balance NUMERIC(19, 4)
)
LANGUAGE SQL
AS $$
WITH ar_accounts AS (
    SELECT
        acc.account_id,
        acc.account_code,
        acc.account_name
    FROM chart_of_account acc
    JOIN account_type at ON at.account_type_id = acc.account_type_id
    WHERE acc.organization_id = p_org_id
      AND acc.is_active = TRUE
      AND (
            LOWER(at.classification) LIKE 'account%%receivable%%' OR
            LOWER(acc.account_name) LIKE '%%receivable%%'
      )
),
balances AS (
    SELECT
        gl.account_id,
        (SUM(gl.debit_amount) - SUM(gl.credit_amount)) AS net_balance,
        CASE
            WHEN p_as_of - gl.transaction_date <= 30 THEN '0-30 Days'
            WHEN p_as_of - gl.transaction_date <= 60 THEN '31-60 Days'
            WHEN p_as_of - gl.transaction_date <= 90 THEN '61-90 Days'
            ELSE '90+ Days'
        END AS bucket,
        CASE
            WHEN p_as_of - gl.transaction_date <= 30 THEN 1
            WHEN p_as_of - gl.transaction_date <= 60 THEN 2
            WHEN p_as_of - gl.transaction_date <= 90 THEN 3
            ELSE 4
        END AS bucket_order
    FROM accounting_generalledger gl
    WHERE gl.organization_id = p_org_id
      AND gl.transaction_date <= p_as_of
    GROUP BY gl.account_id, bucket, bucket_order
)
SELECT
    acc.account_id,
    acc.account_code,
    acc.account_name,
    b.bucket,
    b.bucket_order,
    COALESCE(b.net_balance, 0) AS balance
FROM ar_accounts acc
LEFT JOIN balances b ON b.account_id = acc.account_id
ORDER BY acc.account_code, b.bucket_order;
$$;
"""


def create_functions(apps, schema_editor):
    schema_editor.execute(GENERAL_LEDGER_FUNCTION)
    schema_editor.execute(TRIAL_BALANCE_FUNCTION)
    schema_editor.execute(PROFIT_LOSS_FUNCTION)
    schema_editor.execute(BALANCE_SHEET_FUNCTION)
    schema_editor.execute(CASH_FLOW_FUNCTION)
    schema_editor.execute(AR_AGING_FUNCTION)


def drop_functions(apps, schema_editor):
    for fn_name, signature in [
        ("fn_report_ar_aging", "(BIGINT, DATE)"),
        ("fn_report_cash_flow", "(BIGINT, DATE, DATE)"),
        ("fn_report_balance_sheet", "(BIGINT, DATE)"),
        ("fn_report_profit_loss", "(BIGINT, DATE, DATE)"),
        ("fn_report_trial_balance", "(BIGINT, DATE)"),
        ("fn_report_general_ledger", "(BIGINT, DATE, DATE, BIGINT)"),
    ]:
        schema_editor.execute(f"DROP FUNCTION IF EXISTS {fn_name}{signature};")


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0109_remove_journal_journal_org_date_status_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(create_functions, reverse_code=drop_functions),
    ]
