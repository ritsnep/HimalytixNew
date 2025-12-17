from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.forms.form_factory import VoucherFormFactory as LegacyVoucherFactory
from accounting.models import AuditLog, VoucherConfiguration, Vendor, Customer
from accounting.tests.factories import (
    create_account_type,
    create_accounting_period,
    create_chart_of_account,
    create_journal_type,
    create_organization,
)

try:
    from inventory.models import Product, Warehouse, Location
except Exception:  # Inventory app might not be installed in minimal runs
    Product = Warehouse = Location = None


class GenericVoucherHTTPCreationTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.period = create_accounting_period(organization=self.organization)
        self.journal_type = create_journal_type(organization=self.organization)
        self.accounts = self._create_base_accounts()

        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code='V001',
            display_name='Vendor 1',
            accounts_payable_account=self.accounts['ap'],
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code='C001',
            display_name='Customer 1',
            accounts_receivable_account=self.accounts['ar'],
        )

        self.product = None
        self.location = None
        if Product and Warehouse and Location:
            warehouse = Warehouse.objects.create(
                organization=self.organization,
                code='WH1',
                name='Main Warehouse',
                address_line1='123 Test St',
                city='Test City',
                country_code='US',
                inventory_account=self.accounts['inventory'],
            )
            self.location = Location.objects.create(
                warehouse=warehouse,
                code='LOC1',
                name='Primary Bin',
            )
            self.product = Product.objects.create(
                organization=self.organization,
                code='P001',
                name='Test Product',
                currency_code='USD',
                income_account=self.accounts['revenue'],
                expense_account=self.accounts['expense'],
                inventory_account=self.accounts['inventory'],
                is_inventory_item=True,
                preferred_vendor=self.vendor,
            )

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='pass12345',
        )
        if hasattr(self.user, 'organization'):
            self.user.organization = self.organization
            self.user.save(update_fields=['organization'])

        self.client.force_login(self.user)
        self.configs = self._ensure_voucher_configs()

    def _create_base_accounts(self):
        ap_type = create_account_type(code='AP', name='Accounts Payable', nature='liability')
        ar_type = create_account_type(code='AR', name='Accounts Receivable', nature='asset')
        rev_type = create_account_type(code='REV', name='Revenue', nature='income')
        exp_type = create_account_type(code='EXP', name='Expense', nature='expense')
        inv_type = create_account_type(code='INV', name='Inventory', nature='asset')

        return {
            'ap': create_chart_of_account(organization=self.organization, account_type=ap_type, account_code='2000', account_name='AP Control'),
            'ar': create_chart_of_account(organization=self.organization, account_type=ar_type, account_code='1200', account_name='AR Control'),
            'revenue': create_chart_of_account(organization=self.organization, account_type=rev_type, account_code='4000', account_name='Revenue'),
            'expense': create_chart_of_account(organization=self.organization, account_type=exp_type, account_code='5000', account_name='Expense'),
            'inventory': create_chart_of_account(organization=self.organization, account_type=inv_type, account_code='1300', account_name='Inventory'),
        }

    def _ensure_voucher_configs(self):
        today = date.today().isoformat()
        schemas = {
            'accounting': {
                'header': {
                    'journal_type': {'type': 'select', 'label': 'Journal Type', 'choices': 'JournalType', 'required': True},
                    'period': {'type': 'select', 'label': 'Period', 'choices': 'AccountingPeriod', 'required': True},
                    'journal_date': {'type': 'date', 'label': 'Date', 'required': True, 'kwargs': {'widget': {'attrs': {'value': today}}}},
                    'currency_code': {'type': 'char', 'label': 'Currency', 'required': False, 'kwargs': {'widget': {'attrs': {'value': 'USD'}}}},
                },
                'lines': {
                    'account': {'type': 'select', 'label': 'Account', 'choices': 'ChartOfAccount', 'required': False},
                    'debit_amount': {'type': 'decimal', 'label': 'Debit', 'required': False},
                    'credit_amount': {'type': 'decimal', 'label': 'Credit', 'required': False},
                },
            },
            'purchasing': {
                'header': {
                    'vendor': {'type': 'select', 'label': 'Vendor', 'choices': 'Vendor', 'required': True},
                    'voucher_date': {'type': 'date', 'label': 'Date', 'required': True, 'kwargs': {'widget': {'attrs': {'value': today}}}},
                },
                'lines': {
                    'product_name': {'type': 'char', 'label': 'Product', 'required': False},
                    'quantity_ordered': {'type': 'decimal', 'label': 'Qty', 'required': False},
                    'unit_price': {'type': 'decimal', 'label': 'Unit Price', 'required': False},
                },
            },
            'sales': {
                'header': {
                    'customer': {'type': 'select', 'label': 'Customer', 'choices': 'Customer', 'required': True},
                    'voucher_date': {'type': 'date', 'label': 'Date', 'required': True, 'kwargs': {'widget': {'attrs': {'value': today}}}},
                },
                'lines': {
                    'product_name': {'type': 'char', 'label': 'Product', 'required': False},
                    'quantity_ordered': {'type': 'decimal', 'label': 'Qty', 'required': False},
                    'unit_price': {'type': 'decimal', 'label': 'Unit Price', 'required': False},
                },
            },
            'inventory': {
                'header': {
                    'journal_type': {'type': 'select', 'label': 'Journal Type', 'choices': 'JournalType', 'required': True},
                    'period': {'type': 'select', 'label': 'Period', 'choices': 'AccountingPeriod', 'required': True},
                    'journal_date': {'type': 'date', 'label': 'Date', 'required': True, 'kwargs': {'widget': {'attrs': {'value': today}}}},
                },
                'lines': {
                    'account': {'type': 'select', 'label': 'Account', 'choices': 'ChartOfAccount', 'required': False},
                    'debit_amount': {'type': 'decimal', 'label': 'Debit', 'required': False},
                    'credit_amount': {'type': 'decimal', 'label': 'Credit', 'required': False},
                },
            },
            'billing': {
                'header': {
                    'journal_type': {'type': 'select', 'label': 'Journal Type', 'choices': 'JournalType', 'required': True},
                    'period': {'type': 'select', 'label': 'Period', 'choices': 'AccountingPeriod', 'required': True},
                    'journal_date': {'type': 'date', 'label': 'Date', 'required': True, 'kwargs': {'widget': {'attrs': {'value': today}}}},
                },
                'lines': {
                    'account': {'type': 'select', 'label': 'Account', 'choices': 'ChartOfAccount', 'required': False},
                    'debit_amount': {'type': 'decimal', 'label': 'Debit', 'required': False},
                    'credit_amount': {'type': 'decimal', 'label': 'Credit', 'required': False},
                },
            },
        }

        configs = []
        for module, schema in schemas.items():
            code = f'http_{module}'
            cfg, _ = VoucherConfiguration.objects.get_or_create(
                organization=self.organization,
                code=code,
                defaults={
                    'name': f'HTTP {module.title()}',
                    'module': module,
                    'ui_schema': schema,
                    'is_active': True,
                },
            )
            # Ensure schema/module are updated if the config already existed
            if cfg.ui_schema != schema or cfg.module != module or not cfg.is_active:
                cfg.ui_schema = schema
                cfg.module = module
                cfg.is_active = True
                cfg.save(update_fields=['ui_schema', 'module', 'is_active'])
            configs.append(cfg)
        return configs

    def _build_post_data(self, cfg, today_iso):
        post_data = {
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
        }

        module = cfg.module
        if module in {'accounting', 'inventory', 'billing'}:
            account = self.accounts['expense']
            post_data.update({
                'header-journal_type': str(self.journal_type.pk),
                'header-period': str(self.period.pk),
                'header-journal_date': today_iso,
                'header-currency_code': 'USD',
                'lines-0-account': str(getattr(account, 'account_id', None) or account.pk),
                'lines-0-account_display': f"{account.account_code} - {account.account_name}",
                'lines-0-debit_amount': '10',
                'lines-0-credit_amount': '0',
            })
        elif module == 'purchasing':
            post_data.update({
                'header-vendor': str(getattr(self.vendor, 'vendor_id', None) or self.vendor.pk),
                'header-vendor_display': self.vendor.display_name,
                'header-voucher_date': today_iso,
                'header-voucher_number': 'PO-AUTO-1',
                'lines-0-product_name': 'Test Item',
                'lines-0-quantity_ordered': '1',
                'lines-0-unit_price': '5',
            })
        elif module == 'sales':
            post_data.update({
                'header-customer': str(getattr(self.customer, 'customer_id', None) or self.customer.pk),
                'header-customer_display': self.customer.display_name,
                'header-voucher_date': today_iso,
                'header-voucher_number': 'SO-AUTO-1',
                'lines-0-product_name': 'Test Item',
                'lines-0-quantity_ordered': '1',
                'lines-0-unit_price': '5',
            })
        else:
            post_data['header-voucher_date'] = today_iso

        return post_data

    def _get_parent_fk(self, line_model, header_model):
        for field in line_model._meta.fields:
            try:
                if field.remote_field and field.remote_field.model is header_model:
                    return field.name
            except Exception:
                continue
        return None

    def test_generic_voucher_create_posts_all_configs(self):
        today_iso = timezone.now().date().isoformat()

        for cfg in self.configs:
            url = reverse('accounting:generic_voucher_create', kwargs={'voucher_code': cfg.code})
            header_model = LegacyVoucherFactory._get_model_for_voucher_config(cfg)
            line_model = LegacyVoucherFactory._get_line_model_for_voucher_config(cfg)

            before_header = header_model.objects.filter(organization=self.organization).count()

            post_data = self._build_post_data(cfg, today_iso)
            resp = self.client.post(url, data=post_data)
            if resp.status_code != 302:
                # Bind the same data into the header/line forms to surface validation errors
                header_form_cls = LegacyVoucherFactory.get_generic_voucher_form(cfg, self.organization)
                line_formset_cls = LegacyVoucherFactory.get_generic_voucher_formset(cfg, self.organization, prefix='lines')
                header_form = header_form_cls(data=post_data)
                line_formset = line_formset_cls(data=post_data)
                header_errors = getattr(header_form, 'errors', None)
                line_errors = getattr(line_formset, 'errors', None)
                try:
                    header_instance = header_form.save(commit=False)
                    created_by_val = getattr(header_instance, 'created_by', None)
                    created_by_id = getattr(header_instance, 'created_by_id', None)
                except Exception:
                    created_by_val = '<save-failed>'
                    created_by_id = '<save-failed>'
                content = ''
                try:
                    content = resp.content.decode('utf-8')[:1000]
                except Exception:
                    content = str(resp.content)[:1000]
                self.fail(
                    f"{cfg.code} expected redirect, got {resp.status_code}. "
                    f"Header errors: {getattr(header_errors, 'errors', header_errors)}; "
                    f"Line errors: {getattr(line_errors, 'errors', line_errors)}; "
                    f"created_by={created_by_val!r} created_by_id={created_by_id!r}; "
                    f"Response snippet: {content}"
                )

            self.assertEqual(
                header_model.objects.filter(organization=self.organization).count(),
                before_header + 1,
                f"Header not created for {cfg.code}",
            )

            header_obj = header_model.objects.filter(organization=self.organization).order_by('-pk').first()
            parent_fk = self._get_parent_fk(line_model, header_model)
            line_qs = line_model.objects.all()
            if parent_fk:
                line_qs = line_qs.filter(**{parent_fk: header_obj})

            self.assertTrue(line_qs.exists(), f"Line not created for {cfg.code}")

            ct = ContentType.objects.get_for_model(header_model)
            self.assertTrue(
                AuditLog.objects.filter(
                    content_type=ct,
                    object_id=header_obj.pk,
                    organization=self.organization,
                    action='create',
                ).exists(),
                f"Audit log missing for {cfg.code}",
            )