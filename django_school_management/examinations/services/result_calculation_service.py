import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.core.audit import log_examination_event
from django_school_management.academics.models import StudentEnrollment
from django_school_management.attendance.selectors import attendance_selectors
from django_school_management.examinations.models import (
    Exam, ExamSubject, StudentMark, StudentExamResult, GradeScale
)
from .marks_service import determine_grade_for_percentage

logger = logging.getLogger(__name__)


@transaction.atomic
def calculate_exam_results(school, exam: Exam, section=None, actor=None) -> list:
    """
    Computes complete examination results for all enrolled students in the exam's grade/section.
    Aggregates subject marks, percentages, overall grades, pass/fail status, attendance, and ranks.
    """
    if exam.school != school:
        raise PermissionDenied("Exam does not belong to this school tenant.")

    if actor and not (actor.is_superuser or user_has_role(actor, Role.SCHOOL_ADMIN) or user_has_role(actor, Role.PRINCIPAL) or user_has_role(actor, Role.TEACHER)):
        raise PermissionDenied("Unauthorized to calculate examination results.")

    # Prevent recalculation if locked
    if exam.status == Exam.STATUS_LOCKED:
        raise ValidationError("This examination is locked. Results cannot be recalculated without administrator unlock.")

    # Configured active exam subjects
    exam_subjects = list(exam.subjects.filter(is_active=True).select_related('subject'))
    if not exam_subjects:
        raise ValidationError("Cannot calculate results: No active subjects configured for this exam.")

    total_exam_max_marks = sum(es.max_marks for es in exam_subjects)
    grade_scale = exam.grade_scale or GradeScale.objects.filter(school=school, is_default=True).first()

    target_section = section or exam.section
    enrollment_qs = StudentEnrollment.objects.filter(
        school=school,
        academic_year=exam.academic_year,
        grade_level=exam.grade_level,
        status__in=['ACTIVE', 'ENROLLED']
    ).select_related('student', 'section')

    if target_section:
        enrollment_qs = enrollment_qs.filter(section=target_section)

    enrollments = list(enrollment_qs)

    # Fallback to direct Student placement if no explicit StudentEnrollment rows
    if not enrollments:
        direct_students = Student.objects.filter(
            school=school,
            grade_level=exam.grade_level,
            is_active=True
        )
        if target_section:
            direct_students = direct_students.filter(section=target_section)
        for st in direct_students:
            enr, _ = StudentEnrollment.objects.get_or_create(
                school=school,
                student=st,
                academic_year=exam.academic_year,
                defaults={
                    'grade_level': exam.grade_level,
                    'section': st.section or target_section,
                    'roll_number': st.roll_number or '',
                    'status': 'ACTIVE'
                }
            )
            enrollments.append(enr)

    if not enrollments:
        raise ValidationError("No active student enrollments found for the selected examination class and section.")

    calculated_results = []
    now = timezone.now()

    for enrollment in enrollments:
        student = enrollment.student

        # Fetch student marks for this exam
        marks_qs = StudentMark.objects.filter(
            school=school,
            exam=exam,
            student=student
        ).select_related('exam_subject')
        marks_map = {m.exam_subject_id: m for m in marks_qs}

        total_obtained = Decimal('0.00')
        subjects_passed = 0
        subjects_failed = 0
        absent_count = 0
        present_count = 0

        for es in exam_subjects:
            mark_entry = marks_map.get(es.id)
            if mark_entry and mark_entry.status == StudentMark.STATUS_PRESENT:
                present_count += 1
                if mark_entry.marks_obtained is not None:
                    total_obtained += mark_entry.marks_obtained
                if mark_entry.is_passed:
                    subjects_passed += 1
                else:
                    subjects_failed += 1
            elif mark_entry and mark_entry.status == StudentMark.STATUS_ABSENT:
                absent_count += 1
                subjects_failed += 1
            else:
                # Not entered or missing
                subjects_failed += 1

        # Percentage
        if total_exam_max_marks > Decimal('0.00'):
            percentage = (total_obtained / total_exam_max_marks) * Decimal('100.00')
        else:
            percentage = Decimal('0.00')

        # Overall Grade
        overall_grade, overall_gp, band_passing, remarks = determine_grade_for_percentage(percentage, grade_scale)

        # Result status
        if absent_count == len(exam_subjects):
            result_status = StudentExamResult.RESULT_ABSENT
        elif subjects_failed == 0 and band_passing:
            result_status = StudentExamResult.RESULT_PASSED
        elif subjects_failed == 1:
            result_status = StudentExamResult.RESULT_COMPARTMENT
        else:
            result_status = StudentExamResult.RESULT_FAILED

        # Attendance integration
        att_working_days = 0
        att_present_days = 0
        att_percentage = None
        try:
            att_summary = attendance_selectors.get_student_attendance_summary(school, student, exam.academic_year)
            att_working_days = att_summary.get('total_records') or att_summary.get('total_marked_days', 0)
            att_present_days = att_summary.get('present_count', 0) + att_summary.get('late_count', 0)
            pct_val = att_summary.get('percentage') if att_summary.get('percentage') is not None else att_summary.get('attendance_percentage', 0.0)
            att_percentage = Decimal(str(round(float(pct_val), 2))) if pct_val is not None else None
        except Exception as e:
            logger.warning("Could not fetch attendance summary for student %s: %s", student.id, e)

        # Create or update StudentExamResult
        res_obj, created = StudentExamResult.objects.get_or_create(
            school=school,
            exam=exam,
            student=student,
            defaults={
                'academic_year': exam.academic_year,
                'enrollment': enrollment,
                'total_marks_obtained': total_obtained,
                'total_max_marks': total_exam_max_marks,
                'percentage': percentage,
                'overall_grade': overall_grade,
                'overall_grade_point': overall_gp,
                'result_status': result_status,
                'status': StudentExamResult.STATUS_CALCULATED,
                'subjects_passed': subjects_passed,
                'subjects_failed': subjects_failed,
                'attendance_working_days': att_working_days,
                'attendance_present_days': att_present_days,
                'attendance_percentage': att_percentage,
                'calculated_at': now,
                'calculated_by': actor,
            }
        )

        if not created:
            res_obj.academic_year = exam.academic_year
            res_obj.enrollment = enrollment
            res_obj.total_marks_obtained = total_obtained
            res_obj.total_max_marks = total_exam_max_marks
            res_obj.percentage = percentage
            res_obj.overall_grade = overall_grade
            res_obj.overall_grade_point = overall_gp
            res_obj.result_status = result_status
            if res_obj.status == StudentExamResult.STATUS_DRAFT:
                res_obj.status = StudentExamResult.STATUS_CALCULATED
            res_obj.subjects_passed = subjects_passed
            res_obj.subjects_failed = subjects_failed
            res_obj.attendance_working_days = att_working_days
            res_obj.attendance_present_days = att_present_days
            res_obj.attendance_percentage = att_percentage
            res_obj.calculated_at = now
            res_obj.calculated_by = actor
            res_obj.save()

        calculated_results.append(res_obj)

    # Calculate class and section ranks if ranking enabled
    if exam.ranking_enabled:
        _assign_student_ranks(calculated_results)

    if exam.status in [Exam.STATUS_DRAFT, Exam.STATUS_SCHEDULED, Exam.STATUS_ONGOING]:
        exam.status = Exam.STATUS_COMPLETED
        exam.save(update_fields=['status', 'modified'])

    log_examination_event(
        actor=actor,
        school=school,
        action='CALCULATE_RESULTS',
        resource='Exam',
        resource_id=str(exam.id),
        details={
            'exam_id': exam.id,
            'exam_name': exam.name,
            'students_evaluated': len(calculated_results),
            'target_section_id': target_section.id if target_section else None,
        }
    )

    return calculated_results


def _assign_student_ranks(results: list):
    """
    Computes class_rank and section_rank among the evaluated results based on percentage.
    Handles equal scores (ties) consistently.
    """
    # Exclude all-absent students from competitive ranks
    rankable_class = [r for r in results if r.result_status != StudentExamResult.RESULT_ABSENT]
    rankable_class.sort(key=lambda r: (r.percentage, r.total_marks_obtained), reverse=True)

    # Class rank assignment
    current_rank = 1
    for idx, res in enumerate(rankable_class):
        if idx > 0:
            prev = rankable_class[idx - 1]
            if res.percentage < prev.percentage:
                current_rank = idx + 1
        res.class_rank = current_rank

    # Section rank assignment grouped by section
    section_map = {}
    for res in rankable_class:
        sec_id = res.enrollment.section_id if (res.enrollment and res.enrollment.section_id) else 0
        section_map.setdefault(sec_id, []).append(res)

    for sec_id, sec_results in section_map.items():
        sec_rank = 1
        for idx, res in enumerate(sec_results):
            if idx > 0:
                prev = sec_results[idx - 1]
                if res.percentage < prev.percentage:
                    sec_rank = idx + 1
            res.section_rank = sec_rank

    # Save rank updates
    for res in rankable_class:
        res.save(update_fields=['class_rank', 'section_rank'])


@transaction.atomic
def finalize_exam_results(school, exam: Exam, actor) -> int:
    """Transitions exam and its calculated student results to FINALIZED."""
    if exam.school != school:
        raise PermissionDenied("Exam does not belong to this school tenant.")

    if not (actor.is_superuser or user_has_role(actor, Role.SCHOOL_ADMIN) or user_has_role(actor, Role.PRINCIPAL)):
        raise PermissionDenied("Only Administrators and Principals can finalize examination results.")

    now = timezone.now()
    count = StudentExamResult.objects.filter(
        school=school,
        exam=exam,
        status=StudentExamResult.STATUS_CALCULATED
    ).update(
        status=StudentExamResult.STATUS_FINALIZED,
        finalized_at=now,
        finalized_by=actor
    )

    exam.status = Exam.STATUS_FINALIZED
    exam.save(update_fields=['status', 'modified'])

    log_examination_event(
        actor=actor,
        school=school,
        action='FINALIZE_RESULTS',
        resource='Exam',
        resource_id=str(exam.id),
        details={'exam_id': exam.id, 'records_finalized': count}
    )
    return count


@transaction.atomic
def publish_exam_results(school, exam: Exam, actor) -> int:
    """Transitions exam and its results to PUBLISHED, making them visible to students & parents."""
    if exam.school != school:
        raise PermissionDenied("Exam does not belong to this school tenant.")

    if not (actor.is_superuser or user_has_role(actor, Role.SCHOOL_ADMIN) or user_has_role(actor, Role.PRINCIPAL)):
        raise PermissionDenied("Only Administrators and Principals can publish examination results.")

    now = timezone.now()
    count = StudentExamResult.objects.filter(
        school=school,
        exam=exam
    ).exclude(
        status=StudentExamResult.STATUS_LOCKED
    ).update(
        status=StudentExamResult.STATUS_PUBLISHED,
        published_at=now,
        published_by=actor
    )

    exam.status = Exam.STATUS_PUBLISHED
    exam.save(update_fields=['status', 'modified'])

    log_examination_event(
        actor=actor,
        school=school,
        action='PUBLISH_RESULTS',
        resource='Exam',
        resource_id=str(exam.id),
        details={'exam_id': exam.id, 'records_published': count}
    )
    return count


@transaction.atomic
def lock_exam_results(school, exam: Exam, actor) -> int:
    """Locks exam results to prevent further modifications without administrative corrections."""
    if exam.school != school:
        raise PermissionDenied("Exam does not belong to this school tenant.")

    if not (actor.is_superuser or user_has_role(actor, Role.SCHOOL_ADMIN) or user_has_role(actor, Role.PRINCIPAL)):
        raise PermissionDenied("Only Administrators and Principals can lock examination results.")

    now = timezone.now()
    count = StudentExamResult.objects.filter(
        school=school,
        exam=exam
    ).update(
        status=StudentExamResult.STATUS_LOCKED,
        locked_at=now,
        locked_by=actor
    )

    exam.status = Exam.STATUS_LOCKED
    exam.save(update_fields=['status', 'modified'])

    log_examination_event(
        actor=actor,
        school=school,
        action='LOCK_RESULTS',
        resource='Exam',
        resource_id=str(exam.id),
        details={'exam_id': exam.id, 'records_locked': count}
    )
    return count
