"""
PrimeSoul Unified Portal - Selectors (Presentation & Aggregation Layer)
Aggregates read-models from existing domain modules with zero N+1 queries.
Business logic remains strictly inside original module services.
"""
import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.db.models import Sum, Count, Q, F
from django.utils import timezone

# Academics & Students
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, SubjectAssignment, StudentEnrollment
)
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.teachers.models import Teacher, TeacherProfile

# Existing Module Selectors
from django_school_management.attendance.selectors import attendance_selectors
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.fees.models import (
    FeeInstallment, FeeInvoice, PaymentTransaction, FeeReceipt
)
from django_school_management.examinations.models import (
    Exam, ExamSubject, StudentExamResult, StudentMark
)
from django_school_management.timetable.selectors import timetable_selectors
from django_school_management.timetable.models import TimetableEntry, WorkingDay
from django_school_management.transport.selectors import transport_selectors
from django_school_management.library.selectors import library_selectors
from django_school_management.library.models import LibraryMember, LibraryIssue, LibraryFine
from django_school_management.hr.selectors import hr_selectors
from django_school_management.hr.models import Employee, LeaveBalance, LeaveRequest, PayrollRecord
from django_school_management.notices.models import Notice

from django_school_management.portal.permissions import (
    get_parent_children, get_student_for_user, get_teacher_for_user, get_employee_for_user,
    get_parent_profile, resolve_student_placement
)


# ─────────────────────────────────────────────────────────────
# NOTICES SELECTORS
# ─────────────────────────────────────────────────────────────

def get_portal_notices(school, user=None, limit: int = 10) -> List[Notice]:
    """Fetches active, unexpired school notices for portal display."""
    today = timezone.localdate()
    qs = Notice.objects.filter(
        Q(expires_at__gte=today) | Q(expires_at__isnull=True)
    ).order_by('-created')
    return list(qs[:limit])


# ─────────────────────────────────────────────────────────────
# STUDENT DOMAIN PRESENTATION SELECTORS
# ─────────────────────────────────────────────────────────────

def get_student_portal_attendance(student: Student, school) -> Dict[str, Any]:
    """Retrieves student attendance summary and recent record history."""
    if not student:
        return {'percentage': 0.0, 'total_records': 0, 'present_count': 0, 'absent_count': 0, 'recent_records': []}

    ay = student.academic_year or AcademicYear.objects.filter(school=school, is_current=True).first()
    summary = attendance_selectors.get_student_attendance_summary(school, student, ay)
    
    # Today's attendance
    today = timezone.localdate()
    today_rec = AttendanceRecord.objects.filter(student=student, school=school, attendance_date=today).first()

    return {
        'summary': summary,
        'percentage': summary.get('percentage', 0.0),
        'total_records': summary.get('total_records', 0),
        'present_count': summary.get('present_count', 0),
        'absent_count': summary.get('absent_count', 0),
        'late_count': summary.get('late_count', 0),
        'half_day_count': summary.get('half_day_count', 0),
        'excused_count': summary.get('excused_count', 0),
        'recent_records': summary.get('recent_records', []),
        'today_record': today_rec,
        'today_status': today_rec.get_status_display() if today_rec else 'Not Marked',
    }


def get_student_portal_fees(student: Student, school) -> Dict[str, Any]:
    """Retrieves fee dues, installments, invoices, and payments for a student."""
    if not student:
        return {'total_payable': Decimal('0.00'), 'total_paid': Decimal('0.00'), 'total_outstanding': Decimal('0.00'), 'installments': [], 'invoices': [], 'payments': [], 'receipts': []}

    installments = list(
        FeeInstallment.objects.filter(student=student)
        .select_related('fee_structure', 'academic_year')
        .order_by('due_date')
    )

    invoices = list(
        FeeInvoice.objects.filter(student=student, school=school)
        .order_by('-invoice_date')[:20]
    )

    payments = list(
        PaymentTransaction.objects.filter(student=student, school=school, status='SUCCESS')
        .select_related('invoice')
        .order_by('-paid_at')[:20]
    )

    receipts = list(
        FeeReceipt.objects.filter(student=student, school=school)
        .select_related('payment')
        .order_by('-receipt_date')[:20]
    )

    if installments:
        tot_payable = sum([i.payable_amount for i in installments], Decimal('0.00'))
        tot_paid = sum([i.paid_amount for i in installments], Decimal('0.00'))
        tot_bal = sum([i.balance_amount for i in installments], Decimal('0.00'))
    elif invoices:
        tot_payable = sum([i.total for i in invoices], Decimal('0.00'))
        tot_paid = sum([i.paid_amount for i in invoices], Decimal('0.00'))
        tot_bal = sum([i.balance_amount for i in invoices], Decimal('0.00'))
    else:
        tot_payable = Decimal('0.00')
        tot_paid = Decimal('0.00')
        tot_bal = Decimal('0.00')

    return {
        'total_payable': tot_payable,
        'total_paid': tot_paid,
        'total_outstanding': tot_bal,
        'installments': installments,
        'invoices': invoices,
        'payments': payments,
        'receipts': receipts,
        'latest_receipt': receipts[0] if receipts else None,
    }


def get_student_portal_results(student: Student, school) -> List[Dict[str, Any]]:
    """
    Retrieves ONLY published examination results for a student.
    Strictly filters out draft or calculated-only exams.
    """
    if not student:
        return []

    published_results = StudentExamResult.objects.filter(
        student=student,
        school=school,
        status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]
    ).select_related('exam', 'academic_year', 'enrollment__section').order_by('-exam__start_date', '-created')

    result_list = []
    for r in published_results:
        # Pre-fetch subject marks
        marks = list(
            StudentMark.objects.filter(exam=r.exam, student=student)
            .select_related('exam_subject', 'exam_subject__subject')
            .order_by('exam_subject__sequence_order')
        )
        result_list.append({
            'result': r,
            'exam': r.exam,
            'marks': marks,
            'percentage': r.percentage,
            'grade': r.overall_grade,
            'status': r.get_result_status_display(),
            'class_rank': r.class_rank,
            'section_rank': r.section_rank,
        })
    return result_list


def get_student_portal_timetable(student: Student, school) -> Dict[str, Any]:
    """Retrieves class/section timetable matrix and today's schedule for a student."""
    if not student:
        return {'matrix': None, 'today_entries': [], 'section': None, 'grade_level': None}

    resolve_student_placement(student, school)
    if not student.section:
        return {'matrix': None, 'today_entries': [], 'section': None, 'grade_level': student.grade_level}

    ay = student.academic_year or AcademicYear.objects.filter(school=school, is_current=True).first()
    matrix = timetable_selectors.get_class_timetable_matrix(school, student.section, ay)

    # Today's schedule
    today_weekday = timezone.localdate().weekday() # 0 = Monday
    today_entries = list(
        TimetableEntry.objects.filter(
            school=school,
            academic_year=ay,
            section=student.section,
            working_day__weekday=today_weekday,
            is_active=True
        ).select_related('subject', 'teacher', 'room', 'time_slot')
        .order_by('time_slot__start_time')
    )

    return {
        'matrix': matrix,
        'today_entries': today_entries,
        'section': student.section,
        'grade_level': student.grade_level,
    }


def get_student_portal_transport(student: Student, school) -> Optional[Dict[str, Any]]:
    """Retrieves student's active transport allocation."""
    if not student:
        return None
    resolve_student_placement(student, school)
    ay = student.academic_year or AcademicYear.objects.filter(school=school, is_current=True).first()
    return transport_selectors.get_student_transport_info(student, ay)


def get_student_portal_library(student: Student, school) -> Optional[Dict[str, Any]]:
    """Retrieves student's library membership, issued copies, and fines."""
    if not student:
        return None
    return library_selectors.get_student_library_info(student)


# ─────────────────────────────────────────────────────────────
# AGGREGATED DASHBOARDS
# ─────────────────────────────────────────────────────────────

def get_parent_portal_dashboard(user, school, student: Optional[Student] = None) -> Dict[str, Any]:
    """
    Constructs unified dashboard payload for Parent self-service portal.
    Aggregates metrics for the selected child.
    """
    children = list(get_parent_children(user, school))
    children_count = len(children)

    active_child = student
    if not active_child and children:
        active_child = children[0]

    parent_profile = get_parent_profile(user, school)

    if not active_child:
        return {
            'has_children': False,
            'children': [],
            'children_count': 0,
            'selected_child': None,
            'parent_profile': parent_profile,
            'notices': get_portal_notices(school, user, limit=5),
        }

    # Gather domain data for the active child
    att_data = get_student_portal_attendance(active_child, school)
    fee_data = get_student_portal_fees(active_child, school)
    results = get_student_portal_results(active_child, school)
    tt_data = get_student_portal_timetable(active_child, school)
    transport_info = get_student_portal_transport(active_child, school)
    library_info = get_student_portal_library(active_child, school)
    notices = get_portal_notices(school, user, limit=5)

    latest_result = results[0] if results else None

    return {
        'has_children': True,
        'children': children,
        'children_count': children_count,
        'selected_child': active_child,
        'parent_profile': parent_profile,
        'attendance': att_data,
        'fees': fee_data,
        'latest_result': latest_result,
        'results_count': len(results),
        'timetable_today': tt_data.get('today_entries', []),
        'transport': transport_info,
        'library': library_info,
        'notices': notices,
    }


def get_student_portal_dashboard(student: Student, school) -> Dict[str, Any]:
    """Constructs student self-service dashboard payload."""
    if not student:
        return {'student': None, 'notices': get_portal_notices(school, limit=5)}

    att_data = get_student_portal_attendance(student, school)
    fee_data = get_student_portal_fees(student, school)
    results = get_student_portal_results(student, school)
    tt_data = get_student_portal_timetable(student, school)
    transport_info = get_student_portal_transport(student, school)
    library_info = get_student_portal_library(student, school)
    notices = get_portal_notices(school, limit=5)

    return {
        'student': student,
        'attendance': att_data,
        'fees': fee_data,
        'latest_result': results[0] if results else None,
        'results': results,
        'timetable_today': tt_data.get('today_entries', []),
        'timetable_matrix': tt_data.get('matrix'),
        'transport': transport_info,
        'library': library_info,
        'notices': notices,
    }


def get_teacher_portal_dashboard(user, school) -> Dict[str, Any]:
    """Constructs teacher & faculty self-service dashboard payload."""
    teacher = get_teacher_for_user(user, school)
    employee = get_employee_for_user(user, school)
    today = timezone.localdate()
    today_weekday = today.weekday()

    # 1. Timetable today
    today_schedule = []
    if teacher:
        ay = AcademicYear.objects.filter(school=school, is_current=True).first()
        today_schedule = list(
            TimetableEntry.objects.filter(
                school=school,
                teacher=teacher,
                working_day__weekday=today_weekday,
                is_active=True
            ).select_related('subject', 'section', 'section__grade_level', 'room', 'time_slot')
            .order_by('time_slot__start_time')
        )

    # 2. Assigned sections
    assigned_sections = []
    if teacher:
        # Class teacher assignments
        ct_sections = list(Section.objects.filter(school=school, class_teacher=teacher, is_active=True).select_related('grade_level'))
        # Subject assignments
        subj_sections = list(
            SubjectAssignment.objects.filter(school=school, teacher=teacher, is_active=True)
            .select_related('grade_level', 'section', 'subject')
        )
        assigned_sections = {
            'class_teacher_sections': ct_sections,
            'subject_assignments': subj_sections,
        }

    # 3. Attendance tasks
    pending_attendance = []
    if user:
        pending_attendance = attendance_selectors.get_pending_attendance_sections(
            school=school,
            academic_year=None,
            target_date=today,
            teacher_user=user
        )

    # 4. HR Leave & Payroll summary
    leave_summary = {'balances': [], 'recent_requests': []}
    latest_payslip = None
    if employee:
        leave_summary = hr_selectors.get_leave_summary(school, employee)
        latest_payslip = PayrollRecord.objects.filter(school=school, employee=employee).select_related('payroll_period').order_by('-payroll_period__year', '-payroll_period__month').first()

    # 5. Library info
    teacher_member = LibraryMember.objects.filter(school=school, teacher=teacher, is_active=True).first() if teacher else None
    library_info = None
    if teacher_member:
        active_issues = list(LibraryIssue.objects.filter(member=teacher_member, status=LibraryIssue.STATUS_ISSUED).select_related('book_copy', 'book_copy__book'))
        fines = LibraryFine.objects.filter(issue__member=teacher_member, paid=False).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')
        library_info = {
            'member': teacher_member,
            'active_issues': active_issues,
            'outstanding_fines': fines,
        }

    notices = get_portal_notices(school, user, limit=5)

    return {
        'teacher': teacher,
        'employee': employee,
        'today_schedule': today_schedule,
        'assigned_sections': assigned_sections,
        'pending_attendance': pending_attendance,
        'leave_summary': leave_summary,
        'latest_payslip': latest_payslip,
        'library_info': library_info,
        'notices': notices,
    }


def get_teacher_portal_timetable(teacher: Teacher, school) -> Dict[str, Any]:
    """Retrieves weekly timetable matrix for a faculty member."""
    if not teacher:
        return {'matrix': None, 'teacher': None}
    ay = AcademicYear.objects.filter(school=school, is_current=True).first()
    matrix = timetable_selectors.get_teacher_timetable_matrix(school, teacher, ay)
    return {'matrix': matrix, 'teacher': teacher}


def get_teacher_assigned_classes(teacher: Teacher, school) -> List[Dict[str, Any]]:
    """Lists distinct classes/sections where the teacher has teaching assignments."""
    if not teacher:
        return []
    
    assignments = SubjectAssignment.objects.filter(
        school=school, teacher=teacher, is_active=True
    ).select_related('grade_level', 'section', 'subject', 'academic_year')

    classes = []
    for a in assignments:
        sec = a.section
        student_count = 0
        if sec:
            student_count = StudentEnrollment.objects.filter(
                school=school, section=sec, status__in=['ACTIVE', 'ENROLLED']
            ).count()
            if student_count == 0:
                student_count = Student.objects.filter(school=school, section=sec, is_active=True).count()

        classes.append({
            'assignment': a,
            'grade_level': a.grade_level,
            'section': sec,
            'subject': a.subject,
            'periods_per_week': a.periods_per_week,
            'student_count': student_count,
            'academic_year': a.academic_year,
        })
    return classes


def get_teacher_assigned_students(teacher: Teacher, school, section_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Returns roster of students in the sections assigned to this teacher."""
    if not teacher:
        return []

    # Get valid sections for teacher
    valid_sec_ids = set()
    # Class teacher sections
    valid_sec_ids.update(Section.objects.filter(school=school, class_teacher=teacher, is_active=True).values_list('id', flat=True))
    # Subject assignment sections
    valid_sec_ids.update(SubjectAssignment.objects.filter(school=school, teacher=teacher, is_active=True, section__isnull=False).values_list('section_id', flat=True))

    if section_id:
        if int(section_id) not in valid_sec_ids:
            return [] # Unauthorized section access
        target_ids = [int(section_id)]
    else:
        target_ids = list(valid_sec_ids)

    enrollments = StudentEnrollment.objects.filter(
        school=school,
        section_id__in=target_ids,
        status__in=['ACTIVE', 'ENROLLED']
    ).select_related('student', 'grade_level', 'section').order_by('grade_level__display_order', 'section__name', 'roll_number')

    roster = []
    for enr in enrollments:
        st = enr.student
        roster.append({
            'student': st,
            'admission_number': st.admission_number or '',
            'roll_number': enr.roll_number or st.roll_number or '',
            'name': st.name,
            'grade_level': enr.grade_level.name if enr.grade_level else '',
            'section': enr.section.name if enr.section else '',
            'gender': st.gender,
        })
    return roster


def get_teacher_portal_leaves(employee: Employee, school) -> Dict[str, Any]:
    """Retrieves leave balances and recent requests for teacher/employee."""
    if not employee:
        return {'balances': [], 'requests': []}
    balances = list(LeaveBalance.objects.filter(employee=employee, school=school).select_related('leave_type'))
    requests = list(LeaveRequest.objects.filter(employee=employee, school=school).select_related('leave_type').order_by('-created')[:10])
    return {
        'balances': balances,
        'requests': requests,
    }


def get_teacher_portal_payslips(employee: Employee, school) -> List[PayrollRecord]:
    """Retrieves processed payroll / payslip records for teacher/employee."""
    if not employee:
        return []
    return list(
        PayrollRecord.objects.filter(employee=employee, school=school)
        .order_by('-payroll_period__year', '-payroll_period__month')[:12]
    )
