from django.urls import path

from . import views

app_name = 'voucher_config'

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('select/', views.select_voucher_type, name='select'),
    path('new/<slug:voucher_code>/', views.VoucherEntryView.as_view(), name='new'),
    path('lines/add/', views.lines_add, name='lines_add'),
    path('lines/add-generic/', views.add_line_generic, name='lines_add_generic'),
    path('recalc/', views.recalc, name='recalc'),
    path('validate/', views.validate, name='validate'),
    path('save/', views.save_draft, name='save'),
    path('post/', views.post_voucher, name='post'),
    path('status/', views.status, name='status'),
]
