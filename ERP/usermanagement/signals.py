from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.signals import user_login_failed
from django.utils import timezone
from django.http import HttpRequest

from django.db import transaction

from usermanagement.models import Organization, UserRole, UserPermission, Role, CompanyConfig, LoginEventLog, CustomUser
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
    # Invalidate all users with this role
    user_ids = instance.user_roles.filter(
        is_active=True
    ).values_list('user_id', flat=True)
    
    org_id = instance.organization_id
    PermissionUtils.bulk_invalidate(user_ids, org_id)


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
            try:
                from accounting.services.voucher_seeding import seed_voucher_configs
                seed_voucher_configs(instance, reset=False, repair=True)
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Voucher definition seeding failed for org %s", instance.id)
                raise
            try:
                from voucher_config.seeding import seed_voucher_config_master
                seed_voucher_config_master(instance, reset=False, repair=True)
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Voucher config master seeding failed for org %s", instance.id)
                raise


# ============================================================================
# LOGIN EVENT TRACKING SIGNALS
# ============================================================================

def _get_client_ip(request):
    """Extract client IP address from request."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _get_user_agent(request):
    """Extract user agent from request."""
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:1024]  # Limit to 1KB


def _get_country_info(ip_address):
    """
    Optional: Use GeoIP2 or MaxMind to determine country/city from IP.
    For now, returns empty strings. Can be enhanced later.
    """
    # TODO: Integrate with GeoIP2 backend if django.contrib.gis is available
    return None, None


def log_login_event(user, event_type, request=None, auth_method='email', mfa_method=None, 
                    failure_reason=None, is_suspicious=False, risk_score=0):
    """
    Generic function to log login events.
    
    Args:
        user: CustomUser instance
        event_type: Event type from LoginEventLog.EVENT_TYPE_CHOICES
        request: HttpRequest for IP/user agent extraction
        auth_method: Authentication method used ('email', 'google', 'saml', etc.)
        mfa_method: MFA method used, if applicable
        failure_reason: Reason for failed login
        is_suspicious: Whether event is marked as suspicious
        risk_score: Risk score (0-100)
    """
    try:
        ip = _get_client_ip(request) if request else None
        user_agent = _get_user_agent(request) if request else ''
        session_id = request.session.session_key if request and hasattr(request, 'session') else None
        
        organization = None
        if user and hasattr(user, 'organization'):
            organization = user.organization
        
        country_code, city = _get_country_info(ip)
        
        LoginEventLog.objects.create(
            user=user,
            organization=organization,
            event_type=event_type,
            ip_address=ip,
            user_agent=user_agent,
            session_id=session_id,
            auth_method=auth_method,
            mfa_method=mfa_method,
            failure_reason=failure_reason,
            is_suspicious=is_suspicious,
            risk_score=risk_score,
            country_code=country_code,
            city=city,
        )
    except Exception as e:
        # Don't break login flow if audit fails
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log login event for user {user}: {str(e)}")


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    """
    Signal handler for failed login attempts.
    Called when Django auth backend fails.
    """
    username = credentials.get('username')
    if not username:
        return
    
    try:
        user = CustomUser.objects.get(username=username)
        log_login_event(
            user=user,
            event_type='login_failed_invalid_creds',
            request=request,
            failure_reason='Invalid credentials',
        )
    except CustomUser.DoesNotExist:
        # User doesn't exist; still log the attempt (anonymous)
        ip = _get_client_ip(request) if request else None
        if ip:
            # Log to LoginEventLog with null user
            try:
                LoginEventLog.objects.create(
                    user=None,
                    event_type='login_failed_invalid_creds',
                    ip_address=ip,
                    user_agent=_get_user_agent(request),
                    failure_reason=f'User not found: {username}',
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to log failed login attempt: {str(e)}")
