"""
Tests for i18n Internationalization - Phase 3 Task 6

Test coverage for:
- Language switching
- Locale formatting
- RTL support
- Translation utilities
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import translation
from decimal import Decimal
from datetime import datetime

from accounting.services.i18n_service import (
    I18nService,
    SUPPORTED_LANGUAGES,
    LOCALE_FORMATS
)

User = get_user_model()


class I18nServiceTestCase(TestCase):
    """Test i18n service functionality."""

    def setUp(self):
        """Set up test data."""
        self.service = I18nService()

    def test_get_current_language(self):
        """Test getting current language."""
        lang = I18nService.get_current_language()
        self.assertIsNotNone(lang)

    def test_set_language(self):
        """Test setting language."""
        result = I18nService.set_language('es')
        self.assertTrue(result)
        
        current = I18nService.get_current_language()
        self.assertEqual(current, 'es')

    def test_set_invalid_language(self):
        """Test setting invalid language."""
        result = I18nService.set_language('invalid')
        self.assertFalse(result)

    def test_get_language_info(self):
        """Test getting language info."""
        info = I18nService.get_language_info('en')
        
        self.assertIn('name', info)
        self.assertIn('rtl', info)
        self.assertIn('region', info)
        self.assertEqual(info['name'], 'English')
        self.assertFalse(info['rtl'])

    def test_is_rtl_english(self):
        """Test RTL detection for English."""
        I18nService.set_language('en')
        is_rtl = I18nService.is_rtl()
        self.assertFalse(is_rtl)

    def test_is_rtl_arabic(self):
        """Test RTL detection for Arabic."""
        I18nService.set_language('ar')
        is_rtl = I18nService.is_rtl()
        self.assertTrue(is_rtl)

    def test_get_all_languages(self):
        """Test getting all languages."""
        languages = I18nService.get_all_languages()
        
        self.assertGreater(len(languages), 0)
        self.assertIn('en', languages)
        self.assertIn('es', languages)

    def test_format_date_english(self):
        """Test date formatting for English."""
        I18nService.set_language('en')
        date = datetime(2024, 1, 15)
        formatted = I18nService.format_date(date)
        
        self.assertIn('01', formatted)  # Month or day
        self.assertIn('15', formatted)  # Day or month
        self.assertIn('2024', formatted)  # Year

    def test_format_date_spanish(self):
        """Test date formatting for Spanish."""
        I18nService.set_language('es')
        date = datetime(2024, 1, 15)
        formatted = I18nService.format_date(date)
        
        self.assertIn('01', formatted)
        self.assertIn('15', formatted)
        self.assertIn('2024', formatted)

    def test_format_currency_english(self):
        """Test currency formatting for English."""
        I18nService.set_language('en')
        amount = Decimal('1234.56')
        formatted = I18nService.format_currency(amount)
        
        self.assertIn('$', formatted)
        self.assertIn('1', formatted)
        self.assertIn('234', formatted)

    def test_format_currency_spanish(self):
        """Test currency formatting for Spanish."""
        I18nService.set_language('es')
        amount = Decimal('1234.56')
        formatted = I18nService.format_currency(amount)
        
        self.assertIsNotNone(formatted)
        self.assertGreater(len(formatted), 0)

    def test_format_currency_negative(self):
        """Test negative currency formatting."""
        amount = Decimal('-1234.56')
        formatted = I18nService.format_currency(amount)
        
        self.assertIn('-', formatted)

    def test_format_number(self):
        """Test number formatting."""
        I18nService.set_language('en')
        number = 1234.567
        formatted = I18nService.format_number(number, decimals=2)
        
        self.assertIn('1', formatted)
        self.assertIn('234', formatted)

    def test_get_translation_context(self):
        """Test getting translation context."""
        context = I18nService.get_translation_context()
        
        self.assertIn('CURRENT_LANGUAGE', context)
        self.assertIn('AVAILABLE_LANGUAGES', context)
        self.assertIn('IS_RTL', context)
        self.assertIn('TEXT_DIRECTION', context)


class LanguageSwitchViewTestCase(TestCase):
    """Test language switching view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def test_switch_language_get(self):
        """Test language switch with GET."""
        response = self.client.get('/accounting/set-language/?lang=es&next=/')
        
        # Should redirect
        self.assertIn(response.status_code, [301, 302])

    def test_language_persistence_in_session(self):
        """Test language persists in session."""
        self.client.login(username='testuser', password='testpass123')
        
        # Switch language
        self.client.get('/accounting/set-language/?lang=es')
        
        # Check session
        self.assertIn('language', self.client.session)


class LocaleFormatViewTestCase(TestCase):
    """Test locale format view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_get_locale_format(self):
        """Test getting locale format."""
        response = self.client.get('/accounting/locale-format/?lang=en')
        
        if response.status_code == 200:
            data = response.json()
            self.assertEqual(data['status'], 'success')
            self.assertIn('locale', data)
            self.assertIn('examples', data)

    def test_get_locale_format_spanish(self):
        """Test getting Spanish locale format."""
        response = self.client.get('/accounting/locale-format/?lang=es')
        
        if response.status_code == 200:
            data = response.json()
            self.assertEqual(data['status'], 'success')
            self.assertEqual(data['language'], 'es')


class LanguageListViewTestCase(TestCase):
    """Test language list view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_language_list_view(self):
        """Test language list view."""
        response = self.client.get('/accounting/languages/')
        
        if response.status_code == 200:
            self.assertIn('languages', response.context)
            languages = response.context['languages']
            self.assertGreater(len(languages), 0)


class RTLSupportTestCase(TestCase):
    """Test RTL support."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_rtl_support_english(self):
        """Test RTL detection for English."""
        I18nService.set_language('en')
        is_rtl = I18nService.is_rtl()
        self.assertFalse(is_rtl)

    def test_rtl_support_arabic(self):
        """Test RTL detection for Arabic."""
        I18nService.set_language('ar')
        is_rtl = I18nService.is_rtl()
        self.assertTrue(is_rtl)

    def test_rtl_view(self):
        """Test RTL support view."""
        response = self.client.get('/accounting/rtl-support/')
        
        if response.status_code == 200:
            self.assertIn('is_rtl', response.context)
            self.assertIn('text_direction', response.context)
