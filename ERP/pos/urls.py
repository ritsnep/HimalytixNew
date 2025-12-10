from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.pos_home, name='pos_home'),
    path('api/cart/add/', views.add_to_cart, name='add_to_cart'),
    path('api/cart/update/', views.update_cart_item, name='update_cart_item'),
    path('api/cart/remove/', views.remove_cart_item, name='remove_cart_item'),
    path('api/cart/clear/', views.clear_cart, name='clear_cart'),
    path('api/cart/hold/', views.hold_cart, name='hold_cart'),
    path('api/cart/resume/', views.resume_cart, name='resume_cart'),
    path('api/cart/meta/', views.update_cart_meta, name='update_cart_meta'),
    path('api/cart/held/', views.list_held_carts, name='list_held_carts'),
    path('api/cart/', views.get_cart, name='get_cart'),
    path('api/checkout/', views.checkout, name='checkout'),
    path('api/products/search/', views.search_products, name='search_products'),
    path('api/products/top/', views.top_products, name='top_products'),
    path('api/customers/search/', views.search_customers, name='search_customers'),
]
