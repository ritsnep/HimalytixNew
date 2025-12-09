from django.test import Client
from django.contrib.auth import get_user_model
from usermanagement.models import Organization

User = get_user_model()
client = Client()
user = User.objects.filter(username='admin').first()
if user:
    client.force_login(user)
resp = client.get('/pos/')
print('status', resp.status_code)
print(resp.content[:500])
