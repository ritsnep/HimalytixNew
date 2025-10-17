from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import reverse
from accounting.views.journal_entry_view import JournalEntryView
from usermanagement.models import Organization, CustomUser
from accounting.models import ChartOfAccount

class Command(BaseCommand):
    help = 'Tests the real-time account search feature in the journal entry view.'

    def handle(self, *args, **options):
        self.stdout.write("Starting account search test...")

        # 1. Fetch test data
        try:
            organization = Organization.objects.get(name="TestCorp")
            user = CustomUser.objects.get(username="testuser")
        except (Organization.DoesNotExist, CustomUser.DoesNotExist) as e:
            self.stderr.write(self.style.ERROR(f"Test environment not set up properly: {e}"))
            self.stderr.write(self.style.NOTICE("Please run 'python manage.py setup_test_environment' first."))
            return

        # 2. Simulate a GET request to the search endpoint
        factory = RequestFactory()
        search_query = "Cash"
        url = reverse('accounting:htmx_lookup', kwargs={'model_name': 'Account'})
        request = factory.get(url, {'q': search_query, 'index': 0}, HTTP_HX_REQUEST='true')
        request.user = user

        # Attach the organization to the request, similar to how the UserOrganizationMixin would
        request.organization = organization

        # 3. Call the view's HTMX handler directly
        view = JournalEntryView()
        view.request = request
        view.kwargs = {'handler': 'search_accounts'}
        
        # The dispatch method in the view will call the appropriate htmx handler
        response = view.dispatch(request, handler='search_accounts')

        # 4. Verify the response
        response_content = response.content.decode('utf-8')
        if response.status_code == 200 and "<strong>Cash</strong> (1010)" in response_content:
            self.stdout.write(self.style.SUCCESS("Account search test passed."))
            self.stdout.write(f"  - Found '<strong>Cash</strong> (1010)' in the search results for query '{search_query}'.")
        else:
            self.stderr.write(self.style.ERROR("Account search test failed."))
            self.stderr.write(f"  - Status Code: {response.status_code}")
            self.stderr.write(f"  - Response: {response_content}")

        self.stdout.write("Account search test complete.")