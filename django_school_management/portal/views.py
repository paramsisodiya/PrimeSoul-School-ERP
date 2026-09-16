"""
PrimeSoul Unified Portal - Web Views
Role-aware self-service controllers for Parent, Student, and Teacher portals.
Delegates business logic strictly to existing domain services.
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.urls import reverse

from django.db.models import Sum
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.academics.models import AcademicYear, Section, GradeLevel, SubjectAssignment
from django_school_management.students.models import Student
from django_school_management.notices.models import Notice
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.attendance.services import attendance_service
from django_school_management.attendance.selectors import attendance_selectors
from django_school_management.examinations.models import Exam, ExamSubject, StudentMark
from django_school_management.examinations.services import exam_service
from django_school_management.library.models import LibraryMember, LibraryIssue, LibraryFine
from django_school_management.hr.models import Employee, LeaveType, LeaveBalance, LeaveRequest, PayrollRecord
from django_school_management.hr.services import leave_service
from django_school_management.hr.selectors import hr_selectors
from django_school_management.hr.forms import LeaveApplyForm

from django_school_management.portal.permissions import (
    resolve_portal_school,
    get_parent_profile,
    get_parent_children,
    get_parent_selected_child,
    get_student_for_user,
    get_teacher_for_user,
    get_employee_for_user,
    parent_portal_required,
    student_portal_required,
    teacher_portal_required,
)
from django_school_management.portal.selectors import portal_selectors


# ─────────────────────────────────────────────────────────────
# 1. ROLE-AWARE PORTAL ROOT REDIRECT
# ─────────────────────────────────────────────────────────────

@login_required
def portal_root_redirect(request):
    """
    Directs authenticated users to their corresponding self-service portal:
    - Parent  -> /portal/parent/
    - Student -> /portal/student/
    - Teacher -> /portal/teacher/
    - Staff / Admin -> /dashboard/ (ERP dashboard)
    """
    user = request.user
    school = resolve_portal_school(request)

    if user_has_role(user, Role.PARENT) or get_parent_profile(user, school):
        return redirect('portal:parent_dashboard')

    if user_has_role(user, Role.STUDENT) or get_student_for_user(user, school):
        return redirect('portal:student_dashboard')

    if user_has_role(user, Role.TEACHER) or get_teacher_for_user(user, school):
        return redirect('portal:teacher_dashboard')

    # School admin, Principal, Accountant, Receptionist, Librarian, Transport Manager
    return redirect('index_view')


# ─────────────────────────────────────────────────────────────
# 2. PARENT PORTAL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@parent_portal_required
def parent_dashboard(request):
    """Parent dashboard displaying KPIs and recent activity for the active child."""
    school = resolve_portal_school(request)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    data = portal_selectors.get_parent_portal_dashboard(request.user, school, child)

    context = {
        'school': school,
        'portal_role': 'Parent',
        'parent_profile': get_parent_profile(request.user, school),
        **data,
    }
    return render(request, 'portal/parent/dashboard.html', context)


@login_required
@parent_portal_required
def parent_children(request):
    """Lists all children linked to the parent with quick switch options."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    selected_child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))

    children_data = []
    for c in children:
        att = portal_selectors.get_student_portal_attendance(c, school)
        fees = portal_selectors.get_student_portal_fees(c, school)
        children_data.append({
            'student': c,
            'attendance_pct': att.get('percentage', 0.0),
            'outstanding_fees': fees.get('total_outstanding', Decimal('0.00')),
            'is_selected': bool(selected_child and selected_child.id == c.id),
        })

    context = {
        'school': school,
        'children_data': children_data,
        'children': children,
        'selected_child': selected_child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
    }
    return render(request, 'portal/parent/children.html', context)


@login_required
@parent_portal_required
def parent_child_switch(request, student_id):
    """Switches the active child for the parent session with strict IDOR verification."""
    school = resolve_portal_school(request)
    # Server-side validation
    valid_child = get_parent_selected_child(request, school, student_id=student_id)
    if valid_child:
        if hasattr(request, 'session') and request.session is not None:
            request.session['portal_selected_student_id'] = valid_child.id
        messages.success(request, f"Switched view to {valid_child.name}.")
    else:
        messages.error(request, "Invalid or unauthorized student selection.")

    next_url = request.GET.get('next') or reverse('portal:parent_dashboard')
    return redirect(next_url)


@login_required
@parent_portal_required
def parent_child_detail(request, student_id):
    """Detailed profile of a specific child with verified guardian linkage."""
    school = resolve_portal_school(request)
    allowed_children = {c.id: c for c in get_parent_children(request.user, school)}

    if student_id not in allowed_children:
        raise PermissionDenied("Unauthorized child access.")

    child = allowed_children[student_id]
    guardian_profile = get_parent_profile(request.user, school)

    context = {
        'school': school,
        'child': child,
        'children': list(allowed_children.values()),
        'guardian_profile': guardian_profile,
        'parent_profile': guardian_profile,
        'selected_child': child,
        'portal_role': 'Parent',
    }
    return render(request, 'portal/parent/child_detail.html', context)


@login_required
@parent_portal_required
def parent_attendance(request):
    """Attendance metrics and history for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    att_data = portal_selectors.get_student_portal_attendance(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        **att_data,
    }
    return render(request, 'portal/parent/attendance.html', context)


@login_required
@parent_portal_required
def parent_fees(request):
    """Fee statement, installments, invoices, and payment receipts for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    fee_data = portal_selectors.get_student_portal_fees(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        **fee_data,
    }
    return render(request, 'portal/parent/fees.html', context)


@login_required
@parent_portal_required
def parent_results(request):
    """Published exam results and report card links for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    results = portal_selectors.get_student_portal_results(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        'results': results,
    }
    return render(request, 'portal/parent/results.html', context)


@login_required
@parent_portal_required
def parent_timetable(request):
    """Class and section timetable matrix for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    tt_data = portal_selectors.get_student_portal_timetable(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        **tt_data,
    }
    return render(request, 'portal/parent/timetable.html', context)


@login_required
@parent_portal_required
def parent_transport(request):
    """Transport route, stop, vehicle, and driver contact for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    transport_info = portal_selectors.get_student_portal_transport(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        'transport': transport_info,
    }
    return render(request, 'portal/parent/transport.html', context)


@login_required
@parent_portal_required
def parent_library(request):
    """Library borrowings and fine status for the active child."""
    school = resolve_portal_school(request)
    children = get_parent_children(request.user, school)
    child = get_parent_selected_child(request, school, student_id=request.GET.get('student_id'))
    lib_info = portal_selectors.get_student_portal_library(child, school)

    context = {
        'school': school,
        'children': children,
        'selected_child': child,
        'parent_profile': get_parent_profile(request.user, school),
        'portal_role': 'Parent',
        'library': lib_info,
    }
    return render(request, 'portal/parent/library.html', context)


@login_required
@parent_portal_required
def parent_profile(request):
    """Parent account and profile view."""
    school = resolve_portal_school(request)
    guardian = get_parent_profile(request.user, school)
    children = get_parent_children(request.user, school)
    selected_child = get_parent_selected_child(request, school)

    context = {
        'school': school,
        'guardian': guardian,
        'children': children,
        'selected_child': selected_child,
        'portal_role': 'Parent',
    }
    return render(request, 'portal/parent/profile.html', context)


# ─────────────────────────────────────────────────────────────
# 3. STUDENT PORTAL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@student_portal_required
def student_dashboard(request):
    """Student self-service dashboard."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    data = portal_selectors.get_student_portal_dashboard(student, school)

    context = {
        'school': school,
        'portal_role': 'Student',
        **data,
    }
    return render(request, 'portal/student/dashboard.html', context)


@login_required
@student_portal_required
def student_profile(request):
    """Student academic placement and personal profile view."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
    }
    return render(request, 'portal/student/profile.html', context)


@login_required
@student_portal_required
def student_attendance(request):
    """Student attendance summary and record history."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    att_data = portal_selectors.get_student_portal_attendance(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        **att_data,
    }
    return render(request, 'portal/student/attendance.html', context)


@login_required
@student_portal_required
def student_fees(request):
    """Student fee summary, installments, and payment receipts."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    fee_data = portal_selectors.get_student_portal_fees(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        **fee_data,
    }
    return render(request, 'portal/student/fees.html', context)


@login_required
@student_portal_required
def student_results(request):
    """Published exam results and report cards for the student."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    results = portal_selectors.get_student_portal_results(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        'results': results,
    }
    return render(request, 'portal/student/results.html', context)


@login_required
@student_portal_required
def student_timetable(request):
    """Daily and weekly class timetable schedule for the student."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    tt_data = portal_selectors.get_student_portal_timetable(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        **tt_data,
    }
    return render(request, 'portal/student/timetable.html', context)


@login_required
@student_portal_required
def student_transport(request):
    """Transport allocation, route, and driver contact for the student."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    transport_info = portal_selectors.get_student_portal_transport(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        'transport': transport_info,
    }
    return render(request, 'portal/student/transport.html', context)


@login_required
@student_portal_required
def student_library(request):
    """Student's borrowed library books and fines."""
    school = resolve_portal_school(request)
    student = get_student_for_user(request.user, school)
    lib_info = portal_selectors.get_student_portal_library(student, school)

    context = {
        'school': school,
        'student': student,
        'portal_role': 'Student',
        'library': lib_info,
    }
    return render(request, 'portal/student/library.html', context)


# ─────────────────────────────────────────────────────────────
# 4. TEACHER PORTAL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@teacher_portal_required
def teacher_dashboard(request):
    """Teacher & faculty self-service dashboard."""
    school = resolve_portal_school(request)
    data = portal_selectors.get_teacher_portal_dashboard(request.user, school)

    context = {
        'school': school,
        'portal_role': 'Teacher',
        **data,
    }
    return render(request, 'portal/teacher/dashboard.html', context)


@login_required
@teacher_portal_required
def teacher_profile(request):
    """Teacher academic profile and employee record view."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)
    employee = get_employee_for_user(request.user, school)

    context = {
        'school': school,
        'teacher': teacher,
        'employee': employee,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/profile.html', context)


@login_required
@teacher_portal_required
def teacher_timetable(request):
    """Teacher's personal daily and weekly timetable grid."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)
    tt_data = portal_selectors.get_teacher_portal_timetable(teacher, school)

    context = {
        'school': school,
        'teacher': teacher,
        'portal_role': 'Teacher',
        **tt_data,
    }
    return render(request, 'portal/teacher/timetable.html', context)


@login_required
@teacher_portal_required
def teacher_classes(request):
    """List of sections and subjects assigned to the authenticated teacher."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)
    classes = portal_selectors.get_teacher_assigned_classes(teacher, school)

    context = {
        'school': school,
        'teacher': teacher,
        'classes': classes,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/classes.html', context)


@login_required
@teacher_portal_required
def teacher_students(request):
    """Roster of students enrolled in sections assigned to the teacher."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)
    section_id = request.GET.get('section_id')
    roster = portal_selectors.get_teacher_assigned_students(teacher, school, section_id=section_id)
    classes = portal_selectors.get_teacher_assigned_classes(teacher, school)

    context = {
        'school': school,
        'teacher': teacher,
        'roster': roster,
        'classes': classes,
        'selected_section_id': int(section_id) if section_id and section_id.isdigit() else None,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/students.html', context)


@login_required
@teacher_portal_required
def teacher_attendance(request):
    """Overview of sections assigned to the teacher and pending attendance status."""
    school = resolve_portal_school(request)
    today = timezone.localdate()
    pending = attendance_selectors.get_pending_attendance_sections(
        school=school, academic_year=None, target_date=today, teacher_user=request.user
    )

    context = {
        'school': school,
        'pending_sections': pending,
        'today': today,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/attendance.html', context)


@login_required
@teacher_portal_required
def teacher_attendance_mark(request, section_id):
    """Daily attendance marking sheet for an authorized section."""
    school = resolve_portal_school(request)
    section = get_object_or_404(Section, pk=section_id, school=school)

    # Permission check via existing service
    if not attendance_service.can_user_mark_section(request.user, school, section):
        raise PermissionDenied("Unauthorized to mark attendance for this section.")

    target_date = timezone.localdate()
    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    ay = section.academic_year or AcademicYear.objects.filter(school=school, is_current=True).first()

    if request.method == 'POST':
        # Delegate to existing attendance_service
        try:
            records_data = []
            for key, val in request.POST.items():
                if key.startswith('status_'):
                    student_id = int(key.replace('status_', ''))
                    remarks = request.POST.get(f'remarks_{student_id}', '')
                    records_data.append({
                        'student_id': student_id,
                        'status': val,
                        'remarks': remarks
                    })

            if records_data:
                attendance_service.save_daily_attendance(
                    school=school,
                    academic_year=ay,
                    grade_level=section.grade_level,
                    section=section,
                    attendance_date=target_date,
                    attendance_entries=records_data,
                    actor=request.user
                )
                messages.success(request, f"Attendance recorded successfully for {section} on {target_date}.")
                return redirect('portal:teacher_attendance')
        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e))

    sheet = attendance_selectors.get_daily_attendance_sheet(
        school=school,
        academic_year=ay,
        grade_level=section.grade_level,
        section=section,
        target_date=target_date
    )

    context = {
        'school': school,
        'section': section,
        'target_date': target_date,
        'sheet': sheet,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/attendance_mark.html', context)


@login_required
@teacher_portal_required
def teacher_exams(request):
    """Assigned examination subjects and marks entry links."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)

    # Fetch active exam subjects for teacher's assigned subjects/classes
    teacher_subjects = []
    if teacher:
        teacher_subjects = list(
            SubjectAssignment.objects.filter(
                school=school, teacher=teacher, is_active=True
            ).values_list('subject_id', flat=True)
        )

    active_exams = Exam.objects.filter(
        school=school,
        status__in=[Exam.STATUS_DRAFT, Exam.STATUS_SCHEDULED, Exam.STATUS_ONGOING, Exam.STATUS_COMPLETED]
    ).select_related('grade_level', 'section', 'academic_year').order_by('-start_date')

    exam_tasks = []
    for ex in active_exams:
        exam_subjects = ex.subjects.filter(is_active=True).select_related('subject')
        if teacher and not request.user.is_superuser:
            exam_subjects = exam_subjects.filter(subject_id__in=teacher_subjects)

        for es in exam_subjects:
            can_enter = exam_service.can_user_enter_marks(request.user, school, ex, es)
            exam_tasks.append({
                'exam': ex,
                'exam_subject': es,
                'can_enter_marks': can_enter,
            })

    context = {
        'school': school,
        'exam_tasks': exam_tasks,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/exams.html', context)


@login_required
@teacher_portal_required
def teacher_leave(request):
    """Leave balance and leave request history for the teacher/employee."""
    school = resolve_portal_school(request)
    employee = get_employee_for_user(request.user, school)
    leave_summary = {'balances': [], 'recent_requests': []}
    if employee:
        leave_summary = hr_selectors.get_leave_summary(school, employee)

    context = {
        'school': school,
        'employee': employee,
        'portal_role': 'Teacher',
        **leave_summary,
    }
    return render(request, 'portal/teacher/leave.html', context)


@login_required
@teacher_portal_required
def teacher_leave_apply(request):
    """Applies for leave via existing HR leave_service."""
    school = resolve_portal_school(request)
    employee = get_employee_for_user(request.user, school)
    if not employee:
        messages.error(request, "Employee profile not found.")
        return redirect('portal:teacher_leave')

    if request.method == 'POST':
        form = LeaveApplyForm(request.POST, school=school)
        if form.is_valid():
            try:
                leave_service.apply_leave(
                    school=school,
                    employee=employee,
                    leave_type=form.cleaned_data['leave_type'],
                    start_date=form.cleaned_data['start_date'],
                    end_date=form.cleaned_data['end_date'],
                    reason=form.cleaned_data['reason']
                )
                messages.success(request, "Leave request submitted successfully.")
                return redirect('portal:teacher_leave')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = LeaveApplyForm(school=school)

    context = {
        'school': school,
        'employee': employee,
        'form': form,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/leave_apply.html', context)


@login_required
@teacher_portal_required
def teacher_payslips(request):
    """Payslip statements for the authenticated teacher/employee."""
    school = resolve_portal_school(request)
    employee = get_employee_for_user(request.user, school)
    payslips = []
    if employee:
        payslips = list(
            PayrollRecord.objects.filter(school=school, employee=employee)
            .select_related('payroll_period')
            .order_by('-payroll_period__year', '-payroll_period__month')
        )

    context = {
        'school': school,
        'employee': employee,
        'payslips': payslips,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/payslips.html', context)


@login_required
@teacher_portal_required
def teacher_library(request):
    """Teacher's personal library pass, borrowings, and history."""
    school = resolve_portal_school(request)
    teacher = get_teacher_for_user(request.user, school)
    member = LibraryMember.objects.filter(school=school, teacher=teacher, is_active=True).first() if teacher else None

    active_issues = []
    fines = Decimal('0.00')
    history = []
    if member:
        active_issues = list(LibraryIssue.objects.filter(member=member, status=LibraryIssue.STATUS_ISSUED).select_related('book_copy', 'book_copy__book'))
        fines = LibraryFine.objects.filter(issue__member=member, paid=False).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')
        history = list(LibraryIssue.objects.filter(member=member).select_related('book_copy', 'book_copy__book').order_by('-issue_date')[:20])

    context = {
        'school': school,
        'member': member,
        'active_issues': active_issues,
        'fines': fines,
        'history': history,
        'portal_role': 'Teacher',
    }
    return render(request, 'portal/teacher/library.html', context)


# ─────────────────────────────────────────────────────────────
# 5. SHARED VIEWS (NOTICES & PROFILE)
# ─────────────────────────────────────────────────────────────

@login_required
def portal_notices(request):
    """Notices listing accessible across all portals."""
    school = resolve_portal_school(request)
    notices = portal_selectors.get_portal_notices(school, request.user, limit=30)
    context = {
        'school': school,
        'notices': notices,
    }
    return render(request, 'portal/notices.html', context)


@login_required
def portal_notice_detail(request, pk):
    """Detailed view of a school notice."""
    school = resolve_portal_school(request)
    notice = get_object_or_404(Notice, pk=pk)
    context = {
        'school': school,
        'notice': notice,
    }
    return render(request, 'portal/notice_detail.html', context)


@login_required
def portal_profile(request):
    """Redirects to user's role-specific profile."""
    user = request.user
    school = resolve_portal_school(request)

    if user_has_role(user, Role.PARENT) or get_parent_profile(user, school):
        return redirect('portal:parent_profile')
    if user_has_role(user, Role.STUDENT) or get_student_for_user(user, school):
        return redirect('portal:student_profile')
    if user_has_role(user, Role.TEACHER) or get_teacher_for_user(user, school):
        return redirect('portal:teacher_profile')

    return redirect('index_view')
