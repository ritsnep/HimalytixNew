from uuid import uuid4
from django.contrib.auth import get_user_model
from django.utils import timezone
from allauth.account.auth_backends import AuthenticationBackend
from .models import LoginLog

User = get_user_model()

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

        # Try authentication
        authenticated_user = super().authenticate(request, **credentials)

        # Generate session UUID
        session_uuid = uuid4()
        if request:
            request.session['custom_session_id'] = str(session_uuid)

        # Determine failure reason if authentication failed
        if user_from_username and not authenticated_user:
            if user_from_username.locked_until and user_from_username.locked_until > timezone.now():
                failure_reason = 'account_locked'
            else:
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
        if authenticated_user:
            authenticated_user.last_login_at = timezone.now()
            authenticated_user.failed_login_attempts = 0
            authenticated_user.save(update_fields=['last_login_at', 'failed_login_attempts'])

        return authenticated_user

    def handle_failed_login(self, user, ip_address):
        """Handle security features for failed login attempts"""
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts (adjust as needed)
        if user.failed_login_attempts >= 5:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        user.save(update_fields=['failed_login_attempts', 'locked_until'])