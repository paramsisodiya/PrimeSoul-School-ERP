"""
PrimeSoul HR & Payroll - Modern ERP Forms
"""
from django import forms
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod
)
from django_school_management.accounts.models import User
from django_school_management.academics.models import AcademicYear


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Science & Mathematics'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SCI-MATH'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class HRDesignationForm(forms.ModelForm):
    class Meta:
        model = HRDesignation
        fields = ['name', 'code', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior PGT Teacher'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. PGT-SR'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'user', 'employee_code', 'full_name', 'gender', 'date_of_birth',
            'mobile', 'email', 'address', 'designation', 'department',
            'employment_type', 'joining_date', 'confirmation_date',
            'bank_account_number', 'bank_ifsc', 'bank_name', 'pan_number',
            'aadhaar_last4', 'emergency_contact', 'status', 'photo'
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'employee_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EMP-001'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Legal Name'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit mobile'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'official/personal email'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'designation': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'confirmation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full account number'}),
            'bank_ifsc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HDFC0001234'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HDFC Bank'}),
            'pan_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ABCDE1234F'}),
            'aadhaar_last4': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last 4 digits only', 'maxlength': '4'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name & Phone'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['designation'].queryset = HRDesignation.objects.filter(school=school, is_active=True)
            self.fields['department'].queryset = Department.objects.filter(school=school, is_active=True)
            self.fields['user'].queryset = User.objects.filter(school=school, is_active=True)


class EmployeeDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['document_type', 'title', 'file', 'issue_date', 'expiry_date']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Document description'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'code', 'annual_limit', 'carry_forward_allowed', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Casual Leave'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CL'}),
            'annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'carry_forward_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for leave application'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['leave_type'].queryset = LeaveType.objects.filter(school=school, is_active=True)


LeaveApplyForm = LeaveRequestForm


class SalaryComponentForm(forms.ModelForm):
    class Meta:
        model = SalaryComponent
        fields = ['name', 'code', 'component_type', 'calculation_type', 'default_value', 'taxable', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Basic Salary, HRA, PF'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BASIC, HRA, PF'}),
            'component_type': forms.Select(attrs={'class': 'form-control'}),
            'calculation_type': forms.Select(attrs={'class': 'form-control'}),
            'default_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taxable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = ['year', 'month']
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '2026'}),
            'month': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1-12', 'min': 1, 'max': 12}),
        }
