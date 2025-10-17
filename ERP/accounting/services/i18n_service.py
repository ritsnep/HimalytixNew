"""
Internationalization (i18n) Service - Phase 3 Task 6

Provides multi-language support with:
- Language middleware
- Translation utilities
- RTL support
- Locale formatting
"""

from django.utils.translation import get_language, activate
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from functools import wraps
from decimal import Decimal
from datetime import datetime
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'rtl': False, 'region': 'US'},
    'es': {'name': 'Español', 'rtl': False, 'region': 'ES'},
    'fr': {'name': 'Français', 'rtl': False, 'region': 'FR'},
    'de': {'name': 'Deutsch', 'rtl': False, 'region': 'DE'},
    'ar': {'name': 'العربية', 'rtl': True, 'region': 'SA'},
    'zh': {'name': '中文', 'rtl': False, 'region': 'CN'},
    'ja': {'name': '日本語', 'rtl': False, 'region': 'JP'},
    'pt': {'name': 'Português', 'rtl': False, 'region': 'BR'},
}

# Locale formats
LOCALE_FORMATS = {
    'en': {'date': '%m/%d/%Y', 'currency': '$', 'decimal': '.', 'thousand': ','},
    'es': {'date': '%d/%m/%Y', 'currency': '€', 'decimal': ',', 'thousand': '.'},
    'fr': {'date': '%d/%m/%Y', 'currency': '€', 'decimal': ',', 'thousand': ' '},
    'de': {'date': '%d.%m.%Y', 'currency': '€', 'decimal': ',', 'thousand': '.'},
    'ar': {'date': '%Y-%m-%d', 'currency': '﷼', 'decimal': ',', 'thousand': '.'},
    'zh': {'date': '%Y年%m月%d日', 'currency': '¥', 'decimal': '.', 'thousand': ','},
    'ja': {'date': '%Y年%m月%d日', 'currency': '¥', 'decimal': '.', 'thousand': ','},
    'pt': {'date': '%d/%m/%Y', 'currency': 'R$', 'decimal': ',', 'thousand': '.'},
}


class I18nService:
    """
    Internationalization service for multi-language support.
    
    Provides:
    - Language switching
    - Locale formatting
    - Translation utilities
    - RTL support detection
    """
    
    @staticmethod
    def get_current_language() -> str:
        """Get current active language."""
        return get_language() or 'en'
    
    @staticmethod
    def set_language(language_code: str) -> bool:
        """
        Set active language.
        
        Args:
            language_code: Language code (e.g., 'en', 'es')
            
        Returns:
            bool indicating success
        """
        if language_code in SUPPORTED_LANGUAGES:
            activate(language_code)
            logger.info(f'Language set to: {language_code}')
            return True
        return False
    
    @staticmethod
    def get_language_info(language_code: str = None) -> Dict[str, Any]:
        """
        Get language information.
        
        Args:
            language_code: Language code (default: current language)
            
        Returns:
            dict with language info
        """
        if language_code is None:
            language_code = I18nService.get_current_language()
        
        return SUPPORTED_LANGUAGES.get(language_code, SUPPORTED_LANGUAGES['en'])
    
    @staticmethod
    def is_rtl() -> bool:
        """
        Check if current language uses RTL layout.
        
        Returns:
            bool indicating RTL
        """
        lang = I18nService.get_current_language()
        lang_info = SUPPORTED_LANGUAGES.get(lang, {})
        return lang_info.get('rtl', False)
    
    @staticmethod
    def get_all_languages() -> Dict[str, Dict[str, Any]]:
        """
        Get all supported languages.
        
        Returns:
            dict of all language info
        """
        return SUPPORTED_LANGUAGES
    
    @staticmethod
    def format_date(date_obj: datetime, language_code: str = None) -> str:
        """
        Format date according to locale.
        
        Args:
            date_obj: Date to format
            language_code: Language code (default: current)
            
        Returns:
            Formatted date string
        """
        if language_code is None:
            language_code = I18nService.get_current_language()
        
        locale_format = LOCALE_FORMATS.get(language_code, LOCALE_FORMATS['en'])
        date_format = locale_format.get('date', '%m/%d/%Y')
        
        return date_obj.strftime(date_format)
    
    @staticmethod
    def format_currency(amount: Decimal, language_code: str = None) -> str:
        """
        Format currency according to locale.
        
        Args:
            amount: Amount to format
            language_code: Language code (default: current)
            
        Returns:
            Formatted currency string
        """
        if language_code is None:
            language_code = I18nService.get_current_language()
        
        locale = LOCALE_FORMATS.get(language_code, LOCALE_FORMATS['en'])
        currency = locale.get('currency', '$')
        decimal_sep = locale.get('decimal', '.')
        thousand_sep = locale.get('thousand', ',')
        
        # Format number
        amount_str = str(abs(amount))
        if '.' in amount_str:
            integer, decimal = amount_str.split('.')
        else:
            integer, decimal = amount_str, '00'
        
        # Add thousand separators
        integer_formatted = ''
        for i, digit in enumerate(reversed(integer)):
            if i > 0 and i % 3 == 0:
                integer_formatted = thousand_sep + integer_formatted
            integer_formatted = digit + integer_formatted
        
        # Format with decimal separator
        formatted = f"{integer_formatted}{decimal_sep}{decimal[:2]}"
        
        # Add currency and sign
        if amount < 0:
            formatted = f"-{currency}{formatted}"
        else:
            formatted = f"{currency}{formatted}"
        
        return formatted
    
    @staticmethod
    def format_number(number: float, language_code: str = None, decimals: int = 2) -> str:
        """
        Format number according to locale.
        
        Args:
            number: Number to format
            language_code: Language code (default: current)
            decimals: Decimal places
            
        Returns:
            Formatted number string
        """
        if language_code is None:
            language_code = I18nService.get_current_language()
        
        locale = LOCALE_FORMATS.get(language_code, LOCALE_FORMATS['en'])
        decimal_sep = locale.get('decimal', '.')
        thousand_sep = locale.get('thousand', ',')
        
        # Format number
        formatted = f"{number:,.{decimals}f}"
        
        # Replace separators
        formatted = formatted.replace(',', 'TEMP')  # Temporary replacement
        formatted = formatted.replace('.', decimal_sep)
        formatted = formatted.replace('TEMP', thousand_sep)
        
        return formatted
    
    @staticmethod
    def get_translation_context() -> Dict[str, Any]:
        """
        Get context for template translations.
        
        Returns:
            dict with i18n context
        """
        current_lang = I18nService.get_current_language()
        
        return {
            'CURRENT_LANGUAGE': current_lang,
            'CURRENT_LANGUAGE_NAME': SUPPORTED_LANGUAGES[current_lang]['name'],
            'AVAILABLE_LANGUAGES': SUPPORTED_LANGUAGES,
            'IS_RTL': I18nService.is_rtl(),
            'TEXT_DIRECTION': 'rtl' if I18nService.is_rtl() else 'ltr',
        }


class LanguageMiddleware:
    """
    Middleware for handling language switching.
    
    Supports:
    - Language from URL parameter (?lang=es)
    - Language from user preference (if authenticated)
    - Language from session
    - Language from browser Accept-Language header
    - Default language
    """
    
    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request and set language."""
        # Check URL parameter
        lang = request.GET.get('lang')
        if lang and lang in SUPPORTED_LANGUAGES:
            activate(lang)
            request.session['language'] = lang
            request.LANGUAGE_CODE = lang
        
        # Check session
        elif 'language' in request.session:
            lang = request.session['language']
            if lang in SUPPORTED_LANGUAGES:
                activate(lang)
                request.LANGUAGE_CODE = lang
        
        # Check user preference
        elif request.user.is_authenticated:
            if hasattr(request.user, 'language_preference'):
                lang = request.user.language_preference
                if lang in SUPPORTED_LANGUAGES:
                    activate(lang)
                    request.LANGUAGE_CODE = lang
        
        # Check Accept-Language header
        else:
            accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
            lang = accept_lang.split(',')[0].split('-')[0]
            if lang in SUPPORTED_LANGUAGES:
                activate(lang)
                request.LANGUAGE_CODE = lang
        
        response = self.get_response(request)
        return response


class TranslationHelper:
    """Helper functions for translations."""
    
    @staticmethod
    def get_translated_choices(choices: list, language_code: str = None) -> list:
        """
        Get translated choices for forms.
        
        Args:
            choices: Original choices list
            language_code: Language code (default: current)
            
        Returns:
            list of translated choices
        """
        translated = []
        for value, label in choices:
            # In production, would look up translation
            translated.append((value, str(label)))
        return translated
    
    @staticmethod
    def get_translated_field_errors(errors: Dict, language_code: str = None) -> Dict:
        """
        Get translated form field errors.
        
        Args:
            errors: Form errors dict
            language_code: Language code (default: current)
            
        Returns:
            dict of translated errors
        """
        translated_errors = {}
        for field, error_list in errors.items():
            translated_errors[field] = [
                str(error) for error in error_list
            ]
        return translated_errors


def translate_required(required_languages: list = None):
    """
    Decorator to ensure required languages are set.
    
    Usage:
        @translate_required(required_languages=['en', 'es'])
        def my_view(request):
            pass
    
    Args:
        required_languages: List of required language codes
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            current_lang = I18nService.get_current_language()
            
            if required_languages and current_lang not in required_languages:
                I18nService.set_language(required_languages[0])
            
            return func(request, *args, **kwargs)
        
        return wrapper
    return decorator
