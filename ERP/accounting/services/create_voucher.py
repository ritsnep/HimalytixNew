from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ..models import VoucherModeConfig, Journal, ChartOfAccount, JournalLine, AccountingPeriod
from accounting.config.settings import journal_entry_settings
import logging

logger = logging.getLogger(__name__)


def create_voucher(user, config_id: int, header_data: dict, lines_data: list, udf_header=None, udf_lines=None):
    """
    Create a voucher (journal) and its lines.
    """
    try:
        config = VoucherModeConfig.objects.get(pk=config_id)
    except VoucherModeConfig.DoesNotExist:
        logger.error(
            "VoucherModeConfig with ID %s not found for user %s, organization %s",
            config_id, getattr(user, 'pk', 'N/A'), getattr(user.organization, 'pk', 'N/A'),
            extra={'config_id': config_id, 'user_id': getattr(user, 'pk', 'N/A'),
                   'organization_id': getattr(user.organization, 'pk', 'N/A')}
        )
        raise ValidationError(f"Voucher configuration with ID {config_id} not found.")

    journal_date = header_data.get('journal_date')
    if isinstance(journal_date, str):
        from datetime import datetime
        try:
            journal_date = datetime.strptime(journal_date, '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(
                "Invalid journal date format: %s for user %s, organization %s",
                journal_date, getattr(user, 'pk', 'N/A'), getattr(getattr(user, 'organization', None), 'pk', 'N/A'),
                extra={'journal_date': journal_date, 'user_id': getattr(user, 'pk', 'N/A'),
                       'organization_id': getattr(getattr(user, 'organization', None), 'pk', 'N/A'), 'error': str(e)}
            )
            raise ValidationError(f"Invalid journal date format: {journal_date}. Expected YYYY-MM-DD.")

    # Default journal date to today if missing
    if journal_date is None:
        journal_date = timezone.now().date()
    # Ensure header_data carries the resolved journal_date for Journal()
    header_data = dict(header_data or {})
    header_data.setdefault('journal_date', journal_date)

    # Prefer the user's organization; fall back to the voucher config's organization
    organization = getattr(user, 'organization', None)
    if organization is None:
        try:
            config_org = VoucherModeConfig.objects.only('organization').get(pk=config_id).organization
            organization = config_org
        except VoucherModeConfig.DoesNotExist:
            organization = None
    if organization is None:
        logger.error(
            "Missing organization for user %s and voucher config %s. Cannot determine accounting period.",
            getattr(user, 'pk', 'N/A'), config_id,
            extra={'user_id': getattr(user, 'pk', 'N/A'), 'config_id': config_id}
        )
        raise ValidationError("Missing organization. Cannot determine accounting period.")

    period = AccountingPeriod.objects.filter(
        organization=organization,
        start_date__lte=journal_date,
        end_date__gte=journal_date,
        status='open'
    ).first()

    if not period:
        period = AccountingPeriod.get_current_period(organization)
        if not period:
            logger.error(
                "No open accounting period found for date %s for user %s, organization %s",
                journal_date, getattr(user, 'pk', 'N/A'), getattr(organization, 'pk', 'N/A'),
                extra={'journal_date': journal_date, 'user_id': getattr(user, 'pk', 'N/A'),
                       'organization_id': getattr(organization, 'pk', 'N/A')}
            )
            raise ValidationError("No open accounting period found for the given date.")

    currency_code = header_data.pop('currency_code', 'USD')
    exchange_rate = header_data.pop('exchange_rate', Decimal('1.0'))

    journal = Journal(
        organization=organization,
        created_by=user,
        journal_type=config.journal_type,
        period=period,
        currency_code=currency_code,
        exchange_rate=exchange_rate,
        **header_data
    )
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    lines = []
    for idx, line in enumerate(lines_data, start=1):
        try:
            account = ChartOfAccount.objects.get(pk=line['account'])
        except ChartOfAccount.DoesNotExist:
            logger.error(
                "Account with ID %s not found for journal line %s, user %s, organization %s",
                line['account'], idx, getattr(user, 'pk', 'N/A'), getattr(user.organization, 'pk', 'N/A'),
                extra={'account_id': line['account'], 'line_index': idx, 'user_id': getattr(user, 'pk', 'N/A'),
                       'organization_id': getattr(user.organization, 'pk', 'N/A')}
            )
            raise ValidationError(f"Account with ID {line['account']} not found for line {idx}.")

        debit = Decimal(line.get('debit_amount', 0) or 0)
        credit = Decimal(line.get('credit_amount', 0) or 0)
        if not journal_entry_settings.allow_negative_entries and (debit < 0 or credit < 0):
            logger.error(
                "Negative amounts not allowed for journal line %s (debit: %s, credit: %s), user %s, organization %s",
                idx, debit, credit, getattr(user, 'pk', 'N/A'), getattr(user.organization, 'pk', 'N/A'),
                extra={'line_index': idx, 'debit_amount': debit, 'credit_amount': credit,
                       'user_id': getattr(user, 'pk', 'N/A'),
                       'organization_id': getattr(user.organization, 'pk', 'N/A')}
            )
            raise ValidationError("Negative amounts are not allowed.")
        total_debit += debit
        total_credit += credit
        line_udf = {}
        if udf_lines and len(udf_lines) > idx - 1:
            line_udf = udf_lines[idx - 1]
        lines.append(JournalLine(
            journal=journal,
            line_number=idx,
            account=account,
            description=line.get('description', ''),
            debit_amount=debit,
            credit_amount=credit,
            department_id=line.get('department'),
            project_id=line.get('project'),
            cost_center_id=line.get('cost_center'),
            tax_code_id=line.get('tax_code'),
            memo=line.get('memo', ''),
            udf_data=line_udf,
        ))

    if total_debit != total_credit:
        logger.error(
            "Journal not balanced during creation for user %s, organization %s. Total Debit: %s, Total Credit: %s",
            getattr(user, 'pk', 'N/A'), getattr(user.organization, 'pk', 'N/A'), total_debit, total_credit,
            extra={'user_id': getattr(user, 'pk', 'N/A'),
                   'organization_id': getattr(user.organization, 'pk', 'N/A'), 'total_debit': total_debit,
                   'total_credit': total_credit}
        )
        raise ValidationError('Debit and Credit totals must match')

    journal.total_debit = total_debit
    journal.total_credit = total_credit

    with transaction.atomic():
        journal.save()
        JournalLine.objects.bulk_create(lines)
        logger.info(
            "Journal %s and its lines created successfully for user %s, organization %s",
            journal.journal_number, getattr(user, 'pk', 'N/A'), getattr(user.organization, 'pk', 'N/A'),
            extra={'journal_id': journal.pk, 'journal_number': journal.journal_number,
                   'user_id': getattr(user, 'pk', 'N/A'),
                   'organization_id': getattr(user.organization, 'pk', 'N/A')}
        )

    return journal
