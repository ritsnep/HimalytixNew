from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('usermanagement', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('code', models.CharField(blank=True, max_length=50)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='departments', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('organization', 'code')},
            },
        ),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=150)),
                ('grade', models.CharField(blank=True, max_length=50)),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='positions', to='enterprise.department')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='positions', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee_id', models.CharField(max_length=50)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('employment_type', models.CharField(choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'), ('contract', 'Contract'), ('intern', 'Intern')], default='full_time', max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('on_leave', 'On Leave'), ('terminated', 'Terminated')], default='active', max_length=20)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='employees', to='enterprise.department')),
                ('manager', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employees', to='usermanagement.organization')),
                ('position', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='employees', to='enterprise.position')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['last_name', 'first_name'],
                'unique_together': {('organization', 'employee_id')},
            },
        ),
        migrations.CreateModel(
            name='PayrollCycle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('approved', 'Approved'), ('posted', 'Posted')], default='draft', max_length=20)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payrollcycles', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-period_start'],
            },
        ),
        migrations.CreateModel(
            name='PayrollEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('gross_pay', models.DecimalField(decimal_places=2, max_digits=12)),
                ('deductions', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('net_pay', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payroll_entries', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payrollentrys', to='usermanagement.organization')),
                ('payroll_cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='enterprise.payrollcycle')),
            ],
            options={
                'ordering': ['employee__last_name', 'employee__first_name'],
            },
        ),
        migrations.CreateModel(
            name='LeaveRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('leave_type', models.CharField(max_length=50)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='draft', max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leaverequests', to='usermanagement.organization')),
            ],
        ),
        migrations.CreateModel(
            name='AttendanceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('work_date', models.DateField()),
                ('hours_worked', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('status', models.CharField(default='present', max_length=50)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendancerecords', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-work_date'],
                'unique_together': {('employee', 'work_date')},
            },
        ),
        migrations.CreateModel(
            name='BenefitEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('benefit_name', models.CharField(max_length=150)),
                ('contribution', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('employer_contribution', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='benefits', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='benefitenrollments', to='usermanagement.organization')),
            ],
        ),
        migrations.CreateModel(
            name='FixedAssetCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('depreciation_method', models.CharField(choices=[('straight_line', 'Straight Line'), ('declining_balance', 'Declining Balance')], default='straight_line', max_length=50)),
                ('useful_life_months', models.PositiveIntegerField(default=60)),
                ('salvage_value_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fixedassetcategorys', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='FixedAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('asset_code', models.CharField(max_length=50)),
                ('acquisition_date', models.DateField()),
                ('acquisition_cost', models.DecimalField(decimal_places=2, max_digits=14)),
                ('salvage_value', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('useful_life_months', models.PositiveIntegerField(default=60)),
                ('location', models.CharField(blank=True, max_length=150)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assets', to='enterprise.fixedassetcategory')),
                ('custodian', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_assets', to='enterprise.employee')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fixedassets', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('organization', 'asset_code')},
            },
        ),
        migrations.CreateModel(
            name='AssetDepreciationSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('depreciation_amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('posted_journal', models.BooleanField(default=False)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='depreciation_schedule', to='enterprise.fixedasset')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assetdepreciationschedules', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['period_start'],
            },
        ),
        migrations.CreateModel(
            name='BillOfMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('product_name', models.CharField(max_length=150)),
                ('revision', models.CharField(default='A', max_length=20)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billofmaterials', to='usermanagement.organization')),
            ],
            options={
                'unique_together': {('organization', 'product_name', 'revision')},
            },
        ),
        migrations.CreateModel(
            name='BillOfMaterialItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('component_name', models.CharField(max_length=150)),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=12)),
                ('uom', models.CharField(default='unit', max_length=50)),
                ('bill_of_material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='enterprise.billofmaterial')),
            ],
        ),
        migrations.CreateModel(
            name='WorkOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('work_order_number', models.CharField(max_length=50)),
                ('quantity_to_produce', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('planned', 'Planned'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='planned', max_length=20)),
                ('planned_start', models.DateField(blank=True, null=True)),
                ('planned_end', models.DateField(blank=True, null=True)),
                ('routing_instructions', models.TextField(blank=True)),
                ('bill_of_material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='work_orders', to='enterprise.billofmaterial')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workorders', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-planned_start'],
                'unique_together': {('organization', 'work_order_number')},
            },
        ),
        migrations.CreateModel(
            name='WorkOrderMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('component_name', models.CharField(max_length=150)),
                ('quantity_required', models.DecimalField(decimal_places=4, max_digits=12)),
                ('quantity_issued', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('uom', models.CharField(default='unit', max_length=50)),
                ('work_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='enterprise.workorder')),
            ],
        ),
        migrations.CreateModel(
            name='CRMLead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('source', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(default='new', max_length=50)),
                ('probability', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=50)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crmleads', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Opportunity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('stage', models.CharField(default='qualification', max_length=50)),
                ('expected_close', models.DateField(blank=True, null=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('probability', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunities', to='enterprise.crmlead')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='opportunitys', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-expected_close'],
            },
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('channel', models.CharField(blank=True, max_length=100)),
                ('budget_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaigns', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='Budget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('fiscal_year', models.CharField(max_length=10)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved')], default='draft', max_length=20)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='budgets', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['-fiscal_year', 'name'],
            },
        ),
        migrations.CreateModel(
            name='BudgetLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_name', models.CharField(blank=True, max_length=150)),
                ('account_code', models.CharField(max_length=50)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('budget', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='enterprise.budget')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='budget_lines', to='enterprise.department')),
            ],
        ),
        migrations.CreateModel(
            name='IntegrationEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=150)),
                ('connector_type', models.CharField(choices=[('bank_feed', 'Bank Feed'), ('payment_gateway', 'Payment Gateway'), ('ecommerce', 'E-commerce'), ('logistics', 'Logistics'), ('pos', 'Point of Sale')], max_length=50)),
                ('base_url', models.URLField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='integrationendpoints', to='usermanagement.organization')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='POSDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('identifier', models.CharField(max_length=100)),
                ('location', models.CharField(blank=True, max_length=150)),
                ('status', models.CharField(default='active', max_length=50)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='posdevices', to='usermanagement.organization')),
            ],
            options={
                'unique_together': {('organization', 'identifier')},
            },
        ),
        migrations.CreateModel(
            name='LocaleConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('locale_code', models.CharField(default='en-US', max_length=20)),
                ('timezone', models.CharField(default='UTC', max_length=50)),
                ('default_currency', models.CharField(default='USD', max_length=10)),
                ('tax_region', models.CharField(blank=True, max_length=100)),
                ('enable_e_invoicing', models.BooleanField(default=False)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='localeconfigs', to='usermanagement.organization')),
            ],
            options={
                'unique_together': {('organization', 'locale_code')},
            },
        ),
    ]
