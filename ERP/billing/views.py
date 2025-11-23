from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CreditDebitNote, InvoiceAuditLog, InvoiceHeader
from .permissions import CanCancelInvoice, CanCreateInvoice, CanViewAuditLog
from .serializers import CreditDebitNoteSerializer, InvoiceHeaderSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = InvoiceHeader.objects.select_related("tenant").prefetch_related("lines")
    serializer_class = InvoiceHeaderSerializer
    permission_classes = [IsAuthenticated, CanCreateInvoice]

    def perform_create(self, serializer):
        serializer.save(actor=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanCancelInvoice])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        if invoice.canceled:
            return Response({"detail": "Invoice already canceled."}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("reason", "")
        with transaction.atomic():
            note = CreditDebitNote.objects.create(
                invoice=invoice,
                note_type="credit",
                reason=reason or "Cancellation",
                amount=invoice.total_amount,
                taxable_amount=invoice.taxable_amount,
                vat_amount=invoice.vat_amount,
            )
            invoice._allow_update = True
            invoice.canceled = True
            invoice.canceled_reason = reason
            invoice.sync_status = "canceled"
            invoice._actor = request.user
            invoice.save(update_fields=["canceled", "canceled_reason", "sync_status", "updated_at"])
            InvoiceAuditLog.objects.create(
                user=request.user,
                invoice=invoice,
                action="cancel",
                description=f"Invoice canceled: {reason}",
            )
        return Response(CreditDebitNoteSerializer(note).data, status=status.HTTP_200_OK)


class CreditDebitNoteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = CreditDebitNote.objects.select_related("invoice")
    serializer_class = CreditDebitNoteSerializer
    permission_classes = [IsAuthenticated]


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InvoiceAuditLog.objects.select_related("invoice", "user")
    serializer_class = None  # Will build simple serializer inline
    permission_classes = [IsAuthenticated, CanViewAuditLog]

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self._get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        log = get_object_or_404(self.get_queryset(), pk=kwargs["pk"])
        serializer = self._get_serializer(log)
        return Response(serializer.data)

    def _get_serializer(self, *args, **kwargs):
        from rest_framework import serializers

        class _AuditSerializer(serializers.ModelSerializer):
            invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
            user_name = serializers.CharField(source="user.username", read_only=True)

            class Meta:
                model = InvoiceAuditLog
                fields = ["id", "invoice_number", "user_name", "action", "description", "timestamp"]

        return _AuditSerializer(*args, **kwargs)
