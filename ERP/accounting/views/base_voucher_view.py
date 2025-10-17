"""
Base Voucher View - Core abstract class for all voucher entry operations.

This module provides the foundational BaseVoucherView class that all journal/voucher
entry views inherit from. It handles:
- Organization context management
- Form initialization with proper context
- Common view utilities and permissions
- HTMX integration support
- Transaction management
- Audit logging
"""

import logging
from typing import Optional, Dict, Any, Type, Union

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import ModelForm
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View

from accounting.models import Journal, JournalLine, AccountingPeriod, AuditLog
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin

logger = logging.getLogger(__name__)


class BaseVoucherView(UserOrganizationMixin, View):
    """
    Abstract base class for all voucher/journal entry views.

    Provides common functionality for:
    - Organization context management and filtering
    - Form initialization with organization context
    - Template rendering with consistent context
    - HTMX request detection and handling
    - Transaction management for save operations
    - Audit logging for changes

    Subclasses should override:
    - get() - Handle GET requests
    - post() - Handle POST requests
    - template_name - Template to render
    - permission_required - (app, model, action) tuple
    """

    model = Journal
    template_name: str = None
    permission_required: tuple = ('accounting', 'journal', 'view')
    context_object_name = 'journal'
    
    # Form configuration
    form_class: Optional[Type[ModelForm]] = None
    formset_class: Optional[Type] = None
    
    # HTMX configuration
    htmx_template_name: str = None  # Override for HTMX responses

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Dispatch the request with permission checks and organization context."""
        # Check organization context exists
        organization = self.get_organization()
        if not organization and not request.user.is_superuser:
            logger.warning(
                f"User {request.user.username} attempted access without organization context"
            )
            return render(request, '403.html', {'message': 'No active organization'}, status=403)
        
        return super().dispatch(request, *args, **kwargs)

    def get_journal_type(self) -> Optional[str]:
        """
        Get the journal type from URL kwargs or request parameters.

        Returns:
            str: The journal type code (e.g., 'JNL', 'CR', 'CD')
            None: If not specified
        """
        return self.kwargs.get('journal_type') or self.request.GET.get('journal_type')

    def get_accounting_periods(self):
        """
        Get all open accounting periods for the current organization.

        Returns:
            QuerySet: Open AccountingPeriod objects filtered by organization
        """
        organization = self.get_organization()
        return AccountingPeriod.objects.filter(
            organization=organization,
            status='open'
        ).select_related('fiscal_year')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """
        Build the context dictionary common to all voucher views.

        Adds:
        - organization: Current organization context
        - journal_type: Selected journal type if any
        - accounting_periods: Open periods for dropdowns
        - page_title: View-specific title

        Args:
            **kwargs: Additional context data from subclass

        Returns:
            dict: Complete context for template rendering
        """
        context = kwargs or {}
        
        # Add organization context
        context['organization'] = self.get_organization()
        context['journal_type'] = self.get_journal_type()
        context['accounting_periods'] = self.get_accounting_periods()
        context['page_title'] = getattr(self, 'page_title', 'Journal Entry')
        
        # Add available journal types for dropdowns
        from accounting.models import JournalType
        context['journal_types'] = JournalType.objects.filter(
            organization=context['organization']
        ).values('id', 'code', 'name')
        
        return context

    def get_form_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs to pass to form initialization.

        Ensures organization context is passed to all forms.

        Returns:
            dict: Form initialization kwargs including 'organization'
        """
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs

    def get_form(self, form_class: Optional[Type[ModelForm]] = None) -> ModelForm:
        """
        Instantiate and return the form instance.

        Args:
            form_class: The form class to instantiate (uses self.form_class if not provided)

        Returns:
            ModelForm: Initialized form instance with organization context
        """
        if form_class is None:
            form_class = self.form_class
        
        if form_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define form_class or override get_form()"
            )
        
        return form_class(**self.get_form_kwargs())

    def get_formset_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs to pass to formset initialization.

        Returns:
            dict: Formset kwargs including form_kwargs with organization
        """
        kwargs = {}
        kwargs['form_kwargs'] = {'organization': self.get_organization()}
        return kwargs

    def get_formset(self, formset_class: Optional[Type] = None):
        """
        Instantiate and return the formset instance.

        Args:
            formset_class: The formset class to instantiate

        Returns:
            BaseFormSet: Initialized formset with organization context
        """
        if formset_class is None:
            formset_class = self.formset_class
        
        if formset_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define formset_class or override get_formset()"
            )
        
        return formset_class(**self.get_formset_kwargs())

    def is_htmx_request(self) -> bool:
        """
        Detect if this is an HTMX request.

        Returns:
            bool: True if request has HX-Request header
        """
        return self.request.headers.get('HX-Request') == 'true'

    def render_to_response(
        self,
        context: Dict[str, Any],
        status: int = 200,
        template_name: str = None
    ) -> HttpResponse:
        """
        Render and return the response.

        Handles both standard and HTMX responses based on request type.

        Args:
            context: Context dictionary for template rendering
            status: HTTP status code
            template_name: Template to render (uses self.template_name if not provided)

        Returns:
            HttpResponse: Rendered response
        """
        if template_name is None:
            template_name = self.template_name
        
        # Use HTMX template if available and this is an HTMX request
        if self.is_htmx_request() and self.htmx_template_name:
            template_name = self.htmx_template_name
        
        if template_name is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define template_name"
            )
        
        return render(
            self.request,
            template_name,
            context,
            status=status
        )

    def json_response(
        self,
        data: Dict[str, Any],
        status: int = 200,
        **kwargs
    ) -> JsonResponse:
        """
        Return a JSON response.

        Args:
            data: Dictionary to encode as JSON
            status: HTTP status code
            **kwargs: Additional arguments to JsonResponse

        Returns:
            JsonResponse: JSON-encoded response
        """
        return JsonResponse(data, status=status, **kwargs)

    def error_response(
        self,
        errors: Union[Dict[str, Any], str],
        status: int = 400,
        use_json: bool = False
    ) -> HttpResponse:
        """
        Return an error response in appropriate format.

        Args:
            errors: Error dictionary or message string
            status: HTTP status code (default 400)
            use_json: If True, return JSON; else return HTML

        Returns:
            HttpResponse: Error response in requested format
        """
        if use_json or self.is_htmx_request():
            if isinstance(errors, str):
                errors = {'general': [errors]}
            return self.json_response({'success': False, 'errors': errors}, status=status)
        
        # Return HTML error response
        context = self.get_context_data(errors=errors)
        return self.render_to_response(context, status=status)

    def save_with_audit(
        self,
        journal: Journal,
        lines_data: list = None,
        action: str = 'create'
    ) -> bool:
        """
        Save journal and related data within a transaction with audit logging.

        Args:
            journal: Journal instance to save
            lines_data: List of line data to process
            action: Audit action name ('create', 'update', 'post', etc.)

        Returns:
            bool: True if save successful, False otherwise

        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Set audit fields
                journal.organization = self.get_organization()
                if action == 'create':
                    journal.created_by = self.request.user
                else:
                    journal.updated_by = self.request.user
                
                # Save journal
                journal.save()
                
                # Process lines if provided
                if lines_data:
                    self._save_lines(journal, lines_data)
                
                # Log the audit event
                self._log_audit(journal, action)
                
                logger.info(
                    f"Journal {journal.id} {action}d by {self.request.user.username}"
                )
                return True
                
        except ValidationError as e:
            logger.error(f"Validation error saving journal: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error saving journal: {e}")
            raise

    def _save_lines(self, journal: Journal, lines_data: list) -> None:
        """
        Save journal line items.

        Args:
            journal: Parent Journal instance
            lines_data: List of line data dictionaries
        """
        for line_index, line_data in enumerate(lines_data, start=1):
            line = JournalLine(journal=journal, line_number=line_index)
            for field, value in line_data.items():
                if hasattr(line, field):
                    setattr(line, field, value)
            line.save()

    def _log_audit(self, journal: Journal, action: str) -> None:
        """
        Log an audit event for the journal.

        Args:
            journal: Journal instance
            action: Action performed (create, update, post, delete, etc.)
        """
        try:
            from django.contrib.contenttypes.models import ContentType
            from accounting.models import AuditLog
            
            content_type = ContentType.objects.get_for_model(Journal)
            AuditLog.objects.create(
                user=self.request.user,
                action=action,
                content_type=content_type,
                object_id=journal.id,
                changes={'action': action},
                ip_address=self.get_client_ip()
            )
        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")

    def get_client_ip(self) -> str:
        """
        Get the client's IP address from the request.

        Returns:
            str: Client IP address
        """
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return self.request.META.get('REMOTE_ADDR')

    def get_success_url(self, journal: Journal = None) -> str:
        """
        Get the URL to redirect to after successful save.

        Args:
            journal: The saved Journal instance (optional)

        Returns:
            str: URL to redirect to
        """
        if journal:
            return reverse('accounting:journal_detail', kwargs={'pk': journal.id})
        return reverse('accounting:journal_list')


class VoucherListMixin:
    """Mixin for list views with filtering and pagination."""
    
    paginate_by = 20
    
    def get_queryset(self):
        """Get queryset filtered by organization."""
        qs = super().get_queryset()
        organization = self.get_organization()
        if organization:
            qs = qs.filter(organization=organization)
        return qs.select_related(
            'journal_type', 'period', 'created_by'
        ).prefetch_related('lines')


class VoucherDetailMixin:
    """Mixin for detail views."""
    
    def get_object(self, queryset=None):
        """Get object with organization filtering."""
        obj = super().get_object(queryset)
        if obj.organization != self.get_organization():
            from django.http import Http404
            raise Http404("Journal not found")
        return obj
