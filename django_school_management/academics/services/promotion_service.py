"""
PrimeSoul ERP Academic Management - Safe Promotion Service
Implements controlled, atomic student promotion across Academic Years and Grade Levels.
"""
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django_school_management.core.audit import log_academic_event
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, StudentEnrollment
)
from django_school_management.students.models import Student


def execute_promotion(
    school,
    source_year: AcademicYear,
    target_year: AcademicYear,
    source_grade: GradeLevel,
    target_grade: GradeLevel,
    source_section: Optional[Section] = None,
    target_section: Optional[Section] = None,
    student_ids: Optional[List[int]] = None,
    actor=None
) -> Dict[str, Any]:
    """
    Executes student promotion from a source academic year/class to a target academic year/class.
    Guarantees:
    - Atomicity via transaction.atomic()
    - Historical enrollments are preserved and marked 'PROMOTED'
    - New 'ACTIVE' enrollment created for target academic year
    - Duplicate promotion prevention
    - Student model current placement pointer synchronized
    - Full audit logging
    """
    # Tenant verification
    if (source_year.school != school or target_year.school != school or
            source_grade.school != school or target_grade.school != school):
        raise ValidationError("All academic years and grades must belong to this school tenant.")

    if source_section and source_section.school != school:
        raise ValidationError("Source section does not belong to this school tenant.")

    if target_section and target_section.school != school:
        raise ValidationError("Target section does not belong to this school tenant.")

    if target_section and target_section.grade_level != target_grade:
        raise ValidationError(f"Target section '{target_section.name}' does not belong to target class '{target_grade.name}'.")

    if source_year == target_year and source_grade == target_grade and source_section == target_section:
        raise ValidationError("Source and target academic placement cannot be identical.")

    with transaction.atomic():
        # Fetch eligible source enrollments
        source_qs = StudentEnrollment.objects.filter(
            school=school,
            academic_year=source_year,
            grade_level=source_grade,
            status=StudentEnrollment.STATUS_ACTIVE
        ).select_related('student', 'section')

        if source_section:
            source_qs = source_qs.filter(section=source_section)

        if student_ids:
            source_qs = source_qs.filter(student_id__in=student_ids)

        promoted_count = 0
        skipped = []

        for enrollment in source_qs:
            student = enrollment.student

            # Check if student already enrolled in target academic year
            existing_target = StudentEnrollment.objects.filter(
                school=school,
                student=student,
                academic_year=target_year
            ).first()

            if existing_target:
                skipped.append({
                    'student_id': student.pk,
                    'student_name': student.name,
                    'reason': f"Already enrolled in {existing_target.grade_level.name} for {target_year.name}"
                })
                continue

            # Update source enrollment status to PROMOTED
            enrollment.status = StudentEnrollment.STATUS_PROMOTED
            enrollment.notes = f"{enrollment.notes} | Promoted to {target_grade.name} ({target_year.name})".strip(" |")
            enrollment.save(update_fields=['status', 'notes'])

            # Create new target enrollment
            new_enrollment = StudentEnrollment.objects.create(
                school=school,
                student=student,
                academic_year=target_year,
                grade_level=target_grade,
                section=target_section,
                roll_number=enrollment.roll_number,
                status=StudentEnrollment.STATUS_ACTIVE,
                notes=f"Promoted from {source_grade.name} ({source_year.name})",
                created_by=actor
            )

            # Update student record current pointer if target is current or future year
            student.academic_year = target_year
            student.grade_level = target_grade
            student.section = target_section
            student.save(update_fields=['academic_year', 'grade_level', 'section'])

            promoted_count += 1

        log_academic_event(
            actor=actor,
            school=school,
            action='EXECUTE_PROMOTION',
            resource='StudentEnrollment',
            details={
                'source_year': source_year.name,
                'target_year': target_year.name,
                'source_grade': source_grade.name,
                'target_grade': target_grade.name,
                'promoted_count': promoted_count,
                'skipped_count': len(skipped)
            }
        )

        return {
            'success': True,
            'promoted_count': promoted_count,
            'skipped_count': len(skipped),
            'skipped_students': skipped,
            'failed': skipped,
            'target_year': target_year.name,
            'target_grade': target_grade.name
        }
