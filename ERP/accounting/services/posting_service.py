from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from accounting.models import Journal, JournalLine, AccountingPeriod, GeneralLedger, JournalType, ChartOfAccount
from usermanagement.models import CustomUser, Organization
from accounting.utils.audit import log_audit_event, get_changed_data
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

class PostingService:
    """
    Service layer for handling Journal posting, validation, and reversal.
    Encapsulates business logic and ensures transactional integrity.
    """

    # Error Messages
    ERR_PERIOD_CLOSED = "Posting date falls into a closed accounting period."
    ERR_IMBALANCED_JOURNAL = "Journal is out of balance. Total debits must equal total credits."
    ERR_PERMISSION_DENIED = "You do not have permission to perform this action."
    ERR_JOURNAL_LOCKED = "Journal is locked and cannot be modified or reversed directly."
    ERR_INVALID_STATUS_TRANSITION = "Invalid journal status transition from {current_status} to {new_status}."
    ERR_REVERSAL_NOT_ALLOWED = "Only 'posted' journals can be reversed."
    ERR_REVERSAL_ALREADY_EXISTS = "This journal has already been reversed."
    ERR_SCHEMA_VERSION_MISMATCH = "Journal schema version mismatch. Cannot post with an outdated schema."
    ERR_VOUCHER_TYPE_VALIDATION = "Voucher type specific validation failed: {reason}"
    ERR_ACCOUNT_TYPE_MISMATCH = "Account {account_code} ({account_name}) cannot be used with this voucher type."
    ERR_MISSING_DIMENSION = "Required dimension {dimension} is missing for account {account_code}."
    ERR_INVALID_AMOUNT_PRECISION = "Amount precision for {field} is invalid."
    ERR_DUPLICATE_SUBMISSION = "Duplicate journal submission detected."
    ERR_PERIOD_REOPEN_DENIED = "You do not have permission to reopen accounting periods."
    ERR_PERIOD_NOT_CLOSED = "Period is not closed and cannot be reopened."

    # Allowed Status Transitions
    ALLOWED_TRANSITIONS = {
        'draft': ['awaiting_approval', 'posted'],
        'awaiting_approval': ['approved', 'rejected', 'draft'],
        'approved': ['posted', 'rejected', 'draft'],
        'posted': ['reversed'],
        'rejected': ['draft'],
        'reversed': [], # Reversed journals are terminal
    }

    # Permissions required for each transition
    PERMISSION_MAP = {
        'awaiting_approval': 'accounting.can_submit_for_approval',
        'approved': 'accounting.can_approve_journal',
        'posted': 'accounting.can_post_journal',
        'reversed': 'accounting.can_reverse_journal',
        'rejected': 'accounting.can_reject_journal',
        'draft': 'accounting.can_edit_journal', # For moving back to draft
    }

    def __init__(self, user: CustomUser):
        self.user = user
        self.organization = user.organization # Assuming user has an organization

    def _check_permission(self, permission_codename: str):
        """Checks if the current user has the specified permission."""
        if not self.user.has_perm(permission_codename, obj=self.organization):
            raise PermissionDenied(self.ERR_PERMISSION_DENIED)

    def _validate_status_transition(self, journal: Journal, new_status: str):
        """Validates if the status transition is allowed."""
        if new_status not in self.ALLOWED_TRANSITIONS.get(journal.status, []):
            raise ValidationError(self.ERR_INVALID_STATUS_TRANSITION.format(
                current_status=journal.status, new_status=new_status
            ))
        
        # Check specific permissions for the new status
        permission = self.PERMISSION_MAP.get(new_status)
        if permission:
            self._check_permission(permission)

    def _validate_period_control(self, journal_date: timezone.datetime.date, organization: Organization):
        """Ensures posting is not done to a closed period."""
        if not AccountingPeriod.is_date_in_open_period(organization, journal_date):
            raise ValidationError(self.ERR_PERIOD_CLOSED)

    def _validate_double_entry_invariant(self, journal: Journal):
        """Ensures total debits equal total credits."""
        # Recalculate totals from lines to ensure data integrity
        journal.update_totals()
        if journal.imbalance != Decimal('0.0000'):
            raise ValidationError(self.ERR_IMBALANCED_JOURNAL)

    def _validate_voucher_type_rules(self, journal: Journal):
        """
        Applies voucher-type specific validation rules.
        This would be extended with a schema-driven approach.
        """
        # Example: Contra voucher must only have cash/bank accounts
        if journal.journal_type.code == 'CONTRA':
            for line in journal.lines.all():
                if not line.account.is_bank_account:
                    raise ValidationError(
                        self.ERR_VOUCHER_TYPE_VALIDATION.format(reason="Contra vouchers must only use bank accounts.")
                    )
        # Example: Debit/Credit Note must be linked to a source invoice/GRN
        if journal.journal_type.code in ['DEBIT_NOTE', 'CREDIT_NOTE']:
            if not journal.reference: # Assuming reference stores the link
                raise ValidationError(
                    self.ERR_VOUCHER_TYPE_VALIDATION.format(reason="Debit/Credit Notes require a source reference.")
                )
        
        # Prevent cross-organization ledgers (already handled by FKs, but good to re-iterate)
        for line in journal.lines.all():
            if line.account.organization != journal.organization:
                raise ValidationError(
                    self.ERR_VOUCHER_TYPE_VALIDATION.format(reason="Journal lines cannot use accounts from other organizations.")
                )
        
        # Dimension requirements based on ChartOfAccount settings
        for line in journal.lines.all():
            if line.account.require_cost_center and not line.cost_center:
                raise ValidationError(self="ERR_MISSING_DIMENSION".format(dimension="Cost Center", account_code=line.account.account_code))
            if line.account.require_project and not line.project:
                raise ValidationError(self="ERR_MISSING_DIMENSION".format(dimension="Project", account_code=line.account.account_code))
            if line.account.require_department and not line.department:
                raise ValidationError(self="ERR_MISSING_DIMENSION".format(dimension="Department", account_code=line.account.account_code))


    def _validate_chart_of_accounts_typing(self, journal: Journal):
        """
        Prohibits posting income/expense lines to balance-sheet-only vouchers (and vice-versa).
        This assumes `JournalType` or `VoucherModeConfig` defines allowed account natures.
        """
        # This is a placeholder. Actual implementation would depend on how voucher types
        # are configured to restrict account types.
        # For now, a simple example:
        allowed_natures = {
            'SALES_INVOICE': ['asset', 'income', 'liability'],
            'PURCHASE_INVOICE': ['asset', 'expense', 'liability'],
            'PAYMENT': ['asset', 'liability'],
            'RECEIPT': ['asset', 'income'],
            'JOURNAL_VOUCHER': ['asset', 'liability', 'equity', 'income', 'expense'], # All allowed for general journal
        }.get(journal.journal_type.code, [])

        if not allowed_natures: # If no specific rules, allow all
            return

        for line in journal.lines.all():
            if line.account.account_type.nature not in allowed_natures:
                raise ValidationError(
                    self.ERR_ACCOUNT_TYPE_MISMATCH.format(
                        account_code=line.account.account_code,
                        account_name=line.account.account_name
                    )
                )

    def _validate_amounts_and_rounding(self, journal: Journal):
        """
        Defines precision, rounding mode (e.g., ROUND_HALF_UP) and where applied (line vs total).
        Documents currency formatting.
        """
        # Assuming a global precision for now, can be made currency-specific
        DECIMAL_PLACES = 4
        ROUNDING_MODE = ROUND_HALF_UP

        for line in journal.lines.all():
            if line.debit_amount is not None:
                rounded_debit = line.debit_amount.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)
                if rounded_debit != line.debit_amount:
                    raise ValidationError(self.ERR_INVALID_AMOUNT_PRECISION.format(field="debit_amount"))
                line.debit_amount = rounded_debit # Ensure amounts are rounded
            
            if line.credit_amount is not None:
                rounded_credit = line.credit_amount.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)
                if rounded_credit != line.credit_amount:
                    raise ValidationError(self.ERR_INVALID_AMOUNT_PRECISION.format(field="credit_amount"))
                line.credit_amount = rounded_credit # Ensure amounts are rounded
            
            # Functional amounts also need rounding
            if line.functional_debit_amount is not None:
                line.functional_debit_amount = line.functional_debit_amount.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)
            if line.functional_credit_amount is not None:
                line.functional_credit_amount = line.functional_credit_amount.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)

        # Total debits/credits should also adhere to precision
        journal.total_debit = journal.total_debit.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)
        journal.total_credit = journal.total_credit.quantize(Decimal('1.' + '0'*DECIMAL_PLACES), rounding=ROUNDING_MODE)

    def validate(self, journal: Journal):
        """
        Performs all server-side validations on a journal before posting.
        Raises ValidationError or PermissionDenied on failure.
        """
        logger.info(f"Validating journal {journal.journal_number} (ID: {journal.pk})")
        
        # 1. Period Controls
        self._validate_period_control(journal.journal_date, journal.organization)

        # 2. Double-entry Invariant
        self._validate_double_entry_invariant(journal)

        # 3. Voucher-type specific rules
        self._validate_voucher_type_rules(journal)

        # 4. Chart of Accounts typing
        self._validate_chart_of_accounts_typing(journal)

        # 5. Amounts & Rounding
        self._validate_amounts_and_rounding(journal)

        # 6. Schema/config versioning (placeholder for future implementation)
        # if journal.schema_version != current_schema_version:
        #     raise ValidationError(self.ERR_SCHEMA_VERSION_MISMATCH)

        logger.info(f"Journal {journal.journal_number} (ID: {journal.pk}) validated successfully.")

    @transaction.atomic
    def post(self, journal: Journal):
        """
        Posts a validated journal entry to the General Ledger.
        Ensures atomicity: all GL entries and balance updates happen in one transaction.
        """
        self._check_permission(self.PERMISSION_MAP['posted'])
        self._validate_status_transition(journal, 'posted')
        self.validate(journal) # Run full validation before posting

        if journal.status == 'posted':
            raise ValidationError("Journal is already posted.")
        
        if journal.is_locked:
            raise ValidationError(self.ERR_JOURNAL_LOCKED)

        logger.info(f"Posting journal {journal.journal_number} (ID: {journal.pk})")

        # Generate journal number if not already present (e.g., for direct posting from draft)
        if not journal.journal_number:
            journal.journal_number = journal.journal_type.get_next_journal_number(period=journal.period)
            journal.save(update_fields=['journal_number']) # Save to get the number before lines

        # Lock the journal and its lines
        journal.is_locked = True
        journal.status = 'posted'
        journal.posted_at = timezone.now()
        journal.posted_by = self.user
        journal.save(update_fields=['is_locked', 'status', 'posted_at', 'posted_by', 'updated_at', 'updated_by'])

        # Create General Ledger entries and update account balances
        for line in journal.lines.all():
            # Update account current balance with row-level lock
            account = ChartOfAccount.objects.select_for_update().get(pk=line.account.pk)
            
            if line.debit_amount > 0:
                account.current_balance += line.debit_amount
            elif line.credit_amount > 0:
                account.current_balance -= line.credit_amount
            account.save(update_fields=['current_balance'])

            GeneralLedger.objects.create(
                organization_id=journal.organization,
                account=line.account,
                journal=journal,
                journal_line=line,
                period=journal.period,
                transaction_date=journal.journal_date,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                balance_after=account.current_balance, # Balance after this transaction
                currency_code=line.currency_code,
                exchange_rate=line.exchange_rate,
                functional_debit_amount=line.functional_debit_amount,
                functional_credit_amount=line.functional_credit_amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                description=line.description,
                source_module='Accounting', # Or more specific module
                source_reference=journal.journal_number,
                created_by=self.user,
            )
        
        log_audit_event(self.user, journal, 'posted', details=f"Journal {journal.journal_number} posted.")
        logger.info(f"Journal {journal.journal_number} (ID: {journal.pk}) posted successfully.")
        return journal

    @transaction.atomic
    def reverse(self, original_journal: Journal):
        """
        Reverses a posted journal entry by creating an equal-and-opposite voucher.
        The original journal is marked as 'reversed' and locked.
        """
        self._check_permission(self.PERMISSION_MAP['reversed'])
        self._validate_status_transition(original_journal, 'reversed')

        if original_journal.status != 'posted':
            raise ValidationError(self.ERR_REVERSAL_NOT_ALLOWED)
        
        if original_journal.is_reversal:
            raise ValidationError(self.ERR_REVERSAL_ALREADY_EXISTS)

        logger.info(f"Reversing journal {original_journal.journal_number} (ID: {original_journal.pk})")

        # Create a new journal for the reversal
        reversal_journal = Journal.objects.create(
            organization=original_journal.organization,
            journal_type=original_journal.journal_type, # Use same journal type
            period=original_journal.period,
            journal_date=timezone.now().date(), # Reversal date is today
            reference=f"REV:{original_journal.journal_number}",
            description=f"Reversal of {original_journal.journal_number}: {original_journal.description or ''}",
            currency_code=original_journal.currency_code,
            exchange_rate=original_journal.exchange_rate,
            total_debit=original_journal.total_credit, # Swap debits and credits
            total_credit=original_journal.total_debit,
            status='posted', # Reversal is immediately posted
            posted_at=timezone.now(),
            posted_by=self.user,
            created_by=self.user,
            is_locked=True,
            is_reversal=True,
        )
        # Generate journal number for the reversal
        reversal_journal.journal_number = reversal_journal.journal_type.get_next_journal_number(period=reversal_journal.period)
        reversal_journal.save(update_fields=['journal_number'])

        # Create reversed journal lines
        for original_line in original_journal.lines.all():
            JournalLine.objects.create(
                journal=reversal_journal,
                line_number=original_line.line_number,
                account=original_line.account,
                description=f"Reversal: {original_line.description or ''}",
                debit_amount=original_line.credit_amount, # Swap debit/credit
                credit_amount=original_line.debit_amount,
                currency_code=original_line.currency_code,
                exchange_rate=original_line.exchange_rate,
                functional_debit_amount=original_line.functional_credit_amount,
                functional_credit_amount=original_line.functional_debit_amount,
                department=original_line.department,
                project=original_line.project,
                cost_center=original_line.cost_center,
                tax_code=original_line.tax_code,
                tax_rate=original_line.tax_rate,
                tax_amount=original_line.tax_amount,
                memo=f"Reversal of line {original_line.line_number} from {original_journal.journal_number}",
                created_by=self.user,
            )
        
        # Update totals for the reversal journal
        reversal_journal.update_totals()
        reversal_journal.save()

        # Update GL entries for the reversal journal
        for line in reversal_journal.lines.all():
            account = ChartOfAccount.objects.select_for_update().get(pk=line.account.pk)
            if line.debit_amount > 0:
                account.current_balance += line.debit_amount
            elif line.credit_amount > 0:
                account.current_balance -= line.credit_amount
            account.save(update_fields=['current_balance'])

            GeneralLedger.objects.create(
                organization_id=reversal_journal.organization,
                account=line.account,
                journal=reversal_journal,
                journal_line=line,
                period=reversal_journal.period,
                transaction_date=reversal_journal.journal_date,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                balance_after=account.current_balance,
                currency_code=line.currency_code,
                exchange_rate=line.exchange_rate,
                functional_debit_amount=line.functional_debit_amount,
                functional_credit_amount=line.functional_credit_amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                description=line.description,
                source_module='Accounting (Reversal)',
                source_reference=reversal_journal.journal_number,
                created_by=self.user,
            )

        # Mark original journal as reversed and lock it
        original_journal.status = 'reversed'
        original_journal.is_locked = True
        original_journal.is_reversal = True # Mark that it has been reversed
        original_journal.updated_by = self.user
        original_journal.updated_at = timezone.now()
        original_journal.save(update_fields=['status', 'is_locked', 'is_reversal', 'updated_by', 'updated_at'])

        log_audit_event(self.user, original_journal, 'reversed', details=f"Journal {original_journal.journal_number} reversed by {reversal_journal.journal_number}.")
        log_audit_event(self.user, reversal_journal, 'created_and_posted_as_reversal', details=f"Reversal journal {reversal_journal.journal_number} created for {original_journal.journal_number}.")
        logger.info(f"Journal {original_journal.journal_number} (ID: {original_journal.pk}) successfully reversed by {reversal_journal.journal_number}.")
        return reversal_journal

    def reopen_period(self, period: AccountingPeriod):
        """
        Reopens a closed accounting period. Requires specific permissions.
        """
        self._check_permission('accounting.can_reopen_period')

        if period.status != 'closed':
            raise ValidationError(self.ERR_PERIOD_NOT_CLOSED)
        
        period.status = 'open'
        period.closed_at = None
        period.closed_by = None
        period.updated_at = timezone.now()
        period.updated_by = self.user
        period.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at', 'updated_by'])
        log_audit_event(self.user, period, 'reopened', details=f"Accounting period {period.name} reopened.")
        logger.info(f"Accounting period {period.name} (ID: {period.pk}) reopened successfully.")
        return period