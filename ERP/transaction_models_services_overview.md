# ERP Transaction Models and Services Overview

This document provides a comprehensive overview of all transaction-related models and their corresponding services across the ERP system. The system is organized around the accounting app as the central hub for transaction processing, with specialized apps handling procurement, sales, and inventory operations.

## Architecture Overview

The ERP system follows a modular architecture where:
- **Accounting App**: Core transaction processing, general ledger, and financial operations
- **Purchasing App**: Procurement transactions (purchase orders, goods receipts)
- **Sales App**: Sales transactions (orders, invoices, quotations)
- **Inventory App**: Stock movement transactions
- **POS App**: Point-of-sale transactions

Transaction models are primarily stored in the accounting app, with services providing business logic orchestration.

## 1. Accounting App (Core Transaction Processing)

### Transaction Models

#### Core Journal Models
- **Journal / JournalLine**: General ledger entries for all financial transactions
  - Supports multi-currency, dimensional accounting (department, project, cost center)
  - Status workflow: draft → awaiting_approval → approved → posted → reversed
  - Handles inventory transactions via metadata

- **GeneralLedger**: Posted journal entries in the general ledger
  - Immutable audit trail with balance tracking
  - Supports period-end processing and reporting

#### Purchase Transactions
- **PurchaseInvoice / PurchaseInvoiceLine**: Vendor invoice processing
  - Three-way matching (PO → Receipt → Invoice)
  - Tax calculations and GR/IR clearing accounts
  - Integration with inventory receipts

- **PurchaseOrder / PurchaseOrderLine**: Purchase commitments (stored in purchasing app)
- **GoodsReceipt / GoodsReceiptLine**: Goods received against POs (stored in purchasing app)

#### Sales Transactions
- **SalesInvoice / SalesInvoiceLine**: Customer billing
  - IRD (Nepal tax authority) integration for real-time submission
  - Tax calculations and receivable management
  - QR code generation for e-billing

- **SalesOrder / SalesOrderLine**: Customer order commitments
- **Quotation / QuotationLine**: Non-binding customer quotes
- **DeliveryNote / DeliveryNoteLine**: Goods dispatch documentation

#### Payment Processing
- **APPayment / APPaymentLine**: Outbound vendor payments
- **ARReceipt / ARReceiptLine**: Inbound customer receipts

#### Supporting Models
- **Vendor / Customer**: Master data with payment terms and credit limits
- **ChartOfAccount**: GL account master with control account types
- **TaxCode / TaxType**: Tax configuration and liability tracking
- **CurrencyExchangeRate**: Multi-currency support
- **FiscalYear / AccountingPeriod**: Financial period control
- **JournalType**: Transaction type configuration

### Services

#### Core Posting Infrastructure
- **PostingService**: Central journal posting and reversal engine
  - Validates double-entry bookkeeping
  - Manages period controls and permissions
  - Handles currency conversion and balance updates
  - Supports optimistic locking for concurrent edits

- **InventoryPostingService**: Stock movement posting
  - Records receipts, issues, and adjustments
  - Maintains perpetual inventory balances
  - Creates GL entries for inventory transactions

#### Transaction-Specific Services
- **PurchaseInvoiceService**: Invoice lifecycle management
  - Creates and validates invoices
  - Performs three-way matching
  - Posts to GL with GR/IR handling

- **SalesInvoiceService**: Sales invoice processing
  - Invoice creation and validation
  - Tax calculations and IRD submission
  - Payment allocation and aging

- **SalesOrderService**: Order management
  - Status transitions and fulfillment tracking
  - Conversion to invoices

- **QuotationService**: Quote processing
  - Conversion to orders or invoices
  - Status management

- **APPaymentService**: Vendor payment processing
  - Payment creation and approval workflows
  - Bank account integration

#### Supporting Services
- **ExchangeRateService**: Currency rate management
- **TaxEngine**: Tax calculations and compliance
- **ApprovalWorkflowService**: Multi-step approval processes
- **DocumentSequenceService**: Auto-numbering for documents
- **IRDSubmissionService**: Nepal tax authority integration
- **ReportService**: Financial and transaction reporting
- **AuditService**: Transaction audit trails
- **ProductService** (Inventory App): Product master data management
  - Retrieves product details (unit, HS code, description, VAT)
  - Validates stock availability and pricing
  - Manages standard and party-specific prices
- **VendorService** (Accounting App): Vendor master data management
  - Retrieves vendor details (balance, credit limit, PAN)
  - Auto-selects agents and areas based on vendor
  - Validates credit limits and payment terms
- **PricingService** (Accounting App): Pricing logic and party-specific rates
  - Manages standard vs. party-specific pricing
  - Calculates discounts and validates pricing rules
  - Supports bulk pricing operations
- **AgentService** (Accounting App): Agent and area management
  - Auto-selects agents based on vendor/location
  - Manages agent assignments and validations
  - Provides agent details and area hierarchies
- **ValidationService** (Accounting App): Centralized form and business rule validation
  - Validates complete transaction data
  - Checks credit limits, stock, and pricing rules
  - Provides field-level validation with context
- **NotificationService** (Accounting App): Event-driven notifications
  - Sends approval requests and status updates
  - Handles vendor communications and alerts
  - Manages system error notifications

## 2. Purchasing App (Procurement Transactions)

### Transaction Models
- **PurchaseOrder / PurchaseOrderLine**: Purchase commitments
  - Quantity tracking (ordered, received, invoiced)
  - Approval workflows and status management

- **GoodsReceipt / GoodsReceiptLine**: Physical receipt of goods
  - Quality control and inspection
  - Warehouse allocation and stock updates

### Services
Primarily uses accounting services for financial posting, with procurement-specific logic in views and forms.

## 3. Sales App (Sales Transactions)

### Transaction Models
All sales models are consolidated in the accounting app for unified processing.

### Services
- **SalesOrderService, SalesInvoiceService, QuotationService**: Handled in accounting app
- Specialized sales reporting and analytics services

## 4. Inventory App (Stock Transactions)

### Transaction Models
- **Product**: Item master with accounting integration
- **InventoryItem**: Stock balances by warehouse/location/batch
- **StockLedger**: Detailed transaction history
- **Warehouse / Location**: Storage hierarchy
- **Batch**: Lot tracking for inventory

### Services
- **InventoryPostingService**: Stock movement processing (integrated with accounting)
- Warehouse management and allocation services

## 5. POS App (Point-of-Sale Transactions)

### Transaction Models
- **Cart / CartItem**: Shopping cart transactions
- Sales transactions flow through accounting models (SalesInvoice)

### Services
- Point-of-sale processing with integration to accounting
- Real-time inventory updates and payment processing

## Service Architecture Patterns

### Common Patterns
1. **Transaction Atomicity**: All financial operations use database transactions
2. **Validation Pipeline**: Multi-step validation before posting
3. **Event Emission**: Integration events for downstream processing
4. **Audit Trails**: Immutable logging of all changes
5. **Permission Checks**: Role-based access control
6. **Status Workflows**: Controlled state transitions

### Integration Points
- **Cross-App References**: Models reference each other (e.g., invoices link to inventory items)
- **Shared Services**: Accounting services used by all transaction apps
- **Event-Driven**: Loose coupling through event emission
- **Unified Posting**: All transactions eventually post through PostingService

## Transaction Flow Examples

### Purchase to Pay Cycle
1. PurchaseOrder (purchasing) → GoodsReceipt (purchasing) → PurchaseInvoice (accounting)
2. Three-way matching validation
3. GL posting with inventory updates
4. Payment processing and reconciliation

### Order to Cash Cycle
1. Quotation (accounting) → SalesOrder (accounting) → DeliveryNote (accounting)
2. SalesInvoice creation and IRD submission
3. Payment receipt and allocation
4. Revenue recognition

### Journal Entry Flow
1. Journal creation with validation
2. Approval workflow (if required)
3. Posting to general ledger
4. Inventory transactions (if applicable)
5. Reversal capability

## Key Business Rules

### Financial Controls
- Double-entry bookkeeping validation
- Period-end controls and closures
- Multi-currency handling
- Tax compliance and reporting

### Operational Controls
- Inventory accuracy through perpetual counting
- Approval workflows for high-value transactions
- Audit trails for regulatory compliance
- Automated reconciliation processes

## Development Guidelines

### Adding New Transaction Types
1. Define models in appropriate app (accounting for financial transactions)
2. Create corresponding service class following established patterns
3. Configure voucher types and approval workflows
4. Add validation rules and business logic
5. Integrate with existing posting infrastructure
6. Add reporting and audit capabilities

### Service Development Best Practices
- Use transaction.atomic() for data consistency
- Implement proper error handling and validation
- Follow event-driven architecture for loose coupling
- Include comprehensive audit logging
- Support idempotent operations where applicable
- Document service interfaces and dependencies

This overview serves as a reference for understanding the transaction processing architecture and should be updated as new transaction types are added to the system.
