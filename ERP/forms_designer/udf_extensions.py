"""
Extended field properties for VoucherUDFConfig
This file documents the additional JSON field structure for enhanced UDF features
"""

# Schema for layout_config JSONField
LAYOUT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "grid_column_width": {
            "type": "integer",
            "minimum": 1,
            "maximum": 12,
            "default": 12,
            "description": "Bootstrap grid column width (1-12)"
        },
        "grid_column_offset": {
            "type": "integer",
            "minimum": 0,
            "maximum": 11,
            "default": 0,
            "description": "Bootstrap grid column offset"
        },
        "grid_row": {
            "type": "integer",
            "minimum": 0,
            "description": "Row position in the form"
        },
        "grid_column": {
            "type": "integer",
            "minimum": 0,
            "description": "Column position within the row"
        },
        "css_class": {
            "type": "string",
            "description": "Additional CSS classes"
        },
        "inline_style": {
            "type": "object",
            "description": "Inline CSS styles"
        },
        "wrapper_class": {
            "type": "string",
            "description": "CSS class for field wrapper"
        },
        "label_class": {
            "type": "string",
            "description": "CSS class for field label"
        },
        "group_id": {
            "type": "string",
            "description": "Field group/section identifier"
        }
    }
}

# Schema for visibility_rules JSONField
VISIBILITY_RULES_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": False
        },
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Field name to watch"
                    },
                    "operator": {
                        "type": "string",
                        "enum": ["equals", "not_equals", "greater_than", "less_than", "contains", "in", "not_in", "is_empty", "is_not_empty"],
                        "description": "Comparison operator"
                    },
                    "value": {
                        "description": "Value to compare against"
                    },
                    "logical_op": {
                        "type": "string",
                        "enum": ["AND", "OR"],
                        "default": "AND",
                        "description": "How to combine with next condition"
                    }
                },
                "required": ["field", "operator"]
            }
        },
        "action": {
            "type": "string",
            "enum": ["show", "hide", "enable", "disable"],
            "default": "show",
            "description": "Action to take when conditions are met"
        }
    }
}

# Schema for calculated_field_config JSONField
CALCULATED_FIELD_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": False
        },
        "formula": {
            "type": "string",
            "description": "JavaScript expression for calculation"
        },
        "dependencies": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of field names this calculation depends on"
        },
        "format": {
            "type": "string",
            "enum": ["number", "currency", "percentage", "text"],
            "default": "number",
            "description": "Output format"
        },
        "decimal_places": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "default": 2
        },
        "read_only": {
            "type": "boolean",
            "default": True,
            "description": "Calculated fields are typically read-only"
        }
    }
}

# Schema for extended_validation JSONField
EXTENDED_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "custom_validators": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["regex", "function", "range", "date_range", "unique", "cross_field"],
                        "description": "Type of validation"
                    },
                    "config": {
                        "type": "object",
                        "description": "Validator-specific configuration"
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Custom error message"
                    }
                }
            }
        },
        "async_validation": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": False
                },
                "endpoint": {
                    "type": "string",
                    "description": "API endpoint for validation"
                },
                "debounce": {
                    "type": "integer",
                    "default": 500,
                    "description": "Debounce delay in milliseconds"
                }
            }
        }
    }
}


def get_default_layout_config():
    """Returns default layout configuration"""
    return {
        "grid_column_width": 12,
        "grid_column_offset": 0,
        "grid_row": 0,
        "grid_column": 0,
        "css_class": "",
        "wrapper_class": "mb-3",
        "label_class": "form-label",
        "group_id": None
    }


def get_default_visibility_rules():
    """Returns default visibility rules"""
    return {
        "enabled": False,
        "conditions": [],
        "action": "show"
    }


def get_default_calculated_config():
    """Returns default calculated field configuration"""
    return {
        "enabled": False,
        "formula": "",
        "dependencies": [],
        "format": "number",
        "decimal_places": 2,
        "read_only": True
    }


def get_default_extended_validation():
    """Returns default extended validation"""
    return {
        "custom_validators": [],
        "async_validation": {
            "enabled": False,
            "endpoint": "",
            "debounce": 500
        }
    }
