"""
Auto-numbering service for accounting models.
"""
from django.db import models

def generate_auto_number(model, field, prefix='', suffix=''):
    from django.db.models import Max
    import re
    pattern = rf'^{re.escape(prefix)}(\d+){re.escape(suffix)}$'
    codes = model.objects.values_list(field, flat=True)
    numbers = [
        int(re.match(pattern, code).group(1))
        for code in codes if re.match(pattern, code)
    ]
    next_number = max(numbers, default=0) + 1
    return f"{prefix}{str(next_number).zfill(2)}{suffix}"
