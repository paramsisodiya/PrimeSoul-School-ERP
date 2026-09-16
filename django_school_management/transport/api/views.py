"""
PrimeSoul Transport - REST API ViewSets & Actions
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.academics.models import AcademicYear
from django_school_management.students.models import Student

from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.transport.services import transport_service
from django_school_management.transport.selectors import transport_selectors
from .serializers import (
    TransportVehicleSerializer, TransportStaffSerializer,
    TransportRouteSerializer, TransportStopSerializer,
    VehicleRouteAssignmentSerializer, StudentTransportAssignmentSerializer
)


class TenantScopedMixin:
    """Ensures querysets are strictly scoped to the active request school tenant."""
    def get_school(self):
        user = self.request.user
        if hasattr(self.request, 'tenant') and self.request.tenant:
            return self.request.tenant
        if hasattr(self.request, 'school') and self.request.school:
            return self.request.school
        if user.is_authenticated and hasattr(user, 'school') and user.school:
            return user.school
        if user.is_superuser:
            return School.objects.filter(is_active=True).first()
        return None

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return self.queryset.none()
        return self.queryset.filter(school=school)


class TransportVehicleViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TransportVehicle.objects.all()
    serializer_class = TransportVehicleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class TransportStaffViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TransportStaff.objects.all()
    serializer_class = TransportStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class TransportRouteViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TransportRoute.objects.all()
    serializer_class = TransportRouteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class TransportStopViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TransportStop.objects.all()
    serializer_class = TransportStopSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class VehicleRouteAssignmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = VehicleRouteAssignment.objects.all()
    serializer_class = VehicleRouteAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        school = self.get_school()
        if not user_has_role(request.user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.TRANSPORT_MANAGER):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        ay = get_object_or_404(AcademicYear, pk=data.get('academic_year'), school=school)
        veh = get_object_or_404(TransportVehicle, pk=data.get('vehicle'), school=school)
        rt = get_object_or_404(TransportRoute, pk=data.get('route'), school=school)
        drv = get_object_or_404(TransportStaff, pk=data.get('driver'), school=school)
        att = TransportStaff.objects.filter(pk=data.get('attendant'), school=school).first() if data.get('attendant') else None

        try:
            assignment = transport_service.assign_vehicle_to_route(
                school=school,
                academic_year=ay,
                vehicle=veh,
                route=rt,
                driver=drv,
                attendant=att,
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                actor=request.user
            )
            serializer = self.get_serializer(assignment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StudentTransportAssignmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StudentTransportAssignment.objects.all()
    serializer_class = StudentTransportAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        school = self.get_school()

        # Student scoping: only their own assignment
        if user_has_role(user, Role.STUDENT):
            return qs.filter(student__user=user)

        # Parent scoping: only their children's assignments
        if user_has_role(user, Role.PARENT):
            parent = getattr(user, 'parent_profile', None)
            return qs.filter(student__guardian_relationships__guardian=parent) if parent else qs.none()

        return qs

    def create(self, request, *args, **kwargs):
        school = self.get_school()
        if not (user_has_role(request.user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.TRANSPORT_MANAGER, Role.RECEPTIONIST)):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        ay = get_object_or_404(AcademicYear, pk=data.get('academic_year'), school=school)
        st = get_object_or_404(Student, pk=data.get('student'), school=school)
        rt = get_object_or_404(TransportRoute, pk=data.get('route'), school=school)
        ps = get_object_or_404(TransportStop, pk=data.get('pickup_stop'), school=school)
        ds = get_object_or_404(TransportStop, pk=data.get('drop_stop'), school=school)

        try:
            assignment = transport_service.assign_student_to_transport(
                school=school,
                academic_year=ay,
                student=st,
                route=rt,
                pickup_stop=ps,
                drop_stop=ds,
                transport_status=data.get('transport_status', StudentTransportAssignment.STATUS_ACTIVE),
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                notes=data.get('notes', ''),
                actor=request.user
            )
            serializer = self.get_serializer(assignment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TransportDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        metrics = transport_selectors.get_transport_dashboard_metrics(school)
        return Response({
            'total_vehicles': metrics['total_vehicles'],
            'active_routes': metrics['active_routes'],
            'total_stops': metrics['total_stops'],
            'active_students': metrics['active_students'],
            'drivers_count': metrics['drivers_count'],
            'attendants_count': metrics['attendants_count'],
            'expiring_licenses_count': metrics['expiring_licenses_count'],
            'expiring_vehicles_count': metrics['expiring_vehicles_count'],
        })


class MyTransportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()

        student = None
        if user_has_role(user, Role.STUDENT):
            student = Student.objects.filter(school=school, user=user).first()
        elif user_has_role(user, Role.PARENT):
            parent = getattr(user, 'parent_profile', None)
            rel = parent.student_relationships.first() if parent else None
            student = rel.student if rel else None

        if not student:
            return Response({'detail': "No student record linked to account."}, status=status.HTTP_404_NOT_FOUND)

        info = transport_selectors.get_student_transport_info(student)
        if not info:
            return Response({'detail': "No active transport subscription found for student."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'student_name': student.get_full_name(),
            'route_name': info['route'].name,
            'route_code': info['route'].code,
            'pickup_stop': info['pickup_stop'].name,
            'pickup_time': info['pickup_stop'].pickup_time.strftime('%H:%M') if info['pickup_stop'].pickup_time else None,
            'drop_stop': info['drop_stop'].name,
            'drop_time': info['drop_stop'].drop_time.strftime('%H:%M') if info['drop_stop'].drop_time else None,
            'vehicle_number': info['vehicle'].vehicle_number if info['vehicle'] else None,
            'driver_name': info['driver_name'],
            'driver_phone': info['driver_phone'],
            'attendant_name': info['attendant_name'],
            'attendant_phone': info['attendant_phone'],
        })
