"""
PrimeSoul HR - Employee Management Services
Handles employee onboarding, profile updates, and document management.
All operations are atomic and audited.
"""
from typing import Optional, Dict, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django_school_management.core.audit import log_hr_event
from django_school_management.hr.models import (
    Employee, EmployeeDocument, Department, HRDesignation
)


@transaction.atomic
def create_employee(
    school,
    employee_code: str,
    full_name: str,
    designation: HRDesignation,
    actor=None,
    user=None,
    department: Optional[Department] = None,
    gender: str = 'M',
    date_of_birth=None,
    mobile: str = '',
    email: str = '',
    address: str = '',
    employment_type: str = 'FULL_TIME',
    joining_date=None,
    confirmation_date=None,
    bank_account_number: str = '',
    bank_ifsc: str = '',
    bank_name: str = '',
    pan_number: str = '',
    aadhaar_last4: str = '',
    emergency_contact: str = '',
    status: str = 'ACTIVE',
    photo=None,
) -> Employee:
    """Creates a new employee record within tenant isolation."""
    if Employee.objects.filter(school=school, employee_code=employee_code).exists():
        raise ValidationError(f"Employee code '{employee_code}' already exists in this school.")

    if aadhaar_last4 and (len(aadhaar_last4) != 4 or not aadhaar_last4.isdigit()):
        raise ValidationError("Aadhaar must contain exactly the last 4 digits.")

    employee = Employee.objects.create(
        school=school,
        user=user,
        employee_code=employee_code,
        full_name=full_name,
        gender=gender,
        date_of_birth=date_of_birth,
        mobile=mobile,
        email=email,
        address=address,
        designation=designation,
        department=department,
        employment_type=employment_type,
        joining_date=joining_date,
        confirmation_date=confirmation_date,
        bank_account_number=bank_account_number,
        bank_ifsc=bank_ifsc,
        bank_name=bank_name,
        pan_number=pan_number.upper() if pan_number else '',
        aadhaar_last4=aadhaar_last4,
        emergency_contact=emergency_contact,
        status=status,
        photo=photo,
    )

    log_hr_event(
        actor=actor,
        school=school,
        action='EMPLOYEE_CREATED',
        resource='Employee',
        resource_id=str(employee.pk),
        details={'employee_code': employee_code, 'name': full_name, 'designation': designation.name}
    )
    return employee


@transaction.atomic
def update_employee(
    employee: Employee,
    actor=None,
    **kwargs
) -> Employee:
    """Updates employee details securely."""
    school = employee.school
    new_code = kwargs.get('employee_code')
    if new_code and new_code != employee.employee_code:
        if Employee.objects.filter(school=school, employee_code=new_code).exclude(pk=employee.pk).exists():
            raise ValidationError(f"Employee code '{new_code}' already in use.")

    aadhaar = kwargs.get('aadhaar_last4')
    if aadhaar and (len(aadhaar) != 4 or not aadhaar.isdigit()):
        raise ValidationError("Aadhaar must contain exactly the last 4 digits.")

    for field, value in kwargs.items():
        if hasattr(employee, field):
            if field == 'pan_number' and isinstance(value, str):
                value = value.upper()
            setattr(employee, field, value)

    employee.save()
    log_hr_event(
        actor=actor,
        school=school,
        action='EMPLOYEE_UPDATED',
        resource='Employee',
        resource_id=str(employee.pk),
        details={'employee_code': employee.employee_code}
    )
    return employee


@transaction.atomic
def upload_employee_document(
    school,
    employee: Employee,
    document_type: str,
    title: str,
    file,
    actor=None,
    issue_date=None,
    expiry_date=None
) -> EmployeeDocument:
    """Uploads and associates an identity or statutory document with strict tenant scoping."""
    if employee.school_id != school.pk:
        raise ValidationError("Employee belongs to a different school.")

    doc = EmployeeDocument.objects.create(
        school=school,
        employee=employee,
        document_type=document_type,
        title=title,
        file=file,
        issue_date=issue_date,
        expiry_date=expiry_date,
        uploaded_by=actor
    )
    log_hr_event(
        actor=actor,
        school=school,
        action='DOCUMENT_UPLOADED',
        resource='EmployeeDocument',
        resource_id=str(doc.pk),
        details={'employee_id': employee.pk, 'document_type': document_type, 'title': title}
    )
    return doc
