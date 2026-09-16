"""
PrimeSoul HR & Payroll - UI Views Layer
Tenant-scoped, RBAC-protected views with support for full staff operations, leave workflows, payroll processing, and employee self-portal.
"""
import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord, PayrollLineItem
)
from django_school_management.hr.forms import (
    DepartmentForm, HRDesignationForm, EmployeeForm, EmployeeDocumentForm,
    LeaveTypeForm, LeaveRequestForm, SalaryComponentForm, PayrollPeriodForm
)
from django_school_management.hr.services import (
    employee_service, leave_service, attendance_service, payroll_service
)
from django_school_management.hr.selectors import hr_selectors


def _resolve_school(request):
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


def _check_hr_management_perm(user):
    """Verifies administrative management privileges for HR."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_has_role(
        user,
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.ACCOUNTANT
    )


def _check_payroll_perm(user):
    """Verifies payroll processing and financial record management privileges."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_has_role(
        user,
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.ACCOUNTANT
    )


@login_required
def hr_dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "No active school context.")
        return redirect('dashboard')

    if not _check_hr_management_perm(request.user):
        return redirect('hr:my_hr')

    metrics = hr_selectors.get_hr_dashboard_metrics(school)
    recent_employees = Employee.objects.filter(school=school).select_related('designation', 'department').order_by('-joining_date')[:5]
    pending_leaves = LeaveRequest.objects.filter(school=school, status='PENDING').select_related('employee', 'leave_type')[:5]
    expiry_alerts = hr_selectors.get_document_expiry_alerts(school, days_threshold=30)[:5]

    context = {
        'metrics': metrics,
        'recent_employees': recent_employees,
        'pending_leaves': pending_leaves,
        'expiry_alerts': expiry_alerts,
        'page_title': 'HR & Payroll Dashboard'
    }
    return render(request, 'hr/dashboard.html', context)


@login_required
def employee_list(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    dept_id = request.GET.get('department')
    desig_id = request.GET.get('designation')
    status_filter = request.GET.get('status')
    query = request.GET.get('q', '').strip()

    employees = hr_selectors.get_employee_list(
        school=school,
        department_id=int(dept_id) if dept_id else None,
        designation_id=int(desig_id) if desig_id else None,
        status=status_filter,
        search_query=query
    )

    departments = Department.objects.filter(school=school, is_active=True)
    designations = HRDesignation.objects.filter(school=school, is_active=True)

    context = {
        'employees': employees,
        'departments': departments,
        'designations': designations,
        'query': query,
        'selected_dept': dept_id,
        'selected_desig': desig_id,
        'selected_status': status_filter,
        'page_title': 'Employee Directory'
    }
    return render(request, 'hr/employees.html', context)


@login_required
def employee_detail(request, pk):
    school = _resolve_school(request)
    employee = get_object_or_404(Employee, school=school, pk=pk)

    # Check permission
    can_manage = _check_hr_management_perm(request.user)
    is_self = (employee.user_id == request.user.pk)
    if not can_manage and not is_self:
        raise PermissionDenied()

    documents = EmployeeDocument.objects.filter(school=school, employee=employee, is_active=True)
    leave_balances = LeaveBalance.objects.filter(school=school, employee=employee).select_related('leave_type')
    payslips = PayrollRecord.objects.filter(school=school, employee=employee).select_related('payroll_period').order_by('-payroll_period__year', '-payroll_period__month')[:12]

    context = {
        'employee': employee,
        'documents': documents,
        'leave_balances': leave_balances,
        'payslips': payslips,
        'can_manage': can_manage,
        'page_title': f"{employee.full_name} ({employee.employee_code})"
    }
    return render(request, 'hr/employee_detail.html', context)


@login_required
def employee_create(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            try:
                emp = form.save(commit=False)
                emp.school = school
                emp.save()
                messages.success(request, f"Employee '{emp.full_name}' ({emp.employee_code}) created successfully.")
                return redirect('hr:employee_detail', pk=emp.pk)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = EmployeeForm(school=school)

    return render(request, 'hr/employee_form.html', {'form': form, 'page_title': 'Add New Employee'})


@login_required
def employee_edit(request, pk):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    emp = get_object_or_404(Employee, school=school, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=emp, school=school)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Employee '{emp.full_name}' updated.")
                return redirect('hr:employee_detail', pk=emp.pk)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = EmployeeForm(instance=emp, school=school)

    return render(request, 'hr/employee_form.html', {'form': form, 'page_title': f'Edit Employee: {emp.full_name}'})


@login_required
def department_list(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    departments = Department.objects.filter(school=school)
    form = DepartmentForm()

    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.school = school
            dept.save()
            messages.success(request, f"Department '{dept.name}' created.")
            return redirect('hr:departments')

    context = {
        'departments': departments,
        'form': form,
        'page_title': 'Departments'
    }
    return render(request, 'hr/departments.html', context)


@login_required
def designation_list(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    designations = HRDesignation.objects.filter(school=school)
    form = HRDesignationForm()

    if request.method == 'POST':
        form = HRDesignationForm(request.POST)
        if form.is_valid():
            desig = form.save(commit=False)
            desig.school = school
            desig.save()
            messages.success(request, f"Designation '{desig.name}' created.")
            return redirect('hr:designations')

    context = {
        'designations': designations,
        'form': form,
        'page_title': 'Designations'
    }
    return render(request, 'hr/designations.html', context)


@login_required
def attendance_view(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    today = datetime.date.today()
    date_str = request.GET.get('date', today.isoformat())
    try:
        query_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        query_date = today

    employees = Employee.objects.filter(school=school, status='ACTIVE').select_related('designation', 'department')
    existing_attendance = {
        att.employee_id: att
        for att in EmployeeAttendance.objects.filter(school=school, attendance_date=query_date)
    }

    if request.method == 'POST':
        records = []
        for emp in employees:
            status = request.POST.get(f'status_{emp.pk}')
            remarks = request.POST.get(f'remarks_{emp.pk}', '')
            if status:
                records.append({
                    'employee_id': emp.pk,
                    'status': status,
                    'remarks': remarks
                })
        try:
            attendance_service.record_daily_attendance(
                school=school,
                attendance_date=query_date,
                attendance_data=records,
                actor=request.user
            )
            messages.success(request, f"Attendance for {query_date} saved successfully.")
            return redirect(f"{reverse('hr:attendance')}?date={query_date.isoformat()}")
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'query_date': query_date,
        'employees': employees,
        'existing_attendance': existing_attendance,
        'page_title': 'Staff Daily Attendance'
    }
    return render(request, 'hr/attendance.html', context)


@login_required
def leave_list(request):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        return redirect('hr:my_hr')

    status_filter = request.GET.get('status')
    leave_requests = LeaveRequest.objects.filter(school=school).select_related('employee', 'leave_type', 'approved_by').order_by('-created')
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)

    context = {
        'leave_requests': leave_requests,
        'selected_status': status_filter,
        'page_title': 'Leave Applications'
    }
    return render(request, 'hr/leaves.html', context)


@login_required
def leave_apply(request):
    school = _resolve_school(request)
    emp = Employee.objects.filter(school=school, user=request.user).first()
    if not emp and not request.user.is_superuser:
        messages.error(request, "No employee record linked to your user account.")
        return redirect('hr:my_hr')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, school=school)
        if form.is_valid():
            try:
                target_emp = emp
                if request.user.is_superuser and not target_emp:
                    target_emp = Employee.objects.filter(school=school).first()

                leave_service.apply_leave(
                    school=school,
                    employee=target_emp,
                    leave_type=form.cleaned_data['leave_type'],
                    start_date=form.cleaned_data['start_date'],
                    end_date=form.cleaned_data['end_date'],
                    reason=form.cleaned_data['reason'],
                    actor=request.user
                )
                messages.success(request, "Leave applied successfully.")
                return redirect('hr:my_hr')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = LeaveRequestForm(school=school)

    return render(request, 'hr/leave_apply.html', {'form': form, 'page_title': 'Apply for Leave'})


@login_required
@require_POST
def leave_action(request, pk, action):
    school = _resolve_school(request)
    if not _check_hr_management_perm(request.user):
        raise PermissionDenied()

    leave_req = get_object_or_404(LeaveRequest, school=school, pk=pk)
    rejection_reason = request.POST.get('rejection_reason', '')

    try:
        if action == 'approve':
            leave_service.approve_leave(leave_req, actor=request.user)
            messages.success(request, f"Leave application for {leave_req.employee.full_name} approved.")
        elif action == 'reject':
            leave_service.reject_leave(leave_req, actor=request.user, rejection_reason=rejection_reason)
            messages.info(request, f"Leave application for {leave_req.employee.full_name} rejected.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('hr:leaves')


@login_required
def salary_structures_list(request):
    school = _resolve_school(request)
    if not _check_payroll_perm(request.user):
        raise PermissionDenied()

    structures = EmployeeSalaryStructure.objects.filter(school=school).select_related('employee').prefetch_related('items__component')
    components = SalaryComponent.objects.filter(school=school)
    comp_form = SalaryComponentForm()

    if request.method == 'POST' and 'create_component' in request.POST:
        comp_form = SalaryComponentForm(request.POST)
        if comp_form.is_valid():
            c = comp_form.save(commit=False)
            c.school = school
            c.save()
            messages.success(request, f"Salary Component '{c.name}' created.")
            return redirect('hr:salary_structures')

    context = {
        'structures': structures,
        'components': components,
        'comp_form': comp_form,
        'page_title': 'Salary Components & Structures'
    }
    return render(request, 'hr/salary_structures.html', context)


@login_required
def payroll_periods_list(request):
    school = _resolve_school(request)
    if not _check_payroll_perm(request.user):
        raise PermissionDenied()

    periods = PayrollPeriod.objects.filter(school=school).order_by('-year', '-month')
    form = PayrollPeriodForm()

    if request.method == 'POST':
        form = PayrollPeriodForm(request.POST)
        if form.is_valid():
            try:
                p = form.save(commit=False)
                p.school = school
                p.save()
                messages.success(request, f"Payroll Period {p.get_month_display()} {p.year} created.")
                return redirect('hr:payroll_periods')
            except Exception as e:
                messages.error(request, str(e))

    context = {
        'periods': periods,
        'form': form,
        'page_title': 'Payroll Periods'
    }
    return render(request, 'hr/payroll_periods.html', context)


@login_required
def payroll_process_view(request, period_pk):
    school = _resolve_school(request)
    if not _check_payroll_perm(request.user):
        raise PermissionDenied()

    period = get_object_or_404(PayrollPeriod, school=school, pk=period_pk)
    records = PayrollRecord.objects.filter(school=school, payroll_period=period).select_related('employee').prefetch_related('items__component')
    summary = hr_selectors.get_payroll_summary(school, period.year, period.month)

    if request.method == 'POST' and 'process_payroll' in request.POST:
        try:
            created_records = payroll_service.process_payroll_period(school=school, period=period, actor=request.user)
            messages.success(request, f"Successfully processed payroll for {len(created_records)} employees.")
            return redirect('hr:payroll_process', period_pk=period.pk)
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'period': period,
        'records': records,
        'summary': summary,
        'page_title': f"Payroll: {period.get_month_display()} {period.year}"
    }
    return render(request, 'hr/payroll_process.html', context)


@login_required
@require_POST
def payroll_lock_view(request, period_pk):
    school = _resolve_school(request)
    if not _check_payroll_perm(request.user):
        raise PermissionDenied()

    period = get_object_or_404(PayrollPeriod, school=school, pk=period_pk)
    try:
        payroll_service.lock_payroll_period(period=period, actor=request.user)
        messages.success(request, f"Payroll period {period.get_month_display()} {period.year} is now locked and finalized.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('hr:payroll_process', period_pk=period.pk)


@login_required
def payslip_detail(request, record_pk):
    school = _resolve_school(request)
    record = get_object_or_404(PayrollRecord, school=school, pk=record_pk)

    can_manage = _check_payroll_perm(request.user)
    is_self = (record.employee.user_id == request.user.pk)
    if not can_manage and not is_self:
        raise PermissionDenied()

    earnings = record.items.filter(component__component_type='EARNING')
    deductions = record.items.filter(component__component_type='DEDUCTION')

    context = {
        'record': record,
        'earnings': earnings,
        'deductions': deductions,
        'page_title': f"Payslip: {record.employee.full_name} ({record.payroll_period.get_month_display()} {record.payroll_period.year})"
    }
    return render(request, 'hr/payslip_detail.html', context)


@login_required
def my_hr(request):
    school = _resolve_school(request)
    emp = Employee.objects.filter(school=school, user=request.user).first()

    my_leaves = LeaveRequest.objects.filter(school=school, employee=emp).order_by('-created') if emp else []
    leave_balances = LeaveBalance.objects.filter(school=school, employee=emp).select_related('leave_type') if emp else []
    payslips = PayrollRecord.objects.filter(school=school, employee=emp, status='PAID').select_related('payroll_period').order_by('-payroll_period__year', '-payroll_period__month') if emp else []

    context = {
        'employee': emp,
        'my_leaves': my_leaves,
        'leave_balances': leave_balances,
        'payslips': payslips,
        'page_title': 'My Staff Portal'
    }
    return render(request, 'hr/my_hr.html', context)
