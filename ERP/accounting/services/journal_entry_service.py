from decimal import Decimal
from typing import Any, Dict, List

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounting.models import Attachment, Journal, JournalLine, JournalType, VoucherModeConfig
from accounting.services.posting_service import PostingService
from accounting.utils.audit import log_audit_event
from usermanagement.models import CustomUser, Organization
from usermanagement.utils import PermissionUtils

class JournalEntryService:
    """
    A service to handle the business logic for journal entries.
    """

    def __init__(self, user: CustomUser, organization: Organization):
        self.user = user
        self.organization = organization

    def create_journal_entry(self, journal_data: Dict[str, Any], lines_data: List[Dict[str, Any]], attachments: List[Any] = None) -> Journal:
        """
        Creates a new journal entry and its lines.
        """
        with transaction.atomic():
            journal_type = journal_data.get('journal_type')
            config = self._get_voucher_mode_config(journal_type)

            if not self._has_permission('add'):
                raise PermissionError("You do not have permission to create journal entries.")

            # Apply defaults from config
            if config:
                journal_data.setdefault('currency_code', config.default_currency)
                journal_data.setdefault('description', config.default_narration_template)

            errors = self._validate_journal_entry(journal_data, lines_data, config)
            if errors:
                raise ValueError(errors)

            journal = Journal.objects.create(
                organization=self.organization,
                created_by=self.user,
                **journal_data
            )

            for line_data in lines_data:
                JournalLine.objects.create(journal=journal, **line_data)

            journal.update_totals()
            journal.save()

            log_audit_event(self.user, journal, 'create', {'journal_data': journal_data, 'lines_data': lines_data})

            if attachments:
                self.add_attachments(journal, attachments)

            return journal

    def update_journal_entry(self, journal: Journal, journal_data: Dict[str, Any], lines_data: List[Dict[str, Any]], attachments: List[Any] = None) -> Journal:
        """
        Updates an existing journal entry and its lines.
        """
        with transaction.atomic():
            journal_type = journal_data.get('journal_type', journal.journal_type)
            config = self._get_voucher_mode_config(journal_type)

            if not self._has_permission('change'):
                raise PermissionError("You do not have permission to update journal entries.")

            if journal.status == 'rejected':
                if not self._has_permission('modify'):
                    raise PermissionError("You do not have permission to modify rejected journals.")
                journal.status = 'draft'
                journal.is_locked = False
            elif journal.status != 'draft':
                raise ValueError("Only draft journals can be updated.")

            errors = self._validate_journal_entry(journal_data, lines_data, config)
            if errors:
                raise ValueError(errors)

            for key, value in journal_data.items():
                setattr(journal, key, value)
            
            journal.updated_by = self.user
            journal.save()

            journal.lines.all().delete()
            for line_data in lines_data:
                JournalLine.objects.create(journal=journal, **line_data)

            journal.update_totals()
            journal.save()

            log_audit_event(self.user, journal, 'update', {'journal_data': journal_data, 'lines_data': lines_data})

            if attachments:
                self.add_attachments(journal, attachments)

            return journal

    def add_attachments(self, journal: Journal, attachments: List[Any]):
        """
        Adds attachments to a journal entry.
        """
        for attachment_file in attachments:
            Attachment.objects.create(
                journal=journal,
                file=attachment_file,
                uploaded_by=self.user
            )

    def _get_voucher_mode_config(self, journal_type: JournalType) -> VoucherModeConfig:
        """
        Retrieves the VoucherModeConfig for a given journal type.
        """
        if not journal_type:
            return None
        return VoucherModeConfig.objects.filter(
            organization=self.organization,
            journal_type=journal_type
        ).first()

    def _validate_journal_entry(self, journal_data: Dict[str, Any], lines_data: List[Dict[str, Any]], config: VoucherModeConfig) -> List[str]:
        """
        Validates a journal entry and its lines.
        """
        errors = []
        errors.extend(self._validate_journal_header(journal_data))
        errors.extend(self._validate_journal_lines(lines_data))
        errors.extend(self._validate_debits_and_credits(lines_data))

        if config:
            # Add validation based on VoucherModeConfig rules
            for rule in config.validation_rules:
                # This is a simplified example. A real implementation would need a more robust rule engine.
                if rule.get('field') == 'description' and rule.get('required') and not journal_data.get('description'):
                    errors.append("Description is required by voucher configuration.")

        return errors

    def _validate_journal_header(self, journal_data: Dict[str, Any]) -> List[str]:
        """
        Validates the journal header.
        """
        header_errors = []
        if not journal_data.get('journal_date'):
            header_errors.append("Journal date is required.")
        if not journal_data.get('description'):
            header_errors.append("Journal description is required.")
        return header_errors

    def _validate_journal_lines(self, lines_data: List[Dict[str, Any]]) -> List[str]:
        """
        Validates individual journal lines.
        """
        line_errors = []
        if not lines_data:
            line_errors.append("At least one journal line is required.")
            return line_errors

        for i, line_data in enumerate(lines_data):
            line_num = i + 1
            if not line_data.get('account'):
                line_errors.append(f"Line {line_num}: Account is required.")
            
            debit = Decimal(line_data.get('debit_amount', 0) or 0)
            credit = Decimal(line_data.get('credit_amount', 0) or 0)

            if debit < 0 or credit < 0:
                line_errors.append(f"Line {line_num}: Debit and credit amounts must be positive.")
            if debit > 0 and credit > 0:
                line_errors.append(f"Line {line_num}: Both debit and credit cannot be set on the same line.")

        return line_errors

    def _validate_debits_and_credits(self, lines_data: List[Dict[str, Any]]) -> List[str]:
        """
        Validates that the total debits equal the total credits.
        """
        balance_errors = []
        total_debits = sum(Decimal(line.get('debit_amount', 0) or 0) for line in lines_data)
        total_credits = sum(Decimal(line.get('credit_amount', 0) or 0) for line in lines_data)

        if total_debits != total_credits:
            balance_errors.append(f"Debits ({total_debits}) and credits ({total_credits}) do not balance.")
        
        return balance_errors

    def _has_permission(self, action: str) -> bool:
        """Checks if the user has the required permission."""
        # Map custom actions to Django permission codenames
        perm_map = {
            'add': 'add_journal',
            'change': 'change_journal',
            'delete': 'delete_journal',
            'view': 'view_journal',
            'modify': 'modify_journal',
            'submit_journal': 'can_submit_for_approval',
            'approve_journal': 'can_approve_journal',
            'reject_journal': 'can_reject_journal',
            'post_journal': 'can_post_journal',
        }
        codename = perm_map.get(action)
        if codename and self.user.has_perm(f'accounting.{codename}'):
            return True
        return PermissionUtils.has_permission(
            self.user,
            self.organization,
            'accounting',
            'journal',
            action
        )

    def submit(self, journal: Journal):
        """Submits a journal for approval."""
        if not self._has_permission('submit_journal'):
            raise PermissionError("You do not have permission to submit journal entries.")
        if journal.status != 'draft':
            raise ValueError("Only draft journals can be submitted.")
        journal.status = 'awaiting_approval'
        journal.updated_by = self.user
        journal.save(update_fields=['status', 'updated_by', 'updated_at'])
        log_audit_event(self.user, journal, 'submit')

    def approve(self, journal: Journal):
        """Approves a journal entry."""
        if not self._has_permission('approve_journal'):
            raise PermissionError("You do not have permission to approve journal entries.")
        if journal.status != 'awaiting_approval':
            raise ValueError("Only journals awaiting approval can be approved.")
        journal.status = 'approved'
        journal.updated_by = self.user
        journal.save(update_fields=['status', 'updated_by', 'updated_at'])
        log_audit_event(self.user, journal, 'approve')

    def reject(self, journal: Journal):
        """Rejects a journal entry."""
        if not self._has_permission('reject_journal'):
            raise PermissionError("You do not have permission to reject journal entries.")
        if journal.status != 'awaiting_approval':
            raise ValueError("Only journals awaiting approval can be rejected.")
        journal.status = 'rejected'
        journal.is_locked = False
        journal.updated_by = self.user
        journal.save(update_fields=['status', 'is_locked', 'updated_by', 'updated_at'])
        log_audit_event(self.user, journal, 'reject')

    def post(self, journal: Journal) -> Journal:
        """Posts a journal to the general ledger."""
        if not self._has_permission('post_journal'):
            raise PermissionError("You do not have permission to post journal entries.")

        if journal.status not in ('approved', 'draft'):
            raise ValueError("Only approved journals can be posted.")

        if journal.status == 'draft' and getattr(journal.journal_type, 'requires_approval', False):
            raise ValueError("This journal type requires approval before posting.")

        posting_service = PostingService(self.user)
        try:
            posted_journal = posting_service.post(journal)
        except ValidationError as exc:
            message = "; ".join(exc.messages)
            raise ValueError(message) from exc
        except PermissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        journal.refresh_from_db()
        return posted_journal
