from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from django.db import transaction

from usermanagement.models import Organization, UserRole, UserPermission, Role, CompanyConfig
from usermanagement.utils import PermissionUtils


def _invalidate(user_id, organization_id):
    if not user_id or not organization_id:
        return
    PermissionUtils.invalidate_cache(user_id, organization_id)


@receiver(post_save, sender=UserRole)
def invalidate_cache_on_userrole_save(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_delete, sender=UserRole)
def invalidate_cache_on_userrole_delete(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_save, sender=UserPermission)
def invalidate_cache_on_userpermission_save(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_delete, sender=UserPermission)
def invalidate_cache_on_userpermission_delete(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(m2m_changed, sender=Role.permissions.through)
def invalidate_cache_on_role_permission_change(sender, instance, action, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    for user_role in instance.user_roles.all():
        _invalidate(user_role.user_id, user_role.organization_id)


def _seed_noc_vendor(company: Organization):
    """Create the Nepal Oil Corporation vendor and supporting records for a company."""
    from accounting.models import AccountType, ChartOfAccount, Currency, Vendor

    currency, _ = Currency.objects.get_or_create(
        currency_code="NPR",
        defaults={"currency_name": "Nepalese Rupee", "symbol": "₨"},
    )

    ap_account = (
        ChartOfAccount.objects.filter(
            organization=company, account_name__icontains="accounts payable"
        ).first()
        or ChartOfAccount.objects.filter(
            organization=company, account_type__nature="liability"
        ).first()
    )

    if ap_account is None:
        account_type = AccountType.objects.filter(nature="liability").first()
        if account_type:
            sibling_count = (
                ChartOfAccount.objects.filter(
                    organization=company, account_code__startswith="2000"
                ).count()
                + 1
            )
            code_suffix = str(sibling_count).zfill(2)
            ap_account = ChartOfAccount.objects.create(
                organization=company,
                account_type=account_type,
                account_code=f"2000.{code_suffix}",
                account_name="Accounts Payable - Trade",
                is_control_account=True,
                created_by=None,
                updated_by=None,
            )

    if ap_account is None:
        return

    Vendor.objects.get_or_create(
        organization=company,
        code="NOC",
        defaults={
            "display_name": "Nepal Oil Corporation",
            "legal_name": "Nepal Oil Corporation",
            "tax_id": "",
            "default_currency": currency,
            "accounts_payable_account": ap_account,
            "status": "active",
        },
    )


@receiver(post_save, sender=Organization)
def ensure_company_config(sender, instance: Organization, created, **kwargs):
    defaults = CompanyConfig.defaults_for_vertical(instance.vertical_type)
    CompanyConfig.objects.get_or_create(company=instance, defaults=defaults)

    if created:
        # Seed core vendor + AP setup
        with transaction.atomic():
            _seed_noc_vendor(instance)
