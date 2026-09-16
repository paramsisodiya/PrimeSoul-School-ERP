"""
PrimeSoul HR - Leave Management Services
Handles leave requests, approvals, rejections, cancellations, and balance tracking.
"""
from typing import Optional
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.hr.models import Employee, LeaveType, LeaveBalance, LeaveRequest
from django_school_management.academics.models import AcademicYear
from django_school_management.core.audit import log_hr_event


def get_or_create_leave_balance(
    school, employee: Employee, leave_type: LeaveType, academic_year: AcademicYear
) -> LeaveBalance:
    """Gets or creates the leave balance for an employee in an academic year."""
    balance, _ = LeaveBalance.objects.get_or_create(
        school=school,
        employee=employee,
        leave_type=leave_type,
        academic_year=academic_year,
        defaults={
            'opening_balance': Decimal(str(leave_type.annual_limit)),
            'accrued': Decimal('0.0'),
            'used': Decimal('0.0'),
        }
    )
    return balance


@transaction.atomic
def apply_leave(
    school, employee: Employee, leave_type: LeaveType,
    start_date, end_date, reason: str = '',
    academic_year: Optional[AcademicYear] = None,
    actor=None
) -> LeaveRequest:
    """Applies for leave on behalf of an employee."""
    if employee.school_id != school.id:
        raise ValidationError("Employee does not belong to this school.")

    if end_date < start_date:
        raise ValidationError("End date cannot be before start date.")

    leave_days = (end_date - start_date).days + 1

    # Check for overlapping approved/pending leave
    overlapping = LeaveRequest.objects.filter(
        school=school,
        employee=employee,
        status__in=[LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date
    ).exists()
    if overlapping:
        raise ValidationError("An overlapping leave request already exists for this period.")

    # Check leave balance
    ay = academic_year or AcademicYear.objects.filter(
        school=school, is_current=True
    ).first() or AcademicYear.objects.filter(school=school).first()

    if ay:
        balance = get_or_create_leave_balance(school, employee, leave_type, ay)
        available = balance.closing_balance
        if Decimal(str(leave_days)) > available:
            raise ValidationError(
                f"Insufficient leave balance. Available: {available}, Requested: {leave_days}"
            )

    request = LeaveRequest.objects.create(
        school=school,
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=LeaveRequest.STATUS_PENDING
    )

    log_hr_event(
        actor=actor or (employee.user if employee.user else None),
        school=school, action='APPLY_LEAVE',
        resource='LeaveRequest', resource_id=str(request.pk),
        details={'leave_type': leave_type.name, 'days': leave_days}
    )

    return request


@transaction.atomic
def approve_leave(leave_request: LeaveRequest, school=None, actor=None, approver=None, academic_year=None) -> LeaveRequest:
    """Approves a pending leave request and updates the balance."""
    target_actor = actor or approver
    target_school = school or leave_request.school

    if leave_request.school_id != target_school.id:
        raise ValidationError("Leave request does not belong to this school.")
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("Can only approve pending leave requests.")

    leave_request.status = LeaveRequest.STATUS_APPROVED
    leave_request.approved_by = target_actor
    leave_request.approved_at = timezone.now()
    leave_request.save(update_fields=['status', 'approved_by', 'approved_at'])

    # Update leave balance
    ay = academic_year or AcademicYear.objects.filter(
        school=target_school, is_current=True
    ).first() or AcademicYear.objects.filter(school=target_school).first()

    if ay:
        balance = get_or_create_leave_balance(
            target_school, leave_request.employee, leave_request.leave_type, ay
        )
        balance.used += Decimal(str(leave_request.days_count))
        balance.save(update_fields=['used'])

    log_hr_event(
        actor=target_actor, school=target_school, action='APPROVE_LEAVE',
        resource='LeaveRequest', resource_id=str(leave_request.pk),
        details={'employee': leave_request.employee.full_name}
    )

    return leave_request


@transaction.atomic
def reject_leave(leave_request: LeaveRequest, school=None, actor=None, rejector=None, rejection_reason: str = '') -> LeaveRequest:
    """Rejects a pending leave request."""
    target_actor = actor or rejector
    target_school = school or leave_request.school

    if leave_request.school_id != target_school.id:
        raise ValidationError("Leave request does not belong to this school.")
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("Can only reject pending leave requests.")

    leave_request.status = LeaveRequest.STATUS_REJECTED
    leave_request.approved_by = target_actor
    leave_request.approved_at = timezone.now()
    leave_request.rejection_reason = rejection_reason
    leave_request.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason'])

    log_hr_event(
        actor=target_actor, school=target_school, action='REJECT_LEAVE',
        resource='LeaveRequest', resource_id=str(leave_request.pk),
        details={'employee': leave_request.employee.full_name, 'reason': rejection_reason}
    )

    return leave_request


@transaction.atomic
def cancel_leave(leave_request: LeaveRequest, school=None, actor=None, academic_year=None) -> LeaveRequest:
    """Cancels a leave request. Reverses balance if was approved."""
    target_school = school or leave_request.school

    if leave_request.school_id != target_school.id:
        raise ValidationError("Leave request does not belong to this school.")
    if leave_request.status not in (LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED):
        raise ValidationError("Can only cancel pending or approved leave requests.")

    was_approved = leave_request.status == LeaveRequest.STATUS_APPROVED

    leave_request.status = LeaveRequest.STATUS_CANCELLED
    leave_request.save(update_fields=['status'])

    # Reverse balance if was approved
    if was_approved:
        ay = academic_year or AcademicYear.objects.filter(
            school=target_school, is_current=True
        ).first() or AcademicYear.objects.filter(school=target_school).first()
        if ay:
            balance = get_or_create_leave_balance(
                target_school, leave_request.employee, leave_request.leave_type, ay
            )
            balance.used = max(Decimal('0.0'), balance.used - Decimal(str(leave_request.days_count)))
            balance.save(update_fields=['used'])

    log_hr_event(
        actor=actor, school=target_school, action='CANCEL_LEAVE',
        resource='LeaveRequest', resource_id=str(leave_request.pk),
        details={'employee': leave_request.employee.full_name, 'was_approved': was_approved}
    )

    return leave_request
