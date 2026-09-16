"""
PrimeSoul Unified Portal - Permissions, Context Resolvers & IDOR Guards
Ensures strict multi-tenant and role-based data isolation for Parent, Student, and Teacher portals.
"""
from functools import wraps
from typing import Optional, List
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.teachers.models import Teacher, TeacherProfile
from django_school_management.hr.models import Employee
from django_school_management.tenants.models import School


def resolve_portal_school(request) -> Optional[School]:
    """Safely extracts tenant School from request context or user attributes."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated:
        user_school = getattr(request.user, 'school', None)
        if user_school:
            return user_school
    return School.objects.first()


def resolve_student_placement(student: Optional[Student], school: Optional[School] = None) -> Optional[Student]:
    """Ensures student has grade_level, section, academic_year and roll_number resolved from active enrollment if not directly set."""
    if not student:
        return None
    if not student.grade_level or not student.section or not student.academic_year:
        from django_school_management.academics.models import StudentEnrollment
        qs = StudentEnrollment.objects.filter(student=student, status='ACTIVE')
        if school:
            qs = qs.filter(school=school)
        enrollment = qs.select_related('grade_level', 'section', 'academic_year').first()
        if enrollment:
            if not student.grade_level:
                student.grade_level = enrollment.grade_level
            if not student.section:
                student.section = enrollment.section
            if not student.academic_year:
                student.academic_year = enrollment.academic_year
            if not student.roll_number:
                student.roll_number = enrollment.roll_number
    return student


def get_parent_profile(user, school: Optional[School] = None) -> Optional[ParentProfile]:
    """Finds ParentProfile associated with the given user."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'parent_profile', None)
    if profile:
        return profile
    qs = ParentProfile.objects.filter(user=user)
    if school:
        school_profile = qs.filter(school=school).first()
        if school_profile:
            return school_profile
    return qs.first()


def get_parent_children(user, school: Optional[School] = None):
    """
    Returns a QuerySet/List of all Students legitimately linked to the authenticated Parent user.
    Enforces strict guardian relationship verification and consistent ordering.
    """
    if not user or not user.is_authenticated:
        return Student.objects.none()

    guardian = get_parent_profile(user, school)
    if not guardian:
        # Check if parent user has direct relationship without ParentProfile model
        qs = Student.objects.filter(guardian_relationships__guardian__user=user)
    else:
        qs = Student.objects.filter(guardian_relationships__guardian=guardian)

    if school:
        qs = qs.filter(school=school)

    students = list(qs.select_related('grade_level', 'section', 'academic_year', 'school').distinct().order_by('id'))
    for s in students:
        resolve_student_placement(s, school)
    return students


def get_parent_selected_child(request, school: Optional[School] = None, student_id: Optional[int] = None) -> Optional[Student]:
    """
    Resolves and validates the active child for a parent portal session.
    Server-side validation ensures IDOR prevention (cannot access other parents' children).
    """
    allowed_children = get_parent_children(request.user, school)
    if not allowed_children:
        return None

    allowed_map = {c.id: c for c in allowed_children}

    has_session = hasattr(request, 'session') and request.session is not None

    # 1. If an explicit student_id is requested, validate it strictly
    if student_id:
        try:
            sid = int(student_id)
            if sid in allowed_map:
                if has_session:
                    request.session['portal_selected_student_id'] = sid
                return allowed_map[sid]
            else:
                # Potential IDOR attempt or invalid child ID: Fallback safely to first child
                pass
        except (ValueError, TypeError):
            pass

    # 2. Check session
    if has_session:
        session_id = request.session.get('portal_selected_student_id')
        if session_id and session_id in allowed_map:
            return allowed_map[session_id]

    # 3. Default to the first child
    default_child = allowed_children[0]
    if has_session:
        request.session['portal_selected_student_id'] = default_child.id
    return default_child


def get_student_for_user(user, school: Optional[School] = None) -> Optional[Student]:
    """Resolves the Student record belonging to the authenticated student user."""
    if not user or not user.is_authenticated:
        return None
    st = getattr(user, 'student_profile', None)
    if st:
        if school and st.school and st.school.id != school.id:
            return None
        return resolve_student_placement(st, school)
    qs = Student.objects.filter(user=user)
    if school:
        qs = qs.filter(school=school)
    student = qs.select_related('grade_level', 'section', 'academic_year', 'school').first()
    return resolve_student_placement(student, school)


def get_teacher_for_user(user, school: Optional[School] = None) -> Optional[Teacher]:
    """Resolves Teacher instance for the authenticated faculty user."""
    if not user or not user.is_authenticated:
        return None
    # Check TeacherProfile
    tp = getattr(user, 'teacher_profile', None)
    if tp:
        legacy = Teacher.objects.filter(school=school, email=user.email).first() or Teacher.objects.filter(email=user.email).first()
        if legacy:
            return legacy
    return Teacher.objects.filter(school=school, email=user.email).first() or Teacher.objects.filter(email=user.email).first()


def get_employee_for_user(user, school: Optional[School] = None) -> Optional[Employee]:
    """Resolves HR Employee profile for the authenticated employee/teacher."""
    if not user or not user.is_authenticated:
        return None
    qs = Employee.objects.filter(user=user)
    if school:
        emp = qs.filter(school=school).first()
        if emp:
            return emp
    return qs.first()


# ─────────────────────────────────────────────────────────────
# VIEW DECORATORS
# ─────────────────────────────────────────────────────────────

def parent_portal_required(view_func):
    """Restricts access to authenticated parents or system administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if (
            user_has_role(request.user, Role.PARENT) or
            get_parent_profile(request.user) or
            bool(get_parent_children(request.user)) or
            request.user.is_superuser or
            user_has_role(request.user, Role.SCHOOL_ADMIN, Role.PRINCIPAL)
        ):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Parents.")
        return redirect('portal:portal_root')
    return _wrapped_view


def student_portal_required(view_func):
    """Restricts access to authenticated students or system administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if (
            user_has_role(request.user, Role.STUDENT) or
            get_student_for_user(request.user) or
            request.user.is_superuser or
            user_has_role(request.user, Role.SCHOOL_ADMIN, Role.PRINCIPAL)
        ):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Students.")
        return redirect('portal:portal_root')
    return _wrapped_view


def teacher_portal_required(view_func):
    """Restricts access to authenticated teachers/faculty or system administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if (
            user_has_role(request.user, Role.TEACHER) or
            get_teacher_for_user(request.user) or
            get_employee_for_user(request.user) or
            request.user.is_superuser or
            user_has_role(request.user, Role.SCHOOL_ADMIN, Role.PRINCIPAL)
        ):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Faculty & Staff.")
        return redirect('portal:portal_root')
    return _wrapped_view


# ─────────────────────────────────────────────────────────────
# DRF PERMISSION CLASSES
# ─────────────────────────────────────────────────────────────

class IsPortalParent(permissions.BasePermission):
    """DRF permission: Authenticated Parent."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            user_has_role(request.user, Role.PARENT) or
            get_parent_profile(request.user) is not None or
            bool(get_parent_children(request.user)) or
            request.user.is_superuser
        )


class IsPortalStudent(permissions.BasePermission):
    """DRF permission: Authenticated Student."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            user_has_role(request.user, Role.STUDENT) or
            get_student_for_user(request.user) is not None or
            request.user.is_superuser
        )


class IsPortalTeacher(permissions.BasePermission):
    """DRF permission: Authenticated Teacher/Faculty."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            user_has_role(request.user, Role.TEACHER) or
            get_teacher_for_user(request.user) is not None or
            get_employee_for_user(request.user) is not None or
            request.user.is_superuser
        )
