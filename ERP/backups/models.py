from django.db import models
from django.conf import settings
from tenancy.models import Tenant
import uuid

class BackupDestination(models.Model):
    DESTINATION_TYPES = (
        ('local', 'Local Storage'),
        ('s3', 'Amazon S3'),
        ('gcs', 'Google Cloud Storage'),
        ('gdrive', 'Google Drive'),
        ('dropbox', 'Dropbox'),
    )
    
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=DESTINATION_TYPES, default='local')
    config = models.JSONField(default=dict, help_text="Configuration details like bucket name, folder, etc.")
    credentials = models.JSONField(default=dict, help_text="Encrypted credentials or token references")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.type})"

class BackupPreference(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('manual', 'Manual Only'),
    )
    
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='backup_preference')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    destination = models.ForeignKey(BackupDestination, on_delete=models.SET_NULL, null=True, blank=True)
    notify_emails = models.TextField(blank=True, help_text="Comma separated email addresses")
    retain_days = models.IntegerField(default=7, help_text="Number of days to keep backups")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Backup Prefs for {self.tenant.code}"

class BackupJob(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    KIND_CHOICES = (
        ('manual', 'Manual'),
        ('auto', 'Automated'),
    )
    MODE_CHOICES = (
        ('pg_dump', 'PostgreSQL Dump'),
        ('csv_zip', 'CSV Zip'),
        ('json', 'JSON Dump'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='backups')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='manual')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='pg_dump')
    storage_type = models.CharField(max_length=20, default='local')
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, null=True)
    encryption_method = models.CharField(max_length=20, default='none')
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant.code} - {self.kind} - {self.created_at}"
