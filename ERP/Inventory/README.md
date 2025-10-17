# Inventory Django App

This Django app provides core inventory management functionality, including master data for products, categories, warehouses, and locations, as well as tracking stock levels and movements via a ledger.

## Integration Steps

1.  **Place the App:** Copy the `Inventory` directory into your Django project's apps directory (e.g., `ERP/apps/`).

2.  **Add to `INSTALLED_APPS`:** Add `'Inventory'` to your `INSTALLED_APPS` setting in `ERP/dashboard/settings.py`:

    ```python
    INSTALLED_APPS = [
        # ... other apps
        'mptt', # Ensure django-mptt is installed and added BEFORE Inventory
        'Inventory',
        # ...
    ]
    ```
    *Note: Ensure `mptt` is installed (`pip install django-mptt`) and listed before `Inventory`.*

3.  **Include URLs:** Include the app's URLs in your main `urls.py` (`ERP/dashboard/urls.py`):

    ```python
    from django.contrib import admin
    from django.urls import path, include

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('accounts/', include('allauth.urls')), # Assuming allauth is used
        path('inventory/', include('Inventory.urls', namespace='inventory')),
        # ... other urls
    ]
    ```

4.  **Run Migrations:** Apply the database migrations for the new models:

    ```bash
    python manage.py migrate Inventory
    ```

5.  **Ensure Dependencies:**
    *   Verify `django-mptt` is installed (`pip install django-mptt`).
    *   Ensure your project has `organization.models.Organization` and `accounting.models.ChartOfAccount` models accessible and configured correctly, as the Inventory models have Foreign Keys to them.
    *   Confirm `ActiveTenantMiddleware` is active in `settings.py` to handle organization filtering automatically in views.
    *   Ensure `django-crispy-forms` is installed (`pip install django-crispy-forms`) and configured (e.g., `CRISPY_TEMPLATE_PACK` in settings).
    *   Ensure your base template (`erp_base.html` in the example) exists and includes necessary static files (Tailwind CSS, etc.) and renders the `content` block.

6.  **Configure Tailwind CSS:** Ensure Tailwind CSS is set up in your project and configured to scan the `Inventory/templates/Inventory/` directory for classes.

7.  **Admin Integration:** The models are automatically registered in `admin.py`. You can access them via the Django admin interface.

8.  **Access Views:** The main entry points are:
    *   `/inventory/categories/`
    *   `/inventory/products/`
    *   `/inventory/warehouses/`
    *   `/inventory/stock/` (Current Inventory Levels)
    *   `/inventory/ledger/` (Stock Transaction History)

## Key Features & Design Decisions

*   **Multi-Tenancy:** All models include an `organization` ForeignKey, and views/forms use `OrganizationFilterMixin` to automatically scope data to the active organization provided by `ActiveTenantMiddleware`.
*   **Service Layer (`services.py`):** Complex business logic (like creating ledger entries and updating inventory items) is encapsulated in `services.py` using `@transaction.atomic` for data integrity.
*   **Immutable Ledger (`StockLedger`):** Stock movements are recorded as immutable entries.
*   **Snapshot Table (`InventoryItem`):** Provides a current view of stock levels, updated by the service layer.
*   **MPTT for Categories:** `django-mptt` is used for hierarchical product categories.
*   **Tailwind CSS:** Templates use Tailwind classes for styling.
*   **Crispy Forms:** Forms are rendered using `django-crispy-forms` for easier styling and layout.
*   **Basic CRUD:** Standard Django class-based views provide Create, Read, Update, and Delete functionality for master data.
*   **Operational Views:** Basic list views for `InventoryItem` and `StockLedger` with filtering capabilities are provided.

## Further Development

*   **Implement Operational Flows:** Build dedicated views and forms for Purchase Receiving, Internal Transfers, Sales Picking/Shipping, Adjustments, etc., utilizing the services layer.
*   **HTMX Integration:** Enhance operational views with HTMX for dynamic updates (e.g., scanning locations during receiving/picking).
*   **Permissions:** Add Django permissions to views to control access based on user roles.
*   **Reporting:** Create dedicated reporting views or integrate with a BI tool using the `InventoryItem` and `StockLedger` data.
*   **Costing Logic:** Refine the unit cost calculation logic in `services.py` (e.g., FIFO, LIFO, Weighted Average).
*   **Background Tasks:** Implement Celery tasks for cost recalculation, reorder recommendations, etc., as described in the requirements.
*   **API Endpoints:** Add Django REST Framework serializers and views for headless access to inventory data and operations.

This module provides a solid foundation for building out the full inventory management capabilities of your ERP system.
