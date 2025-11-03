from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from ..models import Journal, JournalType, GeneralLedger
import logging

logger = logging.getLogger(__name__)


class JournalError(Exception):
    """Base exception for journal-related errors."""
    pass


class JournalValidationError(JournalError, ValidationError):
    """Specific validation error for journal entries."""
    pass


class JournalPostingError(JournalError):
    """Error during journal posting process."""
    pass


def post_journal(journal: Journal, user=None) -> Journal:
    """Post a draft journal and create GL entries.

    Accepts an optional user to record as the poster.
    """
    logger.info(
        "post_journal start journal_id=%s",
        journal.pk,
        extra={'journal_id': journal.pk}
    )
    if journal.status != "draft":
        logger.warning(
            "Attempted to post non-draft journal journal_id=%s, status=%s",
            journal.pk, journal.status,
            extra={'journal_id': journal.pk, 'status': journal.status}
        )
        raise JournalPostingError("Only draft journals can be posted")
    line_totals = journal.lines.aggregate(
        debit_sum=Sum("debit_amount"),
        credit_sum=Sum("credit_amount"),
    )
    debit_sum = line_totals.get("debit_sum") or Decimal("0")
    credit_sum = line_totals.get("credit_sum") or Decimal("0")

    if debit_sum != credit_sum or journal.total_debit != journal.total_credit:
        logger.error(
            "Journal not balanced journal_id=%s, total_debit=%s, total_credit=%s, line_debit_sum=%s, line_credit_sum=%s",
            journal.pk, journal.total_debit, journal.total_credit, debit_sum, credit_sum,
            extra={'journal_id': journal.pk, 'total_debit': journal.total_debit,
                   'total_credit': journal.total_credit, 'line_debit_sum': debit_sum, 'line_credit_sum': credit_sum}
        )
        raise JournalValidationError("Journal not balanced")

    if debit_sum != journal.total_debit or credit_sum != journal.total_credit:
        logger.error(
            "Header totals do not match line totals for journal_id=%s",
            journal.pk,
            extra={'journal_id': journal.pk}
        )
        raise JournalValidationError("Header totals do not match line totals")
    with transaction.atomic():
        if journal.period.status != "open":
            logger.warning(
                "Attempted to post journal to closed period journal_id=%s, period_id=%s, period_status=%s",
                journal.pk, journal.period.pk, journal.period.status,
                extra={'journal_id': journal.pk, 'period_id': journal.period.pk,
                       'period_status': journal.period.status}
            )
            raise JournalPostingError("Accounting period is closed")

        jt = JournalType.objects.select_for_update().get(pk=journal.journal_type.pk)
        if not journal.journal_number:
            journal.journal_number = jt.get_next_journal_number(journal.period)

        journal.save()
        logger.info(
            "Journal %s saved before line processing",
            journal.journal_number,
            extra={'journal_id': journal.pk, 'journal_number': journal.journal_number}
        )

        for line in journal.lines.select_related("account").all():
            line.functional_debit_amount = line.debit_amount * journal.exchange_rate
            line.functional_credit_amount = line.credit_amount * journal.exchange_rate
            line.save()
            logger.debug(
                "Journal line %s functional amounts calculated and saved",
                line.pk,
                extra={'journal_line_id': line.pk, 'functional_debit': line.functional_debit_amount,
                       'functional_credit': line.functional_credit_amount}
            )

            account = line.account
            account.current_balance = account.current_balance + line.debit_amount - line.credit_amount
            account.save(update_fields=["current_balance"])
            logger.debug(
                "Account %s balance updated to %s",
                account.account_code, account.current_balance,
                extra={'account_id': account.pk, 'account_code': account.account_code,
                       'new_balance': account.current_balance}
            )

            GeneralLedger.objects.create(
                organization_id=journal.organization,
                account=account,
                journal=journal,
                journal_line=line,
                period=journal.period,
                transaction_date=journal.journal_date,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                balance_after=account.current_balance,
                currency_code=journal.currency_code,
                exchange_rate=journal.exchange_rate,
                functional_debit_amount=line.functional_debit_amount,
                functional_credit_amount=line.functional_credit_amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                description=line.description,
            )
            logger.info(
                "GL entry created for journal line %s",
                line.pk,
                extra={'journal_line_id': line.pk, 'gl_account': account.account_code}
            )

        journal.status = "posted"
        journal.posted_at = timezone.now()
        if hasattr(journal, "posted_by") and user is not None:
            journal.posted_by = user
        journal.save()
        logger.info(
            "Journal %s successfully posted",
            journal.journal_number,
            extra={'journal_id': journal.pk, 'journal_number': journal.journal_number}
        )
    return journal
