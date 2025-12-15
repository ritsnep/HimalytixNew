from django.test import TestCase
from django.core.management import call_command
from accounting.models import VoucherConfiguration
from usermanagement.models import Organization
from accounting.scripts.inspect_all_voucher_ui import inspect_config
from accounting.forms_factory import VoucherFormFactory


class VoucherUISchemaTests(TestCase):
    def test_all_configs_have_no_inspection_issues(self):
        issues = []
        for cfg in VoucherConfiguration.objects.all():
            r = inspect_config(cfg)
            if r['issues']:
                issues.append({'code': cfg.code, 'issues': r['issues']})
        self.assertEqual(len(issues), 0, f"Found issues in voucher configs: {issues}")

    def test_lines_formset_uses_lines_and_header_form_uses_header(self):
        # create a minimal config with header/lines for testing
        org, _ = Organization.objects.get_or_create(code='TEST', defaults={'name': 'Test Org'})
        cfg = VoucherConfiguration.objects.create(code='ut_purchase_order', name='UT Purchase', organization=org, module='purchasing', ui_schema={
            'header': {
                'supplier': {'type': 'select', 'label': 'Supplier', 'order_no': 1},
                'order_date': {'type': 'date', 'label': 'Order Date', 'order_no': 2},
            },
            'lines': [
                {'name': 'item', 'label': 'Item', 'order_no': 1, 'type': 'char'},
                {'name': 'quantity', 'label': 'Quantity', 'order_no': 2, 'type': 'integer'},
            ]
        })
        # header form
        factory = VoucherFormFactory(cfg.ui_schema)
        H = factory.build_form()
        h = H()
        header_ui = cfg.ui_schema.get('header')
        if header_ui:
            if isinstance(header_ui, dict):
                expected = header_ui.get('__order__') or [k for k in header_ui.keys() if k != '__order__']
            else:
                expected = [it.get('name') or it.get('field') for it in header_ui]
            # ignore hidden fields
            expected = [n for n in expected if not (isinstance(header_ui, dict) and header_ui.get(n, {}).get('hidden'))]
            # ensure each expected present in form
            for name in expected:
                self.assertIn(name, h.base_fields, f"Header field {name} missing in header form for {cfg.code}")

        # lines formset
        FS = factory.build_formset(extra=1)
        fs = FS()
        first = fs.forms[0]
        lines_ui = cfg.ui_schema.get('lines')
        if lines_ui:
            if isinstance(lines_ui, dict):
                expected = lines_ui.get('__order__') or [k for k in lines_ui.keys() if k != '__order__']
            else:
                expected = [it.get('name') or it.get('field') for it in lines_ui]
            expected = [n for n in expected if not (isinstance(lines_ui, dict) and lines_ui.get(n, {}).get('hidden'))]
            for name in expected:
                self.assertIn(name, first.base_fields, f"Line field {name} missing in line form for {cfg.code}")

        def test_build_formset_from_configuration_uses_lines_section(self):
            """When a factory is created with a VoucherConfiguration object, the formset must use the 'lines' section."""
            org, _ = Organization.objects.get_or_create(code='TEST2', defaults={'name': 'Test Org 2'})
            cfg = VoucherConfiguration.objects.create(code='ut_cfg_lines', name='UT Lines Config', organization=org, module='testing', ui_schema={
                'header': {
                    'h1': {'type': 'char', 'label': 'H1', 'order_no': 1},
                },
                'lines': [
                    {'name': 'line_item', 'label': 'Line Item', 'order_no': 1, 'type': 'char'},
                    {'name': 'line_qty', 'label': 'Line Qty', 'order_no': 2, 'type': 'integer'},
                ]
            })

            # Use the public helper that the view would use
            fs_cls = VoucherFormFactory.get_generic_voucher_formset(cfg, org, prefix='lines')
            fs = fs_cls()
            first = fs.forms[0]
            self.assertIn('line_item', first.base_fields)
            self.assertIn('line_qty', first.base_fields)
            self.assertNotIn('h1', first.base_fields)
            cfg.delete()

    def test_normalize_management_command_corrects_order_no(self):
        # Create a contrived config to test normalization
        org, _ = Organization.objects.get_or_create(code='TEST', defaults={'name': 'Test Org'})
        cfg = VoucherConfiguration.objects.create(code='ut_test_cfg', name='UT Test', organization=org, module='testing', ui_schema={
            'header': {
                'a': {'type': 'char', 'label': 'A', 'order_no': 2},
                'b': {'type': 'char', 'label': 'B', 'order_no': 1},
            }
        })
        # run the sync_order_no admin action directly to normalize order_no
        from accounting.admin import VoucherConfigurationAdmin

        class DummyRequest:
            def __init__(self):
                self._messages = []
            def message_user(self, request, message, level=None):
                # Admin.action will call self.message_user on admin instance; our dummy ignores
                return

        admin = VoucherConfigurationAdmin(model=VoucherConfiguration, admin_site=None)
        # override message_user to avoid dependency on messages framework in tests
        admin.message_user = lambda request, message, level=None: None
        admin.sync_order_no(DummyRequest(), VoucherConfiguration.objects.filter(pk=cfg.pk))
        cfg.refresh_from_db()
        header = cfg.ui_schema.get('header')
        # after sync, order_no should be normalized to 1..n matching __order__ or insertion order
        # If __order__ not present, sync_order_no uses current insertion order; assert order_no values are 1..n
        names = list(header.keys())
        # filter out any __order__ key
        names = [n for n in names if n != '__order__']
        for idx, name in enumerate(names, start=1):
            self.assertEqual(header[name]['order_no'], idx, f"order_no for {name} not normalized")
        # cleanup
        cfg.delete()

    def test_saving_header_and_lines_via_factory_emulates_view(self):
        """Ensure header and line forms can be saved and associated as in the view logic."""
        from accounting.models import PurchaseOrderVoucher, PurchaseOrderVoucherLine, Vendor

        org, _ = Organization.objects.get_or_create(code='SAVE', defaults={'name': 'Save Org'})
        # Create minimal AccountType and ChartOfAccount so Vendor's required AP account can be set
        from accounting.models import AccountType, ChartOfAccount
        atype = AccountType.objects.create(code='exp', name='Expense')
        coa = ChartOfAccount.objects.create(organization=org, account_type=atype, account_code='5000', account_name='AP Account', is_active=True)
        vendor = Vendor.objects.create(organization=org, code='V001', display_name='Vendor 1', accounts_payable_account=coa)

        cfg = VoucherConfiguration.objects.create(code='ut_po_save', name='UT PO Save', organization=org, module='purchasing', ui_schema={
            'header': {
                'vendor': {'type': 'select', 'label': 'Vendor', 'order_no': 1},
                'voucher_number': {'type': 'char', 'label': 'Voucher Number', 'order_no': 2},
                'voucher_date': {'type': 'date', 'label': 'Voucher Date', 'order_no': 3},
            },
            'lines': [
                {'name': 'product_name', 'label': 'Product', 'order_no': 1, 'type': 'char'},
                {'name': 'quantity_ordered', 'label': 'Qty', 'order_no': 2, 'type': 'decimal'},
                {'name': 'unit_price', 'label': 'Unit Price', 'order_no': 3, 'type': 'decimal'},
            ]
        })

        # Build forms via public helpers
        header_cls = VoucherFormFactory.get_generic_voucher_form(cfg, org)
        fs_cls = VoucherFormFactory.get_generic_voucher_formset(cfg, org, prefix='lines')

        header_data = {
            'vendor': str(vendor.pk),
            'vendor_display': vendor.display_name,
            'voucher_number': 'UT-001',
            'voucher_date': '2025-12-15',
        }

        # Formset management data for single form
        fs_data = {
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-product_name': 'Test Product',
            'lines-0-quantity_ordered': '2',
            'lines-0-unit_price': '12.50',
        }

        # Combine header and lines data as the view would receive
        post_data = {**header_data, **fs_data}

        header_form = header_cls(data=post_data)
        fs = fs_cls(data=post_data)

        self.assertTrue(header_form.is_valid(), header_form.errors)
        self.assertTrue(fs.is_valid(), fs.errors)

        # Emulate save logic from the view
        voucher = header_form.save(commit=False)
        voucher.organization = org
        # Some concrete voucher models enforce non-null created_by in DB; ensure a user exists
        from usermanagement.models import CustomUser
        user = CustomUser.objects.create_user(username='ut_user', email='ut@example.com')
        voucher.created_by = user
        voucher.save()

        # Save lines
        for idx, form in enumerate(fs):
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                line = form.save(commit=False)
                # attach parent FK - PurchaseOrderVoucherLine expects purchase_order_voucher attr
                try:
                    line.purchase_order_voucher = voucher
                except Exception:
                    # fallback: try attribute with camel-case
                    setattr(line, 'purchase_order_voucher', voucher)
                if hasattr(line, 'line_number') and not getattr(line, 'line_number', None):
                    line.line_number = idx + 1
                line.save()

        # Verify saved
        self.assertTrue(PurchaseOrderVoucher.objects.filter(pk=voucher.pk).exists())
        self.assertEqual(PurchaseOrderVoucherLine.objects.filter(purchase_order_voucher=voucher).count(), 1)

        # cleanup
        PurchaseOrderVoucherLine.objects.filter(purchase_order_voucher=voucher).delete()
        voucher.delete()
        cfg.delete()