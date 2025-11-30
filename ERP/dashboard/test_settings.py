from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'foreign_keys': False,  # Disable foreign key constraints
            'init_command': 'PRAGMA foreign_keys=OFF;',  # Ensure foreign keys are off
        }
    }
}

# Disable migrations for tests by setting MIGRATION_MODULES to empty dict
MIGRATION_MODULES = {}

# Exclude problematic apps that cause migration issues
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'service_management']

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

if 'rest_framework' not in INSTALLED_APPS:
    INSTALLED_APPS += ['rest_framework']
if 'api' not in INSTALLED_APPS:
    INSTALLED_APPS += ['api']
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}
