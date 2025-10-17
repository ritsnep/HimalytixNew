from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = 'test'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'tenancy',
    'accounting',
    'usermanagement',
]
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
ROOT_URLCONF = 'test_urls'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'accounting' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {},
    },
]
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
AUTH_USER_MODEL = 'usermanagement.CustomUser'
MIGRATION_MODULES = {
    'usermanagement': None,
    'accounting': None,
}