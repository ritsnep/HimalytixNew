import os
import json
import yaml
from typing import Optional, Dict, Any
from django.conf import settings
from .models import VoucherSchema

# Simple in-memory cache
_schema_cache: Dict[str, Dict[str, Any]] = {}

SCHEMA_DIR = os.path.join(settings.BASE_DIR, 'ERP', 'voucher_schema', 'schemas')


def load_schema(code: str) -> Optional[dict]:
    """
    Load the active schema for a voucher type by code.
    Checks DB first, then falls back to file (YAML/JSON).
    Caches result in memory for fast reloads.
    """
    if code in _schema_cache:
        return _schema_cache[code]

    # Try DB
    schema_obj = VoucherSchema.objects.filter(code=code, is_active=True).order_by('-version').first()
    if schema_obj:
        _schema_cache[code] = schema_obj.content
        return schema_obj.content

    # Fallback to file
    for ext in ('.yml', '.yaml', '.json'):
        path = os.path.join(SCHEMA_DIR, f'{code}{ext}')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                if ext in ('.yml', '.yaml'):
                    content = yaml.safe_load(f)
                else:
                    content = json.load(f)
            _schema_cache[code] = content
            return content
    return None

def invalidate_schema_cache(code: str):
    """Invalidate the schema cache for a given code."""
    if code in _schema_cache:
        del _schema_cache[code] 