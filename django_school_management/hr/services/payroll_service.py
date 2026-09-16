"""
PrimeSoul HR - Payroll Processing Services
Handles salary calculation, payroll processing, locking, and payslip generation.
All operations are transactional and audited.
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import calendar

from django_school_management.hr.models import (
    Employee, EmployeeSalaryStructure, SalaryStructureItem, SalaryComponent,
    PayrollPeriod, PayrollRecord, PayrollLineItem, EmployeeAttendance
)
from django_school_management.core.audit import log_hr_event


def calculate_salary(employee: Employee, payroll_period: PayrollPeriod, working_days: int = 0) -> Dict[str, Any]:
    """
    Deterministic salary calculation based on the active salary structure.
    Returns a dict with earnings, deductions, gross, net, and line items.
    """
    school = employee.school
    period_date = timezone.datetime(payroll_period.year, payroll_period.month, 1).date()

    # Get active salary structure for this period
    structures = EmployeeSalaryStructure.objects.filter(
        school=school,
        employee=employee,
        is_active=True,
        effective_from__lte=period_date
    ).order_by('-effective_from')

    structure = None
    for s in structures:
        if s.effective_to is None or s.effective_to >= period_date:
            structure = s
            break

    if not structure:
        return {
            'gross_earnings': Decimal('0.00'),
            'total_deductions': Decimal('0.00'),
            'net_salary': Decimal('0.00'),
            'line_items': [],
            'working_days': working_days,
            'payable_days': working_days,
            'leave_days': Decimal('0.0'),
        }

    items = SalaryStructureItem.objects.filter(
        salary_structure=structure
    ).select_related('component')

    # Calculate working/payable days
    total_days_in_month = calendar.monthrange(payroll_period.year, payroll_period.month)[1]
    if working_days <= 0:
        working_days = total_days_in_month

    # Count leave days from attendance
    leave_count = EmployeeAttendance.objects.filter(
        school=school,
        employee=employee,
        attendance_date__year=payroll_period.year,
        attendance_date__month=payroll_period.month,
        status__in=[EmployeeAttendance.STATUS_ABSENT, EmployeeAttendance.STATUS_ON_LEAVE]
    ).count()

    half_day_count = EmployeeAttendance.objects.filter(
        school=school,
        employee=employee,
        attendance_date__year=payroll_period.year,
        attendance_date__month=payroll_period.month,
        status=EmployeeAttendance.STATUS_HALF_DAY
    ).count()

    leave_days = Decimal(str(leave_count)) + Decimal(str(half_day_count)) * Decimal('0.5')
    payable_days = max(0, working_days - int(leave_days))

    # Find basic salary for percentage calculations
    basic_amount = Decimal('0.00')
    for item in items:
        if item.component.code.upper() in ('BASIC', 'BASIC_SALARY'):
            basic_amount = item.amount
            break

    # Pro-rate factor
    prorate = Decimal(str(payable_days)) / Decimal(str(working_days)) if working_days > 0 else Decimal('1.00')

    earnings = Decimal('0.00')
    deductions = Decimal('0.00')
    line_items_data = []

    for item in items:
        comp = item.component
        if comp.calculation_type == SalaryComponent.CALC_PERCENTAGE and item.percentage:
            raw_amount = (basic_amount * item.percentage / Decimal('100.00')).quantize(Decimal('0.01'), ROUND_HALF_UP)
        else:
            raw_amount = item.amount

        # Pro-rate based on payable days
        prorated_amount = (raw_amount * prorate).quantize(Decimal('0.01'), ROUND_HALF_UP)

        if comp.component_type == SalaryComponent.TYPE_EARNING:
            earnings += prorated_amount
        else:
            deductions += prorated_amount

        line_items_data.append({
            'component': comp,
            'amount': prorated_amount,
            'calculation_details': f"{comp.get_calculation_type_display()}: ₹{raw_amount} × {prorate:.4f} prorate = ₹{prorated_amount}"
        })

    net_salary = max(Decimal('0.00'), earnings - deductions)

    return {
        'gross_earnings': earnings,
        'total_deductions': deductions,
        'net_salary': net_salary,
        'line_items': line_items_data,
        'working_days': working_days,
        'payable_days': payable_days,
        'leave_days': leave_days,
    }


@transaction.atomic
def process_payroll(school, payroll_period: PayrollPeriod, working_days: int = 0, actor=None) -> PayrollPeriod:
    """
    Processes payroll for all active employees in the school for the given period.
    Creates PayrollRecord and PayrollLineItem for each employee.
    """
    if payroll_period.school_id != school.id:
        raise ValidationError("Payroll period does not belong to this school.")
    if payroll_period.status == PayrollPeriod.STATUS_LOCKED:
        raise ValidationError("Cannot process a locked payroll period.")

    payroll_period.status = PayrollPeriod.STATUS_PROCESSING
    payroll_period.save(update_fields=['status'])

    active_employees = Employee.objects.filter(
        school=school, status=Employee.STATUS_ACTIVE
    )

    for emp in active_employees:
        # Prevent duplicate
        if PayrollRecord.objects.filter(payroll_period=payroll_period, employee=emp).exists():
            continue

        calc = calculate_salary(emp, payroll_period, working_days)

        record = PayrollRecord.objects.create(
            school=school,
            payroll_period=payroll_period,
            employee=emp,
            working_days=calc['working_days'],
            payable_days=calc['payable_days'],
            leave_days=calc['leave_days'],
            gross_earnings=calc['gross_earnings'],
            total_deductions=calc['total_deductions'],
            net_salary=calc['net_salary'],
            status=PayrollRecord.STATUS_CALCULATED
        )

        for li in calc['line_items']:
            PayrollLineItem.objects.create(
                payroll_record=record,
                component=li['component'],
                amount=li['amount'],
                calculation_details=li['calculation_details']
            )

    payroll_period.status = PayrollPeriod.STATUS_PROCESSED
    payroll_period.processed_at = timezone.now()
    payroll_period.processed_by = actor
    payroll_period.save(update_fields=['status', 'processed_at', 'processed_by'])

    log_hr_event(
        actor=actor, school=school, action='PROCESS_PAYROLL',
        resource='PayrollPeriod', resource_id=str(payroll_period.pk),
        details={'year': payroll_period.year, 'month': payroll_period.month}
    )

    return payroll_period


@transaction.atomic
def lock_payroll(school, payroll_period: PayrollPeriod, actor=None) -> PayrollPeriod:
    """Locks a processed payroll to prevent modifications."""
    if payroll_period.school_id != school.id:
        raise ValidationError("Payroll period does not belong to this school.")
    if payroll_period.status != PayrollPeriod.STATUS_PROCESSED:
        raise ValidationError("Can only lock processed payroll periods.")

    payroll_period.status = PayrollPeriod.STATUS_LOCKED
    payroll_period.save(update_fields=['status'])

    # Lock all individual records
    PayrollRecord.objects.filter(
        payroll_period=payroll_period
    ).update(status=PayrollRecord.STATUS_LOCKED)

    log_hr_event(
        actor=actor, school=school, action='LOCK_PAYROLL',
        resource='PayrollPeriod', resource_id=str(payroll_period.pk),
        details={'year': payroll_period.year, 'month': payroll_period.month}
    )

    return payroll_period


def process_payroll_period(school, period: PayrollPeriod, working_days: int = 0, actor=None) -> List[PayrollRecord]:
    """Processes payroll and returns list of created/updated records."""
    process_payroll(school=school, payroll_period=period, working_days=working_days, actor=actor)
    return list(PayrollRecord.objects.filter(payroll_period=period))


def lock_payroll_period(period: PayrollPeriod, school=None, actor=None) -> PayrollPeriod:
    """Helper for locking a payroll period."""
    target_school = school or period.school
    return lock_payroll(school=target_school, payroll_period=period, actor=actor)

