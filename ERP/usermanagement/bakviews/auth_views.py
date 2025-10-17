from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import RedirectView
from django.contrib.auth import logout

class CustomLoginView(LoginView):
    template_name = 'usermanagement/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('dashboard')

    def get_success_url(self):
        return self.success_url

class LogoutView(RedirectView):
    url = reverse_lazy('login')

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs) 