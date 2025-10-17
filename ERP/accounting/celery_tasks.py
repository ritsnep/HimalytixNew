"""
Celery Tasks for Scheduled Operations - Phase 3 Task 4

Scheduled tasks include:
- Period closing
- Auto-posting recurring entries
- Scheduled report generation
- Data cleanup and archival
"""

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from accounting.models import (
    Organization, AccountingPeriod, Journal, JournalLine,
    Account, JournalType, RecurringEntry
)
from accounting.services.report_service import ReportService
from accounting.services.report_export_service import ReportExportService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def close_accounting_period(self, period_id: int) -> dict:
    """
    Close accounting period with validation and journal entry generation.
    
    Args:
        period_id: ID of accounting period to close
        
    Returns:
        dict with status and details
        
    Raises:
        Retries on transaction errors (max 3 attempts)
    """
    try:
        period = AccountingPeriod.objects.get(pk=period_id)
        
        if period.is_closed:
            return {
                'status': 'already_closed',
                'message': f'Period {period.name} already closed',
                'period_id': period_id
            }
        
        with transaction.atomic():
            # Validate all journals in period are posted
            unposted = Journal.objects.filter(
                organization=period.organization,
                date__gte=period.start_date,
                date__lte=period.end_date,
                status__in=['Draft', 'Submitted']
            ).count()
            
            if unposted > 0:
                raise ValueError(f'{unposted} unposted journals in period')
            
            # Calculate totals for closing entries
            closing_entries = _generate_closing_entries(period)
            
            # Create closing journal entries
            closing_journal = Journal.objects.create(
                organization=period.organization,
                journal_type=JournalType.objects.get(code='CJ'),  # Closing Journal
                date=period.end_date,
                reference=f'CLOSING-{period.name}',
                description=f'Period Closing - {period.name}',
                status='Posted'
            )
            
            for entry in closing_entries:
                JournalLine.objects.create(
                    journal=closing_journal,
                    account=entry['account'],
                    debit=entry.get('debit', Decimal('0.00')),
                    credit=entry.get('credit', Decimal('0.00')),
                    description=entry.get('description', 'Closing entry')
                )
            
            # Mark period as closed
            period.is_closed = True
            period.closed_date = timezone.now()
            period.save()
            
            logger.info(f'Period {period.name} closed successfully')
            
            return {
                'status': 'success',
                'period_id': period_id,
                'message': f'Period {period.name} closed',
                'closing_entries': len(closing_entries),
                'closing_journal_id': closing_journal.id
            }
            
    except AccountingPeriod.DoesNotExist:
        logger.error(f'Period {period_id} not found')
        return {'status': 'error', 'message': 'Period not found', 'period_id': period_id}
    except Exception as exc:
        logger.error(f'Error closing period {period_id}: {str(exc)}')
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def post_recurring_entries(self, organization_id: int) -> dict:
    """
    Auto-post recurring journal entries for current period.
    
    Args:
        organization_id: Organization to process
        
    Returns:
        dict with status and number of entries posted
    """
    try:
        organization = Organization.objects.get(pk=organization_id)
        today = timezone.now().date()
        current_period = AccountingPeriod.objects.filter(
            organization=organization,
            start_date__lte=today,
            end_date__gte=today,
            is_closed=False
        ).first()
        
        if not current_period:
            return {
                'status': 'no_period',
                'message': 'No active period found',
                'organization_id': organization_id
            }
        
        with transaction.atomic():
            # Get recurring entries due today
            recurring_entries = RecurringEntry.objects.filter(
                organization=organization,
                is_active=True,
                next_posting_date__lte=today
            )
            
            posted_count = 0
            
            for recurring in recurring_entries:
                # Create journal from template
                journal = Journal.objects.create(
                    organization=organization,
                    journal_type=recurring.journal_type,
                    date=today,
                    reference=f'REC-{recurring.code}-{today.isoformat()}',
                    description=recurring.description,
                    status='Posted'
                )
                
                # Create lines from recurring entry
                for line in recurring.recurringly_lines.all():
                    JournalLine.objects.create(
                        journal=journal,
                        account=line.account,
                        debit=line.debit,
                        credit=line.credit,
                        description=line.description
                    )
                
                # Update next posting date
                next_date = _calculate_next_posting_date(recurring)
                recurring.next_posting_date = next_date
                recurring.save()
                
                posted_count += 1
            
            logger.info(f'Posted {posted_count} recurring entries for {organization.name}')
            
            return {
                'status': 'success',
                'posted_count': posted_count,
                'organization_id': organization_id,
                'message': f'Posted {posted_count} recurring entries'
            }
            
    except Organization.DoesNotExist:
        logger.error(f'Organization {organization_id} not found')
        return {'status': 'error', 'message': 'Organization not found'}
    except Exception as exc:
        logger.error(f'Error posting recurring entries: {str(exc)}')
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True)
def generate_scheduled_reports(self, organization_id: int) -> dict:
    """
    Generate and email scheduled reports.
    
    Args:
        organization_id: Organization to generate reports for
        
    Returns:
        dict with status and reports generated
    """
    try:
        organization = Organization.objects.get(pk=organization_id)
        report_service = ReportService(organization)
        export_service = ReportExportService()
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Generate standard reports
        reports = {
            'general_ledger': report_service.generate_general_ledger(month_start, today),
            'trial_balance': report_service.generate_trial_balance(today),
            'profit_loss': report_service.generate_profit_loss(month_start, today),
            'balance_sheet': report_service.generate_balance_sheet(today),
        }
        
        # Export to Excel
        export_buffer, filename = export_service.export_to_excel(
            'general_ledger',
            reports['general_ledger']
        )
        
        # Email to admin users
        admin_emails = organization.get_admin_emails()
        
        if admin_emails:
            send_scheduled_report_email(
                admin_emails,
                organization.name,
                reports,
                export_buffer,
                filename
            )
        
        logger.info(f'Generated scheduled reports for {organization.name}')
        
        return {
            'status': 'success',
            'organization_id': organization_id,
            'reports_generated': len(reports),
            'emails_sent': len(admin_emails)
        }
        
    except Organization.DoesNotExist:
        logger.error(f'Organization {organization_id} not found')
        return {'status': 'error', 'message': 'Organization not found'}
    except Exception as exc:
        logger.error(f'Error generating scheduled reports: {str(exc)}')
        return {'status': 'error', 'message': str(exc)}


@shared_task
def archive_old_journals(organization_id: int, days_old: int = 365) -> dict:
    """
    Archive and compress old journal entries.
    
    Args:
        organization_id: Organization to archive
        days_old: Age threshold for archival (default 365 days)
        
    Returns:
        dict with status and journals archived
    """
    try:
        organization = Organization.objects.get(pk=organization_id)
        cutoff_date = timezone.now().date() - timedelta(days=days_old)
        
        # Mark old posted journals as archived
        archived_count = Journal.objects.filter(
            organization=organization,
            date__lt=cutoff_date,
            status='Posted',
            archived=False
        ).update(archived=True)
        
        logger.info(f'Archived {archived_count} journals for {organization.name}')
        
        return {
            'status': 'success',
            'organization_id': organization_id,
            'journals_archived': archived_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Organization.DoesNotExist:
        logger.error(f'Organization {organization_id} not found')
        return {'status': 'error', 'message': 'Organization not found'}
    except Exception as exc:
        logger.error(f'Error archiving journals: {str(exc)}')
        return {'status': 'error', 'message': str(exc)}


@shared_task
def cleanup_draft_journals(organization_id: int, days_old: int = 30) -> dict:
    """
    Delete draft journals older than threshold.
    
    Args:
        organization_id: Organization to clean up
        days_old: Age threshold for cleanup (default 30 days)
        
    Returns:
        dict with status and journals deleted
    """
    try:
        organization = Organization.objects.get(pk=organization_id)
        cutoff_date = timezone.now().date() - timedelta(days=days_old)
        
        # Delete old draft journals
        deleted_count, _ = Journal.objects.filter(
            organization=organization,
            date__lt=cutoff_date,
            status='Draft'
        ).delete()
        
        logger.info(f'Deleted {deleted_count} draft journals for {organization.name}')
        
        return {
            'status': 'success',
            'organization_id': organization_id,
            'journals_deleted': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Organization.DoesNotExist:
        logger.error(f'Organization {organization_id} not found')
        return {'status': 'error', 'message': 'Organization not found'}
    except Exception as exc:
        logger.error(f'Error cleaning up journals: {str(exc)}')
        return {'status': 'error', 'message': str(exc)}


@shared_task
def validate_period_entries(organization_id: int, period_id: int) -> dict:
    """
    Validate all entries in accounting period.
    
    Args:
        organization_id: Organization ID
        period_id: Period ID to validate
        
    Returns:
        dict with validation status and any issues found
    """
    try:
        organization = Organization.objects.get(pk=organization_id)
        period = AccountingPeriod.objects.get(pk=period_id, organization=organization)
        
        issues = []
        
        # Check for unbalanced journals
        journals = Journal.objects.filter(
            organization=organization,
            date__gte=period.start_date,
            date__lte=period.end_date
        )
        
        for journal in journals:
            debit_total = sum(
                line.debit or Decimal('0') 
                for line in journal.journalline_set.all()
            )
            credit_total = sum(
                line.credit or Decimal('0')
                for line in journal.journalline_set.all()
            )
            
            if debit_total != credit_total:
                issues.append({
                    'journal_id': journal.id,
                    'reference': journal.reference,
                    'issue': 'Unbalanced (debit != credit)',
                    'debit_total': str(debit_total),
                    'credit_total': str(credit_total)
                })
        
        logger.info(f'Validated period {period.name}: {len(issues)} issues found')
        
        return {
            'status': 'success',
            'organization_id': organization_id,
            'period_id': period_id,
            'total_journals': journals.count(),
            'issues_found': len(issues),
            'issues': issues
        }
        
    except (Organization.DoesNotExist, AccountingPeriod.DoesNotExist) as exc:
        logger.error(f'Validation failed: {str(exc)}')
        return {'status': 'error', 'message': str(exc)}
    except Exception as exc:
        logger.error(f'Error validating period entries: {str(exc)}')
        return {'status': 'error', 'message': str(exc)}


# Helper Functions
# ================

def _generate_closing_entries(period: AccountingPeriod) -> list:
    """
    Generate closing journal entries for period.
    
    Args:
        period: Accounting period to close
        
    Returns:
        list of closing entry dicts
    """
    entries = []
    organization = period.organization
    
    # Get all revenue and expense accounts with balances
    accounts = Account.objects.filter(
        organization=organization,
        account_type__in=['Revenue', 'Expense']
    )
    
    for account in accounts:
        balance = _calculate_account_balance(
            account,
            period.start_date,
            period.end_date
        )
        
        if balance != Decimal('0.00'):
            # Determine debit/credit for closing entry
            if account.account_type == 'Revenue':
                entries.append({
                    'account': account,
                    'debit': balance,
                    'credit': Decimal('0.00'),
                    'description': f'Close revenue: {account.name}'
                })
            else:  # Expense
                entries.append({
                    'account': account,
                    'debit': Decimal('0.00'),
                    'credit': balance,
                    'description': f'Close expense: {account.name}'
                })
    
    return entries


def _calculate_account_balance(
    account: Account,
    start_date: datetime,
    end_date: datetime
) -> Decimal:
    """
    Calculate account balance for period.
    
    Args:
        account: Account to calculate balance for
        start_date: Period start date
        end_date: Period end date
        
    Returns:
        Decimal balance
    """
    lines = JournalLine.objects.filter(
        account=account,
        journal__date__gte=start_date,
        journal__date__lte=end_date,
        journal__status='Posted'
    )
    
    debit_total = sum(
        (line.debit or Decimal('0')) for line in lines
    )
    credit_total = sum(
        (line.credit or Decimal('0')) for line in lines
    )
    
    if account.account_type in ['Asset', 'Expense']:
        return debit_total - credit_total
    else:  # Liability, Revenue, Equity
        return credit_total - debit_total


def _calculate_next_posting_date(recurring_entry) -> datetime:
    """
    Calculate next posting date based on frequency.
    
    Args:
        recurring_entry: RecurringEntry instance
        
    Returns:
        datetime for next posting
    """
    current = recurring_entry.next_posting_date
    frequency = recurring_entry.frequency  # 'Daily', 'Weekly', 'Monthly', 'Quarterly', 'Yearly'
    
    if frequency == 'Daily':
        return current + timedelta(days=1)
    elif frequency == 'Weekly':
        return current + timedelta(weeks=1)
    elif frequency == 'Monthly':
        if current.month == 12:
            return current.replace(year=current.year + 1, month=1)
        else:
            return current.replace(month=current.month + 1)
    elif frequency == 'Quarterly':
        new_month = current.month + 3
        if new_month > 12:
            return current.replace(year=current.year + 1, month=new_month - 12)
        else:
            return current.replace(month=new_month)
    elif frequency == 'Yearly':
        return current.replace(year=current.year + 1)
    else:
        return current + timedelta(days=1)


def send_scheduled_report_email(
    recipients: list,
    organization_name: str,
    reports: dict,
    export_buffer,
    filename: str
) -> bool:
    """
    Send scheduled report via email.
    
    Args:
        recipients: List of email addresses
        organization_name: Organization name
        reports: Dictionary of reports
        export_buffer: File buffer for attachment
        filename: Export filename
        
    Returns:
        bool indicating success
    """
    try:
        context = {
            'organization_name': organization_name,
            'generated_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reports': reports
        }
        
        email_body = render_to_string(
            'accounting/emails/scheduled_report.html',
            context
        )
        
        send_mail(
            subject=f'Scheduled Report - {organization_name}',
            message='See HTML version',
            html_message=email_body,
            from_email='noreply@erp.local',
            recipient_list=recipients,
            attachments=[(filename, export_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]
        )
        
        logger.info(f'Sent scheduled report to {len(recipients)} recipients')
        return True
        
    except Exception as exc:
        logger.error(f'Error sending report email: {str(exc)}')
        return False
