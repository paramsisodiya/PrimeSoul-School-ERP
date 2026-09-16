from rest_framework import permissions
from django_school_management.accounts.roles import Role, user_has_role


def check_roles(user, allowed_roles: list) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    req_role = getattr(user, 'requested_role', None)
    if req_role in allowed_roles:
        return True
    for r in allowed_roles:
        if user_has_role(user, r):
            return True
    return False


class IsSchoolAdminOrAccountant(permissions.BasePermission):
    """
    Allows access to School Admins, Principals, and Accountants.
    """
    def has_permission(self, request, view):
        return check_roles(request.user, [
            Role.SCHOOL_ADMIN,
            Role.PRINCIPAL,
            Role.ACCOUNTANT,
        ])


class CanManageFeeStructures(permissions.BasePermission):
    """
    Only School Admins and Accountants can create/update/delete fee structures & heads.
    Read access permitted to Principal and Receptionist.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.method in permissions.SAFE_METHODS:
            return check_roles(request.user, [
                Role.SCHOOL_ADMIN,
                Role.PRINCIPAL,
                Role.ACCOUNTANT,
                Role.RECEPTIONIST
            ])
        return check_roles(request.user, [
            Role.SCHOOL_ADMIN,
            Role.ACCOUNTANT
        ])


class CanCollectPayments(permissions.BasePermission):
    """
    Allows School Admins, Accountants, and Receptionists to record offline collections.
    """
    def has_permission(self, request, view):
        return check_roles(request.user, [
            Role.SCHOOL_ADMIN,
            Role.PRINCIPAL,
            Role.ACCOUNTANT,
            Role.RECEPTIONIST
        ])


class CanApproveConcessions(permissions.BasePermission):
    """
    Allows School Admin and Principal to approve concessions.
    """
    def has_permission(self, request, view):
        return check_roles(request.user, [
            Role.SCHOOL_ADMIN,
            Role.PRINCIPAL
        ])


class StudentOrParentFeeAccess(permissions.BasePermission):
    """
    Ensures students/parents can only read their own financial records.
    Teachers are explicitly rejected from financial modifications.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Teachers are explicitly denied financial modification or dues access
        if check_roles(request.user, [Role.TEACHER]) and not check_roles(request.user, [Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.ACCOUNTANT]):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if check_roles(request.user, [Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.ACCOUNTANT, Role.RECEPTIONIST]):
            school = getattr(obj, 'school', None) or getattr(getattr(obj, 'student', None), 'school', None)
            return school == request.user.school

        # Parent access
        if check_roles(request.user, [Role.PARENT]):
            student = getattr(obj, 'student', None) or (obj if hasattr(obj, 'guardian_relationships') else None)
            if student and hasattr(student, 'guardian_relationships'):
                return student.guardian_relationships.filter(guardian__user=request.user).exists()
            return False

        # Student access
        if check_roles(request.user, [Role.STUDENT]):
            student = getattr(obj, 'student', None) or obj
            return getattr(student, 'user', None) == request.user

        return False
