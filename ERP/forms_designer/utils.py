from accounting.models import VoucherModeConfig,default_ui_schema
from .models import VoucherSchema, VoucherSchemaStatus
from django.db import transaction

def get_active_schema(voucher_mode_config):
    """
    Returns the active UI schema for the given VoucherModeConfig.
    Preference order:
    1) Active version (is_active=True)
    2) Latest published/approved version
    3) Latest version (any status)
    4) VoucherModeConfig.ui_schema
    5) default_ui_schema()
    """
    qs = VoucherSchema.objects.filter(voucher_mode_config=voucher_mode_config)

    # 1) Active version
    active = qs.filter(is_active=True).order_by('-version').first()
    if active:
        return active.schema

    # 2) Latest published/approved
    released = qs.filter(status__in=[VoucherSchemaStatus.PUBLISHED, VoucherSchemaStatus.APPROVED]).order_by('-version').first()
    if released:
        return released.schema

    # 3) Latest any
    latest = qs.order_by('-version').first()
    if latest:
        return latest.schema
    # Try ui_schema from config
    if voucher_mode_config.ui_schema:
        return voucher_mode_config.ui_schema
    # Fallback to default
    return default_ui_schema()

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