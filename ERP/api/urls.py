from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ChartOfAccountViewSet,
    JournalViewSet,
    JournalImportView,
    CurrencyExchangeRateViewSet,
    TrialBalanceView,
)

router = DefaultRouter()
router.register(r'chart-of-accounts', ChartOfAccountViewSet, basename='chart-of-accounts')
router.register(r'journals', JournalViewSet, basename='journals')
router.register(r'currencies/exchange-rates', CurrencyExchangeRateViewSet, basename='exchange-rates')

urlpatterns = [
    path('', include(router.urls)),
    path('journal-import/', JournalImportView.as_view(), name='journal-import'),
    path('trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),
]