import os
from pathlib import Path
from django.conf import settings
from django.contrib.messages import constants as messages

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# OPENTELEMETRY DISTRIBUTED TRACING (Import early)
# =============================================================================
# Import tracing config (will auto-configure if OTEL_ENABLED=true)
try:
    from utils import tracing
except ImportError:
    pass  # OpenTelemetry dependencies not installed yet


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-^-d#gtg)d41-e2#c%n40_&e)fg_ps9aptfq3_r%*zjjhu!-*-f'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_ALLOWED_TEMPLATE_PACKS = [
    'bootstrap4',
]

# Application definition
# Add or confirm this setting is True
APPEND_SLASH = True
INSTALLED_APPS = [
    'django_prometheus',  # <-- Add first for comprehensive metrics
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
    'drf_spectacular',  # <-- OpenAPI schema generation
    'silk',  # <-- Database query profiling
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
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # <-- Add first
    # 'silk.middleware.SilkyMiddleware',  # <-- DISABLED: Query profiling adds overhead (re-enable only when debugging SQL)
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',  # <-- Response compression
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'tenancy.middleware.ActiveTenantMiddleware',
    'accounting.middleware.RequestMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    "allauth.account.middleware.AccountMiddleware",
    'middleware.security.SecurityHeadersMiddleware',  # <-- Security headers (after auth)
    'middleware.security.RateLimitMiddleware',  # <-- Rate limiting (after auth)
    'middleware.logging.StructuredLoggingMiddleware',  # <-- Structured logging
    'api.versioning.APIVersionMiddleware',  # <-- API versioning
    'middleware.theme.ThemeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',  # <-- Add last
]

ROOT_URLCONF = 'dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
    'APP_DIRS': DEBUG,  # Use app directories loader only in DEBUG
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'middleware.theme.theme',
                'utils.i18n.i18n_context',
            ],
            # Enable cached template loader when not in DEBUG
            **({
                'loaders': [
                    (
                        'django.template.loaders.cached.Loader',
                        [
                            'django.template.loaders.filesystem.Loader',
                            'django.template.loaders.app_directories.Loader',
                        ],
                    )
                ]
            } if not DEBUG else {}),
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

if os.environ.get('USE_SQLITE', '0') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('PGDATABASE', 'erpdb'),
            'USER': os.environ.get('PGUSER', 'postgres'),
            'PASSWORD': os.environ.get('PGPASSWORD', '123'),
            'HOST': os.environ.get('PGHOST', 'localhost'),
            'PORT': os.environ.get('PGPORT', '5433'),
            'CONN_MAX_AGE': int(os.environ.get('PG_CONN_MAX_AGE', '600')),
            'OPTIONS': {
                'connect_timeout': int(os.environ.get('PG_CONNECT_TIMEOUT', '10')),
                'options': f"-c statement_timeout={int(os.environ.get('PG_STATEMENT_TIMEOUT_MS', '30000'))}",
            },
        }
    }

# =============================================================================
# REDIS CACHE CONFIGURATION
# =============================================================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # Use default parser instead of HiredisParser for compatibility
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Don't break if Redis is down
        },
        'KEY_PREFIX': 'himalytix',
        'TIMEOUT': 300,  # Default 5 minute cache timeout
    }
}

# Cache time to live (TTL) settings
CACHE_TTL = {
    'default': 60 * 5,      # 5 minutes
    'long': 60 * 60,        # 1 hour
    'short': 60,            # 1 minute
    'permanent': 60 * 60 * 24  # 1 day
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


# =============================================================================
# STRUCTURED LOGGING CONFIGURATION (structlog)
# =============================================================================
import structlog
import logging
import sys

# Determine log format from environment
LOG_FORMAT = os.getenv('LOG_FORMAT', 'console')  # 'json' or 'console'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Configure standard logging
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL),
)

# Structlog processors
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
]

if LOG_FORMAT == 'json':
    # Production: JSON logging for structured logs
    processors = shared_processors + [
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ]
else:
    # Development: Console logging with colors
    processors = shared_processors + [
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ]

structlog.configure(
    processors=processors,
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processor': structlog.processors.JSONRenderer(),
            'foreign_pre_chain': shared_processors,
        },
        'console': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processor': structlog.dev.ConsoleRenderer(),
            'foreign_pre_chain': shared_processors,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': LOG_FORMAT,
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'application.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': LOG_FORMAT,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        '': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
        },
    },
}


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
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# =============================================================================
# DRF-SPECTACULAR (OpenAPI Schema) CONFIGURATION
# =============================================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'Himalytix ERP API',
    'DESCRIPTION': 'Multi-tenant ERP system for Nepal market - RESTful API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    
    # API Versioning
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    
    # Security
    'SECURITY': [
        {
            'tokenAuth': [],
        },
        {
            'sessionAuth': [],
        }
    ],
    
    # UI Configuration
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
    },
    
    # Schema Generation
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': True,
    
    # Contact & License
    'CONTACT': {
        'name': 'Himalytix Support',
        'email': 'support@himalytix.com',
    },
    'LICENSE': {
        'name': 'MIT License',
        'url': 'https://opensource.org/licenses/MIT',
    },
    
    # Servers
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development'},
        {'url': 'https://staging.himalytix.com', 'description': 'Staging'},
        {'url': 'https://api.himalytix.com', 'description': 'Production'},
    ],
}

# Chart of Account hierarchy limits
COA_MAX_DEPTH = int(os.environ.get("COA_MAX_DEPTH", 10))
COA_MAX_SIBLINGS = int(os.environ.get("COA_MAX_SIBLINGS", 99))

