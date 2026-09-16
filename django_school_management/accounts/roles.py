"""
Role definitions and permission mappings for PrimeSoul School ERP.
Defines all 12 system roles and their default permissions.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Role:
    PLATFORM_SUPER_ADMIN = 'PLATFORM_SUPER_ADMIN'
    SCHOOL_ADMIN = 'SCHOOL_ADMIN'
    PRINCIPAL = 'PRINCIPAL'
    VICE_PRINCIPAL = 'VICE_PRINCIPAL'
    ACADEMIC_COORDINATOR = 'ACADEMIC_COORDINATOR'
    TEACHER = 'TEACHER'
    ACCOUNTANT = 'ACCOUNTANT'
    RECEPTIONIST = 'RECEPTIONIST'
    TRANSPORT_MANAGER = 'TRANSPORT_MANAGER'
    LIBRARIAN = 'LIBRARIAN'
    STUDENT = 'STUDENT'
    PARENT = 'PARENT'

    CHOICES = (
        (PLATFORM_SUPER_ADMIN, 'Platform Super Admin'),
        (SCHOOL_ADMIN, 'School Admin'),
        (PRINCIPAL, 'Principal'),
        (VICE_PRINCIPAL, 'Vice Principal'),
        (ACADEMIC_COORDINATOR, 'Academic Coordinator'),
        (TEACHER, 'Teacher'),
        (ACCOUNTANT, 'Accountant'),
        (RECEPTIONIST, 'Receptionist'),
        (TRANSPORT_MANAGER, 'Transport Manager'),
        (LIBRARIAN, 'Librarian'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent'),
    )

    ALL_ROLES = [
        PLATFORM_SUPER_ADMIN,
        SCHOOL_ADMIN,
        PRINCIPAL,
        VICE_PRINCIPAL,
        ACADEMIC_COORDINATOR,
        TEACHER,
        ACCOUNTANT,
        RECEPTIONIST,
        TRANSPORT_MANAGER,
        LIBRARIAN,
        STUDENT,
        PARENT,
    ]


def ensure_system_roles_exist():
    """
    Creates standard Django Groups corresponding to the 12 PrimeSoul roles if they do not exist.
    """
    for role_name in Role.ALL_ROLES:
        Group.objects.get_or_create(name=role_name)


def assign_role_to_user(user, role_name: str) -> None:
    """
    Assigns a role to a User by updating their group membership and requested_role field.
    """
    if role_name not in Role.ALL_ROLES:
        raise ValueError(f"Invalid role: {role_name}")
    
    group, _ = Group.objects.get_or_create(name=role_name)
    user.groups.clear()
    user.groups.add(group)
    user.requested_role = role_name
    if role_name in (Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN):
        user.is_staff = True
    user.save(update_fields=['requested_role', 'is_staff'] if user.pk else None)


def user_has_role(user, *role_names: str) -> bool:
    """
    Checks if an authenticated user belongs to any of the specified roles.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=role_names).exists() or user.requested_role in role_names
