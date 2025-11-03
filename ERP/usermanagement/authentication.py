from uuid import uuid4
import base64
import hashlib
import hmac
import struct
import time

from django.contrib.auth import get_user_model
from django.utils import timezone
from allauth.account.auth_backends import AuthenticationBackend

from .models import LoginLog

User = get_user_model()
def _normalize_otp(otp_code):
    if otp_code is None:
        return None
    code = str(otp_code).strip().replace(' ', '')
    return code if code else None


def _verify_totp(secret, otp_code, interval=30, digits=6, window=1):
    code = _normalize_otp(otp_code)
    if not secret or not code or not code.isdigit():
        return False

    try:
        key = base64.b32decode(secret.strip().upper())
    except Exception:
        return False

    current_counter = int(time.time() / interval)
    for offset in range(-window, window + 1):
        counter = current_counter + offset
        if counter < 0:
            continue
        msg = struct.pack('>Q', counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        start = digest[19] & 0x0F
        truncated = digest[start:start + 4]
        value = (int.from_bytes(truncated, 'big') & 0x7FFFFFFF) % (10 ** digits)
        if code == f"{value:0{digits}d}":
            return True

    return False


class CustomAuthenticationBackend(AuthenticationBackend):
    def authenticate(self, request, **credentials):
        username = credentials.get('username')
        password = credentials.get('password')
        login_method = credentials.get('login_method', 'email')
        ip_address = request.META.get('REMOTE_ADDR') if request else '127.0.0.1' # Provide a default IP for tests
        failure_reason = None
        user_from_username = None

        # Get user before authentication attempt
        if username:
            try:
                user_from_username = User.objects.get(username=username)
            except User.DoesNotExist:
                failure_reason = 'user_not_found'

        otp_token = credentials.get('otp_token')
        if request and not otp_token:
            otp_token = request.POST.get('otp_token')

        # Check for locked account before authenticating
        locked = False
        if user_from_username:
            if user_from_username.locked_until and user_from_username.locked_until > timezone.now():
                failure_reason = 'account_locked'
                locked = True
            elif user_from_username.locked_until and user_from_username.locked_until <= timezone.now():
                # Unlock account after lockout period expires
                user_from_username.locked_until = None
                user_from_username.failed_login_attempts = 0
                user_from_username.save(update_fields=['locked_until', 'failed_login_attempts'])

        authenticated_user = None
        if not locked:
            authenticated_user = super().authenticate(request, **credentials)

        # Generate session UUID
        session_uuid = uuid4()
        if request:
            request.session['custom_session_id'] = str(session_uuid)

        # Determine failure reason if authentication failed
        if authenticated_user and getattr(authenticated_user, 'mfa_enabled', False):
            if not _verify_totp(authenticated_user.mfa_secret, otp_token):
                failure_reason = 'mfa_required' if not _normalize_otp(otp_token) else 'mfa_invalid'
                self.handle_failed_login(authenticated_user, ip_address)
                authenticated_user = None
        elif user_from_username and not authenticated_user:
            if failure_reason is None:
                failure_reason = 'invalid_password'
            self.handle_failed_login(user_from_username, ip_address)

        # Create login log - now passing User instance instead of ID
        login_log = LoginLog.objects.create(
            user=user_from_username,
            session_id=str(session_uuid),
            login_method=login_method,
            success=authenticated_user is not None,
            ip_address=ip_address,
            created_by=authenticated_user,  # Pass the User instance directly
            failure_reason=failure_reason if not authenticated_user else None
        )

        # Update last login on success
        if request is not None:
            request._auth_failure_reason = failure_reason if authenticated_user is None else None

        if authenticated_user:
            authenticated_user.last_login_at = timezone.now()
            authenticated_user.failed_login_attempts = 0
            authenticated_user.locked_until = None
            authenticated_user.save(update_fields=['last_login_at', 'failed_login_attempts', 'locked_until'])

        return authenticated_user

    def handle_failed_login(self, user, ip_address):
        """Handle security features for failed login attempts"""
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts (adjust as needed)
        if user.failed_login_attempts >= 5:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        user.save(update_fields=['failed_login_attempts', 'locked_until'])
