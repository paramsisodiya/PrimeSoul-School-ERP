"""
Handling permissions for users who are assigned
for basic level actions in the project. (view few data, modify some of their data etc).
UserTypes: Student, Teacher
"""

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from django_school_management.accounts.constants import (
    AccountTypesEnum,
    ProfileApprovalStatusEnum,
)
from django_school_management.accounts.models import User


@login_required
def permission_error(request):
    return HttpResponse("You don't have right permission to access this page.")


def user_is_verified(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.approval_status == ProfileApprovalStatusEnum.approved.value or user.approval_status == 'a'


def user_is_student(user):
    if not user or not user.is_authenticated or not user_is_verified(user):
        return False
    role = (getattr(user, 'requested_role', '') or '').strip().upper()
    return role == 'STUDENT' or getattr(user, 'requested_role', '') == AccountTypesEnum.student.value


def user_is_teacher(user):
    if not user or not user.is_authenticated or not user_is_verified(user):
        return False
    role = (getattr(user, 'requested_role', '') or '').strip().upper()
    return role == 'TEACHER' or getattr(user, 'requested_role', '') == AccountTypesEnum.teacher.value


def user_is_parent(user):
    if not user or not user.is_authenticated or not user_is_verified(user):
        return False
    role = (getattr(user, 'requested_role', '') or '').strip().upper()
    return role == 'PARENT'


def can_access_dashboard(user: User):
    """
    Checks if a user is authorized to access the Admin ERP Dashboard.
    Self-service portal users (Student, Parent, Teacher) and Subscribers
    must NEVER be granted Admin ERP dashboard access.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.approval_status not in [ProfileApprovalStatusEnum.approved.value, 'a', 'approved']:
        return False

    role = (getattr(user, 'requested_role', '') or '').strip().upper()
    portal_and_restricted_roles = {
        'STUDENT', 'PARENT', 'TEACHER', 'SUBSCRIBER',
        AccountTypesEnum.student.value.upper(),
        AccountTypesEnum.teacher.value.upper(),
        AccountTypesEnum.subscriber.value.upper(),
    }
    if role in portal_and_restricted_roles:
        return False

    return True
