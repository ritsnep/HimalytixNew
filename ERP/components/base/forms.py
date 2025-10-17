from django import forms

class DynamicForm(forms.Form):
    """
    Base form class that allows dynamic field configuration.
    Fields can be enabled/disabled through configuration.
    """
    def __init__(self, *args, **kwargs):
        field_config = kwargs.pop('field_config', {})
        super().__init__(*args, **kwargs)
        
        # Apply field configuration
        for field_name, config in field_config.items():
            if field_name in self.fields:
                if 'enabled' in config:
                    if not config['enabled']:
                        del self.fields[field_name]
                if 'required' in config:
                    self.fields[field_name].required = config['required']
                if 'label' in config:
                    self.fields[field_name].label = config['label']
                if 'help_text' in config:
                    self.fields[field_name].help_text = config['help_text']
                if 'widget' in config:
                    self.fields[field_name].widget = config['widget']

class DynamicModelForm(forms.ModelForm):
    """
    Base model form class that allows dynamic field configuration.
    Fields can be enabled/disabled through configuration.
    """
    def __init__(self, *args, **kwargs):
        field_config = kwargs.pop('field_config', {})
        super().__init__(*args, **kwargs)
        
        # Apply field configuration
        for field_name, config in field_config.items():
            if field_name in self.fields:
                if 'enabled' in config:
                    if not config['enabled']:
                        del self.fields[field_name]
                if 'required' in config:
                    self.fields[field_name].required = config['required']
                if 'label' in config:
                    self.fields[field_name].label = config['label']
                if 'help_text' in config:
                    self.fields[field_name].help_text = config['help_text']
                if 'widget' in config:
                    self.fields[field_name].widget = config['widget']
