"""
PrimeSoul HR - DRF Serializers
Sensitive fields are redacted based on role.
"""
from rest_framework import serializers
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord, PayrollLineItem
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ('school',)


class HRDesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HRDesignation
        fields = '__all__'
        read_only_fields = ('school',)


class EmployeeSerializer(serializers.ModelSerializer):
    """Default serializer — redacts sensitive fields."""
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    designation_name = serializers.CharField(source='designation.name', read_only=True, default='')
    masked_bank_account = serializers.CharField(read_only=True)
    masked_pan = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        exclude = ('bank_account_number', 'pan_number')
        read_only_fields = ('school',)


EmployeeListSerializer = EmployeeSerializer
EmployeeDetailSerializer = EmployeeSerializer


class EmployeeAdminSerializer(serializers.ModelSerializer):
    """Admin serializer — includes all fields for authorized users."""
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    designation_name = serializers.CharField(source='designation.name', read_only=True, default='')

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = ('school',)


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = '__all__'
        read_only_fields = ('school', 'uploaded_by', 'uploaded_at')


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'
        read_only_fields = ('school',)


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    closing_balance = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)

    class Meta:
        model = LeaveBalance
        fields = '__all__'
        read_only_fields = ('school',)


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ('school', 'approved_by', 'approved_at')


class EmployeeAttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeAttendance
        fields = '__all__'
        read_only_fields = ('school', 'marked_by')


class SalaryComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryComponent
        fields = '__all__'
        read_only_fields = ('school',)


class SalaryStructureItemSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source='component.name', read_only=True)

    class Meta:
        model = SalaryStructureItem
        fields = '__all__'


class EmployeeSalaryStructureSerializer(serializers.ModelSerializer):
    items = SalaryStructureItemSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeSalaryStructure
        fields = '__all__'
        read_only_fields = ('school',)


class PayrollPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPeriod
        fields = '__all__'
        read_only_fields = ('school', 'processed_at', 'processed_by')


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)

    class Meta:
        model = PayrollRecord
        fields = '__all__'
        read_only_fields = ('school',)


class PayrollLineItemSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source='component.name', read_only=True)

    class Meta:
        model = PayrollLineItem
        fields = '__all__'


class ApplyLeaveRequestSerializer(serializers.Serializer):
    leave_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField()


class ProcessPayrollRequestSerializer(serializers.Serializer):
    payroll_period_id = serializers.IntegerField()
    working_days = serializers.IntegerField(required=False, default=0)
