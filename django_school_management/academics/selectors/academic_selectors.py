"""
PrimeSoul ERP Academic Management - High-Performance Selectors
Optimized database queries with prefetching and aggregations for dashboard, lists, and filters.
"""
from typing import Dict, Any, Optional
from django.db.models import Count, Q
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject,
    SubjectAssignment, StudentEnrollment
)
from django_school_management.teachers.models import Teacher


def get_academic_dashboard_metrics(school) -> Dict[str, Any]:
    """
    Computes all KPI stats required by the PrimeSoul Academic Dashboard.
    Single-school isolated. Avoids N+1 queries.
    """
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    if not current_year:
        current_year = AcademicYear.objects.filter(school=school).order_by('-start_date').first()

    total_classes = GradeLevel.objects.filter(school=school, is_active=True).count()
    total_sections = Section.objects.filter(school=school, is_active=True).count()
    total_subjects = Subject.objects.filter(school=school, is_active=True).count()
    total_teachers = Teacher.objects.filter(school=school).count()

    enrolled_qs = StudentEnrollment.objects.filter(school=school, status=StudentEnrollment.STATUS_ACTIVE)
    if current_year:
        enrolled_qs = enrolled_qs.filter(academic_year=current_year)

    total_enrolled_students = enrolled_qs.count()
    students_without_section = enrolled_qs.filter(section__isnull=True).count()
    sections_without_class_teacher = Section.objects.filter(
        school=school, is_active=True, class_teacher__isnull=True
    ).count()

    assignment_qs = SubjectAssignment.objects.filter(school=school, is_active=True)
    if current_year:
        assignment_qs = assignment_qs.filter(academic_year=current_year)
    subjects_without_teacher = assignment_qs.filter(teacher__isnull=True).count()

    recent_enrollments = (
        enrolled_qs
        .select_related('student', 'grade_level', 'section', 'academic_year')
        .order_by('-created')[:6]
    )

    recent_assignments = (
        assignment_qs
        .select_related('academic_year', 'grade_level', 'section', 'subject', 'teacher')
        .order_by('-created')[:6]
    )

    return {
        'current_year': current_year,
        'total_classes': total_classes,
        'total_sections': total_sections,
        'total_subjects': total_subjects,
        'total_teachers': total_teachers,
        'total_enrolled_students': total_enrolled_students,
        'students_without_section': students_without_section,
        'sections_without_class_teacher': sections_without_class_teacher,
        'subjects_without_teacher': subjects_without_teacher,
        'recent_enrollments': recent_enrollments,
        'recent_assignments': recent_assignments,
    }


def get_academic_years_list(school, query: Optional[str] = None, status_filter: Optional[str] = None):
    qs = AcademicYear.objects.filter(school=school).order_by('-start_date')
    if query:
        qs = qs.filter(name__icontains=query.strip())
    if status_filter:
        qs = qs.filter(status=status_filter)
    return qs


def get_classes_list(school, query: Optional[str] = None, board_filter: Optional[str] = None, active_only: bool = False):
    qs = GradeLevel.objects.filter(school=school).order_by('display_order', 'code')
    if active_only:
        qs = qs.filter(is_active=True)
    if query:
        qs = qs.filter(Q(name__icontains=query.strip()) | Q(code__icontains=query.strip()))
    if board_filter:
        qs = qs.filter(board=board_filter)
    return qs.annotate(section_count=Count('sections', filter=Q(sections__is_active=True)))


def get_sections_list(school, year: Optional[AcademicYear] = None, grade_id: Optional[int] = None, active_only: bool = False):
    qs = Section.objects.filter(school=school).select_related('grade_level', 'academic_year', 'class_teacher')
    if active_only:
        qs = qs.filter(is_active=True)
    if year:
        qs = qs.filter(Q(academic_year=year) | Q(academic_year__isnull=True))
    if grade_id:
        qs = qs.filter(grade_level_id=grade_id)
    return qs.order_by('grade_level__display_order', 'name')


def get_subjects_list(school, query: Optional[str] = None, type_filter: Optional[str] = None, active_only: bool = False):
    qs = Subject.objects.filter(school=school).select_related('instructor').order_by('name')
    if active_only:
        qs = qs.filter(is_active=True)
    if query:
        qs = qs.filter(Q(name__icontains=query.strip()) | Q(code__icontains=query.strip()))
    if type_filter:
        qs = qs.filter(subject_type=type_filter)
    return qs


def get_subject_assignments_list(school, year=None, grade_id=None, section_id=None, teacher_id=None):
    qs = (
        SubjectAssignment.objects.filter(school=school)
        .select_related('academic_year', 'grade_level', 'section', 'subject', 'teacher')
        .order_by('grade_level__display_order', 'section__name', 'subject__name')
    )
    if year:
        qs = qs.filter(academic_year=year)
    if grade_id:
        qs = qs.filter(grade_level_id=grade_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if teacher_id:
        qs = qs.filter(teacher_id=teacher_id)
    return qs


def get_student_enrollments_list(school, year=None, grade_id=None, section_id=None, status_filter=None, query=None):
    qs = (
        StudentEnrollment.objects.filter(school=school)
        .select_related('student', 'academic_year', 'grade_level', 'section')
        .order_by('grade_level__display_order', 'section__name', 'roll_number')
    )
    if year:
        qs = qs.filter(academic_year=year)
    if grade_id:
        qs = qs.filter(grade_level_id=grade_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if query:
        qs = qs.filter(
            Q(student__first_name__icontains=query.strip()) |
            Q(student__last_name__icontains=query.strip()) |
            Q(student__admission_number__icontains=query.strip()) |
            Q(roll_number__icontains=query.strip())
        )
    return qs
