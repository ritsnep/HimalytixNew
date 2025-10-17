from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse

class SaveFormOnSessionExpiryMiddleware:
    """
    Middleware to catch session expiry (401/CSRF), save POST data, and redirect to login.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            # If response is 401 (unauthenticated), save POST data
            if response.status_code == 401 and request.method == "POST":
                request.session['pending_form_data'] = {
                    'path': request.path,
                    'data': request.POST.dict(),
                }
            return response
        except PermissionDenied as e:
            # Handle CSRF/session expiry
            if request.method == "POST":
                request.session['pending_form_data'] = {
                    'path': request.path,
                    'data': request.POST.dict(),
                }
                if request.headers.get('HX-Request') == 'true':
                    return JsonResponse({'redirect': reverse('account_login')}, status=401)
                else:
                    return redirect(f"{reverse('account_login')}?next={request.path}")
            raise e 