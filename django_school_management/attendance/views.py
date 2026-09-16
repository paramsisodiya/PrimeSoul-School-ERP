import csv
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.accounts.permissions import require_school_access
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student
from django_school_management.attendance.models import AttendanceRecord, AttendanceCorrectionLog
from django_school_management.attendance.forms import (
    DailyAttendanceFilterForm, AttendanceCorrectionForm, AttendanceHistoryFilterForm
)
from django_school_management.attendance.services.attendance_service import (
    save_daily_attendance, correct_attendance_record, can_user_mark_section, bulk_mark_all_status
)
from django_school_management.attendance.selectors.attendance_selectors import (
    get_attendance_dashboard_metrics, get_daily_attendance_sheet,
    get_attendance_history_queryset, get_student_attendance_summary,
    get_monthly_attendance_summary, get_low_attendance_students,
    get_pending_attendance_sections
)


def _resolve_school(request):
    """Resolves active school tenant from request or logged-in user."""
    if hasattr(request, 'school') and request.school:
        return request.school
    user = request.user
    if user.is_authenticated and hasattr(user, 'school') and user.school:
        return user.school
    if user.is_superuser:
        return School.objects.filter(is_active=True).first()
    return None


@login_required
def attendance_dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "No active school tenant context found.")
        return redirect('index_view')

    # Student and parent role redirection
    if user_has_role(request.user, Role.STUDENT):
        return redirect('attendance:student_profile')
    if user_has_role(request.user, Role.PARENT):
        return redirect('attendance:student_profile')

    target_date_str = request.GET.get('date')
    if target_date_str:
        try:
            target_date = datetime.date.fromisoformat(target_date_str)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    metrics = get_attendance_dashboard_metrics(school, target_date)
    
    # Teacher-scoped pending view if teacher
    is_teacher = user_has_role(request.user, Role.TEACHER) and not user_has_role(request.user, Role.SCHOOL_ADMIN)
    pending_sections = get_pending_attendance_sections(
        school,
        metrics.get('current_year'),
        target_date,
        teacher_user=request.user if is_teacher else None
    )

    context = {
        'school': school,
        'metrics': metrics,
        'target_date': target_date,
        'pending_sections': pending_sections[:10],
        'is_teacher': is_teacher,
    }
    return render(request, 'attendance/dashboard.html', context)


@login_required
def mark_daily_attendance(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    # RBAC check: Accountant, Receptionist, Student, Parent cannot mark attendance
    if (
        user_has_role(request.user, Role.ACCOUNTANT) or
        user_has_role(request.user, Role.RECEPTIONIST) or
        user_has_role(request.user, Role.STUDENT) or
        user_has_role(request.user, Role.PARENT)
    ) and not (request.user.is_superuser or user_has_role(request.user, Role.SCHOOL_ADMIN)):
        raise PermissionDenied("You do not have permission to mark attendance.")

    filter_form = DailyAttendanceFilterForm(school, request.GET or None)
    
    academic_year = None
    grade_level = None
    section = None
    attendance_date = timezone.localdate()
    sheet = []
    can_mark = False

    # Check query params or defaults
    ay_id = request.GET.get('academic_year')
    gl_id = request.GET.get('grade_level')
    sec_id = request.GET.get('section')
    dt_str = request.GET.get('attendance_date')

    if dt_str:
        try:
            attendance_date = datetime.date.fromisoformat(dt_str)
        except ValueError:
            attendance_date = timezone.localdate()

    if ay_id and gl_id and sec_id:
        try:
            academic_year = AcademicYear.objects.get(id=ay_id, school=school)
            grade_level = GradeLevel.objects.get(id=gl_id, school=school)
            section = Section.objects.get(id=sec_id, school=school, grade_level=grade_level)
            can_mark = can_user_mark_section(request.user, school, section)
            sheet = get_daily_attendance_sheet(school, academic_year, grade_level, section, attendance_date)
        except (AcademicYear.DoesNotExist, GradeLevel.DoesNotExist, Section.DoesNotExist):
            messages.error(request, "Selected session, class, or section is invalid.")

    if request.method == 'POST':
        post_ay_id = request.POST.get('academic_year')
        post_gl_id = request.POST.get('grade_level')
        post_sec_id = request.POST.get('section')
        post_dt_str = request.POST.get('attendance_date')

        try:
            p_ay = AcademicYear.objects.get(id=post_ay_id, school=school)
            p_gl = GradeLevel.objects.get(id=post_gl_id, school=school)
            p_sec = Section.objects.get(id=post_sec_id, school=school, grade_level=p_gl)
            p_date = datetime.date.fromisoformat(post_dt_str)
        except Exception as e:
            messages.error(request, f"Submission error: {e}")
            return redirect(request.get_full_path())

        # Collect attendance rows
        entries = []
        for key, value in request.POST.items():
            if key.startswith('status_'):
                s_id = key.split('_')[1]
                rem = request.POST.get(f'remarks_{s_id}', '')
                corr_reason = request.POST.get(f'corr_reason_{s_id}', '')
                entries.append({
                    'student_id': int(s_id),
                    'status': value,
                    'remarks': rem,
                    'correction_reason': corr_reason
                })

        action = request.POST.get('action')
        try:
            if action == 'mark_all_present':
                res = bulk_mark_all_status(
                    school=school,
                    academic_year=p_ay,
                    grade_level=p_gl,
                    section=p_sec,
                    attendance_date=p_date,
                    target_status=AttendanceRecord.STATUS_PRESENT,
                    actor=request.user
                )
                messages.success(request, f"Marked all {res['total_processed']} students as Present.")
            else:
                res = save_daily_attendance(
                    school=school,
                    academic_year=p_ay,
                    grade_level=p_gl,
                    section=p_sec,
                    attendance_date=p_date,
                    attendance_entries=entries,
                    actor=request.user
                )
                messages.success(
                    request,
                    f"Attendance saved: {res['created_count']} recorded, {res['updated_count']} updated ({res['total_processed']} total)."
                )
        except (ValidationError, PermissionDenied) as err:
            messages.error(request, f"Attendance error: {err}")

        # Redirect with current parameters
        return redirect(f"{request.path}?academic_year={p_ay.id}&grade_level={p_gl.id}&section={p_sec.id}&attendance_date={p_date}")

    context = {
        'school': school,
        'filter_form': filter_form,
        'academic_year': academic_year,
        'grade_level': grade_level,
        'section': section,
        'attendance_date': attendance_date,
        'sheet': sheet,
        'can_mark': can_mark,
        'status_choices': AttendanceRecord.STATUS_CHOICES,
    }
    return render(request, 'attendance/mark.html', context)


@login_required
def attendance_history(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    form = AttendanceHistoryFilterForm(school, request.GET or None)
    filters = {}

    # Scoping for student and parent
    if user_has_role(request.user, Role.STUDENT):
        st = Student.objects.filter(school=school, user=request.user).first()
        if st:
            filters['student_id'] = st.id
        else:
            filters['student_id'] = -1
    elif user_has_role(request.user, Role.PARENT):
        child_ids = Student.objects.filter(
            school=school,
            guardian_relationships__guardian__user=request.user
        ).values_list('id', flat=True)
        # Handle child filter if provided
        req_child = request.GET.get('student_id')
        if req_child and int(req_child) in child_ids:
            filters['student_id'] = int(req_child)
        else:
            pass  # Or scope below

    if request.GET.get('academic_year'):
        filters['academic_year_id'] = request.GET.get('academic_year')
    if request.GET.get('grade_level'):
        filters['grade_level_id'] = request.GET.get('grade_level')
    if request.GET.get('section'):
        filters['section_id'] = request.GET.get('section')
    if request.GET.get('status'):
        filters['status'] = request.GET.get('status')
    if request.GET.get('start_date'):
        filters['start_date'] = request.GET.get('start_date')
    if request.GET.get('end_date'):
        filters['end_date'] = request.GET.get('end_date')
    if request.GET.get('search'):
        filters['search'] = request.GET.get('search')

    qs = get_attendance_history_queryset(school, filters)

    # If parent without specific child selected, filter to their children
    if user_has_role(request.user, Role.PARENT) and 'student_id' not in filters:
        qs = qs.filter(student__guardian_relationships__guardian__user=request.user)

    paginator = Paginator(qs, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'school': school,
        'form': form,
        'page_obj': page_obj,
        'total_count': paginator.count,
    }
    return render(request, 'attendance/history.html', context)


@login_required
def student_attendance_view(request, student_id=None):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    student = None
    if student_id:
        student = get_object_or_404(Student, id=student_id, school=school)
    else:
        if user_has_role(request.user, Role.STUDENT):
            student = Student.objects.filter(school=school, user=request.user).first()
        elif user_has_role(request.user, Role.PARENT):
            student = Student.objects.filter(school=school, guardian_relationships__guardian__user=request.user).first()
        else:
            first_st = Student.objects.filter(school=school, is_active=True).first()
            if first_st:
                return redirect('attendance:student_attendance', student_id=first_st.id)

    if not student:
        messages.warning(request, "No linked student profile found for your account.")
        return redirect('index_view')

    # Security check: if student, cannot view other students
    if user_has_role(request.user, Role.STUDENT) and student.user != request.user:
        raise PermissionDenied("You can only view your own attendance profile.")

    # Security check: if parent, can only view own children
    if user_has_role(request.user, Role.PARENT):
        is_child = Student.objects.filter(
            id=student.id,
            school=school,
            guardian_relationships__guardian__user=request.user
        ).exists()
        if not is_child:
            raise PermissionDenied("You can only view attendance for your registered children.")

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    summary = get_student_attendance_summary(school, student, current_year)

    context = {
        'school': school,
        'student': student,
        'summary': summary,
        'current_year': current_year,
    }
    return render(request, 'attendance/student_profile.html', context)


@login_required
def monthly_attendance_summary_view(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    today = timezone.localdate()
    
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    ay_id = request.GET.get('academic_year', getattr(current_year, 'id', None))
    gl_id = request.GET.get('grade_level')
    sec_id = request.GET.get('section')

    years_list = AcademicYear.objects.filter(school=school).order_by('-start_date')
    classes_list = GradeLevel.objects.filter(school=school, is_active=True).order_by('display_order')
    sections_list = Section.objects.filter(school=school, is_active=True).order_by('grade_level__display_order', 'name')

    rows = []
    selected_gl = None
    selected_sec = None
    selected_ay = None

    if ay_id and gl_id and sec_id:
        try:
            selected_ay = AcademicYear.objects.get(id=ay_id, school=school)
            selected_gl = GradeLevel.objects.get(id=gl_id, school=school)
            selected_sec = Section.objects.get(id=sec_id, school=school, grade_level=selected_gl)
            rows = get_monthly_attendance_summary(school, selected_ay, selected_gl, selected_sec, year, month)
        except Exception:
            messages.error(request, "Invalid class/section selection for monthly summary.")

    months_choices = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    context = {
        'school': school,
        'years_list': years_list,
        'classes_list': classes_list,
        'sections_list': sections_list,
        'selected_ay': selected_ay,
        'selected_gl': selected_gl,
        'selected_sec': selected_sec,
        'year': year,
        'month': month,
        'months_choices': months_choices,
        'rows': rows,
    }
    return render(request, 'attendance/monthly.html', context)


@login_required
def low_attendance_alerts_view(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    try:
        threshold = float(request.GET.get('threshold', 75.0))
    except ValueError:
        threshold = 75.0

    low_students = get_low_attendance_students(school, current_year, threshold=threshold)

    context = {
        'school': school,
        'current_year': current_year,
        'threshold': threshold,
        'low_students': low_students,
        'total_low': len(low_students),
    }
    return render(request, 'attendance/low_attendance.html', context)


@login_required
def pending_attendance_view(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "Tenant school required.")
        return redirect('index_view')

    dt_str = request.GET.get('date')
    if dt_str:
        try:
            target_date = datetime.date.fromisoformat(dt_str)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    is_teacher = user_has_role(request.user, Role.TEACHER) and not user_has_role(request.user, Role.SCHOOL_ADMIN)
    
    sections = get_pending_attendance_sections(
        school,
        current_year,
        target_date,
        teacher_user=request.user if is_teacher else None
    )

    context = {
        'school': school,
        'target_date': target_date,
        'current_year': current_year,
        'sections': sections,
        'is_teacher': is_teacher,
    }
    return render(request, 'attendance/pending.html', context)


@login_required
def correct_attendance_view(request, record_id):
    school = _resolve_school(request)
    if not school:
        return HttpResponseForbidden("School tenant required.")

    record = get_object_or_404(AttendanceRecord, id=record_id, school=school)
    
    if request.method == 'POST':
        form = AttendanceCorrectionForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['new_status']
            reason = form.cleaned_data['reason']
            try:
                correct_attendance_record(record, new_status, reason, request.user)
                messages.success(request, f"Attendance record updated for {record.student.name} to {new_status}.")
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, f"Correction failed: {e}")
        else:
            messages.error(request, "Please provide a valid correction reason.")

    return redirect(request.META.get('HTTP_REFERER', 'attendance:dashboard'))


# ─────────────────────────────────────────────────────────────
# CSV Exports
# ─────────────────────────────────────────────────────────────

@login_required
def export_daily_csv(request):
    school = _resolve_school(request)
    if not school:
        return HttpResponseForbidden()

    ay_id = request.GET.get('academic_year')
    gl_id = request.GET.get('grade_level')
    sec_id = request.GET.get('section')
    dt_str = request.GET.get('attendance_date')

    target_date = datetime.date.fromisoformat(dt_str) if dt_str else timezone.localdate()
    ay = get_object_or_404(AcademicYear, id=ay_id, school=school)
    gl = get_object_or_404(GradeLevel, id=gl_id, school=school)
    sec = get_object_or_404(Section, id=sec_id, school=school, grade_level=gl)

    sheet = get_daily_attendance_sheet(school, ay, gl, sec, target_date)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{gl.name}_{sec.name}_{target_date}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Roll No', 'Student Name', 'Admission No', 'Class', 'Section', 'Date', 'Status', 'Remarks'])

    for row in sheet:
        writer.writerow([
            row['roll_number'],
            row['student_name'],
            row['admission_number'],
            gl.name,
            sec.name,
            str(target_date),
            row['status'],
            row['remarks']
        ])

    return response


@login_required
def export_monthly_csv(request):
    school = _resolve_school(request)
    if not school:
        return HttpResponseForbidden()

    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    ay_id = request.GET.get('academic_year')
    gl_id = request.GET.get('grade_level')
    sec_id = request.GET.get('section')

    ay = get_object_or_404(AcademicYear, id=ay_id, school=school)
    gl = get_object_or_404(GradeLevel, id=gl_id, school=school)
    sec = get_object_or_404(Section, id=sec_id, school=school, grade_level=gl)

    rows = get_monthly_attendance_summary(school, ay, gl, sec, year, month)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="monthly_attendance_{gl.name}_{sec.name}_{year}_{month:02d}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Roll No', 'Student Name', 'Total Days', 'Present', 'Absent', 'Late', 'Half Day', 'Excused', 'Percentage (%)'])

    for r in rows:
        writer.writerow([
            r['roll_number'],
            r['student_name'],
            r['total_days'],
            r['present_days'],
            r['absent_days'],
            r['late_days'],
            r['half_days'],
            r['excused_days'],
            f"{r['percentage']}%"
        ])

    return response


@login_required
def export_low_attendance_csv(request):
    school = _resolve_school(request)
    if not school:
        return HttpResponseForbidden()

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    try:
        threshold = float(request.GET.get('threshold', 75.0))
    except ValueError:
        threshold = 75.0

    low_students = get_low_attendance_students(school, current_year, threshold=threshold)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="low_attendance_report_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Admission No', 'Student Name', 'Class', 'Section', 'Total Marked Days', 'Present', 'Absent', 'Attendance %'])

    for item in low_students:
        st = item['student']
        adm = getattr(st, 'admission_number', '') or getattr(st, 'admission_student_id', '')
        writer.writerow([
            adm,
            st.name,
            item['grade_level'],
            item['section'],
            item['total_days'],
            item['present_days'],
            item['absent_days'],
            f"{item['percentage']}%"
        ])

    return response
