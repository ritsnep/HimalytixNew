from typing import Any
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status

from api.authentication import (
    issue_streamlit_token,
    verify_streamlit_token,
    StreamlitTokenAuthentication,
)


class IssueStreamlitTokenView(APIView):
    """Issue a short-lived signed token for the current logged-in user.

    Requires Django-authenticated user (session). Returns token + claims.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = APIView.authentication_classes

    def post(self, request, *args: Any, **kwargs: Any):
        tenant_id = None
        # Prefer middleware-provided tenant if available
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            tenant_id = getattr(tenant, "id", None)
        else:
            tenant_id = request.session.get("active_tenant")

        token = issue_streamlit_token(request.user, tenant_id=tenant_id)
        return Response(
            {
                "token": token,
                "claims": {
                    "sub": request.user.pk,
                    "username": getattr(request.user, "username", None) or getattr(request.user, "email", None),
                    "tenant_id": tenant_id,
                },
            },
            status=status.HTTP_200_OK,
        )


class VerifyStreamlitTokenView(APIView):
    """Verify a token provided in Authorization: Bearer <token> and return claims."""

    authentication_classes = [StreamlitTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, *args: Any, **kwargs: Any):
        # If authentication succeeded, claims are attached to request.auth or request.streamlit_claims
        claims = getattr(request, "streamlit_claims", None) or request.auth
        return Response({"claims": claims}, status=status.HTTP_200_OK)

