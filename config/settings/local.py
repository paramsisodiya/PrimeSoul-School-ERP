from .base import *
from .base import env


DEBUG = True
SSL_ISSANDBOX = env.bool('SSL_ISSANDBOX', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '.localhost', '.local', '*'])
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost',
        'http://127.0.0.1',
    ]
)

# Custom CSRF failure view to gracefully recover from stale tokens and bfcache
CSRF_FAILURE_VIEW = 'django_school_management.utils.views.csrf_failure_view'

# Optional Debug Toolbar in local development
if 'debug_toolbar' not in THIRD_PARTY_APPS:
    try:
        import debug_toolbar
        THIRD_PARTY_APPS.append('debug_toolbar')
        INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS + THIRD_PARTY_APPS
        MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.common.CommonMiddleware') + 1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = env.list('INTERNAL_IPS', default=['127.0.0.1', '::1'])
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: True,
            'INTERCEPT_REDIRECTS': False,
            'DISABLE_PANELS': {
                'debug_toolbar.panels.redirects.RedirectsPanel',
            },
        }
    except ImportError:
        pass
