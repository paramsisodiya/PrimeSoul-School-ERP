from django.contrib import admin
from .models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord, PayrollLineItem
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'code')


@admin.register(HRDesignation)
class HRDesignationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'school', 'is_active')
    list_filter = ('school', 'category', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'full_name', 'designation', 'department', 'employment_type', 'status', 'school')
    list_filter = ('school', 'status', 'employment_type', 'department')
    search_fields = ('employee_code', 'full_name', 'mobile', 'email')


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'document_type', 'title', 'issue_date', 'expiry_date', 'school')
    list_filter = ('school', 'document_type')
    search_fields = ('employee__full_name', 'title')


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'annual_limit', 'carry_forward_allowed', 'school')
    list_filter = ('school',)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'academic_year', 'opening_balance', 'accrued', 'used', 'closing_balance', 'school')
    list_filter = ('school', 'academic_year')
    search_fields = ('employee__full_name',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status', 'approved_by', 'school')
    list_filter = ('school', 'status', 'leave_type')
    search_fields = ('employee__full_name',)


@admin.register(EmployeeAttendance)
class EmployeeAttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'attendance_date', 'status', 'marked_by', 'school')
    list_filter = ('school', 'status', 'attendance_date')
    search_fields = ('employee__full_name',)


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'component_type', 'calculation_type', 'default_value', 'taxable', 'school')
    list_filter = ('school', 'component_type', 'calculation_type')


class SalaryStructureItemInline(admin.TabularInline):
    model = SalaryStructureItem
    extra = 1


@admin.register(EmployeeSalaryStructure)
class EmployeeSalaryStructureAdmin(admin.ModelAdmin):
    list_display = ('employee', 'effective_from', 'effective_to', 'is_active', 'school')
    list_filter = ('school', 'is_active')
    inlines = [SalaryStructureItemInline]


class PayrollLineItemInline(admin.TabularInline):
    model = PayrollLineItem
    extra = 0
    readonly_fields = ('component', 'amount', 'calculation_details')


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'status', 'processed_at', 'school')
    list_filter = ('school', 'year', 'status')


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'payroll_period', 'gross_earnings', 'total_deductions', 'net_salary', 'status', 'school')
    list_filter = ('school', 'status', 'payroll_period__year', 'payroll_period__month')
    search_fields = ('employee__full_name', 'employee__employee_code')
    inlines = [PayrollLineItemInline]
