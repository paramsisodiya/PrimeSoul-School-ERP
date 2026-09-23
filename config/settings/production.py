"""
PrimeSoul School ERP - Production Settings Configuration
Hardened settings for multi-tenant deployment behind Nginx / Gunicorn.
"""
from .base import *
from .base import env


DEBUG = False

# Explicit production hosts - strictly disallow '*'
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['primesoul.local', 'localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['http://localhost:8000', 'https://localhost:8000'])

# WhiteNoise compressed static storage with Django 5 STORAGES syntax
if 'whitenoise.runserver_nostatic' not in DEFAULT_APPS:
    DEFAULT_APPS.insert(0, 'whitenoise.runserver_nostatic')
INSTALLED_APPS = [app for app in (DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS) if app != 'debug_toolbar']
MIDDLEWARE = [mw for mw in MIDDLEWARE if 'debug_toolbar' not in mw]

if USE_S3 and AWS_STORAGE_BUCKET_NAME:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "access_key": AWS_ACCESS_KEY_ID or None,
                "secret_key": AWS_SECRET_ACCESS_KEY or None,
                "region_name": AWS_S3_REGION_NAME or None,
                "endpoint_url": AWS_S3_ENDPOINT_URL or None,
                "custom_domain": AWS_S3_CUSTOM_DOMAIN or None,
                "file_overwrite": AWS_S3_FILE_OVERWRITE,
                "default_acl": AWS_DEFAULT_ACL,
                "querystring_auth": AWS_QUERYSTRING_AUTH,
            },
        },
        "staticfiles": {
            "BACKEND": "django_school_management.utils.storage.ResilientCompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": env('DEFAULT_FILE_STORAGE_BACKEND', default="django.core.files.storage.FileSystemStorage"),
        },
        "staticfiles": {
            "BACKEND": "django_school_management.utils.storage.ResilientCompressedManifestStaticFilesStorage",
        },
    }

# Production Template Configuration (Cached Template Loader for low memory and high throughput)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "templates")],
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "context_processors.attach_resources.attach_institute_data_ctx_processor",
                "context_processors.attach_resources.attach_urls_for_common_templates",
                "context_processors.attach_resources.attach_dashboard_menu_items",
            ],
        },
    },
]

# Allow WhiteNoise to skip missing optional third-party assets in vendor CSS without throwing 500
WHITENOISE_MANIFEST_STRICT = env.bool('WHITENOISE_MANIFEST_STRICT', default=False)

# Production Security Hardening
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows frontend JS / CSRF headers while protecting session
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'same-origin'

# Production Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(asctime)s [%(levelname)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django_school_management': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
