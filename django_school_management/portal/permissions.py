"""
PrimeSoul Unified Portal - Permissions, Context Resolvers & IDOR Guards
Ensures strict multi-tenant and role-based data isolation for Student/Family and Teacher portals.
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
    return School.objects.filter(is_active=True).first()


def resolve_student_placement(student: Optional[Student], school: Optional[School] = None) -> Optional[Student]:
    """Ensures student has grade_level, section, academic_year and roll_number resolved from active enrollment if not directly set."""
    if not student:
        return None
    if not (student.grade_level and student.section and student.academic_year and student.roll_number):
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
        return []

    guardian = get_parent_profile(user, school)
    if not guardian:
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
    Resolves and validates the active child for a parent/guardian portal session.
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


def get_student_for_user(user, school: Optional[School] = None, request=None) -> Optional[Student]:
    """Resolves the active Student record belonging to the authenticated student or guardian user."""
    if not user or not user.is_authenticated:
        return None

    # 1. Direct Student user lookup
    st = getattr(user, 'student_profile', None)
    if st:
        if school and st.school and st.school.id != school.id:
            return None
        return resolve_student_placement(st, school)

    qs = Student.objects.filter(user=user)
    if school:
        qs = qs.filter(school=school)
    student = qs.select_related('grade_level', 'section', 'academic_year', 'school').first()
    if student:
        return resolve_student_placement(student, school)

    # 2. Guardian / Parent user access
    if request:
        return get_parent_selected_child(request, school)
    children = get_parent_children(user, school)
    return children[0] if children else None


def get_teacher_for_user(user, school: Optional[School] = None):
    """Resolves Teacher or TeacherProfile instance for the authenticated faculty user."""
    if not user or not user.is_authenticated:
        return None

    # 1. Direct Teacher record
    tr = getattr(user, 'teacher_record', None)
    if tr:
        if school and tr.school and tr.school.id != school.id:
            return None
        return tr

    qs_t = Teacher.objects.filter(user=user)
    if school:
        qs_t = qs_t.filter(school=school)
    tr_obj = qs_t.select_related('designation', 'school').first()
    if tr_obj:
        return tr_obj

    # 2. TeacherProfile record
    tp = getattr(user, 'teacher_profile', None)
    if tp:
        if school and tp.school and tp.school.id != school.id:
            return None
        return tp

    qs_tp = TeacherProfile.objects.filter(user=user)
    if school:
        qs_tp = qs_tp.filter(school=school)
    tp_obj = qs_tp.select_related('designation', 'school').first()
    if tp_obj:
        return tp_obj

    # 3. Fallback matching by email
    if user.email:
        legacy = Teacher.objects.filter(email__iexact=user.email.strip())
        if school:
            legacy = legacy.filter(school=school)
        if legacy.exists():
            return legacy.first()

    return None


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

def student_portal_required(view_func):
    """Restricts access to authenticated students, family guardians, or school administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if (
            user_has_role(request.user, Role.STUDENT, Role.PARENT) or
            get_student_for_user(request.user) or
            get_parent_profile(request.user) or
            bool(get_parent_children(request.user)) or
            request.user.is_superuser or
            user_has_role(request.user, Role.SCHOOL_ADMIN)
        ):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Students and Family Guardians.")
        return redirect('portal:portal_root')
    return _wrapped_view


def teacher_portal_required(view_func):
    """Restricts access to authenticated teachers/faculty or school administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if (
            user_has_role(request.user, Role.TEACHER) or
            get_teacher_for_user(request.user) or
            get_employee_for_user(request.user) or
            request.user.is_superuser or
            user_has_role(request.user, Role.SCHOOL_ADMIN)
        ):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Faculty & Staff.")
        return redirect('portal:portal_root')
    return _wrapped_view


# Backward compatibility alias
parent_portal_required = student_portal_required


# ─────────────────────────────────────────────────────────────
# DRF PERMISSION CLASSES
# ─────────────────────────────────────────────────────────────

class IsPortalStudent(permissions.BasePermission):
    """DRF permission: Authenticated Student or Family Guardian."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            user_has_role(request.user, Role.STUDENT, Role.PARENT) or
            get_student_for_user(request.user) is not None or
            get_parent_profile(request.user) is not None or
            request.user.is_superuser
        )


class IsPortalParent(IsPortalStudent):
    """DRF permission alias: Authenticated Guardian/Parent."""
    pass


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
