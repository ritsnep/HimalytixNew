# usermanagement/models.py
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tenancy.models import Tenant


_ACTIVE_ORG_CACHE_MISS = object()
# class CustomUser(AbstractUser):
#     full_name = models.CharField(max_length=100)
#     role = models.CharField(max_length=50, choices=[("superadmin", "Super Admin"), ("admin", "Admin"), ("user", "User")])
#     company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True, blank=True)

#     def __str__(self):
#         return self.username
    

class Organization(models.Model):
    VERTICAL_CHOICES = [
        ("retailer", "Retailer"),
        ("depot", "Depot"),
        ("logistics", "Logistics"),
    ]

    parent_organization = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name='organizations')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    legal_name = models.CharField(max_length=200, null=True, blank=True)
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    registration_number = models.CharField(max_length=50, null=True, blank=True)
    industry_code = models.CharField(max_length=20, null=True, blank=True)
    fiscal_year_start_month = models.SmallIntegerField(default=1)
    fiscal_year_start_day = models.SmallIntegerField(default=1)
    fiscal_year_start = models.DateField(null=True, blank=True)
    base_currency_code = models.CharField(max_length=3, default="USD")
    address = models.TextField(blank=True, default="")
    vertical_type = models.CharField(
        max_length=20,
        choices=VERTICAL_CHOICES,
        default="retailer",
        help_text="Operational vertical for feature toggles.",
    )
    status = models.CharField(max_length=20, default="active")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def company_config(self):
        """Safe accessor for the related CompanyConfig if it exists."""
        return getattr(self, "config", None)
    
    
class OrganizationAddress(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=50)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country_code = models.CharField(max_length=2)
    is_primary = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


class OrganizationContact(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, null=True, blank=True)
    job_title = models.CharField(max_length=100, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("accountant", "Accountant"),
        ("data_entry", "Data Entry"),
        ("user", "User"),
    ]

    user_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    full_name = models.CharField(max_length=100)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="user")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)

    # New fields from schema
    status = models.CharField(max_length=20, default='active')
    auth_provider = models.CharField(max_length=50, default='local')
    auth_provider_id = models.CharField(max_length=255, null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    password_reset_token = models.CharField(max_length=100, null=True, blank=True)
    password_reset_expires = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.SmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    email_verification_token = models.CharField(max_length=100, null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_type = models.CharField(max_length=20, null=True, blank=True)
    mfa_secret = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username
    
    def organizations(self):
        return self.userorganization_set.all()

    def get_active_organization(self):
        cached = getattr(self, '_active_organization_cache', _ACTIVE_ORG_CACHE_MISS)
        if cached is not _ACTIVE_ORG_CACHE_MISS:
            return cached

        organization = getattr(self, 'organization', None)
        if organization:
            self._active_organization_cache = organization
            return organization

        mapping = (
            self.userorganization_set.filter(is_active=True)
            .select_related('organization')
            .order_by('organization__name')
            .first()
        )

        organization = mapping.organization if mapping else None
        self._active_organization_cache = organization
        return organization

    def set_active_organization(self, organization):
        self._active_organization_cache = organization

# class Company(models.Model):
#     name = models.CharField(max_length=255)
#     domain = models.CharField(max_length=255, unique=True)

#     def __str__(self):
#         return self.name


class UserOrganization(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    is_owner = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=50, default='member')
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organization')
        db_table = 'user_organizations'

    def __str__(self):
        return f"{self.user.username} - {self.organization.name}"

class Module(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    icon = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Entity(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='entities')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('module', 'code')
        ordering = ['module', 'display_order', 'name']

    def __str__(self):
        return f"{self.module.name} - {self.name}"


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('usermanagement.CustomUser', on_delete=models.CASCADE, related_name='created_by')
    updated_by = models.ForeignKey('usermanagement.CustomUser', on_delete=models.CASCADE, related_name='updated_by')

    class Meta:
        abstract = True
class LoginLog(models.Model):
    login_datetime = models.DateTimeField(auto_now_add=True)
    # user = models.ForeignKey('usermanagement.CustomUser', on_delete=models.CASCADE)
    user = models.ForeignKey('usermanagement.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    # user = models.ForeignKey('usermanagement.CustomUser', on_delete=models.CASCADE, null=True, blank=True)
    login_method = models.CharField(max_length=50, choices=[("email", "Email"), ("google", "Google"), ("facebook", "Facebook")])
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    session_time = models.DurationField(null=True, blank=True)
    session_id =  models.CharField(max_length=64, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('usermanagement.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_logs')
    # created_by = models.ForeignKey('usermanagement.CustomUser', on_delete=models.CASCADE,  null=True, blank=True,related_name='created_by')
    
    def is_password_expired(self):
        return (timezone.now() - self.password_changed_at) > timezone.timedelta(days=90)
    def __str__(self):
        return f"{self.user.username} - {self.login_datetime}"

    class Meta:
        indexes = [
            models.Index(fields=['user', 'login_datetime']),
            models.Index(fields=['session_id']),
        ]
PERMISSION_ACTION_CHOICES = [
    ('view', 'View'),
    ('add', 'Add'),
    ('change', 'Change'),
    ('delete', 'Delete'),
    ('submit', 'Submit'),
    ('approve', 'Approve'),
    ('reject', 'Reject'),
    ('post', 'Post'),
    ('reverse', 'Reverse'),
    ('modify', 'Modify'),
    ('special', 'Special'),
    ('submit_journal', 'Submit Journal'),
    ('approve_journal', 'Approve Journal'),
    ('reject_journal', 'Reject Journal'),
    ('post_journal', 'Post Journal'),
    ('reverse_journal', 'Reverse Journal'),
    ('close_period', 'Close Period'),
    ('reopen_period', 'Reopen Period'),
    ('close_fiscalyear', 'Close Fiscal Year'),
    ('reopen_fiscalyear', 'Reopen Fiscal Year'),
]


class CompanyConfig(models.Model):
    """Feature toggles per company/tenant."""

    company = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="config")
    enable_noc_purchases = models.BooleanField(default=False)
    enable_dealer_management = models.BooleanField(default=True)
    enable_logistics = models.BooleanField(default=False)
    enable_advanced_inventory = models.BooleanField(default=False)
    enforce_credit_limit = models.BooleanField(default=True)
    credit_enforcement_mode = models.CharField(
        max_length=10,
        choices=[("block", "Block"), ("warn", "Warn")],
        default="block",
        help_text="How to handle dealer credit limit breaches.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_config"

    def __str__(self):
        return f"{self.company.name} config"

    @classmethod
    def defaults_for_vertical(cls, vertical: str) -> dict:
        """Provide sensible defaults per vertical type."""
        vertical = (vertical or "").lower()
        if vertical == "depot":
            return {
                "enable_noc_purchases": True,
                "enable_dealer_management": True,
                "enable_logistics": True,
                "enable_advanced_inventory": True,
            }
        if vertical == "logistics":
            return {
                "enable_noc_purchases": False,
                "enable_dealer_management": False,
                "enable_logistics": True,
                "enable_advanced_inventory": False,
            }
        # retailer/default
        return {
            "enable_noc_purchases": False,
            "enable_dealer_management": True,
            "enable_logistics": False,
            "enable_advanced_inventory": False,
        }


class Permission(models.Model):
    name = models.CharField(max_length=100)
    codename = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='permissions')
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='permissions')
    action = models.CharField(max_length=50, choices=PERMISSION_ACTION_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('codename', 'module', 'entity')
        ordering = ['module', 'entity', 'action']
        
    def __str__(self):
        return f"{self.name} ({self.codename})"

    def save(self, *args, **kwargs):
        if not self.codename:
            self.codename = f"{self.module.code}_{self.entity.code}_{self.action}"
        super().save(*args, **kwargs)

class Role(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')
    permissions = models.ManyToManyField(Permission, related_name='roles')
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_roles')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='updated_roles')
    
    class Meta:
        unique_together = ('code', 'organization')
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class UserRole(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_roles')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_user_roles')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='updated_user_roles')
    
    class Meta:
        unique_together = ('user', 'role', 'organization')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.role.name} ({self.organization.name})"

class UserPermission(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='explicit_user_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='user_permissions')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_permissions')
    is_granted = models.BooleanField(default=True, help_text='True=grant, False=revoke')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'permission', 'organization')
        ordering = ['user', 'organization', 'permission']

    def __str__(self):
        return f"{self.user.username} - {self.permission.codename} ({'grant' if self.is_granted else 'revoke'})"
