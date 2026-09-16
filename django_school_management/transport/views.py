"""
PrimeSoul Transport - Modern UI Views
Handles dashboard, fleet management, routes, stops, staff, student allocations, and parent/student portal.
"""
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
from django_school_management.students.models import Student

from .models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from .forms import (
    TransportVehicleForm, TransportRouteForm, TransportStopForm,
    TransportStaffForm, VehicleRouteAssignmentForm, StudentTransportAssignmentForm
)
from .services import transport_service
from .selectors import transport_selectors


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


def _check_transport_management_perm(user):
    """Verifies administrative management privileges for Transport."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_has_role(
        user,
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.TRANSPORT_MANAGER
    )


# =============================================================================
# 1. DASHBOARD & FLEET OVERVIEW
# =============================================================================

@login_required
def dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "School context required.")
        return redirect('index_view')

    user = request.user
    # Accountants have no transport editing/management access
    if user_has_role(user, Role.ACCOUNTANT) and not user.is_superuser:
        raise PermissionDenied("Accountants do not have access to transport management.")

    # Redirect Students/Parents to their direct view
    if user_has_role(user, Role.STUDENT, Role.PARENT) and not user.is_superuser:
        return redirect('transport:my_transport')

    academic_year = transport_selectors.get_active_academic_year(school)
    metrics = transport_selectors.get_transport_dashboard_metrics(school, academic_year)
    can_manage = _check_transport_management_perm(user)

    # Route Assignment Form for quick inline modal
    assignment_form = VehicleRouteAssignmentForm(school=school, academic_year=academic_year) if can_manage else None

    context = {
        'school': school,
        'academic_year': academic_year,
        'metrics': metrics,
        'can_manage': can_manage,
        'assignment_form': assignment_form,
    }
    return render(request, 'transport/dashboard.html', context)


# =============================================================================
# 2. VEHICLE FLEET MANAGEMENT
# =============================================================================

@login_required
def vehicles_view(request):
    school = _resolve_school(request)
    vehicles = TransportVehicle.objects.filter(school=school).order_by('vehicle_number')
    can_manage = _check_transport_management_perm(request.user)
    form = TransportVehicleForm() if can_manage else None

    context = {
        'school': school,
        'vehicles': vehicles,
        'can_manage': can_manage,
        'form': form,
    }
    return render(request, 'transport/vehicles.html', context)


@login_required
@require_POST
def vehicle_create_view(request):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    form = TransportVehicleForm(request.POST)
    if form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.school = school
        vehicle.save()
        messages.success(request, f"Vehicle '{vehicle.vehicle_number}' added to fleet successfully.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving vehicle: {err_msg}")
    return redirect('transport:vehicles')


@login_required
@require_POST
def vehicle_delete_view(request, pk):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    vehicle = get_object_or_404(TransportVehicle, pk=pk, school=school)
    vehicle.is_active = not vehicle.is_active
    vehicle.save(update_fields=['is_active'])
    status_str = "activated" if vehicle.is_active else "deactivated"
    messages.success(request, f"Vehicle '{vehicle.vehicle_number}' has been {status_str}.")
    return redirect('transport:vehicles')


# =============================================================================
# 3. ROUTES & STOPS
# =============================================================================

@login_required
def routes_view(request):
    school = _resolve_school(request)
    academic_year = transport_selectors.get_active_academic_year(school)
    routes = TransportRoute.objects.filter(school=school, academic_year=academic_year).select_related('academic_year')
    can_manage = _check_transport_management_perm(request.user)
    form = TransportRouteForm(school=school, initial={'academic_year': academic_year}) if can_manage else None

    context = {
        'school': school,
        'academic_year': academic_year,
        'routes': routes,
        'can_manage': can_manage,
        'form': form,
    }
    return render(request, 'transport/routes.html', context)


@login_required
def route_detail_view(request, pk):
    school = _resolve_school(request)
    details = transport_selectors.get_route_details(school, pk)
    if not details:
        messages.error(request, "Route not found.")
        return redirect('transport:routes')

    can_manage = _check_transport_management_perm(request.user)
    stop_form = TransportStopForm() if can_manage else None

    context = {
        'school': school,
        'route': details['route'],
        'stops': details['stops'],
        'assignment': details['assignment'],
        'students_count': details['students_count'],
        'students': details['students'],
        'can_manage': can_manage,
        'stop_form': stop_form,
    }
    return render(request, 'transport/route_detail.html', context)


@login_required
@require_POST
def route_create_view(request):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    form = TransportRouteForm(request.POST, school=school)
    if form.is_valid():
        route = form.save(commit=False)
        route.school = school
        route.save()
        messages.success(request, f"Route '{route.code} - {route.name}' created.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving route: {err_msg}")
    return redirect('transport:routes')


@login_required
@require_POST
def stop_create_view(request, route_id):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    route = get_object_or_404(TransportRoute, pk=route_id, school=school)
    form = TransportStopForm(request.POST)
    if form.is_valid():
        stop = form.save(commit=False)
        stop.school = school
        stop.route = route
        stop.save()
        messages.success(request, f"Stop '{stop.name}' added to {route.code}.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving stop: {err_msg}")
    return redirect('transport:route_detail', pk=route.id)


@login_required
@require_POST
def stop_delete_view(request, pk):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    stop = get_object_or_404(TransportStop, pk=pk, school=school)
    route_id = stop.route_id
    stop.delete()
    messages.success(request, "Stop deleted.")
    return redirect('transport:route_detail', pk=route_id)


# =============================================================================
# 4. TRANSPORT STAFF (DRIVERS & ATTENDANTS)
# =============================================================================

@login_required
def staff_view(request):
    school = _resolve_school(request)
    drivers = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_DRIVER).order_by('name')
    attendants = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_ATTENDANT).order_by('name')
    can_manage = _check_transport_management_perm(request.user)
    form = TransportStaffForm() if can_manage else None

    context = {
        'school': school,
        'drivers': drivers,
        'attendants': attendants,
        'can_manage': can_manage,
        'form': form,
    }
    return render(request, 'transport/staff.html', context)


@login_required
@require_POST
def staff_create_view(request):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    form = TransportStaffForm(request.POST)
    if form.is_valid():
        staff = form.save(commit=False)
        staff.school = school
        staff.save()
        messages.success(request, f"{staff.get_role_display()} '{staff.name}' added successfully.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving staff: {err_msg}")
    return redirect('transport:staff')


# =============================================================================
# 5. VEHICLE-ROUTE ASSIGNMENT
# =============================================================================

@login_required
@require_POST
def assignment_create_view(request):
    school = _resolve_school(request)
    if not _check_transport_management_perm(request.user):
        raise PermissionDenied()

    academic_year = transport_selectors.get_active_academic_year(school)
    form = VehicleRouteAssignmentForm(request.POST, school=school, academic_year=academic_year)
    if form.is_valid():
        try:
            assignment = transport_service.assign_vehicle_to_route(
                school=school,
                academic_year=academic_year,
                vehicle=form.cleaned_data['vehicle'],
                route=form.cleaned_data['route'],
                driver=form.cleaned_data['driver'],
                attendant=form.cleaned_data.get('attendant'),
                start_date=form.cleaned_data.get('start_date'),
                end_date=form.cleaned_data.get('end_date'),
                actor=request.user
            )
            messages.success(request, f"Allocated {assignment.vehicle.vehicle_number} and driver {assignment.driver.name} to route {assignment.route.code}.")
        except ValidationError as e:
            messages.error(request, str(e))
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error creating assignment: {err_msg}")
    return redirect('transport:dashboard')


# =============================================================================
# 6. STUDENT TRANSPORT SUBSCRIPTIONS
# =============================================================================

@login_required
def students_view(request):
    school = _resolve_school(request)
    user = request.user
    can_manage = _check_transport_management_perm(user) or user_has_role(user, Role.RECEPTIONIST)

    academic_year = transport_selectors.get_active_academic_year(school)
    assignments = StudentTransportAssignment.objects.filter(
        school=school, academic_year=academic_year
    ).select_related('student', 'route', 'pickup_stop', 'drop_stop').order_by('student__first_name')

    assign_form = StudentTransportAssignmentForm(school=school) if can_manage else None

    context = {
        'school': school,
        'academic_year': academic_year,
        'assignments': assignments,
        'can_manage': can_manage,
        'assign_form': assign_form,
    }
    return render(request, 'transport/students.html', context)


@login_required
@require_POST
def student_assign_view(request):
    school = _resolve_school(request)
    user = request.user
    if not (_check_transport_management_perm(user) or user_has_role(user, Role.RECEPTIONIST)):
        raise PermissionDenied("You do not have permission to manage student transport.")

    academic_year = transport_selectors.get_active_academic_year(school)
    student_id = request.POST.get('student')
    route_id = request.POST.get('route')
    pickup_stop_id = request.POST.get('pickup_stop')
    drop_stop_id = request.POST.get('drop_stop')
    status_val = request.POST.get('transport_status', StudentTransportAssignment.STATUS_ACTIVE)
    notes = request.POST.get('notes', '')

    student = get_object_or_404(Student, pk=student_id, school=school)
    route = get_object_or_404(TransportRoute, pk=route_id, school=school)
    pickup_stop = get_object_or_404(TransportStop, pk=pickup_stop_id, school=school)
    drop_stop = get_object_or_404(TransportStop, pk=drop_stop_id, school=school)

    try:
        transport_service.assign_student_to_transport(
            school=school,
            academic_year=academic_year,
            student=student,
            route=route,
            pickup_stop=pickup_stop,
            drop_stop=drop_stop,
            transport_status=status_val,
            notes=notes,
            actor=user
        )
        messages.success(request, f"Assigned {student.get_full_name()} to {route.code} ({pickup_stop.name}).")
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect('transport:students')


@login_required
@require_POST
def student_status_toggle_view(request, pk):
    school = _resolve_school(request)
    user = request.user
    if not (_check_transport_management_perm(user) or user_has_role(user, Role.RECEPTIONIST)):
        raise PermissionDenied()

    assignment = get_object_or_404(StudentTransportAssignment, pk=pk, school=school)
    new_status = request.POST.get('status')
    if new_status in dict(StudentTransportAssignment.STATUS_CHOICES):
        transport_service.update_student_transport_status(assignment, new_status, actor=user)
        messages.success(request, f"Status for {assignment.student.get_full_name()} changed to {assignment.get_transport_status_display()}.")

    return redirect('transport:students')


# =============================================================================
# 7. MY TRANSPORT (STUDENT & PARENT PORTAL)
# =============================================================================

@login_required
def my_transport_view(request):
    school = _resolve_school(request)
    user = request.user

    student = None
    if user_has_role(user, Role.STUDENT):
        student = Student.objects.filter(school=school, user=user).first()
    elif user_has_role(user, Role.PARENT):
        parent = getattr(user, 'parent_profile', None)
        rel = parent.student_relationships.first() if parent else None
        student = rel.student if rel else None

    if not student:
        messages.warning(request, "No student profile linked to your user account.")
        return redirect('index_view')

    info = transport_selectors.get_student_transport_info(student)

    context = {
        'school': school,
        'student': student,
        'info': info,
    }
    return render(request, 'transport/my_transport.html', context)
