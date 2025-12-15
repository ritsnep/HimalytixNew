# UAT Checklist — Voucher UI Schema changes

Purpose: Confirm the admin UI and schema-driven form rendering behave correctly across all voucher configurations.

Artifacts generated:
- Automated inspection script: `accounting/scripts/inspect_all_voucher_ui.py`
- HTML snapshots: `accounting/ui_snapshots/*_header.html` and `*_lines.html`
- Unit tests: `accounting/tests/test_voucher_ui.py`
- Snapshot generator: `accounting/scripts/generate_ui_snapshots.py`

How to run automated checks

1. Ensure DB is seeded (this will create/update canonical voucher configs):

```powershell
cd C:\PythonProjects\Himalytix\ERP
python manage.py shell -c "from create_voucher_configs import create_voucher_configs; create_voucher_configs()"
```

2. Run the inspection script to detect schema mismatches:

```powershell
python manage.py shell -c "exec(open('accounting/scripts/inspect_all_voucher_ui.py').read())"
```

Expected: "Inspected N configurations, 0 with issues" (or no errors printed). If issues are reported, open the relevant `VoucherConfiguration` in the Admin UI and fix hidden/disabled/order_no values.

3. Run unit tests:

```powershell
python manage.py test accounting.tests.test_voucher_ui.VoucherUISchemaTests
```

Expected: All tests pass.

Generating snapshots for manual review

```powershell
python manage.py shell -c "exec(open('accounting/scripts/generate_ui_snapshots.py').read())"
```

Files will be created under `accounting/ui_snapshots/`. Open them in a browser and visually verify:
- Field order in header matches business expectation (order_no or `__order__`)
- Line item form fields are the expected ones for each voucher type
- Widgets have Bootstrap `form-control` class and placeholders appear where expected
- Hidden/disabled fields are appropriately hidden or disabled in the rendered HTML

Admin actions to help fix issues

- In the Django Admin for `VoucherConfiguration` list, use the **Edit Schema** button to update hidden/disabled flags and order values.
- Use the admin action **Sync order_no values in UI schema** (available on VoucherConfiguration list) to automatically normalize `order_no` values to continuous 1..N.

Manual UAT checklist (suggested):

- [ ] Verify the Edit Schema UI loads for multiple voucher configs and that toggling hidden/disabled/order_no persists correctly
- [ ] Confirm that header form displays in the correct field order and required placeholders/attributes are present
- [ ] Confirm line formset shows the correct line fields and order
- [ ] Confirm `select` fields render as `select` (dropdowns) and typeahead fields have `_display` helper inputs
- [ ] Confirm running the admin "Sync order_no" action updates the `ui_schema` for selected configs and the snapshots reflect the change
- [ ] For any change, re-run unit tests and inspections to ensure no regressions

How to record findings

- Add notes to this file or create a short issue with the voucher `code`, what failed, a short reproduction, and a suggested fix.
- If a config needs persistent change, edit it via the Admin Edit Schema UI or update the seed `create_voucher_configs.py` and re-run the seed.

Need help?

Tell me which voucher config(s) you'd like me to inspect or adjust next and I can either fix the seed or apply a small change and re-run the snapshots/tests.