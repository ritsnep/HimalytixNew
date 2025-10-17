from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import reverse
from accounting.views.journal_entry_view import JournalEntryView
from accounting.forms import JournalLineFormSet
from usermanagement.models import Organization, CustomUser
from accounting.models import ChartOfAccount, Journal, JournalLine, AccountingPeriod, JournalType
from decimal import Decimal
from django.utils import timezone

class Command(BaseCommand):
    help = 'Tests core UI interactions in the journal entry view (Add Row, Auto-Balance, Row Details, Totals Update).'

    def handle(self, *args, **options):
        self.stdout.write("Starting UI interactions test...")

        try:
            organization = Organization.objects.get(name="TestCorp")
            user = CustomUser.objects.get(username="testuser")
            cash_account = ChartOfAccount.objects.get(organization=organization, account_code='1010')
            sales_revenue_account = ChartOfAccount.objects.get(organization=organization, account_code='4010')
            expense_account = ChartOfAccount.objects.get(organization=organization, account_code='5010')
            journal_type, _ = JournalType.objects.get_or_create(
                organization=organization,
                code="GEN",
                defaults={'name': 'General Journal', 'auto_numbering_prefix': 'GJ'}
            )
            accounting_period = AccountingPeriod.objects.get(fiscal_year__organization=organization, status='open')

        except (Organization.DoesNotExist, CustomUser.DoesNotExist, ChartOfAccount.DoesNotExist, JournalType.DoesNotExist, AccountingPeriod.DoesNotExist) as e:
            self.stderr.write(self.style.ERROR(f"Test environment not set up properly: {e}"))
            self.stderr.write(self.style.NOTICE("Please run 'python manage.py setup_test_environment' first."))
            return

        factory = RequestFactory()

        # Test 1: Add Row
        self.stdout.write("\n--- Testing Add Row ---")
        # Simulate an initial formset with one empty row
        initial_formset_data = {
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '1',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-account': '',
            'lines-0-description': '',
            'lines-0-debit_amount': '',
            'lines-0-credit_amount': '',
        }
        add_row_url = reverse('accounting:journal_add_line')
        request = factory.post(add_row_url, initial_formset_data, HTTP_HX_REQUEST='true')
        request.user = user
        request.organization = organization
        response = JournalEntryView().dispatch(request, handler='add_journal_row')

        if response.status_code == 200 and 'id_lines-1-account' in response.content.decode():
            self.stdout.write(self.style.SUCCESS("Add Row test passed: New row HTML received."))
        else:
            self.stderr.write(self.style.ERROR(f"Add Row test failed. Status: {response.status_code}, Content: {response.content.decode()}"))

        # Test 2: Auto-Balance
        self.stdout.write("\n--- Testing Auto-Balance ---")
        # Create a journal with an imbalance
        journal = Journal.objects.create(
            organization=organization,
            journal_type=journal_type,
            period=accounting_period,
            journal_date=timezone.now().date(),
            description="Test auto-balance",
            currency_code="USD",
            exchange_rate=Decimal('1.00'),
            total_debit=Decimal('0'),
            total_credit=Decimal('0'),
            created_by=user
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=0,
            account=cash_account,
            description="Cash received",
            debit_amount=Decimal('100.00'),
            credit_amount=Decimal('0.00'),
            currency_code="USD",
            exchange_rate=Decimal('1.00')
        )
        # Simulate form data for auto-balance
        auto_balance_data = {
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '1',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-id': journal.lines.first().pk,
            'lines-0-account': cash_account.pk,
            'lines-0-description': 'Cash received',
            'lines-0-debit_amount': '100.00',
            'lines-0-credit_amount': '0.00',
            'lines-0-currency_code': 'USD',
            'lines-0-exchange_rate': '1.00',
        }
        auto_balance_url = reverse('accounting:journal_entry') # Placeholder, as there is no direct replacement
        request = factory.post(auto_balance_url, auto_balance_data, HTTP_HX_REQUEST='true')
        request.user = user
        request.organization = organization
        response = JournalEntryView().dispatch(request, handler='auto_balance_entry')

        if response.status_code == 200 and 'Auto-balancing entry' in response.content.decode() and 'id="totals-section"' in response.content.decode():
            self.stdout.write(self.style.SUCCESS("Auto-Balance test passed: Balancing entry and updated totals received."))
        else:
            self.stderr.write(self.style.ERROR(f"Auto-Balance test failed. Status: {response.status_code}, Content: {response.content.decode()}"))
        
        # Clean up the created journal for auto-balance test
        journal.delete()

        # Test 3: Row Details (Side Panel Update)
        self.stdout.write("\n--- Testing Row Details (Side Panel Update) ---")
        # Create a dummy journal and line for testing row details
        journal_for_detail = Journal.objects.create(
            organization=organization,
            journal_type=journal_type,
            period=accounting_period,
            journal_date=timezone.now().date(),
            description="Test row detail",
            currency_code="USD",
            exchange_rate=Decimal('1.00'),
            total_debit=Decimal('0'),
            total_credit=Decimal('0'),
            created_by=user
        )
        line_for_detail = JournalLine.objects.create(
            journal=journal_for_detail,
            line_number=0,
            account=expense_account,
            description="AWS bill",
            debit_amount=Decimal('500.00'),
            credit_amount=Decimal('0.00'),
            currency_code="USD",
            exchange_rate=Decimal('1.00')
        )

        row_detail_url = reverse('accounting:journal_entry') # Placeholder, as there is no direct replacement
        request = factory.get(row_detail_url, {
            'lines-0-account': expense_account.account_code,
            'lines-0-description': 'AWS bill',
            'lines-0-debit': '500.00',
            'lines-0-credit': '0.00'
        }, HTTP_HX_REQUEST='true')
        request.user = user
        request.organization = organization
        response = JournalEntryView().dispatch(request, handler='journal_row_detail', line_index=0)

        if response.status_code == 200 and 'AWS bill' in response.content.decode() and 'Account Information' in response.content.decode():
            self.stdout.write(self.style.SUCCESS("Row Details test passed: Side panel updated with correct info."))
        else:
            self.stderr.write(self.style.ERROR(f"Row Details test failed. Status: {response.status_code}, Content: {response.content.decode()}"))
        
        # Clean up the created journal for row detail test
        journal_for_detail.delete()

        # Test 4: Real-time Totals Update (validate_journal_line)
        self.stdout.write("\n--- Testing Real-time Totals Update ---")
        # Simulate form data with some entries
        totals_update_data = {
            'lines-TOTAL_FORMS': '2',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-account': cash_account.pk,
            'lines-0-description': 'Initial cash',
            'lines-0-debit_amount': '200.00',
            'lines-0-credit_amount': '0.00',
            'lines-0-currency_code': 'USD',
            'lines-0-exchange_rate': '1.00',
            'lines-1-account': sales_revenue_account.pk,
            'lines-1-description': 'Sales',
            'lines-1-debit_amount': '0.00',
            'lines-1-credit_amount': '150.00',
            'lines-1-currency_code': 'USD',
            'lines-1-exchange_rate': '1.00',
        }
        totals_update_url = reverse('accounting:validate_journal')
        request = factory.post(totals_update_url, totals_update_data, HTTP_HX_REQUEST='true')
        request.user = user
        request.organization = organization
        response = JournalEntryView().dispatch(request, handler='validate_journal_line')

        response_content = response.content.decode()
        if response.status_code == 200 and 'Debit: 200.00' in response_content and 'Credit: 150.00' in response_content and 'Imbalance: 50.00' in response_content:
            self.stdout.write(self.style.SUCCESS("Real-time Totals Update test passed: Totals and imbalance updated correctly."))
        else:
            self.stderr.write(self.style.ERROR(f"Real-time Totals Update test failed. Status: {response.status_code}, Content: {response_content}"))

        self.stdout.write("\nUI interactions test complete.")