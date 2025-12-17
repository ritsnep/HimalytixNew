from django.contrib import messages
from django.views.generic import ListView
from django.shortcuts import redirect
from django.db.models import Q, Count, Sum, Avg, Max, Min
from urllib.parse import urlencode

from usermanagement.utils import PermissionUtils
from accounting.views.views_mixins import UserOrganizationMixin
from accounting.list_registry import get_config

class BaseListView(UserOrganizationMixin, ListView):
    paginate_by = 20
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an active organization to continue.")
            return redirect("usermanagement:select_organization")

        if not self._has_permission(request.user, organization):
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

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
        org = self.get_organization()
        qs = super().get_queryset()
        # Only filter by organization if the model has this field
        if hasattr(self.model, 'organization') and org:
            qs = qs.filter(organization=org)
        elif not org and hasattr(self.model, 'organization'):
            return self.model.objects.none()
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = self.get_organization()

        if self.permission_required:
            app_label, model_name, action = self.permission_required
            context['can_add'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'add')
            context['can_change'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'change')
            context['can_delete'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'delete')

        context['page_title'] = self.model._meta.verbose_name_plural.title()
        return context


class SmartListMixin:
    """Adds dynamic filters and bulk actions based on model metadata/registry."""

    smart_filters_enabled = True
    smart_bulk_enabled = True

    def get_smart_config(self):
        return get_config(self.model)

    def apply_smart_filters(self, qs):
        if not self.smart_filters_enabled:
            return qs

        cfg = self.get_smart_config()
        request = self.request

        # Text search across configured fields
        search_term = request.GET.get('q', '').strip()
        if search_term and cfg.get('search_fields'):
            query = Q()
            for field in cfg['search_fields']:
                query |= Q(**{f"{field}__icontains": search_term})
            qs = qs.filter(query)

        # Choice/status filters
        for field in cfg.get('choice_fields', []):
            val = request.GET.get(field)
            if val:
                qs = qs.filter(**{field: val})

        # Boolean filters (expects yes/no)
        for field in cfg.get('boolean_fields', []):
            val = request.GET.get(field)
            if val in ('yes', 'true', '1'):
                qs = qs.filter(**{field: True})
            elif val in ('no', 'false', '0'):
                qs = qs.filter(**{field: False})

        # Currency filter
        currency_field = cfg.get('currency_field')
        if currency_field:
            currency_val = request.GET.get('currency')
            if currency_val:
                qs = qs.filter(**{f"{currency_field}_id": currency_val})

        # Date range filters
        for field in cfg.get('date_range_fields', []):
            start = request.GET.get(f"{field}_from")
            end = request.GET.get(f"{field}_to")
            if start:
                qs = qs.filter(**{f"{field}__date__gte": start})
            if end:
                qs = qs.filter(**{f"{field}__date__lte": end})

        order_by = cfg.get('order_by') or []
        if order_by:
            qs = qs.order_by(*order_by)

        return qs

    def apply_smart_grouping(self, qs):
        """Apply grouping and aggregation if requested."""
        cfg = self.get_smart_config()
        request = self.request

        group_by_fields = []
        for field in cfg.get('group_by', []):
            if request.GET.get(f'group_{field}'):
                group_by_fields.append(field)

        if not group_by_fields:
            return qs

        # Group by the selected fields
        qs = qs.values(*group_by_fields)

        # Add aggregates
        aggregates = {}
        for field, agg_func in cfg.get('aggregate_fields', {}).items():
            if agg_func == 'count':
                aggregates[f'{field}_count'] = Count(field)
            elif agg_func == 'sum':
                aggregates[f'{field}_sum'] = Sum(field)
            elif agg_func == 'avg':
                aggregates[f'{field}_avg'] = Avg(field)
            elif agg_func == 'max':
                aggregates[f'{field}_max'] = Max(field)
            elif agg_func == 'min':
                aggregates[f'{field}_min'] = Min(field)

        if aggregates:
            qs = qs.annotate(**aggregates)

        # Add count of records in each group
        pk_field = self.model._meta.pk.name
        qs = qs.annotate(record_count=Count(pk_field))

        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self.apply_smart_filters(qs)
        qs = self.apply_smart_grouping(qs)
        return qs

    def get_bulk_actions(self):
        if not self.smart_bulk_enabled:
            return []
        return self.get_smart_config().get('bulk_actions', [])

    def handle_bulk_actions(self, qs):
        actions = self.get_bulk_actions()
        action = self.request.POST.get('action')
        selected_ids = self.request.POST.getlist('selected_ids')

        if not action or action not in actions or not selected_ids:
            messages.warning(self.request, "Select at least one row and a bulk action.")
            return 0

        qs = qs.filter(pk__in=selected_ids)
        updated = 0

        if action == 'activate':
            if hasattr(self.model, 'is_active'):
                updated = qs.update(is_active=True)
            elif hasattr(self.model, 'status'):
                updated = qs.update(status='active')
        elif action == 'deactivate':
            if hasattr(self.model, 'is_active'):
                updated = qs.update(is_active=False)
            elif hasattr(self.model, 'status'):
                updated = qs.update(status='inactive')
        elif action == 'hold' and hasattr(self.model, 'on_hold'):
            updated = qs.update(on_hold=True)
        elif action == 'unhold' and hasattr(self.model, 'on_hold'):
            updated = qs.update(on_hold=False)
        else:
            messages.error(self.request, "Unsupported bulk action for this list.")
            return 0

        return updated

    def post(self, request, *args, **kwargs):
        if not self.smart_bulk_enabled:
            return super().post(request, *args, **kwargs)

        org = self.get_organization()
        if not org and hasattr(self.model, 'organization'):
            messages.error(request, "Organization is required.")
            return redirect(request.path)

        qs = self.get_queryset()
        if hasattr(self.model, 'organization') and org:
            qs = qs.filter(organization=org)
        updated = self.handle_bulk_actions(qs)
        if updated:
            messages.success(request, f"Bulk action applied to {updated} record(s).")
        return self._redirect_with_filters(request)

    def _redirect_with_filters(self, request):
        params = {k: v for k, v in request.POST.items() if k not in ('csrfmiddlewaretoken', 'selected_ids', 'action') and v}
        query = f"?{urlencode(params)}" if params else ''
        return redirect(f"{request.path}{query}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = self.get_smart_config() if self.smart_filters_enabled else None
        if cfg:
            request = self.request
            # Collect choice options from model fields (if available)
            choice_filters = []
            for field_name in cfg.get('choice_fields', []):
                opts = []
                try:
                    field = self.model._meta.get_field(field_name)
                    opts = list(field.choices) if getattr(field, 'choices', None) else []
                except Exception:
                    opts = []
                choice_filters.append({
                    'name': field_name,
                    'options': opts,
                    'value': request.GET.get(field_name, ''),
                })

            boolean_filters = [
                {
                    'name': field_name,
                    'value': request.GET.get(field_name, ''),
                }
                for field_name in cfg.get('boolean_fields', [])
            ]

            date_filters = []
            for field_name in cfg.get('date_range_fields', []):
                date_filters.append({
                    'name': field_name,
                    'from': request.GET.get(f"{field_name}_from", ''),
                    'to': request.GET.get(f"{field_name}_to", ''),
                })

            currency_value = request.GET.get('currency', '')
            filters_ordered = []
            # Search as first filter block
            filters_ordered.append({
                'kind': 'search',
                'label': 'Search',
                'name': 'q',
                'value': request.GET.get('q', ''),
            })
            filters_ordered.extend([{ 'kind': 'choice', **c } for c in choice_filters])
            filters_ordered.extend([{ 'kind': 'boolean', **b } for b in boolean_filters])
            if cfg.get('currency_field'):
                filters_ordered.append({
                    'kind': 'currency',
                    'name': cfg.get('currency_field'),
                    'value': currency_value,
                })
            filters_ordered.extend([{ 'kind': 'date', **d } for d in date_filters])

            basic_filters = filters_ordered[:3]
            advanced_filters = filters_ordered[3:]

            # Group by options
            group_by_options = []
            for field in cfg.get('group_by', []):
                group_by_options.append({
                    'name': field,
                    'label': field.replace('_', ' ').title(),
                    'checked': bool(request.GET.get(f'group_{field}')),
                })

            context['smart_filter_config'] = {
                'basic_filters': basic_filters,
                'advanced_filters': advanced_filters,
                'choice_filters': choice_filters,
                'boolean_filters': boolean_filters,
                'currency_field': cfg.get('currency_field'),
                'currency_value': currency_value,
                'date_filters': date_filters,
                'search_value': request.GET.get('q', ''),
                'group_by_options': group_by_options,
            }
        if self.smart_bulk_enabled:
            context['smart_bulk_actions'] = self.get_bulk_actions()

        # Check if grouping is active
        cfg = self.get_smart_config() if self.smart_filters_enabled else None
        if cfg:
            is_grouped = any(self.request.GET.get(f'group_{field}') for field in cfg.get('group_by', []))
            context['is_grouped'] = is_grouped
            if is_grouped:
                group_by_fields = [field for field in cfg.get('group_by', []) if self.request.GET.get(f'group_{field}')]
                context['group_by_fields'] = group_by_fields
                context['aggregate_fields'] = cfg.get('aggregate_fields', {})

                # Prepare group values for template
                if is_grouped:
                    group_values = []
                    for group in context['object_list']:
                        values = [group[field] for field in group_by_fields]
                        values.append(group.get('code_count') or group.get('record_count') or 0)
                        group_values.append(values)
                    context['group_values'] = group_values

        return context


class SmartListView(SmartListMixin, BaseListView):
    """Convenience view combining BaseListView with smart filters/bulk."""
    pass
