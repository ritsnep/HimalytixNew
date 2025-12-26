from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from accounting.services.vendor_service import VendorService
from inventory.services.product_service import ProductService
from accounting.services.pricing_service import PricingService
from accounting.models import AccountingPeriod, Currency, ChartOfAccount, CostCenter, Department, Project
from inventory.models import Warehouse


class ValidationService:
    """
    Centralized validation service for forms and transactions.
    """

    @staticmethod
    def validate_voucher_header(header_data, voucher_config, organization):
        """
        Validate voucher header data including required fields, dates, and business rules.
        """
        errors = {}

        # Date and period validation
        voucher_date = (
            header_data.get('voucher_date') or
            header_data.get('journal_date') or
            header_data.get('transaction_date') or
            header_data.get('receipt_date')
        )

        if not voucher_date:
            errors['voucher_date'] = 'Voucher date is required'
        else:
            if isinstance(voucher_date, str):
                try:
                    voucher_date = datetime.strptime(voucher_date, '%Y-%m-%d').date()
                except ValueError:
                    errors['voucher_date'] = 'Invalid date format'
                    voucher_date = None

            if voucher_date:
                # Check if date is in open accounting period
                period = AccountingPeriod.get_for_date(organization, voucher_date)
                if not period:
                    errors['voucher_date'] = f'No open accounting period found for {voucher_date}'

                # Date order validations
                order_date = header_data.get('order_date')
                if order_date and voucher_date and order_date > voucher_date:
                    errors['order_date'] = 'Order date cannot be after voucher date'

                delivery_date = header_data.get('delivery_date')
                if delivery_date and order_date and delivery_date < order_date:
                    errors['delivery_date'] = 'Delivery date cannot be before order date'

                due_date = header_data.get('due_date')
                if due_date and voucher_date and due_date < voucher_date:
                    errors['due_date'] = 'Due date cannot be before voucher date'

        # Required business partners based on voucher type
        journal_type = getattr(voucher_config, 'journal_type', None)
        if journal_type:
            journal_type_code = getattr(journal_type, 'journal_type', '').lower()

            # Purchasing vouchers require vendor/supplier
            if 'purchase' in journal_type_code or 'grn' in journal_type_code:
                if not header_data.get('vendor') and not header_data.get('supplier'):
                    errors['vendor'] = 'Vendor is required for purchasing vouchers'

            # Sales vouchers require customer
            if 'sales' in journal_type_code or 'invoice' in journal_type_code:
                if not header_data.get('customer') and not header_data.get('client'):
                    errors['customer'] = 'Customer is required for sales vouchers'

            # Stock/inventory affecting vouchers require warehouse when affects_inventory
            if voucher_config.affects_inventory and 'warehouse' in str(voucher_config.schema_definition or '').lower():
                if not header_data.get('warehouse'):
                    errors['warehouse'] = 'Warehouse is required for inventory vouchers'

        # Currency and exchange rate validation
        currency_code = header_data.get('currency') or header_data.get('currency_code')
        if currency_code:
            try:
                currency = Currency.objects.get(
                    currency_code=currency_code,
                    is_active=True
                )
            except Currency.DoesNotExist:
                errors['currency'] = f'Currency {currency_code} is not active or does not exist'
        else:
            # Use organization base currency
            base_currency = getattr(organization, 'base_currency_code', None)
            if base_currency:
                currency_code = base_currency

        exchange_rate = header_data.get('exchange_rate')
        if exchange_rate is not None:
            try:
                exchange_rate = Decimal(str(exchange_rate))
                if exchange_rate <= 0:
                    errors['exchange_rate'] = 'Exchange rate must be positive'
            except (ValueError, TypeError):
                errors['exchange_rate'] = 'Invalid exchange rate format'

        # Reference uniqueness (optional, within type)
        reference = header_data.get('reference')
        if reference:
            from accounting.models import Voucher  # Assuming Voucher model exists
            if Voucher.objects.filter(organization=organization, voucher_type=getattr(voucher_config, 'code', ''), reference=reference).exists():
                errors['reference'] = 'Reference must be unique within voucher type.'
        
        # UDF validations
        for field_name, field_value in header_data.items():
            if field_name.startswith('udf_'):
                udf_config = voucher_config.get_udf_config(field_name) if hasattr(voucher_config, 'get_udf_config') else None
                if udf_config:
                    pattern = udf_config.get('pattern')
                    if pattern and not re.match(pattern, str(field_value or '')):
                        errors[field_name] = f'Invalid format for {field_name}.'
                    min_length = udf_config.get('min_length')
                    if min_length and len(str(field_value or '')) < min_length:
                        errors[field_name] = f'Minimum length {min_length} for {field_name}.'

        return errors

    @staticmethod
    def validate_voucher_line(line_data, voucher_config, organization, line_index=1):
        """
        Validate individual voucher line data.
        """
        errors = {}

        # Mandatory account or product validation
        account_id = line_data.get('account') or line_data.get('account_id')
        product_id = line_data.get('product') or line_data.get('product_id')

        if not account_id and not product_id:
            if voucher_config.affects_inventory:
                errors['product'] = f'Line {line_index}: Product is required for inventory vouchers'
            else:
                errors['account'] = f'Line {line_index}: Account is required for financial vouchers'

        # Account validation
        if account_id:
            try:
                if isinstance(account_id, str):
                    account = ChartOfAccount.objects.get(
                        organization=organization,
                        account_code=account_id
                    )
                elif isinstance(account_id, ChartOfAccount):  # It's a model instance
                    account = account_id
                    # Verify it belongs to the correct organization
                    if account.organization != organization:
                        errors['account'] = f'Line {line_index}: Account does not belong to this organization'
                        account = None
                else:
                    account = ChartOfAccount.objects.get(
                        organization=organization,
                        pk=account_id
                    )
                if account and not account.is_active:
                    errors['account'] = f'Line {line_index}: Account is inactive'
            except ChartOfAccount.DoesNotExist:
                errors['account'] = f'Line {line_index}: Account does not exist'

        # Debit/Credit rules
        debit_amount = line_data.get('debit_amount', 0)
        credit_amount = line_data.get('credit_amount', 0)

        try:
            debit_amount = Decimal(str(debit_amount or 0))
            credit_amount = Decimal(str(credit_amount or 0))
        except (ValueError, TypeError):
            errors['amounts'] = f'Line {line_index}: Invalid amount format'
            return errors

        if debit_amount < 0 or credit_amount < 0:
            errors['amounts'] = f'Line {line_index}: Amounts cannot be negative'

        if debit_amount > 0 and credit_amount > 0:
            errors['amounts'] = f'Line {line_index}: Cannot have both debit and credit'

        if debit_amount == 0 and credit_amount == 0:
            errors['amounts'] = f'Line {line_index}: Must have either debit or credit amount'

        # Decimal places validation (2 decimal places max)
        if debit_amount != debit_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):
            errors['debit_amount'] = f'Line {line_index}: Debit amount cannot have more than 2 decimal places'

        if credit_amount != credit_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):
            errors['credit_amount'] = f'Line {line_index}: Credit amount cannot have more than 2 decimal places'

        # Quantity validation for inventory
        quantity = line_data.get('quantity') or line_data.get('qty')
        if quantity is not None:
            try:
                quantity = Decimal(str(quantity))
                if quantity <= 0:
                    errors['quantity'] = f'Line {line_index}: Quantity must be positive'
                if voucher_config.affects_inventory and quantity == 0:
                    errors['quantity'] = f'Line {line_index}: Quantity is required for inventory transactions'
            except (ValueError, TypeError):
                errors['quantity'] = f'Line {line_index}: Invalid quantity format'

        # Inventory details validation
        if product_id:
            if not line_data.get('warehouse'):
                errors['warehouse'] = f'Line {line_index}: Warehouse is required when product is specified'

            if voucher_config.affects_inventory:
                if not line_data.get('unit_cost'):
                    errors['unit_cost'] = f'Line {line_index}: Unit cost is required for inventory transactions'

                # GRIR account for receipts, COGS for issues
                journal_type = getattr(voucher_config, 'journal_type', None)
                if journal_type:
                    journal_type_code = getattr(journal_type, 'journal_type', '').lower()
                    if 'receipt' in journal_type_code or 'grn' in journal_type_code:
                        if not line_data.get('grir_account'):
                            errors['grir_account'] = f'Line {line_index}: GRIR account is required for receipts'
                    elif 'issue' in journal_type_code:
                        if not line_data.get('cogs_account'):
                            errors['cogs_account'] = f'Line {line_index}: COGS account is required for issues'

        # UDF validation
        udf_data = line_data.get('udf_data', {})
        if udf_data:
            schema = voucher_config.resolve_ui_schema() if hasattr(voucher_config, 'resolve_ui_schema') else {}
            line_schema = schema.get('lines', {}) if isinstance(schema, dict) else {}

            for field_name, field_config in line_schema.items():
                if not isinstance(field_config, dict) or not field_name.startswith('udf_'):
                    continue

                field_type = field_config.get('type', 'char')
                value = udf_data.get(field_name)

                if field_config.get('required') and not value:
                    errors[field_name] = f'Line {line_index}: {field_config.get("label", field_name)} is required'

                # Pattern validation
                pattern = field_config.get('pattern')
                if pattern and value:
                    try:
                        validator = RegexValidator(regex=pattern)
                        validator(value)
                    except ValidationError:
                        errors[field_name] = f'Line {line_index}: {field_config.get("label", field_name)} does not match required pattern'

                # Length validation
                max_length = field_config.get('max_length')
                if max_length and value and len(str(value)) > max_length:
                    errors[field_name] = f'Line {line_index}: {field_config.get("label", field_name)} exceeds maximum length of {max_length}'

        # Reference uniqueness (optional)
        reference = line_data.get('reference')
        if reference and voucher_config.schema_definition:
            schema = voucher_config.schema_definition
            if isinstance(schema, str):
                import json
                try:
                    schema = json.loads(schema)
                except:
                    schema = {}

            if schema.get('settings', {}).get('enforce_unique_reference', False):
                # Check uniqueness within this voucher (would need voucher context)
                pass

        # Dimensions validation
        cost_centre = line_data.get('cost_centre')
        department = line_data.get('department')
        project = line_data.get('project')
        if any([cost_centre, department, project]) and not all([cost_centre, department, project]):
            errors['dimensions'] = f'Line {line_index}: All dimensions (cost centre, department, project) required if any is provided.'

        return errors

    @staticmethod
    def validate_additional_charges(charges_data, voucher_config, organization):
        """
        Validate additional charges formset data.
        """
        errors = {}

        for idx, charge_data in enumerate(charges_data or [], start=1):
            if charge_data.get('DELETE'):
                continue

            amount = charge_data.get('amount')
            if amount is not None:
                try:
                    amount = Decimal(str(amount))
                    if amount <= 0:
                        errors[f'charge_{idx}'] = f'Charge {idx}: Amount must be positive'
                except (ValueError, TypeError):
                    errors[f'charge_{idx}'] = f'Charge {idx}: Invalid amount format'

            account_id = charge_data.get('account') or charge_data.get('gl_account')
            if not account_id:
                errors[f'charge_{idx}'] = f'Charge {idx}: GL account is required'

        return errors

    @staticmethod
    def validate_payment_receipt(payments_data, voucher_total, organization):
        """
        Validate payment receipt formset data.
        """
        errors = {}

        total_payments = Decimal('0.00')

        for idx, payment_data in enumerate(payments_data or [], start=1):
            if payment_data.get('DELETE'):
                continue

            payment_date = payment_data.get('payment_date')
            if not payment_date:
                errors[f'payment_{idx}'] = f'Payment {idx}: Payment date is required'

            amount = payment_data.get('amount')
            if amount is not None:
                try:
                    amount = Decimal(str(amount))
                    if amount <= 0:
                        errors[f'payment_{idx}'] = f'Payment {idx}: Amount must be positive'
                    total_payments += amount
                except (ValueError, TypeError):
                    errors[f'payment_{idx}'] = f'Payment {idx}: Invalid amount format'

            account_id = payment_data.get('account')
            if not account_id:
                errors[f'payment_{idx}'] = f'Payment {idx}: Account is required'

            currency_code = payment_data.get('currency')
            if currency_code:
                try:
                    Currency.objects.get(
                        currency_code=currency_code,
                        is_active=True
                    )
                except Currency.DoesNotExist:
                    errors[f'payment_{idx}'] = f'Payment {idx}: Currency {currency_code} is not active'

            exchange_rate = payment_data.get('exchange_rate')
            if exchange_rate is not None:
                try:
                    exchange_rate = Decimal(str(exchange_rate))
                    if exchange_rate <= 0:
                        errors[f'payment_{idx}'] = f'Payment {idx}: Exchange rate must be positive'
                except (ValueError, TypeError):
                    errors[f'payment_{idx}'] = f'Payment {idx}: Invalid exchange rate format'

        # Check if payments equal voucher total
        if total_payments > voucher_total:
            errors['total'] = 'Total payments exceed voucher amount'

        return errors

    @staticmethod
    def validate_cross_field_dependencies(header_data, lines_data, voucher_config):
        """
        Validate cross-field dependencies and business rules.
        """
        errors = {}

        # Cost Centre / Department / Project dependencies
        has_cost_center = any(line.get('cost_center') for line in lines_data or [])
        has_department = any(line.get('department') for line in lines_data or [])
        has_project = any(line.get('project') for line in lines_data or [])

        schema = voucher_config.resolve_ui_schema() if hasattr(voucher_config, 'resolve_ui_schema') else {}
        line_schema = schema.get('lines', {}) if isinstance(schema, dict) else {}

        # If any dimension is required, others should be present if organization mandates
        required_dimensions = []
        for field_name, field_config in line_schema.items():
            if isinstance(field_config, dict) and field_config.get('required'):
                if field_name in ['cost_center', 'department', 'project']:
                    required_dimensions.append(field_name)

        if required_dimensions:
            for line_idx, line_data in enumerate(lines_data or [], start=1):
                for dim in required_dimensions:
                    if not line_data.get(dim):
                        errors[f'line_{line_idx}_{dim}'] = f'Line {line_idx}: {dim.replace("_", " ").title()} is required'

        return errors

    @staticmethod
    def validate_purchase_invoice_data(organization, data):
        """
        Validate complete purchase invoice data before saving.
        """
        errors = {}

        # Validate vendor
        if 'vendor_id' in data:
            try:
                vendor_details = VendorService.get_vendor_details(organization, data['vendor_id'])
                if not vendor_details['is_active']:
                    errors['vendor'] = 'Vendor is inactive'
            except ValidationError as e:
                errors['vendor'] = str(e)

        # Validate credit limit
        if 'vendor_id' in data and 'total_amount' in data:
            credit_check = VendorService.validate_vendor_credit_limit(
                organization, data['vendor_id'], data['total_amount']
            )
            if not credit_check['valid']:
                errors['credit_limit'] = credit_check['message']

        # Validate line items
        if 'line_items' in data:
            for i, item in enumerate(data['line_items']):
                item_errors = ValidationService.validate_line_item(
                    item,
                    data.get('vendor_id'),
                    organization=organization,
                )
                if item_errors:
                    errors[f'line_item_{i}'] = item_errors

        # Validate totals
        if 'calculated_total' in data and 'expected_total' in data:
            calculated = Decimal(data['calculated_total'])
            expected = Decimal(data['expected_total'])
            if abs(calculated - expected) > Decimal('0.01'):
                errors['totals'] = 'Calculated total does not match expected total'

        if 'grand_total' in data and 'payments_total' in data:
            grand_total = Decimal(data['grand_total'])
            payments_total = Decimal(data['payments_total'])
            if payments_total > grand_total:
                errors['payments'] = 'Payment total exceeds invoice total'

        return errors

    @staticmethod
    def validate_line_item(item_data, vendor_id=None, organization=None):
        """
        Validate individual line item data.
        """
        errors = {}

        # Validate product
        if 'product_id' in item_data:
            try:
                if organization:
                    product_details = ProductService.get_product_details(organization, item_data['product_id'])
                    if not product_details['is_active']:
                        errors['product'] = 'Product is inactive'
            except ValidationError as e:
                errors['product'] = str(e)
            except TypeError:
                errors['product'] = 'Product validation failed.'

        # Validate quantity and rate
        if 'quantity' in item_data and item_data['quantity'] <= 0:
            errors['quantity'] = 'Quantity must be positive'

        if 'rate' in item_data and item_data['rate'] < 0:
            errors['rate'] = 'Rate cannot be negative'

        # Validate pricing
        if vendor_id and 'product_id' in item_data and 'rate' in item_data and organization:
            pricing = PricingService.get_pricing_for_party(organization, item_data['product_id'], vendor_id)
            if item_data['rate'] < pricing['party_price'] * 0.9:  # Allow 10% variance
                errors['rate'] = 'Rate significantly below party price'

        # Validate stock if warehouse specified
        if 'product_id' in item_data and 'quantity' in item_data and 'warehouse_id' in item_data:
            try:
                stock_check = ProductService.validate_product_for_transaction(
                    item_data['product_id'], item_data['quantity'], item_data['warehouse_id']
                )
                if not stock_check['valid']:
                    errors['stock'] = stock_check['message']
            except Exception as exc:  # Defensive: never let stock validation crash entry
                errors['stock'] = f"Stock validation failed: {exc}"

        return errors

    @staticmethod
    def validate_form_field(field_name, value, context=None):
        """
        Validate individual form fields with context.
        """
        errors = []

        if field_name == 'voucher_no':
            if not value or not value.strip():
                errors.append('Voucher number is required')
            # Add uniqueness check if needed

        elif field_name == 'date_ad':
            from datetime import date
            if isinstance(value, str):
                try:
                    date.fromisoformat(value)
                except ValueError:
                    errors.append('Invalid date format')
            elif isinstance(value, date):
                if value > date.today():
                    errors.append('Date cannot be in the future')

        elif field_name == 'party_invoice_no':
            if len(value) > 50:
                errors.append('Party invoice number too long')

        # Add more field validations as needed

        return errors

    @staticmethod
    def validate_business_rules(data):
        """
        Validate business-specific rules.
        """
        errors = []

        # Example: High-value transaction requires approval
        if 'total_amount' in data and data['total_amount'] > 100000:  # Configurable threshold
            if not data.get('approval_required', False):
                errors.append('High-value transaction requires approval')

        # Example: Certain products require quality check
        if 'line_items' in data:
            for item in data['line_items']:
                if item.get('product_category') == 'raw_material':
                    if not item.get('quality_checked', False):
                        errors.append(f'Product {item["product_id"]} requires quality check')

        return errors

    @staticmethod
    def validate_rounding(total_lines, total_charges, header_amount, tolerance=Decimal('0.01')):
        computed = total_lines + total_charges
        if abs(computed - header_amount) > tolerance:
            raise VoucherProcessError('Rounding difference exceeds tolerance.', code='VCH-ROUND')
    
    # Standardize codes in existing methods, e.g., add code='INV-005' to quantity checks
