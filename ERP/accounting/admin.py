import json

from django.contrib import admin, messages
from django.utils import timezone

from accounting.services.ird_submission_service import IRDSubmissionService
from accounting.tasks import process_ird_submission
from accounting.services.landed_cost_service import LandedCostService

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
    LandedCostDocument,
    LandedCostLine,
    LandedCostAllocation,
    SalesInvoice,
    SalesInvoiceLine,
    DeliveryNote,
    DeliveryNoteLine,
    ARReceipt,
    ARReceiptLine,
    APPayment,
    APPaymentLine,
    PaymentApproval,
    PaymentBatch,
    BankAccount,
    CashAccount,
    BankTransaction,
    AuditLog,
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


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    list_display = (
        'organization',
        'from_currency',
        'to_currency',
        'rate_date',
        'exchange_rate',
        'is_average_rate',
        'is_active',
        'source',
    )
    list_filter = ('organization', 'from_currency', 'to_currency', 'is_average_rate', 'is_active')
    search_fields = (
        'organization__name',
        'from_currency__currency_code',
        'to_currency__currency_code',
        'source',
    )
    date_hierarchy = 'rate_date'
    autocomplete_fields = ('organization', 'from_currency', 'to_currency')


@admin.register(JournalType)
class JournalTypeAdmin(admin.ModelAdmin):
    """Admin interface for Journal Types."""
    list_display = ['code', 'name', 'organization', 'is_system_type', 'requires_approval', 'is_active']
    list_filter = ['organization', 'is_system_type', 'requires_approval', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['organization', 'code']

# admin.site.register(JournalLine)  # Registered as inline with Journal
admin.site.register(Attachment)
admin.site.register(Approval)


class JournalLineInline(admin.TabularInline):
    """Inline admin for JournalLine within Journal admin."""
    model = JournalLine
    extra = 1
    fields = [
        'line_number', 'account', 'description', 
        'debit_amount', 'credit_amount', 
        'department', 'project', 'cost_center',
        'tax_code', 'tax_rate', 'memo'
    ]
    autocomplete_fields = ['account', 'department', 'project', 'cost_center', 'tax_code']
    ordering = ['line_number']


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    """Admin interface for Journal entries with inline lines."""
    
    list_display = [
        'journal_number', 'journal_type', 'journal_date', 
        'description_short', 'total_debit', 'total_credit', 
        'status', 'created_by', 'created_at'
    ]
    
    list_filter = [
        'status', 'journal_type', 'period', 'organization',
        'journal_date', 'created_at'
    ]
    
    search_fields = [
        'journal_number', 'description', 'reference',
        'created_by__username'
    ]
    
    readonly_fields = [
        'journal_number', 'total_debit', 'total_credit', 
        'posted_at', 'posted_by', 'approved_at', 'approved_by',
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'imbalance_display'
    ]
    
    fieldsets = (
        ('Journal Information', {
            'fields': (
                'organization', 'journal_type', 'period', 
                'journal_number', 'journal_date', 'reference'
            )
        }),
        ('Details', {
            'fields': ('description', 'currency_code', 'exchange_rate')
        }),
        ('Totals', {
            'fields': ('total_debit', 'total_credit', 'imbalance_display'),
            'classes': ('collapse',)
        }),
        ('Status & Workflow', {
            'fields': (
                'status', 'is_locked', 
                ('posted_at', 'posted_by'),
                ('approved_at', 'approved_by')
            )
        }),
        ('Audit Information', {
            'fields': (
                ('created_at', 'created_by'),
                ('updated_at', 'updated_by')
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [JournalLineInline]
    
    autocomplete_fields = ['organization', 'journal_type', 'period']
    
    date_hierarchy = 'journal_date'
    
    def description_short(self, obj):
        """Truncated description for list display."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Description'
    
    def imbalance_display(self, obj):
        """Display imbalance with color coding."""
        imbalance = obj.imbalance
        if imbalance == 0:
            return f"✓ Balanced (0.00)"
        return f"⚠ Imbalance: {imbalance}"
    imbalance_display.short_description = 'Balance Check'
    
    def save_model(self, request, obj, form, change):
        """Auto-populate created_by and updated_by fields."""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Save inline formset and update totals."""
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:  # New line
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.save()
        
        for obj in formset.deleted_objects:
            obj.delete()
        
        # Update journal totals after saving lines
        form.instance.update_totals()
        form.instance.save(update_fields=['total_debit', 'total_credit'])
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'organization', 'journal_type', 'period',
            'created_by', 'posted_by', 'approved_by'
        )
    
    actions = ['recalculate_totals', 'mark_as_draft']
    
    def recalculate_totals(self, request, queryset):
        """Admin action to recalculate totals for selected journals."""
        count = 0
        for journal in queryset:
            if journal.status == 'draft':  # Only for draft journals
                journal.update_totals()
                journal.save(update_fields=['total_debit', 'total_credit'])
                count += 1
        
        self.message_user(
            request, 
            f"Successfully recalculated totals for {count} journal(s).",
            messages.SUCCESS
        )
    recalculate_totals.short_description = "Recalculate totals (draft only)"
    
    def mark_as_draft(self, request, queryset):
        """Admin action to mark journals as draft (if allowed)."""
        count = queryset.filter(
            status__in=['rejected']
        ).update(status='draft')
        
        self.message_user(
            request,
            f"Successfully marked {count} journal(s) as draft.",
            messages.SUCCESS
        )
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


class LandedCostLineInline(admin.TabularInline):
    model = LandedCostLine
    extra = 0
    fields = ('description', 'amount', 'credit_account')
    autocomplete_fields = ('credit_account',)


class LandedCostAllocationInline(admin.TabularInline):
    model = LandedCostAllocation
    extra = 0
    fields = ('purchase_line', 'amount', 'factor')
    readonly_fields = fields
    can_delete = False


@admin.register(LandedCostDocument)
class LandedCostDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'purchase_invoice',
        'document_date',
        'basis',
        'total_cost',
        'is_applied',
    )
    list_filter = ('basis', 'is_applied', 'organization')
    search_fields = ('purchase_invoice__invoice_number', 'purchase_invoice__vendor__display_name')
    readonly_fields = ('applied_at', 'journal')
    inlines = [LandedCostLineInline, LandedCostAllocationInline]
    actions = ['apply_selected']

    @admin.action(description="Apply landed cost")
    def apply_selected(self, request, queryset):
        service = LandedCostService(request.user)
        applied = 0
        for doc in queryset.select_related("purchase_invoice", "organization"):
            try:
                service.apply(doc)
                applied += 1
            except Exception as exc:  # noqa: BLE001 - surface failure to admin
                self.message_user(request, f"{doc}: {exc}", level=messages.ERROR)
        if applied:
            self.message_user(
                request,
                f"Applied landed cost on {applied} document(s).",
                level=messages.SUCCESS,
            )

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

    @admin.display(description="IRD response")
    def ird_last_response_pretty(self, obj):
        if not getattr(obj, 'ird_last_response', None):
            return "—"
        return json.dumps(obj.ird_last_response, indent=2, sort_keys=True)


class DeliveryNoteLineInline(admin.TabularInline):
    model = DeliveryNoteLine
    extra = 1
    fields = [
        'line_number', 'product', 'product_code', 'description', 'quantity'
    ]
    readonly_fields = []


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = ('note_number', 'customer_display_name', 'delivery_date', 'warehouse', 'status')
    search_fields = ('note_number', 'customer_display_name', 'reference_number')
    list_filter = ('organization', 'warehouse', 'status')
    inlines = [DeliveryNoteLineInline]
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


# ============================================================================
# AUDIT LOG & ACTIVITY TRACKING ADMIN
# ============================================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only Activity Log for admins to view all system changes.
    Scoped by organization, filterable by date, user, and action type.
    Enforces RBAC: only staff with audit permission can view.
    """
    # Read-only fields to prevent modification
    readonly_fields = (
        'timestamp', 'user', 'organization', 'action', 'content_type',
        'object_id', 'content_object', 'changes', 'details', 'ip_address',
        'content_hash', 'previous_hash', 'is_immutable'
    )
    
    # Display configuration
    list_display = ('get_action_badge', 'get_model_name', 'user', 'timestamp', 'organization', 'ip_address')
    list_filter = (
        ('timestamp', admin.DateFieldListFilter),
        'action',
        'organization',
        'user',
        'content_type',
    )
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'ip_address',
        'details',
    )
    
    fieldsets = (
        ('Change Details', {
            'fields': ('timestamp', 'user', 'organization', 'action', 'details')
        }),
        ('Audit Target', {
            'fields': ('content_type', 'object_id', 'content_object')
        }),
        ('Change Data', {
            'fields': ('changes',),
            'classes': ('collapse',)
        }),
        ('Network & Security', {
            'fields': ('ip_address',),
            'classes': ('collapse',)
        }),
        ('Integrity (Hash-Chaining)', {
            'fields': ('content_hash', 'previous_hash', 'is_immutable'),
            'classes': ('collapse',)
        }),
    )
    
    list_select_related = ('user', 'organization', 'content_type')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def has_view_permission(self, request, obj=None):
        """Check if user is allowed to view audit logs."""
        if not request.user.is_staff:
            return False
        # Superusers and admins can view
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'role') and request.user.role in ['superadmin', 'admin']:
            return True
        return False
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit records."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit records."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superadmin can delete (for archival/compliance)."""
        return request.user.is_superuser
    
    def get_queryset(self, request):
        """Filter audit logs to current organization for non-superusers."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers only see their organization's logs
            active_org = getattr(request, 'active_organization', None)
            if active_org:
                qs = qs.filter(organization=active_org)
        return qs
    
    def get_action_badge(self, obj):
        """Display action as colored badge."""
        action_colors = {
            'create': '#28a745',    # green
            'update': '#ffc107',    # yellow
            'delete': '#dc3545',    # red
            'export': '#17a2b8',    # cyan
            'print': '#6f42c1',     # purple
            'approve': '#20c997',   # teal
            'reject': '#fd7e14',    # orange
            'post': '#007bff',      # blue
            'sync': '#6c757d',      # gray
        }
        color = action_colors.get(obj.action, '#6c757d')
        return f'<span style="background-color: {color}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{obj.get_action_display()}</span>'
    get_action_badge.short_description = 'Action'
    get_action_badge.allow_tags = True
    
    def get_model_name(self, obj):
        """Display the model name that was changed."""
        return obj.content_type.model if obj.content_type else '-'
    get_model_name.short_description = 'Model'
    
    actions = ['export_as_csv']
    
    def export_as_csv(self, request, queryset):
        """Export selected audit logs to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'User', 'Organization', 'Action', 'Model', 'Object ID', 'IP Address', 'Details'])
        
        for audit in queryset:
            writer.writerow([
                audit.timestamp.isoformat(),
                str(audit.user),
                str(audit.organization) if audit.organization else '',
                audit.get_action_display(),
                audit.content_type.model if audit.content_type else '',
                audit.object_id,
                audit.ip_address or '',
                audit.details or '',
            ])
        
        return response
    export_as_csv.short_description = 'Export selected audit logs to CSV'

