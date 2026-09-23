"""
Role definitions and portal resolution for PrimeSoul School ERP.
Simplified into exactly THREE canonical product roles:
1. SCHOOL_ADMIN (Full-control school operator)
2. STUDENT (Student & Family / Guardian access)
3. TEACHER (Teacher / Faculty workflow)

And exactly THREE canonical portal destinations:
1. ADMIN_PORTAL (/dashboard/)
2. STUDENT_PORTAL (/portal/student/)
3. TEACHER_PORTAL (/portal/teacher/)
"""
from django.contrib.auth.models import Group


class Role:
    SCHOOL_ADMIN = 'SCHOOL_ADMIN'
    STUDENT = 'STUDENT'
    TEACHER = 'TEACHER'

    CHOICES = (
        (SCHOOL_ADMIN, 'School Admin'),
        (STUDENT, 'Student'),
        (TEACHER, 'Teacher'),
    )

    ALL_ROLES = [
        SCHOOL_ADMIN,
        STUDENT,
        TEACHER,
    ]

    # Aliases for code-level backward compatibility
    ADMIN = SCHOOL_ADMIN
    PLATFORM_SUPER_ADMIN = SCHOOL_ADMIN
    PRINCIPAL = SCHOOL_ADMIN
    VICE_PRINCIPAL = SCHOOL_ADMIN
    ACADEMIC_COORDINATOR = SCHOOL_ADMIN
    ACCOUNTANT = SCHOOL_ADMIN
    RECEPTIONIST = SCHOOL_ADMIN
    TRANSPORT_MANAGER = SCHOOL_ADMIN
    LIBRARIAN = SCHOOL_ADMIN
    PARENT = STUDENT
    GUARDIAN = STUDENT


class PortalType:
    ADMIN_PORTAL = 'ADMIN_PORTAL'
    STUDENT_PORTAL = 'STUDENT_PORTAL'
    TEACHER_PORTAL = 'TEACHER_PORTAL'


def normalize_role_name(role_name: str) -> str:
    """Maps any legacy role variant to the canonical 3 product roles."""
    if not role_name:
        return Role.SCHOOL_ADMIN
    r = str(role_name).strip().upper()
    if r in ('STUDENT', 'PARENT', 'GUARDIAN'):
        return Role.STUDENT
    if r in ('TEACHER', 'FACULTY'):
        return Role.TEACHER
    return Role.SCHOOL_ADMIN


def get_user_portal(user) -> str:
    """
    Centralized canonical portal resolver for any authenticated user:
    - SCHOOL_ADMIN (and superuser / staff) -> ADMIN_PORTAL (/dashboard/)
    - STUDENT (including family / guardian access) -> STUDENT_PORTAL (/portal/student/)
    - TEACHER -> TEACHER_PORTAL (/portal/teacher/)
    """
    if not user or not user.is_authenticated:
        return PortalType.ADMIN_PORTAL
    if user.is_superuser:
        return PortalType.ADMIN_PORTAL

    role = normalize_role_name(getattr(user, 'requested_role', ''))
    if role == Role.STUDENT:
        return PortalType.STUDENT_PORTAL
    elif role == Role.TEACHER:
        return PortalType.TEACHER_PORTAL

    return PortalType.ADMIN_PORTAL


def ensure_system_roles_exist():
    """
    Creates standard Django Groups corresponding to the 3 canonical PrimeSoul roles.
    """
    for role_name in Role.ALL_ROLES:
        Group.objects.get_or_create(name=role_name)


def assign_role_to_user(user, role_name: str) -> None:
    """
    Assigns a canonical role to a User by updating their group membership and requested_role field.
    """
    canonical_role = normalize_role_name(role_name)
    group, _ = Group.objects.get_or_create(name=canonical_role)
    user.groups.clear()
    user.groups.add(group)
    user.requested_role = canonical_role
    if canonical_role == Role.SCHOOL_ADMIN:
        user.is_staff = True
    else:
        user.is_staff = False
    user.save(update_fields=['requested_role', 'is_staff'] if user.pk else None)


def user_has_role(user, *role_names: str) -> bool:
    """
    Checks if an authenticated user belongs to any of the specified roles.
    Automatically normalizes roles to the 3 canonical roles.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_role = (getattr(user, 'requested_role', '') or '').strip().upper()
    user_canonical = normalize_role_name(user_role)

    for r in role_names:
        if not r:
            continue
        req_canonical = normalize_role_name(str(r))
        if user_canonical == req_canonical or user_role == str(r).strip().upper():
            return True

    return user.groups.filter(name__in=[normalize_role_name(str(r)) for r in role_names]).exists()

