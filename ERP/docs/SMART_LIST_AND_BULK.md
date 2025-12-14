# Smart List Filters & Bulk Actions

This note explains how the smart filter/bulk infrastructure works and how to wire new accounting list pages into it.

## What it does
- Central registry drives search/choice/boolean/date filters and available bulk actions per model.
- `SmartListMixin` / `SmartListView` prepare filter forms, apply queryset filters, and handle bulk actions on POST.
- Shared templates render filters (`smart_filters.html` / `smart_filters_block.html`) and merge DataTables options (including checkbox/action column disabling search/sort).
- Each list template adds a checkbox column and a compact bulk-action control next to the create button.

## Key pieces
- Registry: `accounting/list_registry.py`
  - Configure `search_fields`, `choice_fields`, `boolean_fields`, optional `currency_field`, `date_range_fields`, `order_by`, and `bulk_actions` per model key.
  - Bulk actions currently supported: `activate`, `deactivate`, `hold`, `unhold` (extend as needed in view/mixin if more are added).
- Views: `accounting/views/base_views.py`
  - `SmartListMixin` builds filter context (`basic_filters`, `advanced_filters`) and `SmartListView` processes bulk POST (`selected_ids` + `action`).
- Templates:
  - Base: `accounting/_list_base.html` renders smart filters and expects an optional `<script id="datatable-config">` JSON to merge extra DataTables settings.
  - Filter partials: `accounting/partials/smart_filters.html` and `smart_filters_block.html` render basic + collapsible advanced filters with validation messages.

## Template pattern (per list page)
1) Create button area
```html
<div class="d-flex align-items-center gap-2 flex-wrap">
  <a href="{% url 'accounting:some_create' %}" class="btn btn-success btn-sm">
    <i class="mdi mdi-plus me-1"></i> New Item
  </a>
  <div class="input-group input-group-sm" style="width: 320px;">
    <label class="input-group-text" for="bulk-action">Bulk</label>
    <select id="bulk-action" name="action" class="form-select form-select-sm" form="bulk-action-form">
      <option value="">Select action</option>
      <option value="activate">Mark Active</option>
      <option value="deactivate">Mark Inactive</option>
    </select>
    <button id="bulk-action-apply" type="submit" class="btn btn-outline-primary" form="bulk-action-form">Apply</button>
  </div>
</div>
```

2) Table head/body
```html
<thead>
  <tr>
    <th class="no-search no-export" style="width:30px;"><input type="checkbox" id="select-all" class="form-check-input form-check-sm"></th>
    <!-- existing columns... -->
    <th>Actions</th>
  </tr>
</thead>
<tbody>
  {% for obj in objects %}
  <tr data-pk="{{ obj.pk }}">
    <td><input type="checkbox" class="form-check-input row-select" name="selected_ids" value="{{ obj.pk }}" form="bulk-action-form"></td>
    <!-- existing cells... -->
    <td><!-- actions --></td>
  </tr>
  {% endfor %}
</tbody>
```
Adjust empty-state `colspan` to match new column count.

3) Bulk form container
```html
{% block custom_filters %}
<form id="bulk-action-form" method="post">
  {% csrf_token %}
</form>
{% endblock %}
```

4) DataTables + select-all JS
```html
{% block extra_js %}
<script id="datatable-config" type="application/json">
{
  "columnDefs": [
    {"targets": [0, -1], "orderable": false, "searchable": false}
  ]
}
</script>
{{ block.super }}
<script>
  $(function() {
    var selectAll = $('#select-all');
    var rowChecks = $('input.row-select');
    var actionSelect = $('#bulk-action');
    var applyBtn = $('#bulk-action-apply');

    function syncSelectAll() {
      var checkedCount = rowChecks.filter(':checked').length;
      selectAll.prop('checked', checkedCount > 0 && checkedCount === rowChecks.length);
    }

    selectAll.on('change', function() {
      rowChecks.prop('checked', $(this).is(':checked'));
    });

    rowChecks.on('change', syncSelectAll);

    applyBtn.on('click', function(e) {
      if (!actionSelect.val()) {
        e.preventDefault();
        alert('Choose a bulk action to apply.');
        return;
      }
      if (!rowChecks.filter(':checked').length) {
        e.preventDefault();
        alert('Select at least one item.');
      }
    });
  });
</script>
{% endblock %}
```

## Adding a new smart list
1. Add a registry entry keyed by the model slug in `REGISTRY` with filters/order/bulk actions.
2. Make the list view subclass `SmartListView` (or mixin + ListView) so filters/bulk are processed.
3. Update the template to follow the pattern above and include filter partials via `_list_base.html`.
4. Test: filter basics/advanced, select-all + bulk apply for each action, ensure DataTables ignores checkbox/action columns for sort/search.

## Troubleshooting
- Template errors about missing fields: ensure registry field names match model attributes and template uses provided `filters` context.
- Bulk no-ops: confirm `bulk_actions` list contains the action and the view implements the side effect for that action.
- Sorting misaligned: verify `datatable-config` is valid JSON and includes the checkbox/action columns in `columnDefs` `targets`.
