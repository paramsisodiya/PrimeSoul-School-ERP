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
INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS

STORAGES = {
    "default": {
        "BACKEND": env('DEFAULT_FILE_STORAGE_BACKEND', default="django.core.files.storage.FileSystemStorage"),
    },
    "staticfiles": {
        "BACKEND": "django_school_management.utils.storage.ResilientCompressedManifestStaticFilesStorage",
    },
}

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
