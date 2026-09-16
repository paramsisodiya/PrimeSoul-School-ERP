import logging
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.teachers.models import Teacher
from django_school_management.academics.models import (
    SubjectAssignment, ClassTeacherAssignment, Section
)
from django_school_management.core.audit import log_examination_event
from django_school_management.examinations.models import (
    ExaminationSession, Exam, ExamSubject
)

logger = logging.getLogger(__name__)


def get_teacher_for_user(user, school=None):
    """Safely retrieves the Teacher record associated with a user in a given school tenant."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'teacher_profile', None)
    if profile:
        legacy = Teacher.objects.filter(school=school, email=user.email).first() or Teacher.objects.filter(email=user.email).first()
        if legacy:
            return legacy
    return Teacher.objects.filter(school=school, email=user.email).first() or Teacher.objects.filter(email=user.email).first()


def can_user_enter_marks(user, school, exam, exam_subject=None, section=None) -> bool:
    """
    Evaluates whether a user is authorized to enter or modify marks for an Exam,
    ExamSubject, and Section within the given school tenant.
    
    Rules:
    - Superusers, School Admins, and Principals have full authorization across all classes/subjects.
    - Teachers can enter marks ONLY for:
        1. Sections where they are currently assigned as Class Teacher.
        2. Subjects and sections where they are assigned as Subject Teacher via SubjectAssignment.
    - All other roles (Accountants, Receptionists, Students, Parents) are strictly denied.
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user_has_role(user, Role.SCHOOL_ADMIN) or user_has_role(user, Role.PRINCIPAL):
        user_school = getattr(user, 'school', None)
        return bool(user_school == school or user.is_superuser)

    if not user_has_role(user, Role.TEACHER):
        return False

    teacher = get_teacher_for_user(user, school)
    if not teacher:
        return False

    # Target section
    target_section = section or exam.section

    # 1. Check Class Teacher assignment if section is known
    if target_section:
        if target_section.class_teacher == teacher:
            return True
        is_class_teacher = ClassTeacherAssignment.objects.filter(
            school=school,
            academic_year=exam.academic_year,
            section=target_section,
            teacher=teacher,
            is_active=True
        ).exists()
        if is_class_teacher:
            return True

    # 2. Check Subject Assignment
    subj_filter = {
        'school': school,
        'academic_year': exam.academic_year,
        'grade_level': exam.grade_level,
        'teacher': teacher,
    }
    if exam_subject:
        subj_filter['subject'] = exam_subject.subject
    if target_section:
        # Match specific section or assignment to entire grade level (section=None)
        has_assignment = SubjectAssignment.objects.filter(
            **subj_filter
        ).filter(models_q_section(target_section)).exists()
        if has_assignment:
            return True
    else:
        if SubjectAssignment.objects.filter(**subj_filter).exists():
            return True

    return False


def models_q_section(target_section):
    from django.db.models import Q
    return Q(section=target_section) | Q(section__isnull=True)


def can_user_manage_exam(user, school) -> bool:
    """Checks if user can create/edit sessions, exams, grade scales, or finalize/publish results."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user_has_role(user, Role.SCHOOL_ADMIN) or user_has_role(user, Role.PRINCIPAL):
        user_school = getattr(user, 'school', None)
        return bool(user_school == school)
    return False
