"""
Consolidated Inventory app views.

This file merges all views from the previous `views.py` and the
modular `views/` package (base_views, views_list, views_create,
views_update, views_detail, reports).
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum, Count, F
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.dateparse import parse_date
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView,
)

from accounting.models import AutoIncrementCodeGenerator
from usermanagement.mixins import UserOrganizationMixin
from usermanagement.utils import PermissionUtils
from utils.calendars import (
    CalendarMode,
    ad_to_bs_string,
    bs_to_ad_string,
    maybe_coerce_bs_date,
)

from .forms import (
    StockReceiptForm,
    StockIssueForm,
    ProductCategoryForm,
    ProductForm,
    WarehouseForm,
    LocationForm,
    UnitForm,
    ProductUnitForm,
    PriceListForm,
    PickListForm,
    ShipmentForm,
    RMAForm,
    BillOfMaterialForm,
)
from .models import (
    Batch,
    InventoryItem,
    Product,
    ProductCategory,
    Warehouse,
    Location,
    Unit,
    ProductUnit,
    StockLedger,
    PriceList,
    PickList,
    Shipment,
    RMA,
)
from enterprise.models import BillOfMaterial
from .services import InventoryService


def _get_request_organization(request):
    """Helper to get organization from request (for FBVs)."""
    return getattr(request, 'organization', None) or getattr(
        getattr(request, 'user', None), 'organization', None
    )


# ---------------------------------------------------------------------------
# Simple overview FBVs
# ---------------------------------------------------------------------------

@login_required
def products(request):
    """Simple product listing with on-hand quantities."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing products.')
        return redirect('dashboard')

    products_qs = list(
        Product.objects.filter(organization=organization)
        .select_related('category')
        .order_by('name')
    )
    on_hand_map = {
        row['product_id']: row['total_qty']
        for row in InventoryItem.objects.filter(organization=organization)
        .values('product_id')
        .annotate(total_qty=Sum('quantity_on_hand'))
    }

    for product in products_qs:
        product.total_on_hand = on_hand_map.get(product.id, Decimal('0'))

    context = {
        'organization': organization,
        'products': products_qs,
    }
    return render(request, 'inventory/products.html', context)


@login_required
def categories(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing categories.')
        return redirect('dashboard')

    categories_qs = ProductCategory.objects.filter(
        organization=organization
    ).order_by('name')
    context = {
        'organization': organization,
        'categories': categories_qs,
    }
    return render(request, 'inventory/categories.html', context)


@login_required
def warehouses(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing warehouses.')
        return redirect('dashboard')

    warehouses_qs = list(
        Warehouse.objects.filter(organization=organization)
        .annotate(location_count=Count('locations'))
        .order_by('name')
    )
    warehouse_balances = {
        row['warehouse_id']: row['total_qty']
        for row in InventoryItem.objects.filter(organization=organization)
        .values('warehouse_id')
        .annotate(total_qty=Sum('quantity_on_hand'))
    }

    for warehouse in warehouses_qs:
        warehouse.total_on_hand = warehouse_balances.get(warehouse.id, Decimal('0'))

    context = {
        'organization': organization,
        'warehouses': warehouses_qs,
    }
    return render(request, 'inventory/warehouses.html', context)


@login_required
def stock_movements(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before reviewing stock movements.')
        return redirect('dashboard')

    recent_movements = (
        StockLedger.objects.filter(organization=organization)
        .select_related('product', 'warehouse', 'location')
        .order_by('-txn_date')[:20]
    )

    context = {
        'organization': organization,
        'recent_movements': recent_movements,
    }
    return render(request, 'inventory/stock_movements.html', context)


@login_required
def inventory_dashboard(request):
    """Inventory dashboard overview."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing inventory dashboard.')
        return redirect('dashboard')

    # Get some basic stats
    total_products = Product.objects.filter(organization=organization).count()
    total_warehouses = Warehouse.objects.filter(organization=organization).count()
    total_categories = ProductCategory.objects.filter(organization=organization).count()
    total_units = Unit.objects.filter(organization=organization).count()
    total_locations = Location.objects.filter(warehouse__organization=organization).count()

    context = {
        'organization': organization,
        'cards': [
            {
                'icon': 'mdi-package',
                'color': 'primary',
                'title': 'Products',
                'value': total_products,
                'description': 'Active products tracked',
            },
            {
                'icon': 'mdi-warehouse',
                'color': 'warning',
                'title': 'Warehouses',
                'value': total_warehouses,
                'description': 'Storage locations',
            },
            {
                'icon': 'mdi-tag-multiple',
                'color': 'info',
                'title': 'Categories',
                'value': total_categories,
                'description': 'Product hierarchies',
            },
            {
                'icon': 'mdi-scale-balance',
                'color': 'success',
                'title': 'Units',
                'value': total_units,
                'description': 'Measurement units',
            },
            {
                'icon': 'mdi-map-marker',
                'color': 'secondary',
                'title': 'Locations',
                'value': total_locations,
                'description': 'Tracked sub-locations',
            },
        ],
        'quick_actions': [
            {'url': 'inventory:product_list', 'icon': 'mdi-package', 'label': 'Manage Products'},
            {'url': 'inventory:warehouse_list', 'icon': 'mdi-warehouse', 'label': 'Manage Warehouses'},
            {'url': 'inventory:location_list', 'icon': 'mdi-map-marker', 'label': 'Manage Locations'},
            {'url': 'inventory:unit_list', 'icon': 'mdi-scale-balance', 'label': 'Manage Units'},
            {'url': 'inventory:pricelist_list', 'icon': 'mdi-tag-multiple', 'label': 'Price Lists'},
            {'url': 'inventory:productunit_list', 'icon': 'mdi-package-variant-closed', 'label': 'Product Units'},
            {'url': 'inventory:stock_report', 'icon': 'mdi-chart-bar', 'label': 'Stock Report'},
            {'url': 'inventory:ledger_report', 'icon': 'mdi-book-open', 'label': 'Stock Ledger'},
        ],
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
def stock_ledger_reverse(request, pk):
    """Placeholder for reversing stock ledger entry."""
    # TODO: Implement reverse functionality
    messages.info(request, 'Stock ledger reverse functionality not yet implemented.')
    return redirect('inventory:stock_movements')


# ---------------------------------------------------------------------------
# Manual stock transactions (from original views.py)
# ---------------------------------------------------------------------------

def _resolve_batch(organization, product, batch_number, serial_number):
    if not batch_number and not serial_number:
        return None
    batch_defaults = {
        'serial_number': serial_number or ''
    }
    batch, _ = Batch.objects.get_or_create(
        organization=organization,
        product=product,
        batch_number=batch_number or 'DEFAULT',
        defaults=batch_defaults,
    )
    if serial_number and batch.serial_number != serial_number:
        batch.serial_number = serial_number
        batch.save(update_fields=['serial_number'])
    return batch


@login_required
def stock_receipt_create(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before recording a stock receipt.')
        return redirect('inventory:dashboard')

    form = StockReceiptForm(request.POST or None, organization=organization)
    if request.method == 'POST' and form.is_valid():
        cleaned = form.cleaned_data
        product = cleaned['product']
        warehouse = cleaned['warehouse']
        location = cleaned.get('location')
        batch = _resolve_batch(
            organization,
            product,
            cleaned.get('batch_number'),
            cleaned.get('serial_number'),
        )

        try:
            InventoryService.create_stock_ledger_entry(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                txn_type='manual_receipt',
                reference_id=cleaned['reference_id'],
                qty_in=cleaned['quantity'],
                unit_cost=cleaned['unit_cost'],
                async_ledger=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            form.add_error(None, f'Unable to record stock receipt: {exc}')
        else:
            messages.success(
                request,
                f"Added {cleaned['quantity']} {product.uom} of {product.name} to {warehouse.name}.",
            )
            return redirect('inventory:stock_receipt_create')

    context = {
        'form': form,
        'page_title': 'Manual Stock Receipt',
        'card_title': 'Record Stock Receipt',
        'card_subtitle': 'Capture inventory received outside of purchasing documents.',
        'cancel_url': reverse('inventory:stock_movements'),
        'form_id': 'stock-receipt-form',
    }
    return render(request, 'inventory/stock_transaction_form.html', context)


@login_required
def stock_issue_create(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before issuing stock.')
        return redirect('inventory:dashboard')

    form = StockIssueForm(request.POST or None, organization=organization)
    if request.method == 'POST' and form.is_valid():
        cleaned = form.cleaned_data
        product = cleaned['product']
        warehouse = cleaned['warehouse']
        location = cleaned.get('location')
        batch = _resolve_batch(
            organization,
            product,
            cleaned.get('batch_number'),
            cleaned.get('serial_number'),
        )

        inventory_filter = {
            'organization': organization,
            'product': product,
            'warehouse': warehouse,
            'location': location,
            'batch': batch,
        }
        try:
            inventory_item = InventoryItem.objects.get(**inventory_filter)
        except InventoryItem.DoesNotExist:
            form.add_error(
                None,
                'No on-hand inventory found for the selected product, warehouse, location, and batch.',
            )
        else:
            qty = cleaned['quantity']
            if inventory_item.quantity_on_hand < qty:
                form.add_error('quantity', f'Only {inventory_item.quantity_on_hand} available for issue.')
            else:
                reference = cleaned['reference_id']
                reason = cleaned.get('reason')
                if reason:
                    reference = (f'{reference} | {reason}' if reference else reason)[:100]
                try:
                    InventoryService.create_stock_ledger_entry(
                        organization=organization,
                        product=product,
                        warehouse=warehouse,
                        location=location,
                        batch=batch,
                        txn_type='manual_issue',
                        reference_id=reference,
                        qty_out=qty,
                        unit_cost=inventory_item.unit_cost,
                        async_ledger=False,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    form.add_error(None, f'Unable to record stock issue: {exc}')
                else:
                    messages.success(
                        request,
                        f"Issued {qty} {product.uom} of {product.name} from {warehouse.name}.",
                    )
                    return redirect('inventory:stock_issue_create')

    context = {
        'form': form,
        'page_title': 'Manual Stock Issue',
        'card_title': 'Record Stock Issue',
        'card_subtitle': 'Remove inventory for adjustments, samples, or other manual reasons.',
        'cancel_url': reverse('inventory:stock_movements'),
        'form_id': 'stock-issue-form',
    }
    return render(request, 'inventory/stock_transaction_form.html', context)


# ---------------------------------------------------------------------------
# Stock & Ledger Reports (from reports.py)
# ---------------------------------------------------------------------------

@login_required
def stock_report(request):
    """Display current stock levels across all warehouses."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view stock.')
        return redirect('dashboard')

    # Get filters
    selected_warehouse = request.GET.get('warehouse', '')
    selected_product = request.GET.get('product', '')

    # Build queryset
    stock_items = InventoryItem.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('product__code', 'warehouse__code')

    # Apply filters
    if selected_warehouse:
        stock_items = stock_items.filter(warehouse_id=selected_warehouse)
    if selected_product:
        stock_items = stock_items.filter(product_id=selected_product)

    # Get filter options
    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by('name')

    products = Product.objects.filter(
        organization=organization, is_inventory_item=True
    ).order_by('name')

    context = {
        'organization': organization,
        'stock_items': stock_items,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': selected_warehouse,
        'selected_product': selected_product,
    }
    return render(request, 'inventory/stock_report.html', context)


@login_required
def ledger_report(request):
    """Display stock ledger movements with filtering and AD/BS date support."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view ledger.')
        return redirect('dashboard')

    calendar_mode = CalendarMode.normalize(
        getattr(organization, 'calendar_mode', CalendarMode.DEFAULT)
        if organization
        else CalendarMode.DEFAULT
    )

    def _coerce_date_value(ad_value: str, bs_value: str) -> str:
        ad_value = (ad_value or '').strip()
        bs_value = (bs_value or '').strip()
        if bs_value:
            converted = bs_to_ad_string(bs_value) or maybe_coerce_bs_date(bs_value)
            if converted:
                return converted if isinstance(converted, str) else converted.isoformat()
        if ad_value:
            parsed = parse_date(ad_value)
            if parsed:
                return parsed.isoformat()
        return ad_value

    # Get filters
    selected_warehouse = request.GET.get('warehouse', '')
    selected_product = request.GET.get('product', '')
    selected_txn_type = request.GET.get('txn_type', '')
    date_from_raw = request.GET.get('date_from', '')
    date_to_raw = request.GET.get('date_to', '')
    date_from_bs = request.GET.get('date_from_bs', '')
    date_to_bs = request.GET.get('date_to_bs', '')

    date_from = _coerce_date_value(date_from_raw, date_from_bs)
    date_to = _coerce_date_value(date_to_raw, date_to_bs)

    # Build queryset
    ledger_entries = StockLedger.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).order_by('-txn_date', '-id')

    # Apply filters
    if selected_warehouse:
        ledger_entries = ledger_entries.filter(warehouse_id=selected_warehouse)
    if selected_product:
        ledger_entries = ledger_entries.filter(product_id=selected_product)
    if selected_txn_type:
        ledger_entries = ledger_entries.filter(txn_type=selected_txn_type)
    if date_from:
        ledger_entries = ledger_entries.filter(txn_date__gte=date_from)
    if date_to:
        ledger_entries = ledger_entries.filter(txn_date__lte=date_to)

    # Limit to 100 for performance
    ledger_entries = ledger_entries[:100]

    # Get filter options
    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by('name')

    products = Product.objects.filter(
        organization=organization, is_inventory_item=True
    ).order_by('name')

    txn_types = StockLedger.objects.filter(
        organization=organization
    ).values_list('txn_type', flat=True).distinct().order_by('txn_type')

    date_from_bs_display = date_from_bs or ad_to_bs_string(date_from) or ''
    date_to_bs_display = date_to_bs or ad_to_bs_string(date_to) or ''

    context = {
        'organization': organization,
        'ledger_entries': ledger_entries,
        'warehouses': warehouses,
        'products': products,
        'txn_types': txn_types,
        'selected_warehouse': selected_warehouse,
        'selected_product': selected_product,
        'selected_txn_type': selected_txn_type,
        'date_from': date_from,
        'date_from_bs': date_from_bs_display,
        'date_to': date_to,
        'date_to_bs': date_to_bs_display,
        'calendar_mode': calendar_mode,
    }
    return render(request, 'inventory/ledger_report.html', context)


# ---------------------------------------------------------------------------
# Base list view (from base_views.py)
# ---------------------------------------------------------------------------

class BaseListView(UserOrganizationMixin, ListView):
    """
    Base list view for Inventory models.
    Handles organization filtering, pagination and permission checks.
    """
    paginate_by = 20
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an active organization to continue.")
            return redirect('usermanagement:select_organization')

        if not self._has_permission(request.user, organization):
            messages.error(request, "You don't have permission to access this page.")
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)

    def _get_permission_tuple(self):
        if self.permission_required and len(self.permission_required) == 3:
            return self.permission_required
        meta = self.model._meta
        return meta.app_label, meta.model_name, "view"

    def _has_permission(self, user, organization):
        module, entity, action = self._get_permission_tuple()
        return PermissionUtils.has_permission(user, organization, module, entity, action)

    def get_queryset(self):
        """Filter queryset by organization."""
        queryset = super().get_queryset()
        organization = self.get_organization()
        if organization:
            queryset = queryset.filter(organization=organization)
        # Order safely: prefer created_at if it exists, else fallback to PK.
        model_fields = [f.name for f in self.model._meta.get_fields()]
        if 'created_at' in model_fields:
            return queryset.order_by('-created_at')
        return queryset.order_by('-pk')

    create_url_name = None
    create_button_text = None

    def get_create_url(self):
        if not self.create_url_name:
            return None
        return reverse_lazy(self.create_url_name)

    def get_create_button_text(self):
        if self.create_button_text:
            return self.create_button_text
        if not self.model:
            return None
        verbose_name = self.model._meta.verbose_name.title()
        return f"Add {verbose_name}"

    def get_context_data(self, **kwargs):
        """Add permission context to template."""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        user = self.request.user

        # Add permission flags
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label

        context['can_add'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'add'
        )
        context['can_change'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'change'
        )
        context['can_delete'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'delete'
        )
        context['organization'] = organization

        create_url = self.get_create_url()
        if context['can_add'] and create_url:
            context['create_url'] = create_url
            context['create_button_text'] = self.get_create_button_text()
        else:
            context['create_url'] = None
            context['create_button_text'] = None

        return context


# ---------------------------------------------------------------------------
# List views (from views_list.py)
# ---------------------------------------------------------------------------

class ProductCategoryListView(BaseListView):
    model = ProductCategory
    template_name = 'inventory/product_category_list.html'
    context_object_name = 'categories'
    permission_required = ('Inventory', 'productcategory', 'view')

    create_url_name = 'inventory:product_category_create'


class ProductListView(BaseListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    permission_required = ('Inventory', 'product', 'view')

    create_url_name = 'inventory:product_create'


class WarehouseListView(BaseListView):
    model = Warehouse
    template_name = 'inventory/warehouse_list.html'
    context_object_name = 'warehouses'
    permission_required = ('Inventory', 'warehouse', 'view')

    create_url_name = 'inventory:warehouse_create'


class LocationListView(BaseListView):
    model = Location
    template_name = 'inventory/location_list.html'
    context_object_name = 'locations'
    permission_required = ('Inventory', 'location', 'view')

    def get_queryset(self):
        """Filter by organization via warehouse since Location has no direct org FK."""
        qs = ListView.get_queryset(self)
        organization = self.get_organization()
        if organization:
            qs = qs.filter(warehouse__organization=organization)
        return qs.order_by('-warehouse__code', 'code')

    create_url_name = 'inventory:location_create'


class UnitListView(BaseListView):
    model = Unit
    template_name = 'inventory/unit_list.html'
    context_object_name = 'units'
    permission_required = ('Inventory', 'unit', 'view')

    create_url_name = 'inventory:unit_create'


class ProductUnitListView(BaseListView):
    model = ProductUnit
    template_name = 'inventory/productunit_list.html'
    context_object_name = 'productunits'
    permission_required = ('Inventory', 'productunit', 'view')

    create_url_name = 'inventory:productunit_create'

    def get_queryset(self):
        """Filter queryset by organization through product."""
        queryset = ProductUnit.objects.all()
        organization = self.get_organization()
        if organization:
            queryset = queryset.filter(product__organization=organization)
        # Order safely: prefer created_at if it exists, else fallback to PK.
        model_fields = [f.name for f in self.model._meta.get_fields()]
        if 'created_at' in model_fields:
            return queryset.order_by('-created_at')
        return queryset.order_by('-pk')


class PriceListListView(BaseListView):
    model = PriceList
    template_name = 'inventory/pricelist_list.html'
    context_object_name = 'pricelists'
    permission_required = ('Inventory', 'pricelist', 'view')

    create_url_name = 'inventory:pricelist_create'


class PickListListView(BaseListView):
    model = PickList
    template_name = 'inventory/picklist_list.html'
    context_object_name = 'picklists'
    permission_required = ('Inventory', 'picklist', 'view')

    create_url_name = 'inventory:picklist_create'


class ShipmentListView(BaseListView):
    model = Shipment
    template_name = 'inventory/shipment_list.html'
    context_object_name = 'shipments'
    permission_required = ('Inventory', 'shipment', 'view')

    create_url_name = 'inventory:shipment_create'


class RMAListView(BaseListView):
    model = RMA
    template_name = 'inventory/rma_list.html'
    context_object_name = 'rmas'
    permission_required = ('Inventory', 'rma', 'view')

    create_url_name = 'inventory:rma_create'


class BillOfMaterialListView(BaseListView):
    model = BillOfMaterial
    template_name = 'inventory/billofmaterial_list.html'
    context_object_name = 'boms'
    permission_required = ('Inventory', 'billofmaterial', 'view')

    create_url_name = 'inventory:bom_create'


# ---------------------------------------------------------------------------
# Create views (from views_create.py)
# ---------------------------------------------------------------------------

class ProductCategoryCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ProductCategory
    form_class = ProductCategoryForm
    template_name = 'inventory/product_category_form.html'
    permission_required = 'Inventory.add_productcategory'
    success_url = reverse_lazy('inventory:product_category_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                ProductCategory, 'code', organization=organization, prefix='PC'
            )
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Product Category "{form.instance.name}" created successfully.',
        )
        return super().form_valid(form)


class ProductCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    permission_required = 'Inventory.add_product'
    success_url = reverse_lazy('inventory:product_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                Product, 'code', organization=organization, prefix='PROD'
            )
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Product "{form.instance.name}" created successfully.',
        )
        return super().form_valid(form)


class WarehouseCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    permission_required = 'Inventory.add_warehouse'
    success_url = reverse_lazy('inventory:warehouse_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                Warehouse, 'code', organization=organization, prefix='WH'
            )
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Warehouse "{form.instance.name}" created successfully.',
        )
        return super().form_valid(form)


class LocationCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'inventory/location_form.html'
    permission_required = 'Inventory.add_location'
    success_url = reverse_lazy('inventory:location_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        organization = self.get_organization()
        if organization:
            form.fields['warehouse'].queryset = (
                form.fields['warehouse'].queryset.filter(organization=organization)
            )
        return form

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Location "{form.instance.name or form.instance.code}" created successfully.',
        )
        return super().form_valid(form)


class UnitCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Unit
    form_class = UnitForm
    template_name = 'inventory/unit_form.html'
    permission_required = 'Inventory.add_unit'
    success_url = reverse_lazy('inventory:unit_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                Unit, 'code', organization=organization, prefix='U'
            )
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        messages.success(
            self.request,
            f'Unit "{form.instance.name}" created successfully.',
        )
        return super().form_valid(form)


class ProductUnitCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ProductUnit
    form_class = ProductUnitForm
    template_name = 'inventory/productunit_form.html'
    permission_required = 'Inventory.add_productunit'
    success_url = reverse_lazy('inventory:productunit_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        organization = self.get_organization()
        if organization:
            form.fields['product'].queryset = (
                form.fields['product'].queryset.filter(organization=organization)
            )
            form.fields['unit'].queryset = (
                form.fields['unit'].queryset.filter(organization=organization)
            )
        return form

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Product Unit for "{form.instance.product.name}" created successfully.',
        )
        return super().form_valid(form)


class PriceListCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = PriceList
    form_class = PriceListForm
    template_name = 'inventory/pricelist_form.html'
    permission_required = 'Inventory.add_pricelist'
    success_url = reverse_lazy('inventory:pricelist_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                PriceList, 'code', organization=organization, prefix='PL'
            )
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Price List "{form.instance.name}" created successfully.',
        )
        return super().form_valid(form)


class PickListCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = PickList
    form_class = PickListForm
    template_name = 'inventory/picklist_form.html'
    permission_required = 'Inventory.add_picklist'
    success_url = reverse_lazy('inventory:picklist_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                PickList, 'pick_list_number', organization=organization, prefix='PICK'
            )
            initial['pick_list_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Pick List "{form.instance.pick_list_number}" created successfully.',
        )
        return super().form_valid(form)


class ShipmentCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Shipment
    form_class = ShipmentForm
    template_name = 'inventory/shipment_form.html'
    permission_required = 'Inventory.add_shipment'
    success_url = reverse_lazy('inventory:shipment_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                Shipment, 'shipment_number', organization=organization, prefix='SHIP'
            )
            initial['shipment_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Shipment "{form.instance.shipment_number}" created successfully.',
        )
        return super().form_valid(form)


class RMACreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = RMA
    form_class = RMAForm
    template_name = 'inventory/rma_form.html'
    permission_required = 'Inventory.add_rma'
    success_url = reverse_lazy('inventory:rma_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                RMA, 'rma_number', organization=organization, prefix='RMA'
            )
            initial['rma_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'RMA "{form.instance.rma_number}" created successfully.',
        )
        return super().form_valid(form)


class BillOfMaterialCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'inventory/billofmaterial_form.html'
    permission_required = 'Inventory.add_billofmaterial'
    success_url = reverse_lazy('inventory:bom_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(
                BillOfMaterial, 'bom_number', organization=organization, prefix='BOM'
            )
            initial['bom_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'BOM "{form.instance.bom_number}" created successfully.',
        )
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Update views (from views_update.py)
# ---------------------------------------------------------------------------

class ProductCategoryUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = ProductCategory
    form_class = ProductCategoryForm
    template_name = 'inventory/product_category_form.html'
    permission_required = 'Inventory.change_productcategory'
    success_url = reverse_lazy('inventory:product_category_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Product Category "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class ProductUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    permission_required = 'Inventory.change_product'
    success_url = reverse_lazy('inventory:product_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Product "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class WarehouseUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    permission_required = 'Inventory.change_warehouse'
    success_url = reverse_lazy('inventory:warehouse_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Warehouse "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class LocationUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'inventory/location_form.html'
    permission_required = 'Inventory.change_location'
    success_url = reverse_lazy('inventory:location_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Location "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class UnitUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Unit
    form_class = UnitForm
    template_name = 'inventory/unit_form.html'
    permission_required = 'Inventory.change_unit'
    success_url = reverse_lazy('inventory:unit_list')

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Unit "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class ProductUnitUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = ProductUnit
    form_class = ProductUnitForm
    template_name = 'inventory/productunit_form.html'
    permission_required = 'Inventory.change_productunit'
    success_url = reverse_lazy('inventory:productunit_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        organization = self.get_organization()
        if organization:
            form.fields['product'].queryset = (
                form.fields['product'].queryset.filter(organization=organization)
            )
            form.fields['unit'].queryset = (
                form.fields['unit'].queryset.filter(organization=organization)
            )
        return form

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Product Unit for "{form.instance.product.name}" updated successfully.',
        )
        return super().form_valid(form)


class PriceListUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = PriceList
    form_class = PriceListForm
    template_name = 'inventory/pricelist_form.html'
    permission_required = 'Inventory.change_pricelist'
    success_url = reverse_lazy('inventory:pricelist_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Price List "{form.instance.name}" updated successfully.',
        )
        return super().form_valid(form)


class PickListUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = PickList
    form_class = PickListForm
    template_name = 'inventory/picklist_form.html'
    permission_required = 'Inventory.change_picklist'
    success_url = reverse_lazy('inventory:picklist_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Pick List "{form.instance.pick_list_number}" updated successfully.',
        )
        return super().form_valid(form)


class ShipmentUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Shipment
    form_class = ShipmentForm
    template_name = 'inventory/shipment_form.html'
    permission_required = 'Inventory.change_shipment'
    success_url = reverse_lazy('inventory:shipment_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'Shipment "{form.instance.shipment_number}" updated successfully.',
        )
        return super().form_valid(form)


class RMAUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = RMA
    form_class = RMAForm
    template_name = 'inventory/rma_form.html'
    permission_required = 'Inventory.change_rma'
    success_url = reverse_lazy('inventory:rma_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'RMA "{form.instance.rma_number}" updated successfully.',
        )
        return super().form_valid(form)


class BillOfMaterialUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'inventory/billofmaterial_form.html'
    permission_required = 'Inventory.change_billofmaterial'
    success_url = reverse_lazy('inventory:bom_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(
            self.request,
            f'BOM "{form.instance.bom_number}" updated successfully.',
        )
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Detail views (from views_detail.py)
# ---------------------------------------------------------------------------

class ProductCategoryDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = ProductCategory
    template_name = 'inventory/product_category_detail.html'
    permission_required = 'Inventory.view_productcategory'
    context_object_name = 'category'


class ProductDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    permission_required = 'Inventory.view_product'
    context_object_name = 'product'


class WarehouseDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Warehouse
    template_name = 'inventory/warehouse_detail.html'
    permission_required = 'Inventory.view_warehouse'
    context_object_name = 'warehouse'


class LocationDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Location
    template_name = 'inventory/location_detail.html'
    permission_required = 'Inventory.view_location'
    context_object_name = 'location'


class PriceListDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = PriceList
    template_name = 'inventory/pricelist_detail.html'
    permission_required = 'Inventory.view_pricelist'
    context_object_name = 'pricelist'


class PickListDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = PickList
    template_name = 'inventory/picklist_detail.html'
    permission_required = 'Inventory.view_picklist'
    context_object_name = 'picklist'


class ShipmentDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Shipment
    template_name = 'inventory/shipment_detail.html'
    permission_required = 'Inventory.view_shipment'
    context_object_name = 'shipment'


class RMADetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = RMA
    template_name = 'inventory/rma_detail.html'
    permission_required = 'Inventory.view_rma'
    context_object_name = 'rma'


class BillOfMaterialDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = BillOfMaterial
    template_name = 'inventory/billofmaterial_detail.html'
    permission_required = 'Inventory.view_billofmaterial'
    context_object_name = 'bom'


# ---------------------------------------------------------------------------
# Delete views (only existed in original views.py)
# ---------------------------------------------------------------------------

class ProductCategoryDeleteView(UserOrganizationMixin, DeleteView):
    """Delete a product category with confirmation."""
    model = ProductCategory
    template_name = 'inventory/productcategory_confirm_delete.html'
    context_object_name = 'category'

    def get_queryset(self):
        """Ensure users can only delete categories in their organization."""
        org = self.get_organization()
        return ProductCategory.objects.filter(organization=org)

    def get_success_url(self):
        messages.success(self.request, 'Product Category deleted successfully.')
        return reverse_lazy('inventory:product_category_list')


class ProductDeleteView(UserOrganizationMixin, DeleteView):
    model = Product
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')


class WarehouseDeleteView(UserOrganizationMixin, DeleteView):
    model = Warehouse
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:warehouse_list')


class LocationDeleteView(UserOrganizationMixin, DeleteView):
    model = Location
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:location_list')


class PriceListDeleteView(UserOrganizationMixin, DeleteView):
    model = PriceList
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:pricelist_list')


class PickListDeleteView(UserOrganizationMixin, DeleteView):
    model = PickList
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:picklist_list')


class ShipmentDeleteView(UserOrganizationMixin, DeleteView):
    model = Shipment
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:shipment_list')


class RMADeleteView(UserOrganizationMixin, DeleteView):
    model = RMA
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:rma_list')


class BillOfMaterialDeleteView(UserOrganizationMixin, DeleteView):
    model = BillOfMaterial
    template_name = 'inventory/base_confirm_delete.html'
    success_url = reverse_lazy('inventory:bom_list')
