"""
API Response Utilities

Provides standardized API response formatting, error handling, and response utilities
for consistent API responses across the application.
"""

import json
import logging
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, date
from decimal import Decimal

from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator, Page
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.forms import ModelForm
from django.utils import timezone

logger = logging.getLogger(__name__)


class APIResponse:
    """
    Standardized API response utility for consistent JSON responses.
    """

    # Standard response status codes
    SUCCESS = 'success'
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'

    @staticmethod
    def success(
        data: Any = None,
        message: str = None,
        status_code: int = 200,
        extra: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """
        Create a successful API response.

        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code
            extra: Additional response fields

        Returns:
            JsonResponse with standardized format

        Usage:
            # Simple success
            return APIResponse.success(message="Operation completed")

            # With data
            return APIResponse.success(data=user_data, message="User updated")
        """
        response = {
            'status': APIResponse.SUCCESS,
            'message': message or 'Operation completed successfully',
        }

        if data is not None:
            response['data'] = data

        if extra:
            response.update(extra)

        return JsonResponse(response, status=status_code, safe=False)

    @staticmethod
    def error(
        message: str,
        errors: Optional[Union[List, Dict, str]] = None,
        status_code: int = 400,
        error_code: Optional[str] = None
    ) -> JsonResponse:
        """
        Create an error API response.

        Args:
            message: Error message
            errors: Detailed error information
            status_code: HTTP status code
            error_code: Application-specific error code

        Returns:
            JsonResponse with error format

        Usage:
            # Simple error
            return APIResponse.error("Invalid input", status_code=422)

            # With detailed errors
            return APIResponse.error("Validation failed", errors=form.errors)
        """
        response = {
            'status': APIResponse.ERROR,
            'message': message,
        }

        if error_code:
            response['error_code'] = error_code

        if errors:
            if isinstance(errors, str):
                response['errors'] = [errors]
            elif isinstance(errors, dict):
                response['errors'] = errors
            elif isinstance(errors, list):
                response['errors'] = errors
            else:
                response['errors'] = str(errors)

        return JsonResponse(response, status=status_code, safe=False)

    @staticmethod
    def paginated_response(
        queryset: QuerySet,
        page: int = 1,
        page_size: int = 25,
        serializer: Optional[Any] = None,
        **kwargs
    ) -> JsonResponse:
        """
        Create a paginated API response.

        Args:
            queryset: QuerySet to paginate
            page: Page number (1-based)
            page_size: Items per page
            serializer: Optional serializer function/class
            **kwargs: Additional response data

        Returns:
            JsonResponse with pagination info

        Usage:
            # Paginated response
            return APIResponse.paginated_response(
                User.objects.all(), page=1, page_size=10
            )
        """
        paginator = Paginator(queryset, page_size)

        try:
            page_obj = paginator.page(page)
        except Exception:
            return APIResponse.error("Invalid page number", status_code=400)

        data = APIResponse._serialize_page_data(page_obj, serializer)

        response_data = {
            'data': data,
            'pagination': {
                'page': page_obj.number,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            }
        }

        response_data.update(kwargs)
        return APIResponse.success(data=response_data)

    @staticmethod
    def _serialize_page_data(page_obj: Page, serializer: Optional[Any]) -> List[Dict[str, Any]]:
        """Serialize page data using serializer or basic model serialization."""
        if serializer:
            if callable(serializer):
                return [serializer(item) for item in page_obj.object_list]
            else:
                # Assume it's a serializer class
                return serializer(page_obj.object_list, many=True).data

        # Basic serialization for models
        data = []
        for item in page_obj.object_list:
            if hasattr(item, 'to_dict'):
                data.append(item.to_dict())
            else:
                # Basic model serialization
                item_data = {}
                for field in item._meta.fields:
                    value = getattr(item, field.name)
                    if isinstance(value, (datetime, date)):
                        value = value.isoformat()
                    elif isinstance(value, Decimal):
                        value = str(value)
                    item_data[field.name] = value
                data.append(item_data)
        return data

    @staticmethod
    def validation_error(form_or_errors: Union[ModelForm, Dict, ValidationError]) -> JsonResponse:
        """
        Create response for validation errors.

        Args:
            form_or_errors: Form with errors or error dict

        Returns:
            JsonResponse with validation errors

        Usage:
            # Form validation error
            if not form.is_valid():
                return APIResponse.validation_error(form)
        """
        if hasattr(form_or_errors, 'errors'):
            # Django form or model form
            errors = form_or_errors.errors
        elif isinstance(form_or_errors, ValidationError):
            # Django ValidationError
            errors = form_or_errors.message_dict if hasattr(form_or_errors, 'message_dict') else str(form_or_errors)
        elif isinstance(form_or_errors, dict):
            errors = form_or_errors
        else:
            errors = str(form_or_errors)

        return APIResponse.error(
            message="Validation failed",
            errors=errors,
            status_code=422,
            error_code="VALIDATION_ERROR"
        )

    @staticmethod
    def file_response(
        content: Union[str, bytes],
        filename: str,
        content_type: str = 'application/octet-stream'
    ) -> HttpResponse:
        """
        Create file download response.

        Args:
            content: File content
            filename: Download filename
            content_type: MIME type

        Returns:
            HttpResponse for file download

        Usage:
            # File download response
            csv_content = generate_csv()
            return APIResponse.file_response(csv_content, 'data.csv', 'text/csv')
        """
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class APIError(Exception):
    """
    Custom exception for API errors with standardized response.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: Optional[str] = None,
        errors: Optional[Union[List, Dict]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.errors = errors
        super().__init__(message)

    def to_response(self) -> JsonResponse:
        """Convert exception to API response."""
        return APIResponse.error(
            message=self.message,
            errors=self.errors,
            status_code=self.status_code,
            error_code=self.error_code
        )


class APIResponseBuilder:
    """
    Builder pattern for complex API responses.
    """

    def __init__(self):
        self._status = APIResponse.SUCCESS
        self._message = None
        self._data = None
        self._errors = None
        self._meta = {}
        self._status_code = 200
        self._error_code = None

    def success(self, message: str = None) -> 'APIResponseBuilder':
        """Set success status."""
        self._status = APIResponse.SUCCESS
        self._message = message or "Operation completed successfully"
        return self

    def error(self, message: str, status_code: int = 400, error_code: str = None) -> 'APIResponseBuilder':
        """Set error status."""
        self._status = APIResponse.ERROR
        self._message = message
        self._status_code = status_code
        self._error_code = error_code
        return self

    def data(self, data: Any) -> 'APIResponseBuilder':
        """Set response data."""
        self._data = data
        return self

    def message(self, message: str) -> 'APIResponseBuilder':
        """Set response message."""
        self._message = message
        return self

    def errors(self, errors: Union[List, Dict, str]) -> 'APIResponseBuilder':
        """Set error details."""
        self._errors = errors
        return self

    def meta(self, key: str, value: Any) -> 'APIResponseBuilder':
        """Add metadata."""
        self._meta[key] = value
        return self

    def status_code(self, code: int) -> 'APIResponseBuilder':
        """Set HTTP status code."""
        self._status_code = code
        return self

    def build(self) -> JsonResponse:
        """Build the final API response."""
        response_data = {
            'status': self._status,
            'message': self._message,
        }

        if self._data is not None:
            response_data['data'] = self._data

        if self._errors:
            response_data['errors'] = self._errors

        if self._error_code:
            response_data['error_code'] = self._error_code

        if self._meta:
            response_data['meta'] = self._meta

        return JsonResponse(response_data, status=self._status_code, safe=False)


class APIDataSerializer:
    """
    Utilities for serializing data for API responses.
    """

    @staticmethod
    def serialize_model(instance: Any, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Serialize a model instance to dictionary.

        Args:
            instance: Model instance
            fields: Specific fields to include (optional)

        Returns:
            Serialized dictionary

        Usage:
            # Serialize user
            user_data = APIDataSerializer.serialize_model(user, ['id', 'username', 'email'])
        """
        if hasattr(instance, 'to_dict'):
            return instance.to_dict()

        data = {}
        model_fields = fields or [f.name for f in instance._meta.fields]

        for field_name in model_fields:
            if hasattr(instance, field_name):
                value = getattr(instance, field_name)
                data[field_name] = APIDataSerializer._serialize_value(value)

        return data

    @staticmethod
    def serialize_queryset(
        queryset: QuerySet,
        fields: Optional[List[str]] = None,
        serializer: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Serialize a queryset to list of dictionaries.

        Args:
            queryset: QuerySet to serialize
            fields: Specific fields to include
            serializer: Optional custom serializer

        Returns:
            List of serialized dictionaries
        """
        if serializer:
            if callable(serializer):
                return [serializer(item) for item in queryset]
            else:
                # Assume serializer class
                return serializer(queryset, many=True).data

        return [APIDataSerializer.serialize_model(item, fields) for item in queryset]

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize individual values for JSON compatibility."""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return str(value)
        elif hasattr(value, 'pk'):  # Foreign key
            return value.pk
        elif isinstance(value, (list, tuple)):
            return [APIDataSerializer._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: APIDataSerializer._serialize_value(v) for k, v in value.items()}
        else:
            return value


class APIExceptionHandler:
    """
    Utilities for handling and formatting exceptions in API responses.
    """

    @staticmethod
    def handle_exception(exc: Exception, request=None) -> JsonResponse:
        """
        Handle exceptions and return appropriate API responses.

        Args:
            exc: Exception instance
            request: Optional request object for context

        Returns:
            JsonResponse with error details
        """
        logger.error(f"API Exception: {exc}", exc_info=True)

        if isinstance(exc, APIError):
            return exc.to_response()
        elif isinstance(exc, ValidationError):
            return APIResponse.validation_error(exc)
        elif isinstance(exc, PermissionError):
            return APIResponse.error(
                "Permission denied",
                status_code=403,
                error_code="PERMISSION_DENIED"
            )
        elif isinstance(exc, ValueError):
            return APIResponse.error(
                str(exc),
                status_code=400,
                error_code="VALIDATION_ERROR"
            )
        else:
            # Generic server error
            return APIResponse.error(
                "An unexpected error occurred",
                status_code=500,
                error_code="INTERNAL_ERROR"
            )

    @staticmethod
    def format_validation_errors(errors: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Format Django form validation errors for API response.

        Args:
            errors: Form errors dictionary

        Returns:
            Formatted error dictionary
        """
        formatted = {}
        for field, messages in errors.items():
            if isinstance(messages, list):
                formatted[field] = messages
            else:
                formatted[field] = [str(messages)]

        return formatted


# Response formatters for specific data types
def format_currency_response(amount: Decimal, currency: str, locale: str = 'en') -> Dict[str, Any]:
    """
    Format currency data for API response.

    Args:
        amount: Currency amount
        currency: Currency code
        locale: Locale for formatting

    Returns:
        Formatted currency data
    """
    from .currency import CurrencyFormatter

    return {
        'amount': str(amount),
        'currency': currency,
        'formatted': CurrencyFormatter.format_amount(amount, currency, locale),
        'symbol': CurrencyFormatter._get_currency_info(currency).get('symbol', currency)
    }


def format_date_response(date_obj: Union[date, datetime], include_nepali: bool = True) -> Dict[str, Any]:
    """
    Format date data for API response.

    Args:
        date_obj: Date/datetime object
        include_nepali: Whether to include Nepali date

    Returns:
        Formatted date data
    """
    from .calendars import ad_to_bs_string

    response = {
        'iso': date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj),
        'formatted': date_obj.strftime('%Y-%m-%d'),
        'readable': date_obj.strftime('%B %d, %Y'),
    }

    if include_nepali:
        bs_date = ad_to_bs_string(date_obj)
        if bs_date:
            response['nepali'] = bs_date

    return response


def format_account_response(account: Any) -> Dict[str, Any]:
    """
    Format account data for API response.

    Args:
        account: Account instance

    Returns:
        Formatted account data
    """
    from .coa import COAService

    return {
        'id': account.pk,
        'code': account.account_code,
        'name': account.account_name,
        'type': account.account_type.name if account.account_type else '',
        'nature': account.account_type.nature if account.account_type else '',
        'balance': str(COAService.get_account_balance(account) or 0),
        'is_active': account.is_active,
        'level': account.account_level,
    }


# API response decorators
def api_response(view_func):
    """
    Decorator to wrap view responses in standardized API format.

    Usage:
        @api_response
        def my_view(request):
            # View logic
            return {'data': result, 'message': 'Success'}
    """
    def wrapper(request, *args, **kwargs):
        try:
            result = view_func(request, *args, **kwargs)

            if isinstance(result, JsonResponse):
                return result

            if isinstance(result, dict):
                return APIResponse.success(**result)

            return APIResponse.success(data=result)

        except Exception as e:
            return APIExceptionHandler.handle_exception(e, request)

    return wrapper


def require_api_auth(view_func):
    """
    Decorator to require API authentication.

    Usage:
        @require_api_auth
        def protected_view(request):
            # Only authenticated users can access
            pass
    """
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return APIResponse.error(
                "Authentication required",
                status_code=401,
                error_code="AUTH_REQUIRED"
            )
        return view_func(request, *args, **kwargs)

    return wrapper
