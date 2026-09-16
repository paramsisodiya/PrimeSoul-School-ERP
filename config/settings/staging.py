from .base import *
from .base import env


DEBUG = False

# Explicit staging hosts - never allow '*' in staging
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['.staging.primesoul.in', 'staging.primesoul.in'])
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['https://*.staging.primesoul.in', 'https://staging.primesoul.in']
)

# WhiteNoise compressed static storage
if 'whitenoise.runserver_nostatic' not in DEFAULT_APPS:
    DEFAULT_APPS.insert(0, 'whitenoise.runserver_nostatic')
INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Staging Security Headers
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
