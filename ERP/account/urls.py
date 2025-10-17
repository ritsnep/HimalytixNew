from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('security/', views.security, name='security'),
    path('billing/', views.billing, name='billing'),
]