import yaml
from django.conf import settings
import os

def load_config(config_name):
    """
    Loads a YAML configuration file from the 'config' directory.
    """
    config_path = os.path.join(settings.BASE_DIR, 'accounting', 'config', config_name)
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Handle the case where the config file is not found
        # You can log this event or raise a more specific exception
        return {}

# Load the journal entry configuration
journal_entry_config = load_config('journal_entry_config.yaml')

# You can also define a class to hold the configuration
class JournalEntryConfig:
    def __init__(self, config_dict):
        self._config = config_dict

    def get(self, key, default=None):
        """
        Retrieves a configuration value.
        """
        return self._config.get(key, default)

    @property
    def max_lines_per_entry(self):
        return self.get('max_lines_per_entry', 100)

    @property
    def supported_currencies(self):
        return self.get('supported_currencies', ['USD'])

    @property
    def allow_negative_entries(self):
        return self.get('allow_negative_entries', False)
        
    @property
    def enforce_fiscal_year(self):
        return self.get('enforce_fiscal_year', True)

    @property
    def ui_settings(self):
        return self.get('ui', {})

    @property
    def default_accounts(self):
        return self.get('default_accounts', {})

    @property
    def allowable_journal_entry_types(self):
        return self.get('allowable_journal_entry_types', [])

# Create a singleton instance of the config
journal_entry_settings = JournalEntryConfig(journal_entry_config)