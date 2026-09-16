"""
PrimeSoul Transport - Business Services Layer
Handles vehicle-route scheduling, driver collision avoidance, stop-to-route validation,
student transport assignments, and vehicle capacity enforcement.
"""
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.academics.models import AcademicYear
from django_school_management.students.models import Student
from django_school_management.core.audit import log_transport_event


def assign_vehicle_to_route(
    school,
    academic_year: AcademicYear,
    vehicle: TransportVehicle,
    route: TransportRoute,
    driver: TransportStaff,
    attendant: Optional[TransportStaff] = None,
    start_date=None,
    end_date=None,
    actor=None
) -> VehicleRouteAssignment:
    """
    Allocates a vehicle, driver, and attendant to a school route.
    Rejects conflicting active vehicle or driver double bookings.
    """
    # 1. Multi-Tenant Integrity
    if vehicle.school_id != school.id:
        raise ValidationError("Vehicle does not belong to this school tenant.")
    if route.school_id != school.id:
        raise ValidationError("Route does not belong to this school tenant.")
    if driver.school_id != school.id:
        raise ValidationError("Driver does not belong to this school tenant.")
    if attendant and attendant.school_id != school.id:
        raise ValidationError("Attendant does not belong to this school tenant.")

    # 2. Role Checks
    if driver.role != TransportStaff.ROLE_DRIVER:
        raise ValidationError("Assigned driver must have the DRIVER role.")
    if attendant and attendant.role != TransportStaff.ROLE_ATTENDANT:
        raise ValidationError("Assigned attendant must have the ATTENDANT role.")

    # 3. Vehicle Collision: Cannot assign same vehicle to multiple active routes concurrently
    existing_veh = VehicleRouteAssignment.objects.filter(
        school=school,
        academic_year=academic_year,
        vehicle=vehicle,
        is_active=True
    ).exclude(route=route).first()
    if existing_veh:
        raise ValidationError(
            f"Vehicle Collision: Vehicle '{vehicle.vehicle_number}' is already actively assigned "
            f"to route '{existing_veh.route.code} ({existing_veh.route.name})'."
        )

    # 4. Driver Collision: Cannot assign same driver to multiple active routes concurrently
    existing_driver = VehicleRouteAssignment.objects.filter(
        school=school,
        academic_year=academic_year,
        driver=driver,
        is_active=True
    ).exclude(route=route).first()
    if existing_driver:
        raise ValidationError(
            f"Driver Collision: Driver '{driver.name}' is already assigned "
            f"to route '{existing_driver.route.code} ({existing_driver.route.name})'."
        )

    with transaction.atomic():
        # Deactivate any previous assignment on this route
        VehicleRouteAssignment.objects.filter(
            school=school,
            academic_year=academic_year,
            route=route,
            is_active=True
        ).update(is_active=False)

        assignment = VehicleRouteAssignment.objects.create(
            school=school,
            academic_year=academic_year,
            vehicle=vehicle,
            route=route,
            driver=driver,
            attendant=attendant,
            start_date=start_date or timezone.now().date(),
            end_date=end_date,
            is_active=True
        )

        log_transport_event(
            actor=actor,
            school=school,
            action='ASSIGN_VEHICLE_ROUTE',
            resource_id=str(assignment.id),
            details={
                'route': route.code,
                'vehicle': vehicle.vehicle_number,
                'driver': driver.name,
                'attendant': attendant.name if attendant else None
            }
        )

    return assignment


def assign_student_to_transport(
    school,
    academic_year: AcademicYear,
    student: Student,
    route: TransportRoute,
    pickup_stop: TransportStop,
    drop_stop: TransportStop,
    transport_status: str = StudentTransportAssignment.STATUS_ACTIVE,
    start_date=None,
    end_date=None,
    notes: str = '',
    actor=None,
    enforce_capacity: bool = True
) -> StudentTransportAssignment:
    """
    Subscribes a student to a route and designated pickup/drop stops.
    Validates stop-route relationships and checks vehicle capacity limit.
    """
    # 1. Multi-Tenant Integrity
    if student.school_id != school.id:
        raise ValidationError("Student does not belong to this school tenant.")
    if route.school_id != school.id:
        raise ValidationError("Route does not belong to this school tenant.")
    if pickup_stop.school_id != school.id or drop_stop.school_id != school.id:
        raise ValidationError("Stops do not belong to this school tenant.")

    # 2. Stop to Route Relationship
    if pickup_stop.route_id != route.id:
        raise ValidationError(f"Pickup stop '{pickup_stop.name}' does not belong to route '{route.code}'.")
    if drop_stop.route_id != route.id:
        raise ValidationError(f"Drop stop '{drop_stop.name}' does not belong to route '{route.code}'.")

    # 3. Vehicle Capacity Check
    if enforce_capacity and transport_status == StudentTransportAssignment.STATUS_ACTIVE:
        route_assignment = VehicleRouteAssignment.objects.filter(
            school=school,
            academic_year=academic_year,
            route=route,
            is_active=True
        ).select_related('vehicle').first()

        if route_assignment and route_assignment.vehicle:
            veh_capacity = route_assignment.vehicle.capacity
            current_allocated = StudentTransportAssignment.objects.filter(
                school=school,
                academic_year=academic_year,
                route=route,
                transport_status=StudentTransportAssignment.STATUS_ACTIVE
            ).exclude(student=student).count()

            if current_allocated >= veh_capacity:
                raise ValidationError(
                    f"Vehicle Capacity Exceeded: Assigned vehicle '{route_assignment.vehicle.vehicle_number}' "
                    f"has a capacity of {veh_capacity} seats, and {current_allocated} students are already active."
                )

    with transaction.atomic():
        assignment, created = StudentTransportAssignment.objects.update_or_create(
            academic_year=academic_year,
            student=student,
            defaults={
                'school': school,
                'route': route,
                'pickup_stop': pickup_stop,
                'drop_stop': drop_stop,
                'transport_status': transport_status,
                'start_date': start_date or timezone.now().date(),
                'end_date': end_date,
                'notes': notes
            }
        )

        log_transport_event(
            actor=actor,
            school=school,
            action='ASSIGN_STUDENT_TRANSPORT',
            resource_id=str(assignment.id),
            details={
                'student': student.get_full_name(),
                'route': route.code,
                'pickup': pickup_stop.name,
                'drop': drop_stop.name,
                'status': transport_status
            }
        )

    return assignment


def update_student_transport_status(
    assignment: StudentTransportAssignment,
    new_status: str,
    actor=None
) -> StudentTransportAssignment:
    """Updates status of a student transport assignment."""
    old_status = assignment.transport_status
    assignment.transport_status = new_status
    assignment.save(update_fields=['transport_status'])

    log_transport_event(
        actor=actor,
        school=assignment.school,
        action='UPDATE_STUDENT_TRANSPORT_STATUS',
        resource_id=str(assignment.id),
        details={
            'student': assignment.student.get_full_name(),
            'old_status': old_status,
            'new_status': new_status
        }
    )
    return assignment
