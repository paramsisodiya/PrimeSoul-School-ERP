"""
PrimeSoul HR & Payroll Management - Data Models
Complete employee, leave, attendance, salary, and payroll system for Indian K-12 schools.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin


class Department(ExportModelOperationsMixin('hr_department'), TimeStampedModel):
    """Organizational department within a school."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='hr_departments'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name


class HRDesignation(ExportModelOperationsMixin('hr_designation'), TimeStampedModel):
    """Job title/designation for HR (separate from teachers.Designation)."""
    CATEGORY_TEACHING = 'TEACHING'
    CATEGORY_NON_TEACHING = 'NON_TEACHING'
    CATEGORY_ADMINISTRATIVE = 'ADMINISTRATIVE'
    CATEGORY_SUPPORT = 'SUPPORT'

    CATEGORY_CHOICES = (
        (CATEGORY_TEACHING, 'Teaching Staff'),
        (CATEGORY_NON_TEACHING, 'Non-Teaching Staff'),
        (CATEGORY_ADMINISTRATIVE, 'Administrative Staff'),
        (CATEGORY_SUPPORT, 'Support Staff'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='hr_designations'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_TEACHING)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']
        verbose_name = 'HR Designation'
        verbose_name_plural = 'HR Designations'

    def __str__(self):
        return self.name


class Employee(ExportModelOperationsMixin('employee'), TimeStampedModel):
    """Employee profile for HR and payroll management."""
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_ON_LEAVE = 'ON_LEAVE'
    STATUS_SUSPENDED = 'SUSPENDED'
    STATUS_RESIGNED = 'RESIGNED'
    STATUS_TERMINATED = 'TERMINATED'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ON_LEAVE, 'On Leave'),
        (STATUS_SUSPENDED, 'Suspended'),
        (STATUS_RESIGNED, 'Resigned'),
        (STATUS_TERMINATED, 'Terminated'),
    )

    EMPLOYMENT_FULL_TIME = 'FULL_TIME'
    EMPLOYMENT_PART_TIME = 'PART_TIME'
    EMPLOYMENT_CONTRACT = 'CONTRACT'
    EMPLOYMENT_TEMPORARY = 'TEMPORARY'

    EMPLOYMENT_CHOICES = (
        (EMPLOYMENT_FULL_TIME, 'Full Time'),
        (EMPLOYMENT_PART_TIME, 'Part Time'),
        (EMPLOYMENT_CONTRACT, 'Contract'),
        (EMPLOYMENT_TEMPORARY, 'Temporary'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='employees'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profiles'
    )
    employee_code = models.CharField(max_length=50, db_index=True)
    full_name = models.CharField(max_length=200)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    designation = models.ForeignKey(
        HRDesignation, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, default=EMPLOYMENT_FULL_TIME)
    joining_date = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)

    # Sensitive financial fields — must be protected in API responses
    bank_account_number = models.CharField(max_length=30, blank=True, help_text="Bank account number (protected)")
    bank_ifsc = models.CharField(max_length=20, blank=True, help_text="IFSC code")
    bank_name = models.CharField(max_length=200, blank=True)
    pan_number = models.CharField(max_length=10, blank=True, help_text="PAN card number (protected)")
    aadhaar_last4 = models.CharField(max_length=4, blank=True, help_text="Last 4 digits of Aadhaar only")

    emergency_contact = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    photo = models.ImageField(upload_to='hr/photos/', blank=True, null=True)

    class Meta:
        unique_together = ('school', 'employee_code')
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.employee_code})"

    @property
    def masked_bank_account(self):
        """Returns masked bank account: only last 4 digits visible."""
        if len(self.bank_account_number) > 4:
            return 'X' * (len(self.bank_account_number) - 4) + self.bank_account_number[-4:]
        return self.bank_account_number

    @property
    def masked_pan(self):
        """Returns masked PAN: ABCDE****F"""
        if len(self.pan_number) == 10:
            return self.pan_number[:5] + '****' + self.pan_number[-1]
        return self.pan_number


class EmployeeDocument(ExportModelOperationsMixin('employee_document'), TimeStampedModel):
    """Secure document storage for employee records."""
    DOC_JOINING_LETTER = 'JOINING_LETTER'
    DOC_QUALIFICATION = 'QUALIFICATION'
    DOC_ID_PROOF = 'ID_PROOF'
    DOC_EXPERIENCE = 'EXPERIENCE'
    DOC_CONTRACT = 'CONTRACT'
    DOC_OTHER = 'OTHER'

    DOC_TYPE_CHOICES = (
        (DOC_JOINING_LETTER, 'Joining Letter'),
        (DOC_QUALIFICATION, 'Qualification Certificate'),
        (DOC_ID_PROOF, 'ID Proof'),
        (DOC_EXPERIENCE, 'Experience Certificate'),
        (DOC_CONTRACT, 'Contract / Agreement'),
        (DOC_OTHER, 'Other Document'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='employee_documents'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='documents'
    )
    document_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, default=DOC_OTHER)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='hr/documents/')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} — {self.employee.full_name}"


class LeaveType(ExportModelOperationsMixin('leave_type'), TimeStampedModel):
    """Configurable leave categories."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='leave_types'
    )
    name = models.CharField(max_length=100, help_text="e.g. Casual Leave, Sick Leave, Earned Leave")
    code = models.CharField(max_length=20)
    annual_limit = models.PositiveIntegerField(default=12, help_text="Maximum days per academic year")
    carry_forward_allowed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeaveBalance(ExportModelOperationsMixin('leave_balance'), TimeStampedModel):
    """Per-employee leave balance per type per academic year."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='leave_balances'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='leave_balances'
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE, related_name='balances'
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear', on_delete=models.CASCADE, related_name='leave_balances'
    )
    opening_balance = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    accrued = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    used = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))

    class Meta:
        unique_together = ('school', 'employee', 'leave_type', 'academic_year')

    def __str__(self):
        return f"{self.employee.full_name} — {self.leave_type.name} ({self.closing_balance})"

    @property
    def closing_balance(self):
        return self.opening_balance + self.accrued - self.used


class LeaveRequest(ExportModelOperationsMixin('leave_request'), TimeStampedModel):
    """Employee leave application."""
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='leave_requests'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='leave_requests'
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE, related_name='requests'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_approvals'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.employee.full_name} — {self.leave_type.name} ({self.start_date} to {self.end_date})"

    @property
    def leave_days(self):
        """Calculate total leave days (inclusive)."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def days_count(self):
        """Alias for leave_days."""
        return self.leave_days

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")


class EmployeeAttendance(ExportModelOperationsMixin('employee_attendance'), TimeStampedModel):
    """Daily employee attendance (separate from student attendance)."""
    STATUS_PRESENT = 'PRESENT'
    STATUS_ABSENT = 'ABSENT'
    STATUS_HALF_DAY = 'HALF_DAY'
    STATUS_LATE = 'LATE'
    STATUS_ON_LEAVE = 'ON_LEAVE'

    STATUS_CHOICES = (
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_HALF_DAY, 'Half Day'),
        (STATUS_LATE, 'Late'),
        (STATUS_ON_LEAVE, 'On Leave'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='employee_attendance_records'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='attendance_records'
    )
    attendance_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    remarks = models.TextField(blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ('school', 'employee', 'attendance_date')
        ordering = ['-attendance_date']

    def __str__(self):
        return f"{self.employee.full_name} — {self.attendance_date} ({self.status})"


# =============================================================================
# SALARY & PAYROLL
# =============================================================================

class SalaryComponent(ExportModelOperationsMixin('salary_component'), TimeStampedModel):
    """Configurable earning/deduction component."""
    TYPE_EARNING = 'EARNING'
    TYPE_DEDUCTION = 'DEDUCTION'

    TYPE_CHOICES = (
        (TYPE_EARNING, 'Earning'),
        (TYPE_DEDUCTION, 'Deduction'),
    )

    CALC_FIXED = 'FIXED'
    CALC_PERCENTAGE = 'PERCENTAGE'

    CALC_CHOICES = (
        (CALC_FIXED, 'Fixed Amount'),
        (CALC_PERCENTAGE, 'Percentage of Basic'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='salary_components'
    )
    name = models.CharField(max_length=200, help_text="e.g. Basic Salary, HRA, PF, Professional Tax")
    code = models.CharField(max_length=50)
    component_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_EARNING)
    calculation_type = models.CharField(max_length=20, choices=CALC_CHOICES, default=CALC_FIXED)
    default_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    taxable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['component_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_component_type_display()})"


class EmployeeSalaryStructure(ExportModelOperationsMixin('salary_structure'), TimeStampedModel):
    """Active salary structure for an employee."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='salary_structures'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='salary_structures'
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.employee.full_name} — Structure from {self.effective_from}"

    def calculate_gross(self):
        return sum((item.amount for item in self.items.filter(component__component_type=SalaryComponent.TYPE_EARNING)), Decimal('0.00'))

    def calculate_net(self):
        gross = self.calculate_gross()
        deductions = sum((item.amount for item in self.items.filter(component__component_type=SalaryComponent.TYPE_DEDUCTION)), Decimal('0.00'))
        return max(Decimal('0.00'), gross - deductions)


class SalaryStructureItem(models.Model):
    """Individual component within a salary structure."""
    salary_structure = models.ForeignKey(
        EmployeeSalaryStructure, on_delete=models.CASCADE, related_name='items'
    )
    component = models.ForeignKey(
        SalaryComponent, on_delete=models.CASCADE, related_name='structure_items'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                     help_text="Percentage of basic (used when calculation_type is PERCENTAGE)")

    class Meta:
        unique_together = ('salary_structure', 'component')

    def __str__(self):
        return f"{self.component.name}: ₹{self.amount}"


class PayrollPeriod(ExportModelOperationsMixin('payroll_period'), TimeStampedModel):
    """Monthly payroll processing period."""
    STATUS_DRAFT = 'DRAFT'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_PROCESSED = 'PROCESSED'
    STATUS_LOCKED = 'LOCKED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_LOCKED, 'Locked'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='payroll_periods'
    )
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payrolls_processed'
    )

    class Meta:
        unique_together = ('school', 'year', 'month')
        ordering = ['-year', '-month']

    def __str__(self):
        import calendar
        month_name = calendar.month_name[self.month]
        return f"Payroll {month_name} {self.year} ({self.get_status_display()})"


class PayrollRecord(ExportModelOperationsMixin('payroll_record'), TimeStampedModel):
    """Individual employee's payroll calculation for a period."""
    STATUS_DRAFT = 'DRAFT'
    STATUS_CALCULATED = 'CALCULATED'
    STATUS_LOCKED = 'LOCKED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_CALCULATED, 'Calculated'),
        (STATUS_LOCKED, 'Locked'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='payroll_records'
    )
    payroll_period = models.ForeignKey(
        PayrollPeriod, on_delete=models.CASCADE, related_name='records'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='payroll_records'
    )
    working_days = models.PositiveIntegerField(default=0, help_text="Total working days in period")
    payable_days = models.PositiveIntegerField(default=0, help_text="Days employee is payable for")
    leave_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    class Meta:
        unique_together = ('payroll_period', 'employee')
        ordering = ['employee__full_name']

    def __str__(self):
        return f"{self.employee.full_name} — ₹{self.net_salary} ({self.payroll_period})"

    @property
    def items(self):
        return self.line_items.all()


class PayrollLineItem(models.Model):
    """Detailed breakdown of each salary component in a payroll record."""
    payroll_record = models.ForeignKey(
        PayrollRecord, on_delete=models.CASCADE, related_name='line_items'
    )
    component = models.ForeignKey(
        SalaryComponent, on_delete=models.CASCADE, related_name='payroll_items'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    calculation_details = models.TextField(blank=True, help_text="Explanation of how this was calculated")

    class Meta:
        unique_together = ('payroll_record', 'component')

    def __str__(self):
        return f"{self.component.name}: ₹{self.amount}"
