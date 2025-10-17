import os
import django
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from accounting.forms import JournalLineFormSet
from usermanagement.models import Organization, CustomUser
from accounting.models import ChartOfAccount

class Command(BaseCommand):
    help = 'Tests the "Paste from Excel" functionality in the journal entry view.'

    def handle(self, *args, **options):
        self.stdout.write("Starting 'Paste from Excel' test...")

        # 1. Fetch test data
        try:
            organization = Organization.objects.get(name="TestCorp")
            user = CustomUser.objects.get(username="testuser")
            account1 = ChartOfAccount.objects.get(organization=organization, account_code='1010')
            account2 = ChartOfAccount.objects.get(organization=organization, account_code='5010')
        except (Organization.DoesNotExist, CustomUser.DoesNotExist, ChartOfAccount.DoesNotExist) as e:
            self.stderr.write(self.style.ERROR(f"Test environment not set up properly: {e}"))
            self.stderr.write(self.style.NOTICE("Please run 'python manage.py setup_test_environment' first."))
            return

        # 2. Prepare sample data
        rows_data = [
            [account1.pk, 'Cash Payment for Supplies', '150.00', '0'],
            [account2.pk, 'Office Supplies', '0', '150.00']
        ]

        # 3. Simulate a POST request to populate the formset
        factory = RequestFactory()
        formset_data = {
            'lines-TOTAL_FORMS': len(rows_data),
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
        }

        for i, row_data in enumerate(rows_data):
            formset_data[f'lines-{i}-account'] = row_data[0]
            formset_data[f'lines-{i}-description'] = row_data[1]
            formset_data[f'lines-{i}-debit_amount'] = row_data[2]
            formset_data[f'lines-{i}-credit_amount'] = row_data[3]
            # Add defaults for fields not in the form but required by the model's form representation
            formset_data[f'lines-{i}-currency_code'] = 'USD'
            formset_data[f'lines-{i}-exchange_rate'] = '1'


        request = factory.post('/accounting/journal-entry/', formset_data)
        request.user = user
        
        # 4. Create and validate the formset
        formset = JournalLineFormSet(request.POST, prefix='lines', form_kwargs={'organization': organization})

        if formset.is_valid():
            self.stdout.write(self.style.SUCCESS("Formset is valid after paste simulation."))
            for form in formset:
                self.stdout.write(f"  - Line {form.cleaned_data['account']}: Debit={form.cleaned_data.get('debit_amount', 0)}, Credit={form.cleaned_data.get('credit_amount', 0)}")
        else:
            self.stderr.write(self.style.ERROR("Formset is invalid after paste simulation."))
            for form in formset:
                if form.errors:
                    self.stderr.write(f"  - Line {form.prefix}: {form.errors.as_json()}")
            if formset.non_form_errors():
                self.stderr.write(f"  - Non-form errors: {formset.non_form_errors().as_json()}")

        self.stdout.write("'Paste from Excel' test complete.")