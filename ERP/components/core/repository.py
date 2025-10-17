from django.db import transaction

def save_entity_with_udfs(entity_name, entity_id, data, schema_fields, base_model_cls, udf_value_model_cls):
    """
    Save base entity fields and UDF values in a transaction.
    """
    with transaction.atomic():
        # Save base entity
        if entity_id:
            obj = base_model_cls.objects.get(pk=entity_id)
        else:
            obj = base_model_cls()
        for f in schema_fields:
            if not f.get('IsUDF', False):
                setattr(obj, f['FieldName'], data.get(f['FieldName']))
        obj.save()
        entity_id = obj.pk
        # Save UDF values
        for f in schema_fields:
            if f.get('IsUDF', False):
                val = data.get(f['FieldName'])
                udf_value_model_cls.objects.update_or_create(
                    entity_id=entity_id, field_id=f['FieldId'],
                    defaults={'text_value': val if f['DataType'] == 'varchar' else None,
                              'number_value': val if f['DataType'] in ('int', 'decimal', 'float') else None,
                    }
                )
    return entity_id
    return entity_id
