import os
import subprocess
import shutil
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from tenancy.models import Tenant
from .models import BackupJob, BackupPreference

logger = logging.getLogger(__name__)

@shared_task
def run_nightly_backups():
    """
    Iterate over all active tenants and run backups.
    """
    logger.info("Starting nightly backups")
    tenants = Tenant.objects.filter(is_active=True)
    for tenant in tenants:
        # Check preferences
        pref = getattr(tenant, 'backup_preference', None)
        if pref and pref.frequency == 'manual':
            continue
            
        run_tenant_backup.delay(tenant.id)

@shared_task
def run_tenant_backup(tenant_id, user_id=None):
    """
    Run backup for a specific tenant.
    """
    try:
        tenant = Tenant.objects.get(pk=tenant_id)
    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found")
        return

    job = BackupJob.objects.create(
        tenant=tenant,
        requested_by_id=user_id,
        kind='manual' if user_id else 'auto',
        status='running',
        started_at=timezone.now()
    )
    
    try:
        # Prepare paths
        backup_root = os.path.join(settings.MEDIA_ROOT, 'backups')
        tenant_backup_dir = os.path.join(backup_root, tenant.code)
        os.makedirs(tenant_backup_dir, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        # Naming convention: schema_timestamp.dump
        filename = f"{tenant.data_schema}_{timestamp}.dump"
        filepath = os.path.join(tenant_backup_dir, filename)
        
        # Get DB config
        db_conf = settings.DATABASES['default']
        
        # Check if postgres
        if 'postgresql' not in db_conf['ENGINE']:
            raise ValueError("Only PostgreSQL backups are supported currently")

        # Construct pg_dump command
        env = os.environ.copy()
        env['PGPASSWORD'] = db_conf['PASSWORD']
        
        # pg_dump -h host -p port -U user -d dbname -n schema -F c -f file
        cmd = [
            'pg_dump',
            '-h', db_conf['HOST'],
            '-p', str(db_conf['PORT']),
            '-U', db_conf['USER'],
            '-d', db_conf['NAME'],
            '-n', tenant.data_schema,
            '-F', 'c', # Custom format
            '-f', filepath
        ]
        
        logger.info(f"Running backup for {tenant.code}: {' '.join(cmd)}")
        
        # Run with timeout to prevent hanging processes
        try:
            subprocess.run(cmd, env=env, check=True, timeout=3600) # 1 hour timeout
        except subprocess.TimeoutExpired:
            raise Exception("Backup process timed out after 1 hour")
        except subprocess.CalledProcessError as e:
            raise Exception(f"pg_dump failed with exit code {e.returncode}")
        
        # Update job
        if os.path.exists(filepath):
            # Upload if configured
            try:
                _upload_to_destination(job, filepath)
            except Exception as upload_error:
                logger.error(f"Upload failed for {tenant.code}: {upload_error}")
                # We don't fail the job if upload fails, but we log it.
                # Or maybe we should mark it as partial success?
                # For now, just log.

            job.status = 'success'
            job.file_path = filepath
            job.file_size = os.path.getsize(filepath)
            job.completed_at = timezone.now()
            job.save()
            
            # Apply retention policy
            _apply_retention(tenant)
        else:
            raise FileNotFoundError("Backup file was not created")
            
    except Exception as e:
        logger.exception(f"Backup failed for {tenant.code}")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        # Don't re-raise to avoid Celery retry loops for permanent errors
        
def _apply_retention(tenant):
    """
    Keep only the last N backups.
    """
    pref = getattr(tenant, 'backup_preference', None)
    retention_days = pref.retain_days if pref else 7
    
    # Find successful backups ordered by date desc
    backups = BackupJob.objects.filter(
        tenant=tenant, 
        status='success'
    ).order_by('-created_at')
    
    # We want to keep backups within retention window, OR at least the last N backups?
    # Plan says "keep last 7 successful".
    
    if backups.count() > retention_days:
        to_delete = backups[retention_days:]
        for job in to_delete:
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                except OSError as e:
                    logger.warning(f"Failed to delete old backup file {job.file_path}: {e}")
            job.delete() # Or mark as deleted/archived

def _upload_to_destination(job, filepath):
    tenant = job.tenant
    pref = getattr(tenant, 'backup_preference', None)
    if not pref or not pref.destination:
        return

    dest = pref.destination
    if dest.type == 's3':
        try:
            import boto3
        except ImportError:
            logger.error("boto3 not installed, cannot upload to S3")
            return

        s3 = boto3.client(
            's3',
            aws_access_key_id=dest.credentials.get('access_key'),
            aws_secret_access_key=dest.credentials.get('secret_key'),
            region_name=dest.config.get('region', 'us-east-1')
        )
        bucket = dest.config.get('bucket')
        key = f"{tenant.code}/{os.path.basename(filepath)}"
        s3.upload_file(filepath, bucket, key)
        job.storage_type = 's3'
        job.save()
        logger.info(f"Uploaded backup to S3: {bucket}/{key}")
    
    # Add other providers here (gcs, gdrive, dropbox)
