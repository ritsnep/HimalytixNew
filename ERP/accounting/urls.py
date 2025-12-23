from django.urls import path

from accounting.views import purchase_invoice_views as purchase_views

app_name = "accounting"

urlpatterns = [
	path('purchase/new-enhanced/', purchase_views.purchase_invoice_new_enhanced, name='purchase_invoice_new_enhanced'),
	path('purchase/add-line/', purchase_views.purchase_add_line_hx, name='purchase_add_line_hx'),
	path('purchase/remove-line/', purchase_views.purchase_remove_line_hx, name='purchase_remove_line_hx'),
	path('purchase/recalc/', purchase_views.purchase_recalc_hx, name='purchase_recalc_hx'),
	path('purchase/add-payment/', purchase_views.purchase_add_payment_hx, name='purchase_add_payment_hx'),
	path('purchase/remove-payment/', purchase_views.purchase_remove_payment_hx, name='purchase_remove_payment_hx'),
	path('purchase/payment-recalc/', purchase_views.purchase_payment_recalc_hx, name='purchase_payment_recalc_hx'),
	path('purchase/supplier-summary/', purchase_views.purchase_supplier_summary_hx, name='purchase_supplier_summary_hx'),
	path('purchase/apply-order/', purchase_views.purchase_apply_order_hx, name='purchase_apply_order_hx'),
]
