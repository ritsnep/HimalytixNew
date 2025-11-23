from django.urls import path

from . import views

app_name = "enterprise"

urlpatterns = [
    # HR / Payroll
    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/new/", views.DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<int:pk>/", views.DepartmentUpdateView.as_view(), name="department_update"),
    path("positions/", views.PositionListView.as_view(), name="position_list"),
    path("positions/new/", views.PositionCreateView.as_view(), name="position_create"),
    path("positions/<int:pk>/", views.PositionUpdateView.as_view(), name="position_update"),
    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),
    path("employees/new/", views.EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/", views.EmployeeUpdateView.as_view(), name="employee_update"),
    path("payroll-cycles/", views.PayrollCycleListView.as_view(), name="payroll_cycle_list"),
    path("payroll-cycles/new/", views.PayrollCycleCreateView.as_view(), name="payroll_cycle_create"),
    path("payroll-cycles/<int:pk>/", views.PayrollCycleUpdateView.as_view(), name="payroll_cycle_update"),
    path("payroll-entries/", views.PayrollEntryListView.as_view(), name="payroll_entry_list"),
    path("payroll-entries/new/", views.PayrollEntryCreateView.as_view(), name="payroll_entry_create"),
    path("payroll-entries/<int:pk>/", views.PayrollEntryUpdateView.as_view(), name="payroll_entry_update"),
    path("leave-requests/", views.LeaveRequestListView.as_view(), name="leave_request_list"),
    path("leave-requests/new/", views.LeaveRequestCreateView.as_view(), name="leave_request_create"),
    path("leave-requests/<int:pk>/", views.LeaveRequestUpdateView.as_view(), name="leave_request_update"),
    path("attendance/", views.AttendanceRecordListView.as_view(), name="attendance_record_list"),
    path("attendance/new/", views.AttendanceRecordCreateView.as_view(), name="attendance_record_create"),
    path("attendance/<int:pk>/", views.AttendanceRecordUpdateView.as_view(), name="attendance_record_update"),
    path("benefits/", views.BenefitEnrollmentListView.as_view(), name="benefit_enrollment_list"),
    path("benefits/new/", views.BenefitEnrollmentCreateView.as_view(), name="benefit_enrollment_create"),
    path("benefits/<int:pk>/", views.BenefitEnrollmentUpdateView.as_view(), name="benefit_enrollment_update"),
    # Fixed Assets
    path("assets/categories/", views.FixedAssetCategoryListView.as_view(), name="fixedasset_category_list"),
    path("assets/categories/new/", views.FixedAssetCategoryCreateView.as_view(), name="fixedasset_category_create"),
    path("assets/categories/<int:pk>/", views.FixedAssetCategoryUpdateView.as_view(), name="fixedasset_category_update"),
    path("assets/", views.FixedAssetListView.as_view(), name="fixedasset_list"),
    path("assets/new/", views.FixedAssetCreateView.as_view(), name="fixedasset_create"),
    path("assets/<int:pk>/", views.FixedAssetUpdateView.as_view(), name="fixedasset_update"),
    path(
        "assets/depreciation/",
        views.AssetDepreciationScheduleListView.as_view(),
        name="depreciation_schedule_list",
    ),
    path(
        "assets/depreciation/new/",
        views.AssetDepreciationScheduleCreateView.as_view(),
        name="depreciation_schedule_create",
    ),
    path(
        "assets/depreciation/<int:pk>/",
        views.AssetDepreciationScheduleUpdateView.as_view(),
        name="depreciation_schedule_update",
    ),
    # Manufacturing
    path("manufacturing/boms/", views.BillOfMaterialListView.as_view(), name="bom_list"),
    path("manufacturing/boms/new/", views.BillOfMaterialCreateView.as_view(), name="bom_create"),
    path("manufacturing/boms/<int:pk>/", views.BillOfMaterialUpdateView.as_view(), name="bom_update"),
    path("manufacturing/bom-items/", views.BillOfMaterialItemListView.as_view(), name="bom_item_list"),
    path("manufacturing/bom-items/new/", views.BillOfMaterialItemCreateView.as_view(), name="bom_item_create"),
    path("manufacturing/bom-items/<int:pk>/", views.BillOfMaterialItemUpdateView.as_view(), name="bom_item_update"),
    path("manufacturing/work-orders/", views.WorkOrderListView.as_view(), name="workorder_list"),
    path("manufacturing/work-orders/new/", views.WorkOrderCreateView.as_view(), name="workorder_create"),
    path("manufacturing/work-orders/<int:pk>/", views.WorkOrderUpdateView.as_view(), name="workorder_update"),
    path(
        "manufacturing/work-order-materials/",
        views.WorkOrderMaterialListView.as_view(),
        name="womaterial_list",
    ),
    path(
        "manufacturing/work-order-materials/new/",
        views.WorkOrderMaterialCreateView.as_view(),
        name="womaterial_create",
    ),
    path(
        "manufacturing/work-order-materials/<int:pk>/",
        views.WorkOrderMaterialUpdateView.as_view(),
        name="womaterial_update",
    ),
    # CRM
    path("crm/leads/", views.CRMLeadListView.as_view(), name="crmlead_list"),
    path("crm/leads/new/", views.CRMLeadCreateView.as_view(), name="crmlead_create"),
    path("crm/leads/<int:pk>/", views.CRMLeadUpdateView.as_view(), name="crmlead_update"),
    path("crm/opportunities/", views.OpportunityListView.as_view(), name="opportunity_list"),
    path("crm/opportunities/new/", views.OpportunityCreateView.as_view(), name="opportunity_create"),
    path("crm/opportunities/<int:pk>/", views.OpportunityUpdateView.as_view(), name="opportunity_update"),
    path("crm/campaigns/", views.CampaignListView.as_view(), name="campaign_list"),
    path("crm/campaigns/new/", views.CampaignCreateView.as_view(), name="campaign_create"),
    path("crm/campaigns/<int:pk>/", views.CampaignUpdateView.as_view(), name="campaign_update"),
    # Budgeting
    path("budgeting/budgets/", views.BudgetListView.as_view(), name="budget_list"),
    path("budgeting/budgets/new/", views.BudgetCreateView.as_view(), name="budget_create"),
    path("budgeting/budgets/<int:pk>/", views.BudgetUpdateView.as_view(), name="budget_update"),
    path("budgeting/lines/", views.BudgetLineListView.as_view(), name="budgetline_list"),
    path("budgeting/lines/new/", views.BudgetLineCreateView.as_view(), name="budgetline_create"),
    path("budgeting/lines/<int:pk>/", views.BudgetLineUpdateView.as_view(), name="budgetline_update"),
    # Integrations
    path(
        "integrations/endpoints/",
        views.IntegrationEndpointListView.as_view(),
        name="integrationendpoint_list",
    ),
    path(
        "integrations/endpoints/new/",
        views.IntegrationEndpointCreateView.as_view(),
        name="integrationendpoint_create",
    ),
    path(
        "integrations/endpoints/<int:pk>/",
        views.IntegrationEndpointUpdateView.as_view(),
        name="integrationendpoint_update",
    ),
    path("integrations/pos-devices/", views.POSDeviceListView.as_view(), name="posdevice_list"),
    path("integrations/pos-devices/new/", views.POSDeviceCreateView.as_view(), name="posdevice_create"),
    path("integrations/pos-devices/<int:pk>/", views.POSDeviceUpdateView.as_view(), name="posdevice_update"),
    # Localization & Tax
    path("localization/", views.LocaleConfigListView.as_view(), name="localeconfig_list"),
    path("localization/new/", views.LocaleConfigCreateView.as_view(), name="localeconfig_create"),
    path("localization/<int:pk>/", views.LocaleConfigUpdateView.as_view(), name="localeconfig_update"),
]
