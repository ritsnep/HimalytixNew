from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("usermanagement", "0026_alter_organization_base_currency_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("query_name", models.CharField(blank=True, help_text="Stored procedure or query identifier used to fetch data.", max_length=255)),
                ("base_template_name", models.CharField(blank=True, help_text="Fallback Django template path for the base layout.", max_length=255)),
                ("template_html", models.TextField(blank=True, help_text="Inline custom template HTML saved from the designer.")),
                ("template_json", models.JSONField(blank=True, default=dict, help_text="Raw JSON from the drag-and-drop designer (for rebuild).")),
                ("engine", models.CharField(choices=[("django", "Django Templates"), ("jinja", "Jinja2")], default="django", max_length=20)),
                ("is_custom_enabled", models.BooleanField(default=False, help_text="Per-report toggle to allow custom template rendering.")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_created_report_definitions", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reporting_definitions", to="usermanagement.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_updated_report_definitions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["organization_id", "code"],
                "db_table": "reporting_report_definition",
                "unique_together": {("organization", "code")},
            },
        ),
        migrations.CreateModel(
            name="ScheduledReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_code", models.CharField(max_length=100)),
                ("parameters", models.JSONField(blank=True, default=dict)),
                ("recipients", models.JSONField(default=list, help_text="List of email recipients for the report run.")),
                ("format", models.CharField(choices=[("pdf", "PDF"), ("excel", "Excel"), ("csv", "CSV"), ("html", "HTML")], default="pdf", max_length=10)),
                ("frequency", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly"), ("cron", "Custom cron")], max_length=20)),
                ("cron", models.CharField(blank=True, help_text="Optional cron expression used when frequency is 'cron'.", max_length=64)),
                ("next_run", models.DateTimeField()),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(default="pending", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("send_copy_to_owner", models.BooleanField(default=True, help_text="Send a copy to the user who created the schedule.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_created_scheduled_reports", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reporting_scheduled_reports", to="usermanagement.organization")),
                ("report_definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="schedules", to="reporting.reportdefinition")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_updated_scheduled_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-next_run"],
                "db_table": "reporting_scheduled_report",
            },
        ),
        migrations.CreateModel(
            name="ReportTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("template_html", models.TextField()),
                ("template_json", models.JSONField(blank=True, default=dict)),
                ("engine", models.CharField(choices=[("django", "Django Templates"), ("jinja", "Jinja2")], default="django", max_length=20)),
                ("is_default", models.BooleanField(default=False, help_text="Marks the template as the default for this definition.")),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("is_gallery", models.BooleanField(default=False, help_text="Indicates if this template is a pre-built gallery item.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_created_report_templates", to=settings.AUTH_USER_MODEL)),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="templates", to="reporting.reportdefinition")),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reporting_report_templates", to="usermanagement.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_updated_report_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-is_default", "-updated_at", "name"],
                "db_table": "reporting_report_template",
            },
        ),
        migrations.CreateModel(
            name="ReportExecutionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], default="pending", max_length=20)),
                ("run_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("output_format", models.CharField(blank=True, max_length=10)),
                ("message", models.TextField(blank=True)),
                ("attachment_name", models.CharField(blank=True, max_length=255)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reporting_report_run_logs", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reporting_report_executions", to="usermanagement.organization")),
                ("report_definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="reporting.reportdefinition")),
                ("scheduled_report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="executions", to="reporting.scheduledreport")),
            ],
            options={
                "ordering": ["-run_at"],
                "db_table": "reporting_report_execution_log",
            },
        ),
        migrations.AddIndex(
            model_name="scheduledreport",
            index=models.Index(fields=["organization", "report_code"], name="reporting_s_organiz_236bb4_idx"),
        ),
        migrations.AddIndex(
            model_name="scheduledreport",
            index=models.Index(fields=["is_active", "next_run"], name="reporting_s_is_act_604c4d_idx"),
        ),
        migrations.AddIndex(
            model_name="reportexecutionlog",
            index=models.Index(fields=["organization", "report_definition"], name="reporting_r_organizat_7d61d8_idx"),
        ),
        migrations.AddIndex(
            model_name="reportexecutionlog",
            index=models.Index(fields=["status", "run_at"], name="reporting_r_status__698d25_idx"),
        ),
    ]
