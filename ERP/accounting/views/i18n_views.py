"""
i18n Views - Language Switching and Management - Phase 3 Task 6

Views for:
- Language switching
- Language preferences
- Locale formatting display
"""

from django.views.generic import View, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
import logging

from accounting.services.i18n_service import (
    I18nService,
    SUPPORTED_LANGUAGES,
    LOCALE_FORMATS
)
from accounting.models import Organization, User
from accounting.mixins import UserOrganizationMixin

logger = logging.getLogger(__name__)


class LanguageSwitchView(View):
    """
    Handle language switching.
    
    Supports:
    - GET: Redirect to previous page with language set
    - POST (AJAX): Return language data
    """
    
    http_method_names = ['get', 'post']
    
    def get(self, request):
        """Switch language and redirect."""
        language_code = request.GET.get('lang', 'en')
        
        if language_code not in SUPPORTED_LANGUAGES:
            language_code = 'en'
        
        # Set language
        I18nService.set_language(language_code)
        request.session['language'] = language_code
        
        logger.info(f'User {request.user} switched to language: {language_code}')
        
        # Redirect to previous page or home
        next_url = request.GET.get('next', '/')
        response = redirect(next_url)
        response.set_cookie('language', language_code)
        
        return response
    
    def post(self, request):
        """Get language info (AJAX)."""
        language_code = request.POST.get('lang', 'en')
        
        if language_code not in SUPPORTED_LANGUAGES:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid language code'
            }, status=400)
        
        # Set language
        I18nService.set_language(language_code)
        request.session['language'] = language_code
        
        # Get language info
        lang_info = I18nService.get_language_info(language_code)
        
        return JsonResponse({
            'status': 'success',
            'language': language_code,
            'language_name': lang_info['name'],
            'is_rtl': lang_info['rtl'],
            'message': f'Language changed to {lang_info["name"]}'
        })


class LanguageListView(LoginRequiredMixin, TemplateView):
    """
    Display available languages and current language.
    
    Provides:
    - Current language info
    - List of available languages
    - Language statistics
    """
    
    template_name = 'accounting/i18n/language_list.html'
    
    def get_context_data(self, **kwargs):
        """Add language data to context."""
        context = super().get_context_data(**kwargs)
        
        current_lang = I18nService.get_current_language()
        
        # Build language list with details
        languages = []
        for code, info in SUPPORTED_LANGUAGES.items():
            languages.append({
                'code': code,
                'name': info['name'],
                'region': info['region'],
                'rtl': info['rtl'],
                'is_current': code == current_lang,
                'locale_format': LOCALE_FORMATS.get(code, LOCALE_FORMATS['en'])
            })
        
        context['current_language'] = current_lang
        context['current_language_info'] = I18nService.get_language_info()
        context['languages'] = languages
        context['is_rtl'] = I18nService.is_rtl()
        context['total_languages'] = len(languages)
        
        return context


class LocaleFormatView(LoginRequiredMixin, View):
    """
    Get locale formatting for current language.
    
    Returns:
    - Date format
    - Currency format
    - Number format
    - Time format
    """
    
    http_method_names = ['get']
    
    def get(self, request):
        """Get locale format info."""
        language_code = request.GET.get('lang') or I18nService.get_current_language()
        
        if language_code not in LOCALE_FORMATS:
            language_code = 'en'
        
        locale = LOCALE_FORMATS[language_code]
        
        # Format examples
        from decimal import Decimal
        from datetime import datetime
        
        examples = {
            'date_format': locale['date'],
            'date_example': I18nService.format_date(datetime.now(), language_code),
            'currency_format': I18nService.format_currency(Decimal('1234.56'), language_code),
            'number_format': I18nService.format_number(1234.56, language_code),
            'thousand_separator': locale['thousand'],
            'decimal_separator': locale['decimal'],
            'currency_symbol': locale['currency'],
        }
        
        return JsonResponse({
            'status': 'success',
            'language': language_code,
            'locale': locale,
            'examples': examples
        })


class UserLanguagePreferenceView(LoginRequiredMixin, View):
    """
    Set user's language preference.
    
    Stores preference on user account for persistence.
    """
    
    http_method_names = ['post']
    
    def post(self, request):
        """Set user language preference."""
        language_code = request.POST.get('lang', 'en')
        
        if language_code not in SUPPORTED_LANGUAGES:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid language code'
            }, status=400)
        
        try:
            # Update user preference
            user = request.user
            user.language_preference = language_code
            user.save()
            
            # Set session language
            I18nService.set_language(language_code)
            request.session['language'] = language_code
            
            logger.info(f'User {user} set language preference to: {language_code}')
            
            return JsonResponse({
                'status': 'success',
                'message': f'Language preference set to {SUPPORTED_LANGUAGES[language_code]["name"]}'
            })
        
        except Exception as e:
            logger.error(f'Error setting language preference: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class OrganizationLanguageSettingView(UserOrganizationMixin, View):
    """
    Set organization's default language.
    
    Organization admins can set default language for all users.
    """
    
    http_method_names = ['post']
    
    def post(self, request):
        """Set organization language."""
        org = self.get_user_organization()
        language_code = request.POST.get('lang', 'en')
        
        if language_code not in SUPPORTED_LANGUAGES:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid language code'
            }, status=400)
        
        try:
            # Update organization setting
            org.default_language = language_code
            org.save()
            
            logger.info(f'Organization {org.name} set default language to: {language_code}')
            
            return JsonResponse({
                'status': 'success',
                'message': f'Organization language set to {SUPPORTED_LANGUAGES[language_code]["name"]}'
            })
        
        except Exception as e:
            logger.error(f'Error setting organization language: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class TranslationStatisticsView(LoginRequiredMixin, TemplateView):
    """
    Display translation statistics and coverage.
    
    Shows:
    - Translation completion percentage per language
    - Missing translations
    - Recent translation updates
    """
    
    template_name = 'accounting/i18n/translation_stats.html'
    
    def get_context_data(self, **kwargs):
        """Add translation statistics to context."""
        context = super().get_context_data(**kwargs)
        
        # In production, would query translation status from gettext
        languages_stats = []
        
        for code, info in SUPPORTED_LANGUAGES.items():
            languages_stats.append({
                'code': code,
                'name': info['name'],
                'coverage': 95 + (hash(code) % 5),  # Mock data
                'last_updated': timezone.now(),
                'strings_translated': 450 + (hash(code) % 100),
                'total_strings': 500,
            })
        
        context['languages_stats'] = languages_stats
        context['average_coverage'] = sum(s['coverage'] for s in languages_stats) / len(languages_stats)
        
        return context


class RTLSupportView(LoginRequiredMixin, TemplateView):
    """
    Display RTL (Right-to-Left) support information.
    
    Shows:
    - RTL layout detection
    - RTL language list
    - RTL CSS framework information
    """
    
    template_name = 'accounting/i18n/rtl_support.html'
    
    def get_context_data(self, **kwargs):
        """Add RTL information to context."""
        context = super().get_context_data(**kwargs)
        
        current_lang = I18nService.get_current_language()
        is_rtl = I18nService.is_rtl()
        
        # Get RTL languages
        rtl_languages = [
            (code, info) for code, info in SUPPORTED_LANGUAGES.items()
            if info['rtl']
        ]
        
        context['is_rtl'] = is_rtl
        context['current_language'] = current_lang
        context['rtl_languages'] = rtl_languages
        context['text_direction'] = 'rtl' if is_rtl else 'ltr'
        context['margin_start'] = 'margin-right' if is_rtl else 'margin-left'
        context['margin_end'] = 'margin-left' if is_rtl else 'margin-right'
        context['padding_start'] = 'padding-right' if is_rtl else 'padding-left'
        context['padding_end'] = 'padding-left' if is_rtl else 'padding-right'
        
        return context
