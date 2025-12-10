from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404, FileResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import os

from usermanagement.utils import PermissionUtils
from inventory.models import Product
from accounting.models import Customer, SalesInvoice
from .services import ExportService
from .models import BackupJob
from .tasks import run_tenant_backup

@method_decorator(login_required, name='dispatch')
class ExportView(View):
    def get(self, request, dataset, fmt):
        # Check permissions - simplified for now, should be granular
        if not PermissionUtils.is_org_admin(request.user, request.organization):
             messages.error(request, "You do not have permission to export data.")
             return redirect('dashboard')

        queryset = None
        if dataset == 'products':
            queryset = Product.objects.filter(organization=request.organization)
        elif dataset == 'customers':
            queryset = Customer.objects.filter(organization=request.organization)
        elif dataset == 'invoices':
            queryset = SalesInvoice.objects.filter(organization=request.organization)
        else:
            raise Http404("Dataset not found")

        try:
            buffer, filename, content_type = ExportService.export_dataset(dataset, queryset, fmt)
            
            response = HttpResponse(buffer.getvalue(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            messages.error(request, f"Export failed: {str(e)}")
            return redirect('backups:dashboard')

@login_required
def export_dashboard(request):
    if not PermissionUtils.is_org_admin(request.user, request.organization):
        messages.error(request, "You do not have permission to access backups.")
        return redirect('dashboard')

    # List recent backups for this tenant
    # Note: request.tenant is set by middleware, but we should ensure we filter by the tenant associated with the user's org
    # In this system, Organization belongs to Tenant.
    # Assuming request.tenant is correct context.
    
    backups = BackupJob.objects.filter(
        tenant=request.tenant
    ).order_by('-created_at')[:20]

    return render(request, 'backups/export_dashboard.html', {
        'backups': backups
    })

@login_required
def trigger_backup(request):
    if request.method != 'POST':
        return redirect('backups:dashboard')
        
    if not PermissionUtils.is_org_admin(request.user, request.organization):
        messages.error(request, "Permission denied.")
        return redirect('backups:dashboard')

    # Rate limiting: Check if there's a running job or one created in last hour
    one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
    recent_jobs = BackupJob.objects.filter(
        tenant=request.tenant,
        kind='manual',
        created_at__gte=one_hour_ago
    )
    
    if recent_jobs.exists():
        messages.warning(request, "A manual backup was already requested recently. Please wait before requesting another.")
        return redirect('backups:dashboard')

    # Trigger task
    run_tenant_backup.delay(request.tenant.id, request.user.id)
    messages.success(request, "Backup process started. It will appear in the list shortly.")
    return redirect('backups:dashboard')

@login_required
def delete_backup(request, job_id):
    if request.method != 'POST':
        return redirect('backups:dashboard')
        
    if not PermissionUtils.is_org_admin(request.user, request.organization):
        messages.error(request, "Permission denied.")
        return redirect('backups:dashboard')

    job = get_object_or_404(BackupJob, id=job_id, tenant=request.tenant)
    
    try:
        if job.file_path and os.path.exists(job.file_path):
            os.remove(job.file_path)
        job.delete()
        messages.success(request, "Backup deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting backup: {e}")
        
    return redirect('backups:dashboard')

@login_required
def backup_list_partial(request):
    """HTMX partial for refreshing the backup list."""
    if not PermissionUtils.is_org_admin(request.user, request.organization):
        return HttpResponseForbidden()
        
    backups = BackupJob.objects.filter(
        tenant=request.tenant
    ).order_by('-created_at')[:20]
    
    return render(request, 'backups/partials/backup_list.html', {'backups': backups})

@login_required
def download_backup(request, job_id):
    if not PermissionUtils.is_org_admin(request.user, request.organization):
        raise Http404()

    job = get_object_or_404(BackupJob, id=job_id, tenant=request.tenant)
    
    if not job.file_path or not os.path.exists(job.file_path):
        messages.error(request, "Backup file not found on server.")
        return redirect('backups:dashboard')

    try:
        response = FileResponse(open(job.file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(job.file_path)}"'
        return response
    except Exception as e:
        messages.error(request, f"Error downloading file: {e}")
        return redirect('backups:dashboard')

