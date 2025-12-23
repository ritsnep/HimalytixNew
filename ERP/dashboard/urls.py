"""dason URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from usermanagement.forms import DasonLoginForm
from dashboard import views
from dashboard import health
from django.contrib.auth.decorators import login_required
from .views import CustomLoginView
from django.conf import settings
from django.conf.urls.static import static
from .views import service_worker
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # ==========================================================================
    # HEALTH CHECK ENDPOINTS (No authentication required)
    # ==========================================================================
    path('health/', health.health_check, name='health'),
    path('health/ready/', health.health_ready, name='health-ready'),
    path('health/live/', health.health_live, name='health-live'),
    path('maintenance/status/', views.maintenance_status, name='maintenance_status'),
    path('maintenance/stream/', views.maintenance_stream, name='maintenance_stream'),
    
    # ==========================================================================
    # SILK QUERY PROFILER (Development only - protect in production!)
    # ==========================================================================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Metrics endpoint
    path('', include('django_prometheus.urls')),  # Adds /metrics endpoint
    
    # Dashboard
    path('manage/', include(('usermanagement.urls', 'usermanagement'), namespace='usermanagement')),
    path('account/', include('account.urls')),
    path('inventory/', include('inventory.urls')),
    path('billing/', include('billing.urls', namespace='billing')),
    path('purchasing/', include(('purchasing.urls', 'purchasing'), namespace='purchasing')),
    path('ird/', include('ird_integration.urls', namespace='ird_integration')),
    path('service-management/', include('service_management.urls', namespace='service_management')),
    
    # Include accounting app with explicit namespace for reverse('accounting:*') lookups
    path('accounting/', include(('accounting.urls', 'accounting'), namespace='accounting')),
    path('voucher-config/', include(('voucher_config.urls', 'voucher_config'), namespace='voucher_config')),
    path('vouchers/sales-invoice/', include('vouchers.sales_invoice.urls', namespace='vouchers_sales_invoice')),
    path('print/', include('printing.urls')),
    path('pos/', include(('pos.urls', 'pos'), namespace='pos')),
    path('backups/', include(('backups.urls', 'backups'), namespace='backups')),
    # path('accounting/', include('accounting.new_journal_entry_urls')),
    # path('admin/', admin.site.urls),
    path("accounts/login/", CustomLoginView.as_view(), name="account_login"),
    path('accounts/', include('allauth.urls')),  # Important!
    path('forms_designer/', include('forms_designer.urls')),
    path('reports/', include(('reporting.urls', 'reporting'), namespace='reporting')),
    path('api/lpg/', include('lpg_vertical.urls')),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("settings", views.Settings.as_view(), name="settings"),
    # # Custum change password done page redirect
    # path(
    #     "account/password/change/",
    #     login_required(views.MyPasswordChangeView.as_view()),
    #     name="account_change_password",
    # ),
    # # Custum set password done page redirect
    # path(
    #     "account/password/set/",
    #     login_required(views.MyPasswordSetView.as_view()),
    #     name="account_set_password",
    # ),
    # Apps
    path("apps/", include("apps.urls")),
    # Components
    path("components/", include("components.urls")),
    # Pages
    path("pages/", include("pages.urls")),
    # # Include the allauth and 2FA urls from their respective packages.
    # path("/", include("allauth_2fa.urls")),
    # path("account/", include("allauth.urls")),
    
    # API v1 (versioned endpoints)
    path("api/v1/", include("api.v1.urls")),
    path("api/v1/configuration/", include("configuration.urls")),
    
    # Vertical-specific API endpoints
    path("api/inventory/", include("inventory.api.urls")),
    path("api/billing/", include("billing.api.urls")),
    path("api/service-management/", include("service_management.api.urls")),
    
    # Vertical Dashboard endpoints (API)
    path("api/dashboards/", include("dashboard.api.dashboard_urls")),

    # Vertical Dashboard HTML page (accessible from sidebar)
    path("dashboards/vertical/", include("dashboard.views_vertical.urls")),
    path("notifications/", include(("notification_center.urls", "notification_center"), namespace="notification_center")),

    # Streamlit V2 login bootstrap
    path("V2/login", views.v2_login_redirect, name="v2_login"),
    path("enterprise/", include("enterprise.urls")),
    
    # i18n / region
    path('i18n/set-language/', views.set_language, name='set_language'),
    path('i18n/set-region/', views.set_region, name='set_region'),
    # Service worker at site root
    path('sw.js', service_worker, name='service_worker'),
]

if settings.ENABLE_SILK:
    urlpatterns.append(path('silk/', include('silk.urls', namespace='silk')))

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
