from accounting.models import VoucherModeConfig,default_ui_schema
from .models import VoucherSchema
from django.db import transaction

def get_active_schema(voucher_mode_config):
    """
    Returns the active UI schema for the given VoucherModeConfig.
    Checks VoucherSchema (latest), then ui_schema, then default_ui_schema().
    """
    # Try latest versioned schema
    latest_schema = VoucherSchema.objects.filter(voucher_mode_config=voucher_mode_config).order_by('-version').first()
    if latest_schema:
        return latest_schema.schema
    # Try ui_schema from config
    if voucher_mode_config.ui_schema:
        return voucher_mode_config.ui_schema
    # Fallback to default
    return default_ui_schema(voucher_mode_config)

@transaction.atomic
def save_schema(voucher_mode_config, schema, user=None):
    """
    Saves the schema to VoucherModeConfig.ui_schema and creates a new VoucherSchema version.
    """
    # Update ui_schema on config
    voucher_mode_config.ui_schema = schema
    voucher_mode_config.save(update_fields=['ui_schema'])
    # Determine next version
    last = VoucherSchema.objects.filter(voucher_mode_config=voucher_mode_config).order_by('-version').first()
    next_version = (last.version + 1) if last else 1
    # Create versioned schema
    VoucherSchema.objects.create(
        voucher_mode_config=voucher_mode_config,
        schema=schema,
        created_by=user,
        version=next_version
    ) 