from decimal import Decimal
from django.db.models import Avg, Max, Min, Count, Q, Sum
from django.utils import timezone

from django_school_management.academics.models import StudentEnrollment, AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student
from django_school_management.examinations.models import (
    ExaminationSession, Exam, ExamSubject, StudentMark, StudentExamResult, GradeScale
)


def get_exam_dashboard_metrics(school) -> dict:
    """
    Computes high-level aggregated metrics for the examination & results dashboard.
    """
    today = timezone.now().date()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    sessions_qs = ExaminationSession.objects.filter(school=school)
    if current_year:
        sessions_qs = sessions_qs.filter(academic_year=current_year)

    active_sessions_count = sessions_qs.filter(
        status__in=[ExaminationSession.STATUS_SCHEDULED, ExaminationSession.STATUS_ONGOING]
    ).count()

    exams_qs = Exam.objects.filter(school=school)
    if current_year:
        exams_qs = exams_qs.filter(academic_year=current_year)

    upcoming_exams_count = exams_qs.filter(
        status__in=[Exam.STATUS_DRAFT, Exam.STATUS_SCHEDULED]
    ).count()

    completed_exams_count = exams_qs.filter(
        status__in=[Exam.STATUS_COMPLETED, Exam.STATUS_FINALIZED, Exam.STATUS_PUBLISHED, Exam.STATUS_LOCKED]
    ).count()

    results_qs = StudentExamResult.objects.filter(school=school)
    if current_year:
        results_qs = results_qs.filter(academic_year=current_year)

    pending_finalization_count = results_qs.filter(status=StudentExamResult.STATUS_CALCULATED).count()
    published_results_count = results_qs.filter(status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]).count()

    total_appeared = results_qs.exclude(result_status=StudentExamResult.RESULT_ABSENT).count()
    passed_count = results_qs.filter(result_status=StudentExamResult.RESULT_PASSED).count()
    failed_count = results_qs.filter(result_status__in=[StudentExamResult.RESULT_FAILED, StudentExamResult.RESULT_COMPARTMENT]).count()

    pass_percentage = round((passed_count / total_appeared) * 100.0, 2) if total_appeared > 0 else 0.0

    recent_exams = list(
        exams_qs.select_related('grade_level', 'section', 'session', 'assessment_type')
        .order_by('-created')[:8]
    )

    return {
        'current_year': current_year,
        'active_sessions_count': active_sessions_count,
        'upcoming_exams_count': upcoming_exams_count,
        'completed_exams_count': completed_exams_count,
        'pending_finalization_count': pending_finalization_count,
        'published_results_count': published_results_count,
        'total_appeared': total_appeared,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'pass_percentage': pass_percentage,
        'recent_exams': recent_exams,
    }


def get_class_result_summary(school, exam: Exam, section=None) -> dict:
    """
    Computes comprehensive analytics for a class/section in an examination:
    Pass %, average %, highest/lowest %, grade distribution, and subject-wise metrics.
    Avoids N+1 queries.
    """
    results_qs = StudentExamResult.objects.filter(
        school=school,
        exam=exam
    ).select_related('student', 'enrollment__section')

    if section:
        results_qs = results_qs.filter(enrollment__section=section)

    total_students = results_qs.count()
    appeared_qs = results_qs.exclude(result_status=StudentExamResult.RESULT_ABSENT)
    appeared_count = appeared_qs.count()
    absent_count = results_qs.filter(result_status=StudentExamResult.RESULT_ABSENT).count()
    passed_count = results_qs.filter(result_status=StudentExamResult.RESULT_PASSED).count()
    failed_count = results_qs.filter(result_status=StudentExamResult.RESULT_FAILED).count()
    compartment_count = results_qs.filter(result_status=StudentExamResult.RESULT_COMPARTMENT).count()

    stats = appeared_qs.aggregate(
        avg_pct=Avg('percentage'),
        max_pct=Max('percentage'),
        min_pct=Min('percentage'),
    )

    avg_pct = round(stats['avg_pct'] or Decimal('0.00'), 2)
    max_pct = round(stats['max_pct'] or Decimal('0.00'), 2)
    min_pct = round(stats['min_pct'] or Decimal('0.00'), 2)
    pass_pct = round((passed_count / appeared_count) * 100.0, 2) if appeared_count > 0 else 0.0

    # Grade distribution
    grade_counts = (
        appeared_qs.values('overall_grade')
        .annotate(count=Count('id'))
        .order_by('overall_grade')
    )
    grade_distribution = {item['overall_grade'] or 'Other': item['count'] for item in grade_counts}

    # Subject-wise statistics
    exam_subjects = list(exam.subjects.filter(is_active=True).select_related('subject'))
    marks_qs = StudentMark.objects.filter(school=school, exam=exam)
    if section:
        marks_qs = marks_qs.filter(enrollment__section=section)

    subject_stats = []
    for es in exam_subjects:
        subj_marks = marks_qs.filter(exam_subject=es)
        present_marks = subj_marks.filter(status=StudentMark.STATUS_PRESENT)
        present_cnt = present_marks.count()
        subj_absent = subj_marks.filter(status=StudentMark.STATUS_ABSENT).count()

        agg = present_marks.aggregate(
            avg_m=Avg('marks_obtained'),
            max_m=Max('marks_obtained'),
            min_m=Min('marks_obtained'),
            passed_cnt=Count('id', filter=Q(is_passed=True))
        )
        avg_m = round(agg['avg_m'] or Decimal('0.00'), 2)
        max_m = round(agg['max_m'] or Decimal('0.00'), 2)
        min_m = round(agg['min_m'] or Decimal('0.00'), 2)
        pass_c = agg['passed_cnt'] or 0
        fail_c = present_cnt - pass_c

        subj_pass_pct = round((pass_c / present_cnt) * 100.0, 2) if present_cnt > 0 else 0.0

        subject_stats.append({
            'subject_id': es.subject.id,
            'subject_name': es.subject.name,
            'max_marks': es.max_marks,
            'passing_marks': es.passing_marks,
            'present_count': present_cnt,
            'absent_count': subj_absent,
            'avg_marks': avg_m,
            'max_marks_obtained': max_m,
            'min_marks_obtained': min_m,
            'passed_count': pass_c,
            'failed_count': fail_c,
            'pass_percentage': subj_pass_pct,
        })

    return {
        'exam': exam,
        'section': section,
        'total_students': total_students,
        'appeared_count': appeared_count,
        'absent_count': absent_count,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'compartment_count': compartment_count,
        'pass_percentage': pass_pct,
        'average_percentage': avg_pct,
        'highest_percentage': max_pct,
        'lowest_percentage': min_pct,
        'grade_distribution': grade_distribution,
        'subject_stats': subject_stats,
    }


def get_marks_entry_sheet(school, exam: Exam, exam_subject: ExamSubject, section=None) -> list:
    """
    Returns active enrolled students for an exam/section matched with their current mark entry.
    Prepared for fast, keyboard-friendly bulk marks entry.
    """
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

    # Fallback to direct Student placement if needed
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

    if target_section:
        enrollment_qs = enrollment_qs.filter(section=target_section)

    enrollments = list(enrollment_qs)

    # Fetch existing marks
    marks_map = {
        m.student_id: m for m in StudentMark.objects.filter(
            school=school,
            exam=exam,
            exam_subject=exam_subject
        ).select_related('student')
    }

    sheet = []
    for enr in enrollments:
        student = enr.student
        existing_mark = marks_map.get(student.id)
        sheet.append({
            'student_id': student.id,
            'student_name': student.name,
            'roll_number': enr.roll_number or getattr(student, 'roll_number', '') or '',
            'admission_number': getattr(student, 'admission_number', '') or '',
            'section_name': enr.section.name if enr.section else '',
            'status': existing_mark.status if existing_mark else StudentMark.STATUS_NOT_ENTERED,
            'marks_obtained': existing_mark.marks_obtained if existing_mark else None,
            'grade': existing_mark.grade if existing_mark else '',
            'is_passed': existing_mark.is_passed if existing_mark else True,
            'remarks': existing_mark.remarks if existing_mark else '',
            'mark_id': existing_mark.id if existing_mark else None,
        })

    return sheet
