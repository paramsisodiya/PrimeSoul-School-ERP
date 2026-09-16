"""
PrimeSoul HR - Employee Attendance Service
Daily attendance recording and summary for employees (separate from student attendance).
"""
from typing import Dict, Any, List
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.hr.models import Employee, EmployeeAttendance
from django_school_management.core.audit import log_hr_event


@transaction.atomic
def record_employee_attendance(
    school, employee: Employee, attendance_date, status: str,
    remarks: str = '', actor=None
) -> EmployeeAttendance:
    """Records or updates daily attendance for an employee."""
    if employee.school_id != school.id:
        raise ValidationError("Employee does not belong to this school.")

    if status not in dict(EmployeeAttendance.STATUS_CHOICES):
        raise ValidationError(f"Invalid attendance status: {status}")

    record, created = EmployeeAttendance.objects.update_or_create(
        school=school,
        employee=employee,
        attendance_date=attendance_date,
        defaults={
            'status': status,
            'remarks': remarks,
            'marked_by': actor,
        }
    )

    log_hr_event(
        actor=actor, school=school,
        action='MARK_ATTENDANCE' if created else 'UPDATE_ATTENDANCE',
        resource='EmployeeAttendance', resource_id=str(record.pk),
        details={'employee': employee.full_name, 'date': str(attendance_date), 'status': status}
    )

    return record


@transaction.atomic
def record_daily_attendance(
    school, attendance_date, attendance_data: List[Dict[str, Any]], actor=None
) -> List[EmployeeAttendance]:
    """Bulk records or updates daily attendance from form submission."""
    saved_records = []
    for item in attendance_data:
        emp = Employee.objects.get(pk=item['employee_id'], school=school)
        rec = record_employee_attendance(
            school=school,
            employee=emp,
            attendance_date=attendance_date,
            status=item['status'],
            remarks=item.get('remarks', ''),
            actor=actor
        )
        saved_records.append(rec)
    return saved_records


def get_monthly_summary(school, employee: Employee, year: int, month: int) -> Dict[str, Any]:
    """Returns monthly attendance summary for an employee."""
    records = EmployeeAttendance.objects.filter(
        school=school,
        employee=employee,
        attendance_date__year=year,
        attendance_date__month=month
    )

    summary = {
        'present': records.filter(status=EmployeeAttendance.STATUS_PRESENT).count(),
        'absent': records.filter(status=EmployeeAttendance.STATUS_ABSENT).count(),
        'half_day': records.filter(status=EmployeeAttendance.STATUS_HALF_DAY).count(),
        'late': records.filter(status=EmployeeAttendance.STATUS_LATE).count(),
        'on_leave': records.filter(status=EmployeeAttendance.STATUS_ON_LEAVE).count(),
        'total_records': records.count(),
    }

    return summary
