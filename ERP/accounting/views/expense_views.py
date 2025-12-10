import logging

from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from accounting.forms import ExpenseEntryForm
from accounting.mixins import PermissionRequiredMixin
from accounting.services import process_receipt_with_ocr
from accounting.tasks import analyze_document_ocr
from utils.file_uploads import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_UPLOAD_BYTES,
    iter_validated_files,
)

logger = logging.getLogger(__name__)

RECEIPT_ALLOWED_EXTENSIONS = (
    ALLOWED_ATTACHMENT_EXTENSIONS
    & {".jpg", ".jpeg", ".png", ".pdf", ".heic"}
)
if not RECEIPT_ALLOWED_EXTENSIONS:
    RECEIPT_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def _prepare_receipt_file(uploaded_file, *, label: str):
    """Validate and normalize receipt upload for OCR processing."""
    files = list(
        iter_validated_files(
            uploaded_file,
            allowed_extensions=RECEIPT_ALLOWED_EXTENSIONS,
            max_bytes=MAX_ATTACHMENT_UPLOAD_BYTES,
            allow_archive=False,
            label=label,
        )
    )
    if not files:
        raise ValidationError("Uploaded file is empty.")
    return files[0][1]


def _celery_available() -> bool:
    """Return True when Celery is configured for async processing."""
    return bool(getattr(settings, "CELERY_BROKER_URL", None))


class ExpenseEntryCreateView(PermissionRequiredMixin, FormView):
    template_name = 'accounting/expenses/expense_entry_form.html'
    form_class = ExpenseEntryForm
    success_url = reverse_lazy('accounting:expense_entry_new')
    # Align with documented permission naming: accounting_expenseentry_add
    permission_required = 'accounting_expenseentry_add'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Quick Expense Entry'
        context['breadcrumbs'] = [('Expenses', None), ('Quick Entry', None)]
        return context

    def form_valid(self, form):
        expense_entry = form.create_expense_entry(self.request.user)
        journal_number = expense_entry.journal.journal_number
        messages.success(
            self.request,
            f"Expense recorded against {expense_entry.category.name} (Journal {journal_number}).",
        )
        return super().form_valid(form)


class ExpenseReceiptOCRView(PermissionRequiredMixin, View):
    permission_required = 'accounting_expenseentry_add'

    def post(self, request, *args, **kwargs):
        if 'receipt' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No receipt file found.'}, status=400)

        try:
            safe_file = _prepare_receipt_file(request.FILES['receipt'], label="Expense receipt OCR")
            safe_file.seek(0)
            file_bytes = safe_file.read()

            extracted_data = None
            task_id = None

            if _celery_available():
                task = analyze_document_ocr.delay(file_bytes, getattr(safe_file, "name", None))
                task_id = task.id
                if task.ready() and isinstance(task.result, dict):
                    extracted_data = task.result.get('extracted_data') or task.result
            else:
                extracted_data = process_receipt_with_ocr(
                    ContentFile(file_bytes, name=getattr(safe_file, "name", "receipt_upload"))
                )

            response_payload = {'success': True, 'task_id': task_id}
            if extracted_data:
                response_payload['extracted_data'] = extracted_data
            else:
                response_payload['status'] = 'queued'
            return JsonResponse(response_payload)

        except ValidationError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "receipt_ocr.expense_failed",
                extra={
                    'user_id': getattr(request.user, "pk", None),
                    'organization_id': getattr(request.user, "organization_id", None),
                },
            )
            return JsonResponse({'success': False, 'error': 'Failed to process receipt with OCR.'}, status=500)


class ExpenseReceiptOCRStatusView(PermissionRequiredMixin, View):
    permission_required = 'accounting_expenseentry_add'

    def get(self, request, task_id, *args, **kwargs):
        if not _celery_available():
            return JsonResponse({'success': False, 'error': 'OCR queue not configured.'}, status=400)

        result = AsyncResult(task_id)
        status = result.status.lower()

        if result.failed():
            return JsonResponse({'success': False, 'status': status, 'error': str(result.result)}, status=500)

        if result.ready():
            payload = result.result or {}
            data = payload.get('extracted_data') if isinstance(payload, dict) else payload
            return JsonResponse({'success': True, 'status': status, 'extracted_data': data})

        return JsonResponse({'success': True, 'status': status})
