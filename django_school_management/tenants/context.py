"""
Thread-local context manager for the active tenant (School).
Ensures safe tenant isolation across requests and asynchronous workers.
"""
import threading
from typing import Optional

_thread_locals = threading.local()


def set_current_school(school) -> None:
    """Sets the active school tenant in thread-local storage."""
    _thread_locals.school = school


def get_current_school():
    """Retrieves the active school tenant from thread-local storage."""
    return getattr(_thread_locals, 'school', None)


def clear_current_school() -> None:
    """Clears the active school tenant from thread-local storage."""
    if hasattr(_thread_locals, 'school'):
        delattr(_thread_locals, 'school')


# Aliases for generic multi-tenancy terminology
set_current_tenant = set_current_school
get_current_tenant = get_current_school
clear_current_tenant = clear_current_school
