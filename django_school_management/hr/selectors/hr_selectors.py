"""
PrimeSoul HR - Selectors (Read-Only Queries)
Dashboard metrics, employee lists, leave summaries, payroll stats, and document expiry alerts.
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from django_school_management.hr.models import (
    Employee, Department, HRDesignation, LeaveRequest, LeaveBalance,
    EmployeeAttendance, PayrollPeriod, PayrollRecord, EmployeeDocument
)


def get_dashboard_metrics(school) -> Dict[str, Any]:
    """Returns real HR dashboard metrics from database."""
    today = timezone.localdate()

    total_employees = Employee.objects.filter(school=school).count()
    active_employees = Employee.objects.filter(school=school, status='ACTIVE').count()
    on_leave = Employee.objects.filter(school=school, status='ON_LEAVE').count()
    departments = Department.objects.filter(school=school, is_active=True).count()
    designations = HRDesignation.objects.filter(school=school, is_active=True).count()

    pending_leave = LeaveRequest.objects.filter(
        school=school, status='PENDING'
    ).count()

    present_today = EmployeeAttendance.objects.filter(
        school=school, attendance_date=today, status='PRESENT'
    ).count()

    # Current/latest payroll
    latest_payroll = PayrollPeriod.objects.filter(school=school).order_by('-year', '-month').first()
    payroll_status = latest_payroll.get_status_display() if latest_payroll else 'No Payroll'

    payroll_total = Decimal('0.00')
    if latest_payroll:
        payroll_total = PayrollRecord.objects.filter(
            payroll_period=latest_payroll
        ).aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')

    # Document expiry alerts (next 30 days)
    expiry_threshold = today + timedelta(days=30)
    expiring_docs = EmployeeDocument.objects.filter(
        school=school, is_active=True,
        expiry_date__isnull=False,
        expiry_date__lte=expiry_threshold,
        expiry_date__gte=today
    ).count()

    return {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'on_leave': on_leave,
        'departments': departments,
        'total_departments': departments,
        'total_designations': designations,
        'pending_leaves': pending_leave,
        'pending_leave_requests': pending_leave,
        'present_today': present_today,
        'payroll_status': payroll_status,
        'payroll_total': payroll_total,
        'expiring_documents': expiring_docs,
    }

get_hr_dashboard_metrics = get_dashboard_metrics


def get_employee_list(
    school,
    department_id: Optional[int] = None,
    designation_id: Optional[int] = None,
    status: Optional[str] = None,
    search_query: Optional[str] = None
):
    """Filters employee directory."""
    qs = Employee.objects.filter(school=school).select_related('department', 'designation')
    if department_id:
        qs = qs.filter(department_id=department_id)
    if designation_id:
        qs = qs.filter(designation_id=designation_id)
    if status:
        qs = qs.filter(status=status)
    if search_query:
        qs = qs.filter(
            Q(full_name__icontains=search_query) |
            Q(employee_code__icontains=search_query) |
            Q(mobile__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    return qs


def get_document_expiry_alerts(school, days_threshold: int = 30) -> List[EmployeeDocument]:
    """Retrieves documents expiring within the threshold."""
    today = timezone.localdate()
    cutoff = today + timedelta(days=days_threshold)
    return list(EmployeeDocument.objects.filter(
        school=school, is_active=True,
        expiry_date__isnull=False,
        expiry_date__lte=cutoff,
        expiry_date__gte=today
    ).select_related('employee'))


def get_leave_summary(school, employee: Employee) -> Dict[str, Any]:
    """Returns leave summary for an employee."""
    balances = LeaveBalance.objects.filter(
        school=school, employee=employee
    ).select_related('leave_type', 'academic_year').order_by('leave_type__name')

    recent_requests = LeaveRequest.objects.filter(
        school=school, employee=employee
    ).order_by('-start_date')[:10]

    return {
        'balances': list(balances),
        'recent_requests': list(recent_requests),
    }


def get_payroll_summary(school, year: Optional[int] = None, month: Optional[int] = None, payroll_period: Optional[PayrollPeriod] = None) -> Dict[str, Any]:
    """Returns payroll summary for a period."""
    if payroll_period is None and year and month:
        payroll_period = PayrollPeriod.objects.filter(school=school, year=year, month=month).first()

    if not payroll_period:
        return {
            'total_employees': 0,
            'total_gross': Decimal('0.00'),
            'total_deductions': Decimal('0.00'),
            'total_net': Decimal('0.00'),
            'records': []
        }

    records = PayrollRecord.objects.filter(
        payroll_period=payroll_period
    ).select_related('employee')

    total_gross = records.aggregate(total=Sum('gross_earnings'))['total'] or Decimal('0.00')
    total_deductions = records.aggregate(total=Sum('total_deductions'))['total'] or Decimal('0.00')
    total_net = records.aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')

    return {
        'period': payroll_period,
        'records': list(records),
        'total_employees': records.count(),
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_net': total_net,
    }
