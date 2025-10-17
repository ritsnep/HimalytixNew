from pydantic import BaseModel, create_model
from typing import List, Dict

TYPE_MAP = {
    'varchar': (str, ...), 'text': (str, ...),
    'int': (int, ...), 'bigint': (int, ...),
    'decimal': (float, ...), 'float': (float, ...),
    'date': (str, ...), 'boolean': (bool, ...),
}

def create_dynamic_model(entity_name: str, fields: List[Dict]):
    """
    Given entity schema fields, create a Pydantic model class.
    """
    field_defs = {}
    for fld in fields:
        name = fld['FieldName']
        ftype = fld['DataType']
        ptype, default = TYPE_MAP.get(ftype, (str, ...))
        default = None if not fld.get('IsRequired', False) else ...
        field_defs[name] = (ptype, default)
    DynamicModel = create_model(entity_name + "Model", **field_defs, __base__=BaseModel)
    for fld in fields:
        if 'DisplayName' in fld:
            DynamicModel.__fields__[fld['FieldName']].field_info.description = fld['DisplayName']
    return DynamicModel
