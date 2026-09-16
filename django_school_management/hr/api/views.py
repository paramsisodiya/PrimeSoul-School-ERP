"""
PrimeSoul HR & Payroll - REST API ViewSets & Actions
Tenant-scoped endpoints with RBAC and sensitive data protection.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord
)
from django_school_management.hr.api.serializers import (
    DepartmentSerializer, HRDesignationSerializer, EmployeeListSerializer,
    EmployeeDetailSerializer, EmployeeDocumentSerializer, LeaveTypeSerializer,
    LeaveBalanceSerializer, LeaveRequestSerializer, EmployeeAttendanceSerializer,
    SalaryComponentSerializer, EmployeeSalaryStructureSerializer,
    PayrollPeriodSerializer, PayrollRecordSerializer,
    ApplyLeaveRequestSerializer, ProcessPayrollRequestSerializer
)
from django_school_management.hr.services import leave_service, payroll_service
from django_school_management.hr.selectors import hr_selectors


class TenantScopedMixin:
    """Ensures queryset is filtered by active school context."""
    def get_school(self):
        req = self.request
        return getattr(req, 'school', None) or getattr(req.user, 'school', None) or School.objects.first()

    def get_queryset(self):
        qs = super().get_queryset()
        school = self.get_school()
        if school and hasattr(qs.model, 'school'):
            return qs.filter(school=school)
        return qs


class DepartmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class HRDesignationViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = HRDesignation.objects.all()
    serializer_class = HRDesignationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class EmployeeViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return EmployeeDetailSerializer
        return EmployeeListSerializer

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class EmployeeDocumentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = EmployeeDocument.objects.all()
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school(), uploaded_by=self.request.user)


class LeaveTypeViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class LeaveBalanceViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = LeaveBalance.objects.all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL):
            return qs.filter(employee__user=user)
        return qs


class LeaveRequestViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL):
            return qs.filter(employee__user=user)
        return qs


class EmployeeAttendanceViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = EmployeeAttendance.objects.all()
    serializer_class = EmployeeAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL):
            return qs.filter(employee__user=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.get_school(), marked_by=self.request.user)


class SalaryComponentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = SalaryComponent.objects.all()
    serializer_class = SalaryComponentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class EmployeeSalaryStructureViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = EmployeeSalaryStructure.objects.all()
    serializer_class = EmployeeSalaryStructureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.ACCOUNTANT):
            return qs.filter(employee__user=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class PayrollPeriodViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class PayrollRecordViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = PayrollRecord.objects.all()
    serializer_class = PayrollRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.ACCOUNTANT):
            return qs.filter(employee__user=user)
        return qs


class HRDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        metrics = hr_selectors.get_dashboard_metrics(school)
        return Response(metrics)


class MyEmployeeProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        emp = Employee.objects.filter(school=school, user=request.user).first()
        if not emp:
            return Response({'detail': 'No employee record found for current user.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(EmployeeDetailSerializer(emp, context={'request': request}).data)


class MyLeaveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        emp = Employee.objects.filter(school=school, user=request.user).first()
        if not emp:
            return Response({'detail': 'No employee record found.'}, status=status.HTTP_404_NOT_FOUND)
        summary = hr_selectors.get_leave_summary(school, emp)
        return Response({
            'balances': LeaveBalanceSerializer(summary['balances'], many=True).data,
            'recent_requests': LeaveRequestSerializer(summary['recent_requests'], many=True).data
        })


class MyPayslipsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        emp = Employee.objects.filter(school=school, user=request.user).first()
        if not emp:
            return Response({'detail': 'No employee record found.'}, status=status.HTTP_404_NOT_FOUND)
        records = PayrollRecord.objects.filter(school=school, employee=emp).order_by('-payroll_period__year', '-payroll_period__month')
        return Response(PayrollRecordSerializer(records, many=True).data)


class ApplyLeaveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()

        employee = Employee.objects.filter(school=school, user=user).first()
        if not employee:
            return Response({'detail': 'No employee record linked.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApplyLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        leave_type = get_object_or_404(LeaveType, pk=data['leave_type_id'], school=school)

        try:
            lr = leave_service.apply_leave(
                school=school, employee=employee, leave_type=leave_type,
                start_date=data['start_date'], end_date=data['end_date'],
                reason=data['reason'], actor=user
            )
            return Response(LeaveRequestSerializer(lr).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProcessPayrollAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.ACCOUNTANT):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProcessPayrollRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        period = get_object_or_404(PayrollPeriod, pk=data['payroll_period_id'], school=school)

        try:
            records = payroll_service.process_payroll_period(
                school=school, period=period, actor=user
            )
            return Response({'status': 'processed', 'records_count': len(records), 'period': PayrollPeriodSerializer(period).data})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
