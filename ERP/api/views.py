import csv
import logging
from io import TextIOWrapper

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.contrib.contenttypes.models import ContentType
from rest_framework import renderers, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter

from accounting.models import (
    ApprovalTask,
    ChartOfAccount,
    CurrencyExchangeRate,
    FiscalYear,
    GeneralLedger,
    Journal,
)
from accounting.services import post_journal, close_period
from accounting.utils.idempotency import resolve_idempotency_key
from accounting.services.workflow_service import WorkflowService
from accounting.services.document_lifecycle import DocumentLifecycleService
from utils.file_uploads import MAX_IMPORT_UPLOAD_BYTES, iter_validated_files

from .permissions import IsOrganizationMember
from .serializers import (
    ChartOfAccountSerializer,
    CurrencyExchangeRateSerializer,
    FiscalYearSerializer,
    JournalSerializer,
)

logger = logging.getLogger(__name__)

class BaseOrgViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    renderer_classes = [renderers.JSONRenderer, renderers.BrowsableAPIRenderer]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user.organization)

class ChartOfAccountViewSet(BaseOrgViewSet):
    queryset = ChartOfAccount.objects.all()
    serializer_class = ChartOfAccountSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("parent_account", "account_type")

class JournalViewSet(BaseOrgViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("journal_type", "period").prefetch_related("lines__account")

    def perform_create(self, serializer):
        journal = serializer.save(organization=self.request.user.organization)
        post_journal(journal, user=self.request.user, idempotency_key=resolve_idempotency_key(self.request))

    def _pending_task(self, journal: Journal) -> ApprovalTask | None:
        content_type = ContentType.objects.get_for_model(Journal)
        return (
            ApprovalTask.objects.filter(
                content_type=content_type,
                object_id=journal.pk,
                status="pending",
            )
            .order_by("-updated_at")
            .first()
        )

    def _serialized_response(self, journal: Journal):
        serializer = self.get_serializer(journal)
        return Response(serializer.data)

    def _handle_transition_response(self, journal: Journal, func):
        try:
            result = func()
        except (ValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return result

    @action(detail=True, methods=["post"], url_path="submit")
    def submit_for_approval(self, request, pk=None):
        journal = self.get_object()

        if self._pending_task(journal):
            return Response({"detail": "Approval already pending."}, status=status.HTTP_400_BAD_REQUEST)

        def _work():
            lifecycle = DocumentLifecycleService(journal=journal, acting_user=request.user)
            lifecycle.transition("awaiting_approval")
            WorkflowService(request.user).submit_with_policy(journal, area="journal", initiator=request.user)
            return self._serialized_response(journal)

        return self._handle_transition_response(journal, _work)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        journal = self.get_object()
        notes = request.data.get("notes", "")
        task = self._pending_task(journal)
        if not task:
            return Response({"detail": "No pending approval task."}, status=status.HTTP_400_BAD_REQUEST)

        def _work():
            result = WorkflowService(request.user).approve(task, request.user, approved=True, notes=notes)
            if result.status == "approved":
                lifecycle = DocumentLifecycleService(journal=journal, acting_user=request.user)
                lifecycle.transition("approved")
            journal.refresh_from_db()
            return self._serialized_response(journal)

        return self._handle_transition_response(journal, _work)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        journal = self.get_object()
        notes = request.data.get("notes", "")
        task = self._pending_task(journal)
        if not task:
            return Response({"detail": "No pending approval task."}, status=status.HTTP_400_BAD_REQUEST)

        def _work():
            result = WorkflowService(request.user).approve(task, request.user, approved=False, notes=notes)
            if result.status == "rejected":
                lifecycle = DocumentLifecycleService(journal=journal, acting_user=request.user)
                lifecycle.transition("rejected")
            journal.refresh_from_db()
            return self._serialized_response(journal)

        return self._handle_transition_response(journal, _work)

    @action(detail=True, methods=["post"], url_path="post")
    def post(self, request, pk=None):
        journal = self.get_object()

        def _work():
            post_journal(journal, user=request.user, idempotency_key=resolve_idempotency_key(request))
            return self._serialized_response(journal)

        return self._handle_transition_response(journal, _work)

class CurrencyExchangeRateViewSet(BaseOrgViewSet):
    queryset = CurrencyExchangeRate.objects.all()
    serializer_class = CurrencyExchangeRateSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("from_currency", "to_currency")

class JournalImportView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    renderer_classes = [renderers.JSONRenderer, renderers.BrowsableAPIRenderer]

    @extend_schema(
        request={'multipart/form-data': {'type': 'object', 'properties': {'file': {'type': 'string', 'format': 'binary'}}}},
        responses={
            200: inline_serializer(
                name='JournalImportResponse',
                fields={'created': drf_serializers.ListField(child=drf_serializers.IntegerField())}
            ),
            400: inline_serializer(
                name='JournalImportError',
                fields={'detail': drf_serializers.CharField()}
            )
        },
        summary="Import Journals from CSV",
        description="Upload a CSV file to bulk import journal entries"
    )
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            extracted = list(
                iter_validated_files(
                    file,
                    allowed_extensions={".csv"},
                    max_bytes=MAX_IMPORT_UPLOAD_BYTES,
                    allow_archive=True,
                    max_members=1,
                    label="Journal import",
                )
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _, content = extracted[0]
        content.seek(0)
        reader = csv.DictReader(TextIOWrapper(content, encoding="utf-8"))
        created = []
        for row in reader:
            serializer = JournalSerializer(data=row)
            if serializer.is_valid():
                journal = serializer.save(organization=request.user.organization)
                post_journal(journal, user=request.user, idempotency_key=resolve_idempotency_key(request))
                created.append(journal.journal_id)
            else:
                logger.debug("Invalid row: %s", serializer.errors)
        return Response({"created": created})


from decimal import Decimal
from django.db.models import Sum

def get_trial_balance(organization, fiscal_year):
    """Return trial balance data for an organization and fiscal year."""
    accounts = ChartOfAccount.objects.filter(organization=organization, is_active=True).values("account_id", "account_code", "account_name").order_by("account_code")
    gl_totals = GeneralLedger.objects.filter(
        organization_id=organization.id,
        period__fiscal_year=fiscal_year,
        is_archived=False,
    ).values("account_id").annotate(
        debit_total=Sum("debit_amount"),
        credit_total=Sum("credit_amount"),
    )
    totals_map = {row["account_id"]: row for row in gl_totals}
    results = []
    for account in accounts:
        totals = totals_map.get(account["account_id"], {})
        debit = totals.get("debit_total") or Decimal("0")
        credit = totals.get("credit_total") or Decimal("0")
        balance = debit - credit
        results.append(
            {
                "account_id": account["account_id"],
                "account_code": account["account_code"],
                "account_name": account["account_name"],
                "debit_total": debit,
                "credit_total": credit,
                "balance": balance,
            }
        )
    return results

class TrialBalanceView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    renderer_classes = [renderers.JSONRenderer, renderers.BrowsableAPIRenderer]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='fiscal_year',
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="ID of the fiscal year to get trial balance for"
            )
        ],
        responses={
            200: inline_serializer(
                name='TrialBalanceResponse',
                fields={
                    'results': drf_serializers.ListField(
                        child=inline_serializer(
                            name='TrialBalanceEntry',
                            fields={
                                'account_id': drf_serializers.IntegerField(),
                                'account_code': drf_serializers.CharField(),
                                'account_name': drf_serializers.CharField(),
                                'debit_total': drf_serializers.DecimalField(max_digits=20, decimal_places=2),
                                'credit_total': drf_serializers.DecimalField(max_digits=20, decimal_places=2),
                                'balance': drf_serializers.DecimalField(max_digits=20, decimal_places=2),
                            }
                        )
                    )
                }
            ),
            400: inline_serializer(
                name='TrialBalanceError',
                fields={'detail': drf_serializers.CharField()}
            )
        },
        summary="Get Trial Balance",
        description="Retrieve trial balance for a specific fiscal year"
    )
    def get(self, request):
        fiscal_year = request.query_params.get("fiscal_year")
        if not fiscal_year:
            return Response({"detail": "fiscal_year parameter required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fy = FiscalYear.objects.get(pk=fiscal_year, organization=request.user.organization)
        except FiscalYear.DoesNotExist:
            raise Http404

        data = get_trial_balance(request.user.organization, fy)
        return Response({"results": data})
