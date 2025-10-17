from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.forms import model_to_dict
from django.utils import timezone
from django.contrib.auth import get_user_model
from usermanagement.models import CustomUser, Organization
from django.utils.crypto import get_random_string
from django.db.models import Max, Q, F, CheckConstraint, Sum
import logging
from django.core.exceptions import ValidationError
from django.db import transaction
import re
from django.db.models import JSONField
from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)
User = get_user_model()

class ActiveAccountManager(models.Manager):
    """Manager that returns only non-archived accounts."""
    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)

class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    changes = models.JSONField()
    details = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['timestamp']),
        ]

class ChartOfAccount(models.Model):
    """
    Represents a chart of accounts entry that can be hierarchically organized.
    Each account can have a parent account, creating a tree structure.
    """
    # Default starting codes for each account nature
    NATURE_ROOT_CODE = {
        'asset': '1000',
        'liability': '2000',
        'equity': '3000',
        'income': '4000',
        'expense': '5000',
    }
    ROOT_STEP = 100
    account_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='chart_of_accounts')
    parent_account = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_accounts')
    account_type = models.ForeignKey('AccountType', on_delete=models.PROTECT)
    account_code = models.CharField(max_length=50, validators=[RegexValidator(r'^\d{4}(?:\.\d{2})*$', 'Invalid COA code format.')])
    account_name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_accounts')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_accounts')
    rowversion = models.BinaryField(editable=False, null=True, blank=True)

    objects = models.Manager()
    active_accounts = ActiveAccountManager()

    class Meta:
        ordering = ['account_code']
        unique_together = [('organization', 'account_code')]

class JournalLine(models.Model):
    """
    Represents a single line in a journal entry.
    """
    journal_line_id = models.BigAutoField(primary_key=True)
    journal = models.ForeignKey('Journal', on_delete=models.CASCADE, related_name='lines')
    line_number = models.BigIntegerField()
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    description = models.TextField(null=True, blank=True)
    debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    functional_debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    functional_credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True)
    tax_code = models.ForeignKey('TaxCode', on_delete=models.SET_NULL, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    memo = models.TextField(null=True, blank=True)
    reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reconciled_journal_lines')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_journal_lines')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_journal_lines')
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_journal_lines')
    rowversion = models.BinaryField(editable=False, null=True, blank=True)
    udf_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['journal', 'line_number']

    def clean(self):
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("A journal line cannot have both a debit and a credit amount.")
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("A journal line must have either a debit or a credit amount.")

# (Other models stay the same)
