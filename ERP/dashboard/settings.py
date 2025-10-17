import os
from pathlib import Path
from django.conf import settings
from django.contrib.messages import constants as messages

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-^-d#gtg)d41-e2#c%n40_&e)fg_ps9aptfq3_r%*zjjhu!-*-f'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

CRISPY_TEMPLATE_PACK = 'bootstrap4'

# Application definition
# Add or confirm this setting is True
APPEND_SLASH = True
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "apps",
    "components",
    "pages",
    'usermanagement',
    "django.contrib.sites",   # Required by allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",  
    'crispy_forms',
    'crispy_bootstrap4',
    'tenancy',
    'accounting',
    'api',
    'rest_framework',
    'rest_framework.authtoken',
    'metadata',
    'voucher_schema',
    'mptt', # Ensure django-mptt is installed and added BEFORE Inventory
    'Inventory',
    'forms_designer',
    'django_htmx',
    'widget_tweaks',
    'formtools',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'tenancy.middleware.ActiveTenantMiddleware',
    'accounting.middleware.RequestMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    "allauth.account.middleware.AccountMiddleware",
    'middleware.theme.ThemeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'middleware.theme.theme',
                'utils.i18n.i18n_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'dashboard.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
# DATABASES = {
#     'default': {
#         'ENGINE': 'mssql',
#         'NAME': 'erptest1',
#         'USER': 'erpuser',
#         'PASSWORD': 'user@123',
#         'HOST': 'localhost',
#         'PORT': '1433',
#         'OPTIONS': {
#             'driver': 'ODBC Driver 17 for SQL Server',  # Make sure this driver is installed
#             'Trusted_Connection': 'no',
#         },
#     }
# }    

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'neondb',
#         'USER': 'neondb_owner',
#         'PASSWORD': 'npg_RQZX3leSNV7F',
#         'HOST': 'ep-white-cloud-a8r61wfa-pooler.eastus2.azure.neon.tech',
#         'PORT': '5432',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'erpdb',  # Default local Postgres DB name
        'USER': 'postgres',  # Default local Postgres user
        'PASSWORD': '123',   # Your local Postgres password
        'HOST': 'localhost',
        'PORT': '5433',
    }
}
AUTH_USER_MODEL = 'usermanagement.CustomUser'
    

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'
LANGUAGES = [
    ('en', 'English'),
    ('ne', 'Nepali'),
]
LANGUAGE_COOKIE_NAME = 'django_language'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# This is where Django will look for static files during development
# (e.g., your custom CSS/JS that isn't part of an app)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static') # Your existing /Himalytix/ERP/static/ folder
]

# This is where 'python manage.py collectstatic' will gather ALL static files for deployment.
# It should be a DIFFERENT directory, typically outside your project source code.
STATIC_ROOT = os.path.join(BASE_DIR.parent, 'collected_static_files') # <-- Changed this line


MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}
LOGIN_URL = '/accounts/login/'  # or whatever your login URL is

# LOGIN_URL = "/authentication/login/"
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


AUTHENTICATION_BACKENDS = [
    # "django.contrib.auth.backends.ModelBackend",
    # "allauth.account.auth_backends.AuthenticationBackend",
    'usermanagement.authentication.CustomAuthenticationBackend',
    
]
SITE_ID = 1
# Redirects
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"

# Signup/Login behavior
# ACCOUNT_AUTHENTICATION_METHOD = "username_email"
# ACCOUNT_EMAIL_REQUIRED = True
# ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"  # or "mandatory" if you handle emails
ACCOUNT_FORMS = {
    'login': 'usermanagement.forms.DasonLoginForm',
}

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

SESSION_COOKIE_AGE = 3 * 60 * 60  # 3 hours
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {                               # <--- new handler
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/app.log',   # path for your log text file
            'formatter': 'verbose',
        },
    },
    'formatters': {                            # optional formatting
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'root': {
        'handlers': ['console', 'file'],       # output to both terminal and file
        'level': 'INFO',
    },
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Chart of Account hierarchy limits
COA_MAX_DEPTH = int(os.environ.get("COA_MAX_DEPTH", 10))
COA_MAX_SIBLINGS = int(os.environ.get("COA_MAX_SIBLINGS", 99))

