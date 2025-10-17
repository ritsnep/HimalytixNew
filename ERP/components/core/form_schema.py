def schema_to_form_fields(schema_fields):
    """
    Convert schema fields to a list of dicts suitable for form rendering.
    """
    field_map = {
        'varchar': 'text',
        'text': 'text',
        'int': 'number',
        'bigint': 'number',
        'decimal': 'number',
        'float': 'number',
        'date': 'date',
        'boolean': 'checkbox',
    }
    fields = []
    for f in schema_fields:
        input_type = field_map.get(f['DataType'], 'text')
        field = {
            'name': f['FieldName'],
            'label': f.get('DisplayName', f['FieldName']),
            'input_type': input_type,
            'required': f.get('IsRequired', False),
            'placeholder': f.get('Placeholder', ''),
            'pattern': f.get('Pattern', None),
            'help_text': f.get('HelpText', ''),
            'options': f.get('Options', []),
        }
        fields.append(field)
    return {'fields': fields}
