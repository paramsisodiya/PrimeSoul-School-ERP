import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.core.audit import log_examination_event
from django_school_management.students.models import Student
from django_school_management.academics.models import StudentEnrollment
from django_school_management.examinations.models import (
    Exam, ExamSubject, StudentMark, MarksCorrectionLog, GradeScale
)
from .exam_service import can_user_enter_marks

logger = logging.getLogger(__name__)


def determine_grade_for_percentage(percentage: Decimal, grade_scale: GradeScale):
    """
    Returns (grade_name, grade_point, is_passing, remarks) for a given percentage
    using the provided GradeScale.
    """
    if percentage is None or not grade_scale:
        return ('', None, True, '')

    bands = list(grade_scale.bands.all().order_by('-min_percentage'))
    for band in bands:
        if band.min_percentage <= percentage <= band.max_percentage:
            return (band.name, band.grade_point, band.is_passing, band.remarks)

    # Fallback to last band if below lowest min_percentage
    if bands:
        last_band = bands[-1]
        if percentage < last_band.min_percentage:
            return (last_band.name, last_band.grade_point, last_band.is_passing, last_band.remarks)

    return ('', None, True, '')


@transaction.atomic
def save_bulk_marks(school, exam: Exam, exam_subject: ExamSubject, section, marks_data: list, actor, correction_reason: str = None) -> list:
    """
    Atomically saves or updates marks for an entire class section in a single subject.
    
    marks_data structure:
    [
        {
            'student_id': int,
            'status': 'PRESENT' | 'ABSENT' | 'NOT_ENTERED',
            'marks_obtained': Decimal or float or str or None,
            'remarks': str (optional)
        },
        ...
    ]
    """
    if exam.school != school or exam_subject.exam != exam:
        raise PermissionDenied("Exam or Exam Subject does not belong to this school tenant.")

    if not can_user_enter_marks(actor, school, exam, exam_subject, section):
        raise PermissionDenied("You are not authorized to enter marks for this class, section, or subject.")

    # Guard: Locked exam cannot be modified without admin role & reason
    if exam.status == Exam.STATUS_LOCKED:
        is_admin = actor.is_superuser or user_has_role(actor, Role.SCHOOL_ADMIN) or user_has_role(actor, Role.PRINCIPAL)
        if not is_admin:
            raise PermissionDenied("This examination is locked. Marks cannot be modified.")
        if not correction_reason or not correction_reason.strip():
            raise ValidationError("A valid correction justification reason is required to modify marks in a locked examination.")

    # Active grade scale
    grade_scale = exam.grade_scale or GradeScale.objects.filter(school=school, is_default=True).first()

    saved_records = []
    correction_count = 0

    for item in marks_data:
        student_id = item.get('student_id')
        status = item.get('status', StudentMark.STATUS_NOT_ENTERED)
        raw_marks = item.get('marks_obtained')
        remarks = item.get('remarks', '') or ''

        student = Student.objects.filter(id=student_id, school=school).first()
        if not student:
            continue

        # Get student's enrollment
        enrollment = StudentEnrollment.objects.filter(
            school=school,
            student=student,
            academic_year=exam.academic_year,
            grade_level=exam.grade_level
        ).first()

        # Parse & validate marks
        marks_obtained = None
        grade_name = ''
        grade_point = None
        is_passed = True

        if status == StudentMark.STATUS_PRESENT:
            if raw_marks is None or str(raw_marks).strip() == '':
                raise ValidationError(f"Marks obtained is required for present student: {student.name}")
            try:
                marks_obtained = Decimal(str(raw_marks).strip())
            except Exception:
                raise ValidationError(f"Invalid marks value for student {student.name}: {raw_marks}")

            if marks_obtained < Decimal('0.00'):
                raise ValidationError(f"Marks cannot be negative for student {student.name}: {marks_obtained}")

            if marks_obtained > exam_subject.max_marks:
                raise ValidationError(f"Marks ({marks_obtained}) cannot exceed maximum marks ({exam_subject.max_marks}) for {student.name}")

            # Percentage & Grade
            if exam_subject.max_marks > 0:
                subj_percentage = (marks_obtained / exam_subject.max_marks) * Decimal('100.00')
                grade_name, grade_point, band_passing, _ = determine_grade_for_percentage(subj_percentage, grade_scale)
                is_passed = (marks_obtained >= exam_subject.passing_marks) and band_passing

        elif status == StudentMark.STATUS_ABSENT:
            marks_obtained = None
            is_passed = False
            grade_name = 'AB'
        else:
            status = StudentMark.STATUS_NOT_ENTERED
            marks_obtained = None
            is_passed = True

        # Fetch existing record or create
        mark_record = StudentMark.objects.filter(
            school=school,
            exam=exam,
            exam_subject=exam_subject,
            student=student
        ).first()

        if mark_record:
            # Check for changes to log audit correction
            has_changed = (
                mark_record.status != status or
                mark_record.marks_obtained != marks_obtained
            )

            if has_changed and mark_record.status != StudentMark.STATUS_NOT_ENTERED:
                # Require reason if exam finalized or locked
                if exam.status in [Exam.STATUS_FINALIZED, Exam.STATUS_PUBLISHED, Exam.STATUS_LOCKED] and not correction_reason:
                    raise ValidationError(f"Correction reason is mandatory to modify finalized marks for {student.name}.")

                MarksCorrectionLog.objects.create(
                    school=school,
                    mark_record=mark_record,
                    exam=exam,
                    student=student,
                    subject=exam_subject.subject,
                    previous_marks=mark_record.marks_obtained,
                    previous_status=mark_record.status,
                    new_marks=marks_obtained,
                    new_status=status,
                    reason=correction_reason or "Marks updated via bulk entry",
                    corrected_by=actor
                )
                correction_count += 1

            mark_record.status = status
            mark_record.marks_obtained = marks_obtained
            mark_record.grade = grade_name
            mark_record.grade_point = grade_point
            mark_record.is_passed = is_passed
            mark_record.remarks = remarks
            mark_record.updated_by = actor
            if enrollment:
                mark_record.enrollment = enrollment
            mark_record.save()
            saved_records.append(mark_record)
        else:
            mark_record = StudentMark.objects.create(
                school=school,
                academic_year=exam.academic_year,
                exam=exam,
                exam_subject=exam_subject,
                student=student,
                enrollment=enrollment,
                status=status,
                marks_obtained=marks_obtained,
                grade=grade_name,
                grade_point=grade_point,
                is_passed=is_passed,
                remarks=remarks,
                entered_by=actor,
                updated_by=actor
            )
            saved_records.append(mark_record)

    log_examination_event(
        actor=actor,
        school=school,
        action='BULK_MARKS_SAVE',
        resource='StudentMark',
        resource_id=f"Exam:{exam.id}-Subj:{exam_subject.subject.id}",
        details={
            'exam_id': exam.id,
            'exam_name': exam.name,
            'subject_id': exam_subject.subject.id,
            'subject_name': exam_subject.subject.name,
            'records_saved': len(saved_records),
            'corrections_logged': correction_count,
        }
    )

    return saved_records


@transaction.atomic
def correct_single_student_mark(school, mark_record: StudentMark, new_status: str, new_marks: Decimal, reason: str, actor) -> StudentMark:
    """
    Dedicated single-record marks correction requiring explicit justification.
    """
    if mark_record.school != school:
        raise PermissionDenied("Mark record does not belong to this school tenant.")

    if not reason or not reason.strip():
        raise ValidationError("A valid correction reason is required.")

    if not can_user_enter_marks(actor, school, mark_record.exam, mark_record.exam_subject):
        raise PermissionDenied("You are not authorized to correct marks for this examination.")

    exam_subject = mark_record.exam_subject
    grade_scale = mark_record.exam.grade_scale or GradeScale.objects.filter(school=school, is_default=True).first()

    marks_obtained = None
    grade_name = ''
    grade_point = None
    is_passed = True

    if new_status == StudentMark.STATUS_PRESENT:
        if new_marks is None:
            raise ValidationError("Marks obtained is required when status is Present.")
        marks_obtained = Decimal(str(new_marks).strip())
        if marks_obtained < Decimal('0.00'):
            raise ValidationError("Marks cannot be negative.")
        if marks_obtained > exam_subject.max_marks:
            raise ValidationError(f"Marks cannot exceed maximum marks ({exam_subject.max_marks}).")

        if exam_subject.max_marks > 0:
            pct = (marks_obtained / exam_subject.max_marks) * Decimal('100.00')
            grade_name, grade_point, band_passing, _ = determine_grade_for_percentage(pct, grade_scale)
            is_passed = (marks_obtained >= exam_subject.passing_marks) and band_passing
    elif new_status == StudentMark.STATUS_ABSENT:
        marks_obtained = None
        is_passed = False
        grade_name = 'AB'
    else:
        new_status = StudentMark.STATUS_NOT_ENTERED
        marks_obtained = None
        is_passed = True

    # Record correction log
    MarksCorrectionLog.objects.create(
        school=school,
        mark_record=mark_record,
        exam=mark_record.exam,
        student=mark_record.student,
        subject=exam_subject.subject,
        previous_marks=mark_record.marks_obtained,
        previous_status=mark_record.status,
        new_marks=marks_obtained,
        new_status=new_status,
        reason=reason.strip(),
        corrected_by=actor
    )

    mark_record.status = new_status
    mark_record.marks_obtained = marks_obtained
    mark_record.grade = grade_name
    mark_record.grade_point = grade_point
    mark_record.is_passed = is_passed
    mark_record.updated_by = actor
    mark_record.save()

    log_examination_event(
        actor=actor,
        school=school,
        action='MARK_CORRECTION',
        resource='StudentMark',
        resource_id=str(mark_record.id),
        details={
            'student_id': mark_record.student.id,
            'subject_id': exam_subject.subject.id,
            'reason': reason.strip(),
            'previous_marks': str(mark_record.previous_marks) if hasattr(mark_record, 'previous_marks') else None,
            'new_marks': str(marks_obtained),
        }
    )

    return mark_record
