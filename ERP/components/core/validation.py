from pydantic import ValidationError

def validate_with_schema(model_cls, data, custom_validators=None):
    """
    Validate data using the dynamic model and any custom validators.
    Returns (is_valid, errors).
    """
    errors = []
    try:
        obj = model_cls(**data)
    except ValidationError as ve:
        errors.extend(ve.errors())
    if custom_validators:
        for field, func in custom_validators.items():
            is_valid, msg = func(data.get(field))
            if not is_valid:
                errors.append({'loc': [field], 'msg': msg})
    return (not errors, errors)
