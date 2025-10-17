from django.shortcuts import render
from .metadata_loader import get_entity_schema
from .form_schema import schema_to_form_fields

def dynamic_entity_form(request, entity_name):
    schema_fields = get_entity_schema(entity_name)
    schema = schema_to_form_fields(schema_fields)
    return render(request, "dynamic_form.html", {"schema": schema})
