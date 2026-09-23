import datetime
from typing import List, Dict, Any, Optional
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from django_school_management.attendance.models import AttendanceRecord, AttendanceCorrectionLog
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, SubjectAssignment,
    ClassTeacherAssignment, StudentEnrollment
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher, TeacherProfile
from django_school_management.core.audit import log_attendance_event


def get_teacher_for_user(user, school=None):
    """
    Finds the Teacher / TeacherProfile instance associated with a user.
    """
    if not user or not user.is_authenticated:
        return None
    # Check direct TeacherProfile
    profile = getattr(user, 'teacher_profile', None)
    if profile:
        # Check matching legacy Teacher
        legacy_teacher = Teacher.objects.filter(email=user.email).first()
        if not legacy_teacher and school:
            legacy_teacher = Teacher.objects.filter(school=school, email=user.email).first()
        return legacy_teacher or profile

    # Check Teacher by email or user
    return Teacher.objects.filter(email=user.email).first()


def can_user_mark_section(user, school, section: Section) -> bool:
    """
    Evaluates whether the user is authorized to mark or edit attendance for a section.
    - SuperAdmins, School Admins, Principals, Vice Principals, Academic Coordinators:
      Authorized across all sections belonging to their school.
    - Teachers: Authorized ONLY for sections where they are assigned as Class Teacher
      or Subject Teacher.
    - Other roles (Accountant, Receptionist, Student, Parent): Denied.
    """
    if not user or not user.is_authenticated or not school or not section:
        return False

    if user.is_superuser or user_has_role(user, Role.PLATFORM_SUPER_ADMIN):
        return True

    # Validate school tenant matching
    user_school = getattr(user, 'school', None)
    if user_school and user_school.pk != school.pk:
        return False
    if section.school and section.school.pk != school.pk:
        return False

    # Administrative roles have full school access
    admin_roles = [
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.VICE_PRINCIPAL,
        Role.ACADEMIC_COORDINATOR,
    ]
    for r in admin_roles:
        if user_has_role(user, r):
            return True

    # Check Teacher role
    if user_has_role(user, Role.TEACHER):
        # 1. Check direct section.class_teacher
        teacher = get_teacher_for_user(user, school)
        if section.class_teacher and teacher and (
            section.class_teacher.pk == getattr(teacher, 'pk', None) or
            (section.class_teacher.email and section.class_teacher.email.lower() == user.email.lower())
        ):
            return True

        is_legacy_teacher = isinstance(teacher, Teacher)
        # 2. Check ClassTeacherAssignment
        if ClassTeacherAssignment.objects.filter(
            school=school, section=section, is_active=True
        ).filter(
            models.Q(teacher__email__iexact=user.email) |
            (models.Q(teacher=teacher) if is_legacy_teacher else models.Q(pk__in=[]))
        ).exists():
            return True

        # 3. Check SubjectAssignment for this section or grade level
        if SubjectAssignment.objects.filter(
            school=school, is_active=True
        ).filter(
            models.Q(section=section) | (models.Q(section__isnull=True) & models.Q(grade_level=section.grade_level))
        ).filter(
            models.Q(teacher__email__iexact=user.email) |
            (models.Q(teacher=teacher) if is_legacy_teacher else models.Q(pk__in=[]))
        ).exists():
            return True

        return False

    return False


def save_daily_attendance(
    school,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    section: Section,
    attendance_date: datetime.date,
    attendance_entries: List[Dict[str, Any]],
    actor,
    default_remarks: str = ""
) -> Dict[str, Any]:
    """
    Atomic operation to record daily student attendance for a class-section.
    - Validates tenant boundaries, section grade alignment, and actor permissions.
    - Automatically updates existing attendance records if already present, recording
      the change in AttendanceCorrectionLog when status is modified.
    - Validates that every student is legitimately enrolled in that class and section.
    """
    if not school:
        raise ValidationError("School tenant is required.")
    if not academic_year:
        raise ValidationError("Academic year is required.")
    if not grade_level or not section:
        raise ValidationError("Class and section are required.")
    if not attendance_date:
        raise ValidationError("Attendance date is required.")

    # Validate tenant alignment
    if academic_year.school and academic_year.school != school:
        raise ValidationError("Academic year does not belong to this school.")
    if grade_level.school and grade_level.school != school:
        raise ValidationError("Class does not belong to this school.")
    if section.school and section.school != school:
        raise ValidationError("Section does not belong to this school.")
    if section.grade_level != grade_level:
        raise ValidationError(f"Section {section.name} does not belong to Class {grade_level.name}.")

    # Validate actor authorization
    if not can_user_mark_section(actor, school, section):
        raise PermissionDenied("You do not have permission to mark attendance for this section.")

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for entry in attendance_entries:
            student_id = entry.get('student_id')
            raw_status = entry.get('status', AttendanceRecord.STATUS_PRESENT)
            status = raw_status.upper()
            remarks = entry.get('remarks', default_remarks).strip()
            correction_reason = entry.get('correction_reason', '').strip()

            valid_statuses = dict(AttendanceRecord.STATUS_CHOICES).keys()
            if status not in valid_statuses:
                raise ValidationError(f"Invalid attendance status '{status}'. Valid choices: {list(valid_statuses)}")

            try:
                student = Student.objects.get(id=student_id, school=school)
            except Student.DoesNotExist:
                raise ValidationError(f"Student with ID {student_id} not found in this school.")

            # Validate enrollment integrity: check StudentEnrollment or student's current assignment
            is_enrolled = StudentEnrollment.objects.filter(
                school=school,
                student=student,
                academic_year=academic_year,
                grade_level=grade_level
            ).filter(
                models.Q(section=section) | models.Q(section__isnull=True)
            ).exists()

            if not is_enrolled:
                # Fallback to direct student fields if StudentEnrollment was not yet created
                if student.grade_level != grade_level or (student.section and student.section != section):
                    raise ValidationError(
                        f"Student {student.name} is not enrolled in Class {grade_level.name} - Section {section.name} for {academic_year.name}."
                    )

            # Check existing record for that student on that date
            existing_record = AttendanceRecord.objects.select_for_update().filter(
                school=school,
                academic_year=academic_year,
                student=student,
                attendance_date=attendance_date
            ).first()

            if existing_record:
                if existing_record.status != status:
                    reason = correction_reason or remarks or f"Status updated from {existing_record.status} to {status} during attendance submission."
                    AttendanceCorrectionLog.objects.create(
                        attendance_record=existing_record,
                        school=school,
                        previous_status=existing_record.status,
                        new_status=status,
                        reason=reason,
                        corrected_by=actor
                    )
                    existing_record.status = status
                    existing_record.remarks = remarks or existing_record.remarks
                    existing_record.updated_by = actor
                    existing_record.grade_level = grade_level
                    existing_record.section = section
                    existing_record.save()
                    updated_count += 1
                else:
                    if remarks and remarks != existing_record.remarks:
                        existing_record.remarks = remarks
                        existing_record.updated_by = actor
                        existing_record.save(update_fields=['remarks', 'updated_by', 'updated_at'])
            else:
                AttendanceRecord.objects.create(
                    school=school,
                    academic_year=academic_year,
                    grade_level=grade_level,
                    section=section,
                    student=student,
                    attendance_date=attendance_date,
                    status=status,
                    remarks=remarks,
                    marked_by=actor
                )
                created_count += 1

        # Audit Event
        log_attendance_event(
            actor=actor,
            school=school,
            action='DAILY_ATTENDANCE_SAVED',
            resource='Section',
            resource_id=str(section.id),
            details={
                'academic_year': academic_year.name,
                'class': grade_level.name,
                'section': section.name,
                'date': str(attendance_date),
                'records_created': created_count,
                'records_updated': updated_count,
                'total_entries': len(attendance_entries)
            }
        )

    return {
        'created_count': created_count,
        'updated_count': updated_count,
        'total_processed': len(attendance_entries)
    }


def correct_attendance_record(
    record: AttendanceRecord,
    new_status: str,
    reason: str,
    actor
) -> AttendanceRecord:
    """
    Explicit correction of a single attendance record.
    Requires a non-empty justification reason and records change history.
    """
    if not reason or not reason.strip():
        raise ValidationError("A valid justification reason is mandatory for attendance corrections.")

    new_status = new_status.upper()
    valid_statuses = dict(AttendanceRecord.STATUS_CHOICES).keys()
    if new_status not in valid_statuses:
        raise ValidationError(f"Invalid attendance status '{new_status}'.")

    if not can_user_mark_section(actor, record.school, record.section):
        raise PermissionDenied("You do not have permission to modify attendance for this section.")

    prev_status = record.status
    if prev_status == new_status:
        return record

    with transaction.atomic():
        record.status = new_status
        record.updated_by = actor
        record.save(update_fields=['status', 'updated_by', 'updated_at'])

        AttendanceCorrectionLog.objects.create(
            attendance_record=record,
            school=record.school,
            previous_status=prev_status,
            new_status=new_status,
            reason=reason.strip(),
            corrected_by=actor
        )

        log_attendance_event(
            actor=actor,
            school=record.school,
            action='ATTENDANCE_CORRECTED',
            resource='AttendanceRecord',
            resource_id=str(record.id),
            details={
                'student': record.student.name,
                'date': str(record.attendance_date),
                'previous_status': prev_status,
                'new_status': new_status,
                'reason': reason.strip()
            }
        )

    return record


def bulk_mark_all_status(
    school,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    section: Section,
    attendance_date: datetime.date,
    target_status: str,
    actor
) -> Dict[str, Any]:
    """
    Convenience helper to set all enrolled students of a section to a single status.
    """
    # Fetch active students for this section
    enrollments = StudentEnrollment.objects.filter(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        status__in=['ACTIVE', 'ENROLLED']
    ).select_related('student')

    if enrollments.exists():
        student_ids = [e.student_id for e in enrollments]
    else:
        student_ids = list(Student.objects.filter(
            school=school,
            grade_level=grade_level,
            section=section,
            is_active=True
        ).values_list('id', flat=True))

    entries = [{'student_id': s_id, 'status': target_status, 'remarks': ''} for s_id in student_ids]
    return save_daily_attendance(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        attendance_date=attendance_date,
        attendance_entries=entries,
        actor=actor
    )
