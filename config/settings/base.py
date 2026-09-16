import os
from pathlib import Path

import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from django.core.exceptions import ImproperlyConfigured
from django.contrib.messages import constants as messages

from django_school_management.accounts.constants import AccountURLConstants
from utilities.constants import settings_message_constants


######################## Django Core & Custom Configs ########################
##############################################################################

BASE_DIR = Path(__file__).parent.parent.parent

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, True),
    USE_PAYMENT_OPTIONS=(bool, True),
    USE_SENTRY=(bool, False),
    USE_MAILCHIMP=(bool, False),
    SSL_ISSANDBOX=(bool, True),
    USE_STRIPE=(bool, False),
    IS_DEMO_ENV=(bool, False),
)
# reading .env file
env.read_env(str(BASE_DIR / "envs/.env"))

SECRET_KEY = env('SECRET_KEY', default='primesoul-insecure-dev-key-change-in-production-!@#$12345')

DEBUG = env('DEBUG')

try:
    DJANGO_ADMIN_URL = env('DJANGO_ADMIN_URL')
except ImproperlyConfigured:
    DJANGO_ADMIN_URL = 'admin'

DEFAULT_APPS = [
    'django_school_management.accounts.apps.AccountsConfig',  # must be on top
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # allauth required
    'django.contrib.sites',
]

LOCAL_APPS = [
    'django_school_management.tenants.apps.TenantsConfig',
    'django_school_management.students.apps.StudentsConfig',
    'django_school_management.teachers.apps.TeachersConfig',
    'django_school_management.result.apps.ResultConfig',
    'django_school_management.academics.apps.AcademicsConfig',
    'django_school_management.pages.apps.PagesConfig',
    'django_school_management.articles.apps.ArticlesConfig',
    'django_school_management.institute.apps.InstituteConfig',
    'django_school_management.curriculum.apps.CurriculumConfig',
    'django_school_management.payments.apps.PaymentsConfig',
    'django_school_management.notices.apps.NoticesConfig',
    'django_school_management.fees.apps.FeesConfig',
    'django_school_management.attendance.apps.AttendanceConfig',
    'django_school_management.examinations.apps.ExaminationsConfig',
    'django_school_management.timetable.apps.TimetableConfig',
    'django_school_management.transport.apps.TransportConfig',
    'django_school_management.library.apps.LibraryConfig',
    'django_school_management.hr.apps.HRConfig',
    'django_school_management.portal.apps.PortalConfig',
    'django_school_management.communication.apps.CommunicationConfig',
    'django_school_management.admissions.apps.AdmissionsConfig',
    'django_school_management.inventory.apps.InventoryConfig',
    'django_school_management.reports.apps.ReportsConfig',
]

# third party apps
THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap4',
    'rolepermissions',
    'taggit',
    'django_extensions',
    'django_filters',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'ckeditor',
    'ckeditor_uploader',
    'mptt',
    'widget_tweaks',
    'django_social_share',
    'django_countries',
    'import_export',
    # 'admin_honeypot',   # admin_honeypot doesn't support Django 4
    'django_tables2',
    'bootstrap4',
    'django_file_form',
    'tinymce',
    # API Documentation and Advanced Features
    'drf_yasg',
    'django_rest_passwordreset',
    # Monitoring
    'django_prometheus',
]

INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS

SITE_ID = 1

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_school_management.tenants.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
    'django_school_management.utils.middleware.AppMetricsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # ctx processeor to attach institute data in templates
                "context_processors.attach_resources.attach_institute_data_ctx_processor",
                "context_processors.attach_resources.attach_urls_for_common_templates",
                "context_processors.attach_resources.attach_dashboard_menu_items",
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration with Environment / PostgreSQL, DATABASE_URL, or SQLite Fallback
DATABASE_URL = env('DATABASE_URL', default='')
DB_ENGINE = env('DB_ENGINE', default='django_prometheus.db.backends.postgresql' if env('DB_NAME', default='') else '')
DB_NAME = env('DB_NAME', default='')

if DATABASE_URL:
    DATABASES = {
        'default': env.db_url_config(
            DATABASE_URL,
            engine='django_prometheus.db.backends.postgresql'
        )
    }
    DATABASES['default']['CONN_MAX_AGE'] = env.int('CONN_MAX_AGE', default=600)
elif DB_NAME:
    db_opts = {}
    db_sslmode = env('DB_SSLMODE', default='')
    if db_sslmode:
        db_opts['sslmode'] = db_sslmode
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE or 'django_prometheus.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': env('DB_USER', default='postgres'),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env.int('DB_PORT', default=5432),
            'CONN_MAX_AGE': env.int('CONN_MAX_AGE', default=600),
            'OPTIONS': db_opts,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Cache Configuration (Redis with LocMem fallback for local/testing)
REDIS_HOST = env('REDIS_HOST', default='')
REDIS_PORT = env('REDIS_PORT', default='6379')

if REDIS_HOST:
    CACHES = {
        'default': {
            'BACKEND': 'django_prometheus.cache.backends.redis.RedisCache',
            'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/0',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'primesoul-cache',
        }
    }

# Write session to the DB, only load it from the cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# SET MYSQLDB charset for storing text if mysql backend
if 'mysql' in DATABASES['default']['ENGINE']:
    DATABASES['default']['OPTIONS'] = {'charset': 'utf8mb4'}

# Password validation - Enabled standard Django password validators
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Internationalization - Defaulting to Indian Standard Time (Asia/Kolkata)
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE', default='Asia/Kolkata')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)

STATIC_ROOT = str(BASE_DIR / 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    str(BASE_DIR / 'static')
]

MESSAGE_TAGS = {
    messages.DEBUG: 'alert-info',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger'
}

MEDIA_ROOT = str(BASE_DIR / 'media')
MEDIA_URL = '/media/'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_USE_TLS = True

EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# login/register redirects

LOGIN_REDIRECT_URL = AccountURLConstants.profile_complete
LOGOUT_REDIRECT_URL = 'account_login'

LOGIN_URL = AccountURLConstants.profile_complete
LOGOUT_URL = 'account_logout'


######################## Third Party Configs ########################
#####################################################################

# DRF CONFIGS
REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated'
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.openapi.AutoSchema',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
}

# CORS Configuration - Explicit origins required for SaaS security
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
)
CORS_ALLOW_CREDENTIALS = True

# SENTRY - For logging and monitoring purposes
USE_SENTRY = env('USE_SENTRY')
if USE_SENTRY:
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=False,
        debug=False
    )

# django-prometheus - production-ready defaults
PROMETHEUS_EXPORT_MIGRATIONS = env.bool('PROMETHEUS_EXPORT_MIGRATIONS', True)
PROMETHEUS_METRIC_NAMESPACE = "primesoul_school"
PROMETHEUS_LATENCY_BUCKETS = (
    0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0,
    2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, float("inf"),
)

# for permission management
ROLEPERMISSIONS_MODULE = 'django_school_management.accounts.roles'

CRISPY_TEMPLATE_PACK = 'bootstrap4'

CKEDITOR_UPLOAD_PATH = 'ck-uploads/'
CKEDITOR_IMAGE_BACKEND = 'pillow'
CKEDITOR_ALLOW_NONIMAGE_FILES = False
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'extraPlugins': ['codesnippet', 'markdown'], 'width': '100%',
    },
}

# STOP SENDING EMAIL FOR USER REGISTRATION
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Django taggit.
TAGGIT_CASE_INSENSITIVE = True

# =========================== PAYMENTS ===========================
USE_PAYMENT_OPTIONS = env('USE_PAYMENT_OPTIONS')

if USE_PAYMENT_OPTIONS:
    try:
        BRAINTREE_MERCHANT_ID = env('BRAINTREE_MERCHANT_ID', default='')
        BRAINTREE_PUBLIC_KEY = env('BRAINTREE_PUBLIC_KEY', default='')
        BRAINTREE_PRIVATE_KEY = env('BRAINTREE_PRIVATE_KEY', default='')

        STORE_ID = env('STORE_ID', default='')
        STORE_PASS = env('STORE_PASS', default='')
        SSL_ISSANDBOX = env('SSL_ISSANDBOX', default=True)
    except Exception:
        pass

USE_STRIPE = env('USE_STRIPE')
if USE_STRIPE:
    STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='')
    STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
    STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

# CELERY BROKER CONFIG
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'

# MAILCHIMP INTEGRATION
USE_MAILCHIMP = env('USE_MAILCHIMP')
if USE_MAILCHIMP:
    MAILCHIMP_API_KEY = env('MAILCHIMP_API_KEY')
    MAILCHIMP_DATA_CENTER = env('MAILCHIMP_DATA_CENTER')
    MAILCHIMP_LIST_ID = env('MAILCHIMP_LIST_ID')

TINYMCE_DEFAULT_CONFIG = {
    "theme": "silver",
    "height": 500,
    "menubar": False,
    "plugins": "advlist,autolink,lists,link,image,charmap,print,preview,anchor,"
    "searchreplace,visualblocks,code,fullscreen,insertdatetime,media,table,paste,"
    "code,help,wordcount",
    "toolbar": "undo redo | formatselect | "
    "bold italic backcolor | alignleft aligncenter "
    "alignright alignjustify | bullist numlist outdent indent | "
    "removeformat | help",
}

# RAZORPAY CONFIGURATION
RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET', default='')
RAZORPAY_WEBHOOK_SECRET = env('RAZORPAY_WEBHOOK_SECRET', default='')

IS_DEMO_ENV = env.bool('IS_DEMO_ENV', default=False)
DEMO_SUPERUSER_USERNAME = env('DEMO_SUPERUSER_USERNAME', default='demosuperuser')
DEMO_SUPERUSER_EMAIL = env('DEMO_SUPERUSER_EMAIL', default='demosuperuser@example.com')
DEMO_SUPERUSER_PASSWORD = env('DEMO_SUPERUSER_PASSWORD', default='demo@123')

# CSRF FAILURE VIEW - Resilient recovery from expired/stale tokens and bfcache
CSRF_FAILURE_VIEW = 'django_school_management.utils.views.csrf_failure_view'

# DJANGO DEBUG TOOLBAR CONFIGURATION
# Permanently exclude RedirectsPanel so all redirects execute immediately
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: True,
    'INTERCEPT_REDIRECTS': False,
    'DISABLE_PANELS': {
        'debug_toolbar.panels.redirects.RedirectsPanel',
    },
}
DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.history.HistoryPanel',
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
]

