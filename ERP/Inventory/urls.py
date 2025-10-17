from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.products, name='products'),
    path('categories/', views.categories, name='categories'),
    path('warehouses/', views.warehouses, name='warehouses'),
    path('stock-movements/', views.stock_movements, name='stock_movements'),
]
