"""
PrimeSoul Core - Enterprise Audit Logging
Centralized audit event recorder for security events, administrative mutations, and financial transactions.
"""
import logging
from typing import Optional, Dict, Any

audit_logger = logging.getLogger('primesoul.audit')


def log_audit_event(
    event_type: str,
    actor_id: Optional[int],
    school_id: Optional[int],
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    status: str = 'SUCCESS'
) -> None:
    """
    Standardized audit logger for statutory and institutional compliance.
    """
    record = {
        'event_type': event_type,
        'actor_id': actor_id,
        'school_id': school_id,
        'action': action,
        'resource': resource,
        'resource_id': resource_id,
        'status': status,
        'ip_address': ip_address,
        'details': details or {},
    }
    audit_logger.info(
        "AUDIT: [%s] action=%s resource=%s/%s actor=%s school=%s status=%s ip=%s",
        event_type, action, resource, resource_id, actor_id, school_id, status, ip_address,
        extra={'audit_record': record}
    )


def log_security_event(actor, school, action: str, details: Optional[Dict[str, Any]] = None, ip: Optional[str] = None) -> None:
    """Shortcut for logging security/RBAC/auth actions."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='SECURITY',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource='SecurityContext',
        details=details,
        ip_address=ip
    )


def log_financial_event(actor, school, action: str, invoice_or_receipt_id: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging fee invoice/receipt mutations."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='FINANCIAL',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource='FeeLedger',
        resource_id=invoice_or_receipt_id,
        details=details
    )


def log_academic_event(actor, school, action: str, resource: str, resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging academic structure, assignment, enrollment, and promotion actions."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='ACADEMIC',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_attendance_event(actor, school, action: str, resource: str = 'AttendanceRecord', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging daily attendance marking, bulk saves, and status corrections."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='ATTENDANCE',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_examination_event(actor, school, action: str, resource: str = 'Exam', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging examination sessions, marks entry, finalization, publishing, locking and corrections."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='EXAMINATION',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_timetable_event(actor, school, action: str, resource: str = 'TimetableEntry', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging timetable setup, slot allocation, generation, cloning, clearing and entry mutations."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='TIMETABLE',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_transport_event(actor, school, action: str, resource: str = 'Transport', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging vehicle fleet, route, stop, staff and student transport allocations."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='TRANSPORT',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_library_event(actor, school, action: str, resource: str = 'Library', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging library catalog, issue/return, fine, and member operations."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='LIBRARY',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )


def log_hr_event(actor, school, action: str, resource: str = 'HR', resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """Shortcut for logging employee, leave, attendance, payroll, and payslip operations."""
    actor_id = getattr(actor, 'pk', None) if actor else None
    school_id = getattr(school, 'pk', None) if school else None
    log_audit_event(
        event_type='HR_PAYROLL',
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details
    )
