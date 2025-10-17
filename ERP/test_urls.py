from django.urls import include, path

urlpatterns = [
    path('accounting/', include(('accounting.urls', 'accounting'), namespace='accounting')),
]