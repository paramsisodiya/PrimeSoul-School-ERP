from django.conf import settings
from .base import BaseNotificationProvider
from .mock import MockNotificationProvider
from .django_email import DjangoEmailProvider


_provider_instances = {}


def get_notification_provider(channel: str = 'IN_APP') -> BaseNotificationProvider:
    """
    Factory function returning the configured provider instance for a channel.
    Defaults to MockNotificationProvider during testing or when mock is configured.
    """
    provider_setting = getattr(settings, 'NOTIFICATION_PROVIDER', 'mock').lower()

    if provider_setting == 'mock':
        if 'mock' not in _provider_instances:
            _provider_instances['mock'] = MockNotificationProvider()
        return _provider_instances['mock']

    if channel == 'EMAIL':
        if 'django_email' not in _provider_instances:
            _provider_instances['django_email'] = DjangoEmailProvider()
        return _provider_instances['django_email']

    # Fallback to Mock Provider for SMS / WhatsApp / In-App unless specialized provider classes are registered
    if 'mock' not in _provider_instances:
        _provider_instances['mock'] = MockNotificationProvider()
    return _provider_instances['mock']
