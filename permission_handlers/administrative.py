"""
Handling permissions for administrators who are assigned to handle everything.
Admins have direct role after superuser.
UserTypes: Admin, SuperAdmin
"""
from .editor import (
    user_is_editor,
    user_is_academic_officer,
    user_is_editor_or_ac_officer
)
from .basic import user_is_verified, user_is_teacher, user_is_student

def user_is_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user_is_verified(user):
        return False
    role = (getattr(user, 'requested_role', '') or '').strip().upper()
    admin_roles = {
        'ADMIN', 'SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN', 'PRINCIPAL',
        'VICE_PRINCIPAL', 'ACADEMIC_COORDINATOR', 'ACCOUNTANT',
        'RECEPTIONIST', 'TRANSPORT_MANAGER', 'LIBRARIAN'
    }
    return role in admin_roles or getattr(user, 'requested_role', '') == 'admin'

def user_is_superuser(user):
    return user.is_superuser if user.is_authenticated else False

def user_is_admin_or_su(user):
    return user.is_superuser or user_is_admin(user)

def user_is_admin_su_or_ac_officer(user):
    return user_is_admin_or_su(user) or user_is_academic_officer(user) \
        if user.is_authenticated else False

def user_editor_admin_or_su(user):
    return user_is_admin_or_su(user) or user_is_editor(user) \
        if user.is_authenticated else False

def user_is_admin_su_editor_or_ac_officer(user):
    return user_is_admin_or_su(user) or user_is_editor_or_ac_officer(user) \
        if user.is_authenticated else False

def user_is_teacher_or_administrative(user):
    """ administrative user refers to: superuser, 
    editor, admin, academic-officer.
    """
    return user_is_admin_su_editor_or_ac_officer(user) or user_is_teacher(user) \
        if user.is_authenticated else False

def user_is_student_or_administrative(user):
    """ administrative user refers to: superuser, 
    editor, admin, academic-officer.
    """
    return user_is_admin_su_editor_or_ac_officer(user) or user_is_student(user) \
        if user.is_authenticated else False
