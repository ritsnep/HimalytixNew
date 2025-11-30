"""
Analytics Service Tests - Phase 3 Task 8

Comprehensive test coverage for analytics service, views, and reporting functionality.

Test Classes:
    - AnalyticsServiceTestCase: Service calculations and caching
    - FinancialMetricsTestCase: P&L and balance sheet
    - TrendAnalyzerTestCase: Trend analysis and forecasting
    - PerformanceMetricsTestCase: System performance metrics
    - AnalyticsDashboardViewTestCase: Dashboard view rendering
    - FinancialAnalyticsViewTestCase: Financial analysis view
    - AccountAnalyticsViewTestCase: Account analysis view
    - AnalyticsExportTestCase: Export functionality
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, date, timedelta
import json

from accounting.models import (
    Organization, Account, Journal, JournalLine, JournalType,
    AccountingPeriod, FiscalYear
)
from accounting.services.analytics_service import (
    AnalyticsService, FinancialMetrics, TrendAnalyzer, PerformanceMetrics, CacheManager
)

User = get_user_model()


# ============================================================================
# Analytics Service Tests
# ============================================================================

class AnalyticsServiceTestCase(TestCase):
    """Test AnalyticsService calculations and dashboard generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        
        # Create fiscal year and period
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code='FY2025',
            name='Fiscal Year 2025',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31)
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name='January',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        # Create accounts
        self.cash_account = Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code='3000',
            name='Revenue',
            account_type='REVENUE'
        )
        self.expense_account = Account.objects.create(
            organization=self.organization,
            code='4000',
            name='Expenses',
            account_type='EXPENSE'
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code='GJ',
            name='General Journal'
        )
        
        # Create test journal
        self.journal = Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type,
            is_posted=True
        )
        
        # Create journal lines
        JournalLine.objects.create(
            journal=self.journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal('1000.00')
        )
        JournalLine.objects.create(
            journal=self.journal,
            line_number=2,
            account=self.revenue_account,
            credit_amount=Decimal('1000.00')
        )
    
    def test_dashboard_summary_creation(self):
        """Test dashboard summary generation."""
        service = AnalyticsService(self.organization)
        summary = service.get_dashboard_summary(date(2025, 1, 31))
        
        self.assertIn('financial_summary', summary)
        self.assertIn('balance_sheet', summary)
        self.assertIn('cash_position', summary)
        self.assertIn('approval_status', summary)
        self.assertIn('top_accounts', summary)
        self.assertIn('monthly_trend', summary)
    
    def test_financial_overview(self):
        """Test financial overview calculation."""
        service = AnalyticsService(self.organization)
        overview = service.get_financial_overview(date(2025, 1, 31))
        
        self.assertIn('revenue', overview)
        self.assertIn('expenses', overview)
        self.assertIn('net_income', overview)
    
    def test_approval_status(self):
        """Test approval status calculation."""
        service = AnalyticsService(self.organization)
        status = service.get_approval_status()
        
        self.assertIn('pending_count', status)
        self.assertIn('approved_today', status)
        self.assertIn('rejected_today', status)
        self.assertIn('pending_journals', status)
    
    def test_top_accounts_by_activity(self):
        """Test top accounts retrieval by activity."""
        service = AnalyticsService(self.organization)
        top_accounts = service.get_top_accounts(limit=5, by='activity')
        
        self.assertIsInstance(top_accounts, list)
        if top_accounts:
            self.assertIn('id', top_accounts[0])
            self.assertIn('code', top_accounts[0])
            self.assertIn('name', top_accounts[0])
            self.assertIn('activity_count', top_accounts[0])
    
    def test_top_accounts_by_balance(self):
        """Test top accounts retrieval by balance."""
        service = AnalyticsService(self.organization)
        top_accounts = service.get_top_accounts(limit=5, by='balance')
        
        self.assertIsInstance(top_accounts, list)
    
    def test_account_balance_history(self):
        """Test account balance history retrieval."""
        service = AnalyticsService(self.organization)
        history = service.get_account_balance_history(self.cash_account.id, months=12)
        
        self.assertIsInstance(history, list)
        if history:
            self.assertIn('date', history[0])
            self.assertIn('balance', history[0])


# ============================================================================
# Financial Metrics Tests
# ============================================================================

class FinancialMetricsTestCase(TestCase):
    """Test FinancialMetrics calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code='FY2025',
            name='Fiscal Year 2025',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31)
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name='January',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        # Create accounts
        Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
        Account.objects.create(
            organization=self.organization,
            code='2000',
            name='Accounts Payable',
            account_type='LIABILITY'
        )
        Account.objects.create(
            organization=self.organization,
            code='3000',
            name='Revenue',
            account_type='REVENUE'
        )
        Account.objects.create(
            organization=self.organization,
            code='4000',
            name='Expenses',
            account_type='EXPENSE'
        )
    
    def test_financial_summary(self):
        """Test financial summary calculation."""
        metrics = FinancialMetrics(self.organization)
        summary = metrics.get_financial_summary(date(2025, 1, 31))
        
        self.assertIn('revenue', summary)
        self.assertIn('expenses', summary)
        self.assertIn('net_income', summary)
        self.assertIn('revenue_margin', summary)
        self.assertIn('expense_ratio', summary)
    
    def test_balance_sheet(self):
        """Test balance sheet calculation."""
        metrics = FinancialMetrics(self.organization)
        bs = metrics.get_balance_sheet(date(2025, 1, 31))
        
        self.assertIn('assets', bs)
        self.assertIn('liabilities', bs)
        self.assertIn('equity', bs)
        self.assertIn('debt_to_equity', bs)
    
    def test_cash_position(self):
        """Test cash position calculation."""
        metrics = FinancialMetrics(self.organization)
        cash = metrics.get_cash_position(date(2025, 1, 31))
        
        self.assertIn('current_cash', cash)
        self.assertIn('trend', cash)
        self.assertIn('trend_percent', cash)
        self.assertIn('forecast_next_month', cash)


# ============================================================================
# Trend Analyzer Tests
# ============================================================================

class TrendAnalyzerTestCase(TestCase):
    """Test TrendAnalyzer calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        
        # Create accounts
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code='3000',
            name='Revenue',
            account_type='REVENUE'
        )
        self.expense_account = Account.objects.create(
            organization=self.organization,
            code='4000',
            name='Expenses',
            account_type='EXPENSE'
        )
    
    def test_monthly_trend(self):
        """Test monthly trend calculation."""
        analyzer = TrendAnalyzer(self.organization)
        trend = analyzer.get_monthly_trend(months=6)
        
        self.assertEqual(len(trend), 6)
        for month_data in trend:
            self.assertIn('month', month_data)
            self.assertIn('revenue', month_data)
            self.assertIn('expenses', month_data)
            self.assertIn('net_income', month_data)
    
    def test_revenue_forecast(self):
        """Test revenue forecasting."""
        analyzer = TrendAnalyzer(self.organization)
        forecast = analyzer.get_revenue_forecast(months_ahead=3)
        
        self.assertEqual(len(forecast), 3)
        for month_forecast in forecast:
            self.assertIn('month', month_forecast)
            self.assertIn('forecasted_revenue', month_forecast)


# ============================================================================
# Performance Metrics Tests
# ============================================================================

class PerformanceMetricsTestCase(TestCase):
    """Test PerformanceMetrics calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
    
    def test_performance_summary(self):
        """Test performance summary calculation."""
        metrics = PerformanceMetrics(self.organization)
        summary = metrics.get_performance_summary()
        
        self.assertIn('total_records', summary)
        self.assertIn('posting_success_rate', summary)
        self.assertIn('avg_posting_time_ms', summary)
        self.assertIn('cache_hit_rate', summary)


# ============================================================================
# Cache Manager Tests
# ============================================================================

class CacheManagerTestCase(TestCase):
    """Test CacheManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.cache_manager = CacheManager(self.organization.id)
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        key = self.cache_manager.get_key('dashboard_summary', date(2025, 1, 1))
        
        self.assertIn(str(self.organization.id), key)
        self.assertIn('dashboard_summary', key)
        self.assertIn('2025-01-01', key)
    
    def test_cache_key_without_date(self):
        """Test cache key generation without date."""
        key = self.cache_manager.get_key('approval_status')
        
        self.assertIn('approval_status', key)


# ============================================================================
# Analytics Views Tests
# ============================================================================

class AnalyticsDashboardViewTestCase(TestCase):
    """Test AnalyticsDashboardView."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_dashboard_view_requires_login(self):
        """Test dashboard requires authentication."""
        client = Client()
        response = client.get(reverse('analytics:dashboard'))
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_view_loads(self):
        """Test dashboard view loads successfully."""
        response = self.client.get(reverse('analytics:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/dashboard.html')
    
    def test_dashboard_with_date_parameter(self):
        """Test dashboard with custom date."""
        response = self.client.get(
            reverse('analytics:dashboard'),
            {'as_of_date': '2025-01-31'}
        )
        
        self.assertEqual(response.status_code, 200)


class FinancialAnalyticsViewTestCase(TestCase):
    """Test FinancialAnalyticsView."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_financial_view_loads(self):
        """Test financial analysis view loads."""
        response = self.client.get(reverse('analytics:financial'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/financial_analysis.html')
    
    def test_financial_view_context(self):
        """Test financial view has required context."""
        response = self.client.get(reverse('analytics:financial'))
        
        self.assertIn('financial_summary', response.context)
        self.assertIn('balance_sheet', response.context)
        self.assertIn('cash_position', response.context)
        self.assertIn('key_ratios', response.context)


class AccountAnalyticsViewTestCase(TestCase):
    """Test AccountAnalyticsView."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.login(username='testuser', password='testpass123')
        
        self.account = Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
    
    def test_account_analysis_view_loads(self):
        """Test account analysis view loads."""
        response = self.client.get(
            reverse('analytics:account_analysis', args=[self.account.id])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/account_analysis.html')
    
    def test_account_analysis_context(self):
        """Test account analysis view context."""
        response = self.client.get(
            reverse('analytics:account_analysis', args=[self.account.id])
        )
        
        self.assertEqual(response.context['account'], self.account)
        self.assertIn('balance_history', response.context)
        self.assertIn('current_balance', response.context)


# ============================================================================
# Analytics Export Tests
# ============================================================================

class AnalyticsExportTestCase(TestCase):
    """Test export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_export_csv(self):
        """Test exporting analytics as CSV."""
        response = self.client.get(
            reverse('analytics:export'),
            {'format': 'csv', 'report': 'financial'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
    
    def test_export_json(self):
        """Test exporting analytics as JSON."""
        response = self.client.get(
            reverse('analytics:export'),
            {'format': 'json', 'report': 'dashboard'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
