"""
PrimeSoul School ERP - Phase 17: Advanced Reports & Analytics Views
Role-aware, tenant-isolated reporting dashboard with live DB aggregation
and multi-format export engine (CSV and ReportLab PDF).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import timezone

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.examinations.models import Exam
from django_school_management.admissions.models import AdmissionSession
from django_school_management.reports.selectors import report_selectors
from django_school_management.reports.services import export_service


def _resolve_school(request) -> School:
    """Safely extracts tenant School from request context or user attributes."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated:
        user_school = getattr(request.user, 'school', None)
        if user_school:
            return user_school
    return School.objects.filter(is_active=True).first()


def _check_reports_access(user, module: str = 'general') -> bool:
    """
    Strict RBAC validation for Reports module.
    Parents and Students are strictly blocked from administrative reports.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # Block parent & student unconditionally
    if user_has_role(user, Role.PARENT, Role.STUDENT):
        return False

    # Broad administrative roles
    if user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL):
        return True

    # Module-specific role permissions
    if module in ['finance', 'inventory', 'general'] and user_has_role(user, Role.ACCOUNTANT):
        return True

    if module in ['academics', 'attendance', 'examinations', 'general'] and user_has_role(user, Role.ACADEMIC_COORDINATOR, Role.TEACHER):
        return True

    if module in ['admissions', 'general'] and user_has_role(user, Role.RECEPTIONIST):
        return True

    if module in ['transport', 'general'] and user_has_role(user, Role.TRANSPORT_MANAGER):
        return True

    if module in ['library', 'general'] and user_has_role(user, Role.LIBRARIAN):
        return True

    return False


# ==============================================================================
# 1. EXECUTIVE DASHBOARD
# ==============================================================================

@login_required
def executive_dashboard(request):
    """
    School Executive Command Hub: Aggregated KPIs across all 9 ERP modules.
    """
    if not _check_reports_access(request.user, module='general'):
        raise PermissionDenied("Access to reporting hub is restricted to authorized school staff.")

    school = _resolve_school(request)
    kpis = report_selectors.get_executive_dashboard_kpis(school)

    context = {
        'school': school,
        'kpis': kpis,
        'is_admin': user_has_role(request.user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL) or request.user.is_superuser,
    }
    return render(request, 'reports/dashboard.html', context)


# ==============================================================================
# 2. FINANCE REPORTS
# ==============================================================================

@login_required
def finance_reports(request):
    if not _check_reports_access(request.user, module='finance'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    academic_year_id = request.GET.get('academic_year')
    payment_method = request.GET.get('payment_method')
    status = request.GET.get('status')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_finance_reports(
        school=school,
        start_date=start_date,
        end_date=end_date,
        academic_year_id=int(academic_year_id) if academic_year_id else None,
        payment_method=payment_method,
        status=status
    )

    if export_fmt == 'csv':
        headers = ['Receipt No', 'Date', 'Student Name', 'Admission No', 'Amount Paid (₹)', 'Payment Method', 'Issued By']
        rows = [
            [
                r.receipt_number,
                r.receipt_date.strftime('%d-%m-%Y'),
                r.student.get_full_name() if r.student else '',
                getattr(r.student, 'admission_number', ''),
                r.amount,
                r.payment_method,
                r.issued_by.get_full_name() if r.issued_by else ''
            ]
            for r in data['receipts_list']
        ]
        return export_service.export_to_csv('Finance_Fee_Receipts_Report', headers, rows)

    elif export_fmt == 'pdf':
        headers = ['Receipt No', 'Date', 'Student', 'Amount (₹)', 'Method', 'Issued By']
        rows = [
            [
                r.receipt_number,
                r.receipt_date.strftime('%d-%m-%Y'),
                r.student.get_full_name() if r.student else '',
                f"₹{r.amount}",
                r.payment_method,
                r.issued_by.get_full_name() if r.issued_by else ''
            ]
            for r in data['receipts_list']
        ]
        return export_service.export_to_pdf(
            school.name,
            'Fee Collection & Receipts Statement',
            headers,
            rows,
            'Finance_Collection_Statement',
            filters_summary=f"Date: {start_date or 'All'} to {end_date or 'All'}"
        )

    academic_years = AcademicYear.objects.filter(school=school)
    return render(request, 'reports/finance.html', {
        'school': school,
        'data': data,
        'academic_years': academic_years,
        'selected_year': academic_year_id,
        'start_date': start_date,
        'end_date': end_date,
        'selected_method': payment_method,
        'selected_status': status,
    })


# ==============================================================================
# 3. ACADEMIC REPORTS
# ==============================================================================

@login_required
def academic_reports(request):
    if not _check_reports_access(request.user, module='academics'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    academic_year_id = request.GET.get('academic_year')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_academic_reports(school, int(academic_year_id) if academic_year_id else None)

    if export_fmt == 'csv':
        headers = ['Class / Grade', 'Total Students', 'Sections Breakdown']
        rows = [
            [
                c['name'],
                c['total_students'],
                ', '.join([f"{s['name']}: {s['student_count']}" for s in c['sections']])
            ]
            for c in data['class_strengths']
        ]
        return export_service.export_to_csv('Academic_Class_Strength_Report', headers, rows)

    elif export_fmt == 'pdf':
        headers = ['Class / Grade', 'Total Students', 'Sections Breakdown']
        rows = [
            [
                c['name'],
                c['total_students'],
                ', '.join([f"{s['name']}: {s['student_count']}" for s in c['sections']])
            ]
            for c in data['class_strengths']
        ]
        return export_service.export_to_pdf(
            school.name,
            'Student Enrollment & Class Strength Report',
            headers,
            rows,
            'Academic_Class_Strength_Report'
        )

    academic_years = AcademicYear.objects.filter(school=school)
    return render(request, 'reports/academics.html', {
        'school': school,
        'data': data,
        'academic_years': academic_years,
        'selected_year': academic_year_id,
    })


# ==============================================================================
# 4. ATTENDANCE REPORTS
# ==============================================================================

@login_required
def attendance_reports(request):
    if not _check_reports_access(request.user, module='attendance'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    date_str = request.GET.get('date')
    grade_id = request.GET.get('grade')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_attendance_reports(
        school=school,
        date=date_str,
        grade_id=int(grade_id) if grade_id else None
    )

    if export_fmt == 'csv':
        headers = ['Date', 'Student Name', 'Grade', 'Section', 'Status', 'Remarks']
        rows = [
            [
                r.attendance_date.strftime('%d-%m-%Y'),
                r.student.get_full_name() if r.student else '',
                r.grade_level.name if r.grade_level else '',
                r.section.name if r.section else '',
                r.get_status_display(),
                getattr(r, 'remarks', '') or ''
            ]
            for r in data['attendance_records']
        ]
        return export_service.export_to_csv('Daily_Attendance_Report', headers, rows)

    elif export_fmt == 'pdf':
        headers = ['Date', 'Student', 'Grade', 'Section', 'Status']
        rows = [
            [
                r.attendance_date.strftime('%d-%m-%Y'),
                r.student.get_full_name() if r.student else '',
                r.grade_level.name if r.grade_level else '',
                r.section.name if r.section else '',
                r.get_status_display()
            ]
            for r in data['attendance_records']
        ]
        return export_service.export_to_pdf(
            school.name,
            f"Daily Attendance Report ({data['date']})",
            headers,
            rows,
            'Daily_Attendance_Report'
        )

    grades = GradeLevel.objects.filter(school=school, is_active=True)
    return render(request, 'reports/attendance.html', {
        'school': school,
        'data': data,
        'grades': grades,
        'selected_grade': grade_id,
        'selected_date': date_str or str(timezone.now().date()),
    })


# ==============================================================================
# 5. EXAMINATION REPORTS
# ==============================================================================

@login_required
def examination_reports(request):
    if not _check_reports_access(request.user, module='examinations'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    exam_id = request.GET.get('exam')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_examination_reports(school, int(exam_id) if exam_id else None)

    if export_fmt == 'csv' and data.get('results_list'):
        headers = ['Rank', 'Student Name', 'Roll No', 'Class', 'Total Marks', 'Percentage', 'Grade', 'Result']
        rows = [
            [
                r.class_rank or '-',
                r.student.get_full_name() if r.student else '',
                getattr(r.student, 'roll_number', ''),
                r.exam.grade_level.name if r.exam and r.exam.grade_level else '',
                r.total_marks_obtained,
                f"{r.percentage}%",
                r.overall_grade or '-',
                'Passed' if r.result_status == 'PASSED' else 'Failed'
            ]
            for r in data['results_list']
        ]
        return export_service.export_to_csv('Examination_Performance_Report', headers, rows)

    elif export_fmt == 'pdf' and data.get('results_list'):
        headers = ['Rank', 'Student', 'Class', 'Marks', 'Percentage', 'Result']
        rows = [
            [
                r.class_rank or '-',
                r.student.get_full_name() if r.student else '',
                r.exam.grade_level.name if r.exam and r.exam.grade_level else '',
                str(r.total_marks_obtained),
                f"{r.percentage}%",
                'Passed' if r.result_status == 'PASSED' else 'Failed'
            ]
            for r in data['results_list']
        ]
        exam_name = data['selected_exam'].name if data.get('selected_exam') else 'Examination'
        return export_service.export_to_pdf(
            school.name,
            f"Examination Performance Statement - {exam_name}",
            headers,
            rows,
            'Exam_Performance_Report'
        )

    return render(request, 'reports/examinations.html', {
        'school': school,
        'data': data,
        'selected_exam_id': exam_id,
    })


# ==============================================================================
# 6. ADMISSIONS ANALYTICS
# ==============================================================================

@login_required
def admissions_reports(request):
    if not _check_reports_access(request.user, module='admissions'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    session_id = request.GET.get('session')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_admissions_reports(school, int(session_id) if session_id else None)

    if export_fmt == 'csv':
        headers = ['Grade / Class', 'Total Applications', 'Admitted Students']
        rows = [
            [cw['grade_level__name'] or 'General', cw['total'], cw['admitted']]
            for cw in data['class_wise']
        ]
        return export_service.export_to_csv('Admissions_Funnel_Report', headers, rows)

    return render(request, 'reports/admissions.html', {
        'school': school,
        'data': data,
        'selected_session_id': session_id,
    })


# ==============================================================================
# 7. TRANSPORT REPORTS
# ==============================================================================

@login_required
def transport_reports(request):
    if not _check_reports_access(request.user, module='transport'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    export_fmt = request.GET.get('export')
    data = report_selectors.get_transport_reports(school)

    if export_fmt == 'csv':
        headers = ['Route Name', 'Vehicle', 'Capacity', 'Allocated Students', 'Utilization %']
        rows = [
            [r['name'], r['vehicle'], r['capacity'], r['allocated'], f"{r['utilization']}%"]
            for r in data['routes_summary']
        ]
        return export_service.export_to_csv('Transport_Route_Utilization_Report', headers, rows)

    return render(request, 'reports/transport.html', {'school': school, 'data': data})


# ==============================================================================
# 8. LIBRARY REPORTS
# ==============================================================================

@login_required
def library_reports(request):
    if not _check_reports_access(request.user, module='library'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    export_fmt = request.GET.get('export')
    data = report_selectors.get_library_reports(school)

    if export_fmt == 'csv':
        headers = ['Book Title', 'Accession No', 'Member Name', 'Issue Date', 'Due Date']
        rows = [
            [
                o.book_copy.book.title,
                o.book_copy.accession_number,
                o.member.user.get_full_name() if o.member and o.member.user else 'Member',
                o.issue_date.strftime('%d-%m-%Y'),
                o.due_date.strftime('%d-%m-%Y')
            ]
            for o in data['overdue_list']
        ]
        return export_service.export_to_csv('Library_Overdue_Books_Report', headers, rows)

    return render(request, 'reports/library.html', {'school': school, 'data': data})


# ==============================================================================
# 9. HR & PAYROLL REPORTS (PII MASKED)
# ==============================================================================

@login_required
def hr_reports(request):
    if not _check_reports_access(request.user, module='general'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    export_fmt = request.GET.get('export')
    data = report_selectors.get_hr_reports(school)

    if export_fmt == 'csv':
        headers = ['Employee ID', 'Staff Name', 'Department', 'Designation', 'Role Type', 'PAN (Masked)', 'Bank Acc (Masked)']
        rows = [
            [
                e['employee_id'],
                e['full_name'],
                e['department'],
                e['designation'],
                e['role_type'],
                e['pan_masked'],
                e['bank_masked']
            ]
            for e in data['employees_list']
        ]
        return export_service.export_to_csv('HR_Staff_Headcount_Report', headers, rows)

    return render(request, 'reports/hr.html', {'school': school, 'data': data})


# ==============================================================================
# 10. INVENTORY REPORTS
# ==============================================================================

@login_required
def inventory_reports(request):
    if not _check_reports_access(request.user, module='inventory'):
        raise PermissionDenied("Access restricted.")

    school = _resolve_school(request)
    report_type = request.GET.get('report', 'current_stock')
    export_fmt = request.GET.get('export')

    data = report_selectors.get_inventory_reports(school, report_type=report_type)

    if export_fmt == 'csv':
        if report_type == 'asset_register':
            headers = ['Asset Tag', 'Asset Name', 'Category', 'Location', 'Purchase Cost (₹)', 'Status', 'Condition']
            rows = [
                [a.asset_tag, a.name, a.category.name, a.current_location or 'Storage', a.purchase_cost, a.get_status_display(), a.get_condition_display()]
                for a in data['assets']
            ]
            return export_service.export_to_csv('Fixed_Asset_Register_Report', headers, rows)
        else:
            headers = ['SKU', 'Item Name', 'Category', 'Unit', 'Reorder Level', 'Current Total Stock']
            rows = [
                [i.sku, i.name, i.category.name, i.unit.short_code, i.reorder_level, i.current_stock]
                for i in data['items']
            ]
            return export_service.export_to_csv('Inventory_Stock_Balances_Report', headers, rows)

    return render(request, 'reports/inventory.html', {
        'school': school,
        'data': data,
        'report_type': report_type,
    })
