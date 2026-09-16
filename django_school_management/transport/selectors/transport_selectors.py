"""
PrimeSoul Transport - Data Selectors & KPI Aggregations
"""
import datetime
from typing import Dict, Any, List, Optional
from django.utils import timezone

from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.academics.models import AcademicYear
from django_school_management.students.models import Student


def get_active_academic_year(school, requested_year_id: Optional[int] = None) -> Optional[AcademicYear]:
    """Resolves target academic year for transport operations."""
    if requested_year_id:
        ay = AcademicYear.objects.filter(school=school, pk=requested_year_id).first()
        if ay:
            return ay
    return AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).first()


def get_transport_dashboard_metrics(school, academic_year: Optional[AcademicYear] = None) -> Dict[str, Any]:
    """
    Aggregates real transport fleet, logistics, and safety compliance metrics.
    """
    ay = academic_year or get_active_academic_year(school)
    today = timezone.now().date()
    license_warning_threshold = today + datetime.timedelta(days=30)

    total_vehicles = TransportVehicle.objects.filter(school=school, is_active=True).count()
    active_routes = TransportRoute.objects.filter(school=school, academic_year=ay, is_active=True).count() if ay else 0
    total_stops = TransportStop.objects.filter(school=school, is_active=True).count()

    active_students = StudentTransportAssignment.objects.filter(
        school=school,
        academic_year=ay,
        transport_status=StudentTransportAssignment.STATUS_ACTIVE
    ).count() if ay else 0

    drivers_count = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_DRIVER, is_active=True).count()
    attendants_count = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_ATTENDANT, is_active=True).count()

    # Expiring driver licenses (<30 days or already expired)
    expiring_licenses = TransportStaff.objects.filter(
        school=school,
        role=TransportStaff.ROLE_DRIVER,
        is_active=True,
        license_expiry__isnull=False,
        license_expiry__lte=license_warning_threshold
    )

    # Vehicles needing document renewal
    expiring_vehicles = [
        v for v in TransportVehicle.objects.filter(school=school, is_active=True)
        if v.has_expiring_documents
    ]

    # Active route assignments
    assignments = VehicleRouteAssignment.objects.filter(
        school=school,
        academic_year=ay,
        is_active=True
    ).select_related('vehicle', 'route', 'driver', 'attendant')

    return {
        'academic_year': ay,
        'total_vehicles': total_vehicles,
        'active_routes': active_routes,
        'total_stops': total_stops,
        'active_students': active_students,
        'drivers_count': drivers_count,
        'attendants_count': attendants_count,
        'expiring_licenses_count': expiring_licenses.count(),
        'expiring_licenses': expiring_licenses,
        'expiring_vehicles_count': len(expiring_vehicles),
        'expiring_vehicles': expiring_vehicles,
        'assignments': assignments,
    }


def get_route_details(school, route_id: int) -> Dict[str, Any]:
    """Fetches comprehensive details for a route including ordered stops and active assignment."""
    route = TransportRoute.objects.filter(school=school, pk=route_id).select_related('academic_year').first()
    if not route:
        return {}

    stops = list(route.stops.filter(is_active=True).order_by('sequence'))
    assignment = VehicleRouteAssignment.objects.filter(
        school=school,
        route=route,
        is_active=True
    ).select_related('vehicle', 'driver', 'attendant').first()

    students = StudentTransportAssignment.objects.filter(
        school=school,
        route=route,
        transport_status=StudentTransportAssignment.STATUS_ACTIVE
    ).select_related('student', 'pickup_stop', 'drop_stop')

    return {
        'route': route,
        'stops': stops,
        'assignment': assignment,
        'students_count': len(students),
        'students': students
    }


def get_student_transport_info(student: Student, academic_year: Optional[AcademicYear] = None) -> Optional[Dict[str, Any]]:
    """
    Returns public/parent safe transport details without leaking private staff background info.
    """
    school = student.school
    ay = academic_year or get_active_academic_year(school)

    assignment = StudentTransportAssignment.objects.filter(
        school=school,
        academic_year=ay,
        student=student,
        transport_status=StudentTransportAssignment.STATUS_ACTIVE
    ).select_related('route', 'pickup_stop', 'drop_stop').first()

    if not assignment:
        return None

    route_assignment = VehicleRouteAssignment.objects.filter(
        school=school,
        academic_year=ay,
        route=assignment.route,
        is_active=True
    ).select_related('vehicle', 'driver', 'attendant').first()

    return {
        'assignment': assignment,
        'route': assignment.route,
        'pickup_stop': assignment.pickup_stop,
        'drop_stop': assignment.drop_stop,
        'vehicle': route_assignment.vehicle if route_assignment else None,
        'driver_name': route_assignment.driver.name if route_assignment and route_assignment.driver else "Assigned Fleet Driver",
        'driver_phone': route_assignment.driver.phone if route_assignment and route_assignment.driver else None,
        'attendant_name': route_assignment.attendant.name if route_assignment and route_assignment.attendant else None,
        'attendant_phone': route_assignment.attendant.phone if route_assignment and route_assignment.attendant else None,
    }
