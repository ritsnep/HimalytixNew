from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

# Speed up tests by disabling migrations. Django will use ``syncdb`` instead.
class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

if 'rest_framework' not in INSTALLED_APPS:
    INSTALLED_APPS += ['rest_framework']
if 'api' not in INSTALLED_APPS:
    INSTALLED_APPS += ['api']
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}
