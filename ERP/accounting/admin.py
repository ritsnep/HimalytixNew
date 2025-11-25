import json

from django.contrib import admin, messages
from django.utils import timezone

from accounting.services.ird_submission_service import IRDSubmissionService
from accounting.tasks import process_ird_submission

from .models import (
    FiscalYear,
    AccountingPeriod,
    Department,
    Project,
    CostCenter,
    AccountType,
    ChartOfAccount,
    Currency,
    CurrencyExchangeRate,
    JournalType,
    Journal,
    JournalLine,
    TaxAuthority,
    TaxType,
    TaxCode,
    VoucherModeConfig,
    VoucherModeDefault,
    GeneralLedger,
    Attachment,
    Approval,
    PaymentTerm,
    Vendor,
    VendorAddress,
    VendorContact,
    VendorBankAccount,
    Customer,
    CustomerAddress,
    CustomerContact,
    CustomerBankAccount,
    Dimension,
    DimensionValue,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceMatch,
    SalesInvoice,
    SalesInvoiceLine,
    ARReceipt,
    ARReceiptLine,
    APPayment,
    APPaymentLine,
    PaymentApproval,
    PaymentBatch,
    BankAccount,
    CashAccount,
    BankTransaction,
    BankStatement,
    BankStatementLine,
    Budget,
    BudgetLine,
    AssetCategory,
    Asset,
    AssetEvent,
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalTask,
    IntegrationEvent,
    JournalDebugPreference,
    UDFDefinition,
    UDFValue,
    IRDSubmissionTask,
)

# @admin.register(Journal)
# class JournalAdmin(admin.ModelAdmin):
#     list_display = ('batch_number', 'journal_type', 'period', 'status', 'created_at')
#     search_fields = ('batch_number', 'description')
#     list_filter = ('journal_type', 'status', 'period')

@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name')
    list_display = ('code', 'name', 'organization', 'is_current', 'status')
    list_filter = ('organization', 'is_current', 'status')


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    search_fields = ('name', 'fiscal_year__code')
    list_display = ('name', 'fiscal_year', 'organization', 'status', 'start_date', 'end_date')
    list_filter = ('organization', 'status')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name')
    list_display = ('code', 'name', 'organization')
    list_filter = ('organization',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name', 'description')
    list_display = ('code', 'name', 'organization', 'is_active')
    list_filter = ('organization', 'is_active')


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name', 'description')
    list_display = ('code', 'name', 'organization', 'is_active')
    list_filter = ('organization', 'is_active')


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name')
    list_display = ('code', 'name', 'nature', 'is_active')
    list_filter = ('nature', 'is_active')


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(admin.ModelAdmin):
    search_fields = ('account_code', 'account_name')
    list_display = ('account_code', 'account_name', 'account_type', 'organization', 'is_active')
    list_filter = ('organization', 'account_type', 'is_active')


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    search_fields = ('currency_code', 'currency_name')
    list_display = ('currency_code', 'currency_name', 'symbol', 'is_active')
    list_filter = ('is_active',)


admin.site.register(CurrencyExchangeRate)
admin.site.register(JournalType)
admin.site.register(JournalLine)
admin.site.register(Attachment)
admin.site.register(Approval)
@admin.register(TaxAuthority)
class TaxAuthorityAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')


@admin.register(TaxType)
class TaxTypeAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')


@admin.register(TaxCode)
class TaxCodeAdmin(admin.ModelAdmin):
    search_fields = ('code', 'name', 'description')
    list_display = ('code', 'name', 'tax_rate', 'is_active')
    list_filter = ('is_active',)
admin.site.register(VoucherModeConfig)
admin.site.register(VoucherModeDefault)
admin.site.register(GeneralLedger)
admin.site.register(BankAccount)
admin.site.register(CashAccount)
admin.site.register(BankTransaction)
admin.site.register(BankStatement)
admin.site.register(BankStatementLine)


@admin.register(UDFDefinition)
class UDFDefinitionAdmin(admin.ModelAdmin):
    list_display = ("display_name", "field_name", "field_type", "content_type", "organization", "is_active")
    list_filter = ("organization", "content_type", "field_type", "is_active", "is_filterable", "is_pivot_dim")
    search_fields = ("display_name", "field_name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("organization",)


@admin.register(UDFValue)
class UDFValueAdmin(admin.ModelAdmin):
    list_display = ("udf_definition", "content_type", "object_id", "created_at")
    list_filter = ("udf_definition", "content_type")
    search_fields = ("object_id",)

@admin.register(JournalDebugPreference)
class JournalDebugPreferenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "enabled", "updated_at", "updated_by")
    list_filter = ("enabled",)
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization", "updated_by")
    list_select_related = ("organization", "updated_by")


class VendorAddressInline(admin.TabularInline):
    model = VendorAddress
    extra = 0
    fields = ('address_type', 'line1', 'city', 'country_code', 'is_primary')


class VendorContactInline(admin.TabularInline):
    model = VendorContact
    extra = 0
    fields = ('name', 'email', 'phone', 'is_primary')


class VendorBankInline(admin.TabularInline):
    model = VendorBankAccount
    extra = 0
    fields = ('bank_name', 'account_number', 'currency', 'is_primary')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('code', 'display_name', 'status', 'organization', 'payment_term', 'is_active')
    search_fields = ('code', 'display_name', 'legal_name', 'tax_id')
    list_filter = ('organization', 'status', 'payment_term', 'on_hold')
    inlines = [VendorAddressInline, VendorContactInline, VendorBankInline]
    list_select_related = ('organization', 'payment_term')


class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0
    fields = ('address_type', 'line1', 'city', 'country_code', 'is_primary')


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 0
    fields = ('name', 'email', 'phone', 'is_primary')


class CustomerBankInline(admin.TabularInline):
    model = CustomerBankAccount
    extra = 0
    fields = ('bank_name', 'account_number', 'currency', 'is_primary')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'display_name', 'status', 'organization', 'payment_term', 'is_active')
    search_fields = ('code', 'display_name', 'legal_name', 'tax_id')
    list_filter = ('organization', 'status', 'payment_term', 'on_credit_hold')
    inlines = [CustomerAddressInline, CustomerContactInline, CustomerBankInline]
    list_select_related = ('organization', 'payment_term')


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'term_type', 'organization', 'net_due_days', 'discount_percent', 'is_active')
    list_filter = ('term_type', 'organization', 'is_active')
    search_fields = ('code', 'name', 'description')


@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'dimension_type', 'organization', 'is_active')
    list_filter = ('organization', 'dimension_type', 'is_active')
    search_fields = ('code', 'name', 'description')


@admin.register(DimensionValue)
class DimensionValueAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'dimension', 'is_active')
    list_filter = ('dimension', 'is_active')
    search_fields = ('code', 'name', 'description')


class PurchaseInvoiceLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 0
    fields = (
        'line_number',
        'description',
        'account',
        'quantity',
        'unit_cost',
        'line_total',
        'tax_code',
        'tax_amount',
        'po_reference',
        'receipt_reference',
    )
    readonly_fields = ('line_total',)
    autocomplete_fields = ('account', 'tax_code')


class PurchaseInvoiceMatchInline(admin.TabularInline):
    model = PurchaseInvoiceMatch
    extra = 0
    fields = (
        'invoice_line',
        'po_reference',
        'receipt_reference',
        'expected_quantity',
        'received_quantity',
        'invoiced_quantity',
        'unit_price_variance',
        'status',
    )
    readonly_fields = fields


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'vendor',
        'invoice_date',
        'due_date',
        'status',
        'match_status',
        'total',
    )
    search_fields = ('invoice_number', 'vendor__display_name', 'po_number', 'receipt_reference')
    list_filter = ('organization', 'status', 'match_status')
    readonly_fields = ('subtotal', 'tax_total', 'total', 'base_currency_total')
    inlines = [PurchaseInvoiceLineInline, PurchaseInvoiceMatchInline]
    list_select_related = ('vendor', 'organization')


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 0
    fields = (
        'line_number',
        'description',
        'revenue_account',
        'quantity',
        'unit_price',
        'line_total',
        'tax_code',
        'tax_amount',
    )
    readonly_fields = ('line_total',)
    autocomplete_fields = ('revenue_account', 'tax_code')


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'customer',
        'invoice_date',
        'due_date',
        'status',
        'total',
        'ird_status',
        'ird_ack_id',
        'ird_last_submitted_at',
    )
    search_fields = ('invoice_number', 'customer__display_name', 'reference_number', 'ird_ack_id')
    list_filter = ('organization', 'status', 'ird_status')
    readonly_fields = (
        'subtotal',
        'tax_total',
        'total',
        'base_currency_total',
        'ird_status',
        'ird_ack_id',
        'ird_last_submitted_at',
        'ird_signature',
        'ird_last_response_pretty',
    )
    inlines = [SalesInvoiceLineInline]
    list_select_related = ('customer', 'organization')
    actions = ['action_queue_ird_submission', 'action_reset_ird_metadata']

    @admin.display(description="IRD response")
    def ird_last_response_pretty(self, obj):
        if not obj.ird_last_response:
            return "—"
        return json.dumps(obj.ird_last_response, indent=2, sort_keys=True)

    @admin.action(description="Queue IRD submission")
    def action_queue_ird_submission(self, request, queryset):
        service = IRDSubmissionService(request.user)
        queued = 0
        already_pending = 0
        for invoice in queryset:
            has_pending = invoice.ird_submission_tasks.filter(
                status__in=[
                    IRDSubmissionTask.STATUS_PENDING,
                    IRDSubmissionTask.STATUS_PROCESSING,
                ]
            ).exists()
            service.enqueue_invoice(invoice)
            if has_pending:
                already_pending += 1
            else:
                queued += 1
        if queued:
            messages.success(request, f"Queued {queued} invoice(s) for IRD submission.")
        if already_pending:
            messages.warning(request, f"{already_pending} invoice(s) already had a pending IRD job.")

    @admin.action(description="Reset IRD metadata (allow re-submit)")
    def action_reset_ird_metadata(self, request, queryset):
        updated = queryset.update(
            ird_signature='',
            ird_ack_id='',
            ird_status='',
            ird_last_response={},
            ird_last_submitted_at=None,
        )
        messages.success(request, f"Cleared IRD metadata on {updated} invoice(s).")


class ARReceiptLineInline(admin.TabularInline):
    model = ARReceiptLine
    extra = 0
    fields = ('invoice', 'applied_amount', 'discount_taken')
    autocomplete_fields = ('invoice',)


@admin.register(ARReceipt)
class ARReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'customer', 'receipt_date', 'payment_method', 'amount')
    search_fields = ('receipt_number', 'customer__display_name', 'reference')
    list_filter = ('organization', 'payment_method')
    inlines = [ARReceiptLineInline]
    list_select_related = ('customer', 'organization')


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'depreciation_expense_account', 'accumulated_depreciation_account')
    list_filter = ('organization',)
    search_fields = ('name',)


class AssetEventInline(admin.TabularInline):
    model = AssetEvent
    extra = 0
    fields = ('event_type', 'event_date', 'amount', 'description')


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'category', 'acquisition_date', 'cost', 'accumulated_depreciation', 'status')
    list_filter = ('organization', 'category', 'status')
    search_fields = ('name',)
    inlines = [AssetEventInline]
    list_select_related = ('organization', 'category')


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0
    fields = ('sequence', 'role', 'min_amount')


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'area', 'active')
    inlines = [ApprovalStepInline]


@admin.register(ApprovalTask)
class ApprovalTaskAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'content_object', 'status', 'current_step', 'updated_at')
    list_filter = ('status',)
    search_fields = ('workflow__name', 'notes')
    list_select_related = ('workflow',)


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'source_object', 'source_id', 'created_at')
    readonly_fields = ('event_type', 'payload', 'source_object', 'source_id', 'created_at')


@admin.register(IRDSubmissionTask)
class IRDSubmissionTaskAdmin(admin.ModelAdmin):
    list_display = (
        'submission_id',
        'invoice',
        'organization',
        'status',
        'priority',
        'attempts',
        'next_attempt_at',
        'last_attempt_at',
    )
    list_filter = ('status', 'priority', 'organization')
    search_fields = ('invoice__invoice_number', 'invoice__customer__display_name')
    autocomplete_fields = ('invoice', 'organization')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    actions = ['action_retry_submissions']

    @admin.action(description="Retry selected submissions now")
    def action_retry_submissions(self, request, queryset):
        count = 0
        now = timezone.now()
        for task in queryset:
            task.status = IRDSubmissionTask.STATUS_PENDING
            task.next_attempt_at = now
            task.last_error = ''
            task.save(update_fields=['status', 'next_attempt_at', 'last_error', 'updated_at'])
            process_ird_submission.delay(task.pk)
            count += 1
        messages.success(request, f"Queued {count} IRD submission(s) for retry.")


class APPaymentLineInline(admin.TabularInline):
    model = APPaymentLine
    extra = 0
    fields = ('invoice', 'applied_amount', 'discount_taken')
    autocomplete_fields = ('invoice',)


class PaymentApprovalInline(admin.TabularInline):
    model = PaymentApproval
    extra = 0
    fields = ('approver', 'status', 'notes', 'decided_at')
    readonly_fields = ('decided_at',)


@admin.register(APPayment)
class APPaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'vendor', 'payment_date', 'payment_method', 'status', 'amount')
    search_fields = ('payment_number', 'vendor__display_name')
    list_filter = ('organization', 'status', 'payment_method')
    inlines = [APPaymentLineInline, PaymentApprovalInline]
    list_select_related = ('vendor', 'organization')


class APPaymentInline(admin.TabularInline):
    model = APPayment
    extra = 0
    fields = ('payment_number', 'vendor', 'payment_date', 'amount', 'status')


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 0
    fields = (
        'account',
        'dimension_value',
        'cost_center',
        'project',
        'department',
        'total_amount',
    )
    readonly_fields = ('total_amount',)
    autocomplete_fields = ('account', 'dimension_value', 'cost_center', 'project', 'department')

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'fiscal_year', 'organization', 'version', 'status')
    list_filter = ('status', 'organization', 'fiscal_year')
    search_fields = ('name',)
    inlines = [BudgetLineInline]
    list_select_related = ('fiscal_year', 'organization')
@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'scheduled_date', 'status', 'total_amount')
    search_fields = ('batch_number',)
    list_filter = ('organization', 'status')
    inlines = [APPaymentInline]
    list_select_related = ('organization',)
