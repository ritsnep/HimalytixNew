from django.contrib import admin
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
)

# @admin.register(Journal)
# class JournalAdmin(admin.ModelAdmin):
#     list_display = ('batch_number', 'journal_type', 'period', 'status', 'created_at')
#     search_fields = ('batch_number', 'description')
#     list_filter = ('journal_type', 'status', 'period')

admin.site.register(FiscalYear)
admin.site.register(AccountingPeriod)
admin.site.register(Department)
admin.site.register(Project)
admin.site.register(CostCenter)
admin.site.register(AccountType)
admin.site.register(ChartOfAccount)
admin.site.register(Currency)
admin.site.register(CurrencyExchangeRate)
admin.site.register(JournalType)
admin.site.register(JournalLine)
admin.site.register(Attachment)
admin.site.register(Approval)
admin.site.register(TaxAuthority)
admin.site.register(TaxType)
admin.site.register(TaxCode)
admin.site.register(VoucherModeConfig)
admin.site.register(VoucherModeDefault)
admin.site.register(GeneralLedger)
admin.site.register(BankAccount)
admin.site.register(CashAccount)
admin.site.register(BankTransaction)
admin.site.register(BankStatement)
admin.site.register(BankStatementLine)

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


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'customer',
        'invoice_date',
        'due_date',
        'status',
        'total',
    )
    search_fields = ('invoice_number', 'customer__display_name', 'reference_number')
    list_filter = ('organization', 'status')
    readonly_fields = ('subtotal', 'tax_total', 'total', 'base_currency_total')
    inlines = [SalesInvoiceLineInline]


class ARReceiptLineInline(admin.TabularInline):
    model = ARReceiptLine
    extra = 0
    fields = ('invoice', 'applied_amount', 'discount_taken')


@admin.register(ARReceipt)
class ARReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'customer', 'receipt_date', 'payment_method', 'amount')
    search_fields = ('receipt_number', 'customer__display_name', 'reference')
    list_filter = ('organization', 'payment_method')
    inlines = [ARReceiptLineInline]


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


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'source_object', 'source_id', 'created_at')
    readonly_fields = ('event_type', 'payload', 'source_object', 'source_id', 'created_at')


class APPaymentLineInline(admin.TabularInline):
    model = APPaymentLine
    extra = 0
    fields = ('invoice', 'applied_amount', 'discount_taken')


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

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'fiscal_year', 'organization', 'version', 'status')
    list_filter = ('status', 'organization', 'fiscal_year')
    search_fields = ('name',)
    inlines = [BudgetLineInline]
@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'scheduled_date', 'status', 'total_amount')
    search_fields = ('batch_number',)
    list_filter = ('organization', 'status')
    inlines = [APPaymentInline]
