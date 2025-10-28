from typing import Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header


SIGNING_SALT = "streamlit-v2"
DEFAULT_TTL_SECONDS = 600  # 10 minutes


def issue_streamlit_token(user, tenant_id: Optional[int] = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    payload = {
        "sub": user.pk,
        "username": getattr(user, "username", None) or getattr(user, "email", None),
        "tenant_id": tenant_id,
        "iat": signing.time.time(),
        "ttl": ttl_seconds,
    }
    # signing.dumps attaches a timestamp and supports max_age on loads
    token = signing.dumps(payload, key=settings.SECRET_KEY, salt=SIGNING_SALT)
    return token


def verify_streamlit_token(token: str, max_age: Optional[int] = None) -> dict:
    try:
        data = signing.loads(token, key=settings.SECRET_KEY, salt=SIGNING_SALT, max_age=max_age or DEFAULT_TTL_SECONDS)
        return data
    except signing.BadSignature as e:
        raise exceptions.AuthenticationFailed("Invalid token") from e
    except signing.SignatureExpired as e:
        raise exceptions.AuthenticationFailed("Token expired") from e


class StreamlitTokenAuthentication(BaseAuthentication):
    """Authenticate requests bearing a short-lived signed token.

    Expects header: Authorization: Bearer <signed-object>
    Maps to request.user via sub claim, and provides claims on request.auth.
    """

    keyword = b"Bearer"

    def authenticate(self, request) -> Optional[Tuple[object, dict]]:
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower():
            return None
        if len(auth) == 1:
            raise exceptions.AuthenticationFailed("Invalid Authorization header. No credentials provided.")
        if len(auth) > 2:
            raise exceptions.AuthenticationFailed("Invalid Authorization header. Token string should not contain spaces.")

        token = auth[1].decode("utf-8")
        claims = verify_streamlit_token(token)

        User = get_user_model()
        try:
            user = User.objects.get(pk=claims.get("sub"))
        except User.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("User not found") from e

        # Attach claims for downstream use
        request.streamlit_claims = claims
        return (user, claims)
