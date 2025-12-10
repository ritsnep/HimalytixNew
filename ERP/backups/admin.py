from django.contrib import admin
from .models import BackupDestination, BackupPreference, BackupJob

@admin.register(BackupDestination)
class BackupDestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_active', 'created_at')
    list_filter = ('type', 'is_active')
    search_fields = ('name',)

@admin.register(BackupPreference)
class BackupPreferenceAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'frequency', 'destination', 'retain_days')
    list_filter = ('frequency', 'destination')
    search_fields = ('tenant__code', 'tenant__name')

@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'kind', 'status', 'file_size', 'created_at')
    list_filter = ('kind', 'status', 'created_at')
    search_fields = ('tenant__code', 'id')
    readonly_fields = ('id', 'created_at', 'completed_at', 'file_path', 'file_size', 'checksum')
