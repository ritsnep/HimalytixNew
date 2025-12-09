from django.template.loader import get_template
from django.template import RequestContext
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from usermanagement.models import Organization

User = get_user_model()
factory = RequestFactory()
request = factory.get('/pos/')
user = User.objects.filter(username='admin').first()
org = Organization.objects.first()
if user:
    request.user = user
request.organization = org

template = get_template('pos/pos.html')
ctx = RequestContext(request, {'cart': None, 'pos_settings': None})
content = template.render(ctx)
print('Rendered length', len(content))
