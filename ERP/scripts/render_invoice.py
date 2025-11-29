from django.test import RequestFactory
from django.contrib.auth import get_user_model
from accounting.views.ird_invoice_views import SalesInvoiceDetailView
from accounting.models import SalesInvoice
from django.contrib.sessions.middleware import SessionMiddleware

OUT = 'scripts/invoice_1.html'

User = get_user_model()
rf = RequestFactory()
req = rf.get('/')

# Use an existing superuser or create one for rendering
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.create(username='test_superuser', is_superuser=True, is_staff=True)
    user.set_password('x')
    user.save()
    print('Created test superuser:', user.username)
else:
    print('Using superuser:', user.username)

req.user = user
# Attach session to the request so context processors that use session work
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(req)
req.session.save()

from django.test import Client
from django.contrib.auth import get_user_model
from accounting.models import SalesInvoice

OUT = 'scripts/invoice_1.html'

User = get_user_model()
client = Client()

# Use an existing superuser or create one for rendering
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.create(username='test_superuser', is_superuser=True, is_staff=True)
    user.set_password('x')
    user.save()
    print('Created test superuser:', user.username)
else:
    print('Using superuser:', user.username)

client.force_login(user)

invoice_id = 1
url = f'/accounting/invoices/{invoice_id}/'
resp = client.get(url)
if resp.status_code != 200:
    print('GET', url, 'returned', resp.status_code)

with open(OUT, 'wb') as f:
    f.write(resp.content)

print('Saved invoice HTML to', OUT)
