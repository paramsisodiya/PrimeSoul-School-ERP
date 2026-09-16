from decimal import Decimal
from django.db import models
from django.conf import settings
from django_school_management.tenants.models import TenantModel, School


class FeeHeadCategory(models.TextChoices):
    TUITION = 'TUITION', 'Tuition Fee'
    ADMISSION = 'ADMISSION', 'Admission Fee'
    ANNUAL = 'ANNUAL', 'Annual Charges'
    DEVELOPMENT = 'DEVELOPMENT', 'Development Fee'
    COMPUTER = 'COMPUTER', 'Computer / IT Fee'
    LAB = 'LAB', 'Science / Lab Fee'
    ACTIVITY = 'ACTIVITY', 'Sports & Activity Fee'
    EXAM = 'EXAM', 'Examination Fee'
    TRANSPORT = 'TRANSPORT', 'Transport / Bus Fee'
    LIBRARY = 'LIBRARY', 'Library Fee'
    HOSTEL = 'HOSTEL', 'Hostel Fee'
    OTHER = 'OTHER', 'Other / Miscellaneous'


class FeeFrequency(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly (Q1, Q2, Q3, Q4)'
    HALF_YEARLY = 'HALF_YEARLY', 'Half-Yearly'
    ANNUAL = 'ANNUAL', 'Annual (One-Time)'
    CUSTOM = 'CUSTOM', 'Custom Frequency'


class ConcessionType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage (%)'
    FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount (₹)'
    FULL_WAIVER = 'FULL_WAIVER', '100% Full Waiver'


class InstallmentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PARTIAL = 'PARTIAL', 'Partially Paid'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    WAIVED = 'WAIVED', 'Waived'
    CANCELLED = 'CANCELLED', 'Cancelled'


class InvoiceStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PARTIAL = 'PARTIAL', 'Partially Paid'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'


class PaymentGateway(models.TextChoices):
    CASH = 'CASH', 'Cash'
    CHEQUE = 'CHEQUE', 'Cheque / Demand Draft'
    UPI = 'UPI', 'UPI Manual / Static QR'
    CARD = 'CARD', 'Debit / Credit Card (POS)'
    NET_BANKING = 'NET_BANKING', 'Net Banking / NEFT / RTGS'
    RAZORPAY = 'RAZORPAY', 'Razorpay Payment Gateway'
    OTHER = 'OTHER', 'Other Gateway / Mode'


class PaymentStatus(models.TextChoices):
    INITIATED = 'INITIATED', 'Initiated'
    PENDING = 'PENDING', 'Pending / Processing'
    SUCCESS = 'SUCCESS', 'Success / Completed'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ChequeClearanceStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Clearance'
    CLEARED = 'CLEARED', 'Cleared / Realized'
    BOUNCED = 'BOUNCED', 'Bounced / Returned'


class FeeHead(TenantModel):
    """
    Categorized Fee Component (e.g. Tuition Fee, Computer Fee, Lab Fee).
    Scoped per School tenant.
    """
    name = models.CharField(max_length=150, help_text="e.g. Tuition Fee")
    code = models.CharField(max_length=50, help_text="e.g. TUITION, ANNUAL, TRANSPORT")
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=50,
        choices=FeeHeadCategory.choices,
        default=FeeHeadCategory.TUITION
    )
    is_recurring = models.BooleanField(default=True, help_text="True if charged on recurring intervals")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code'], name='unique_school_fee_head_code')
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class FeeStructure(TenantModel):
    """
    Master Fee Structure defined for a specific Grade Level in an Academic Year.
    """
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='fee_structures'
    )
    grade_level = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        related_name='fee_structures'
    )
    name = models.CharField(max_length=150, help_text="e.g. Class 10 Standard Fee 2026-27")
    effective_from = models.DateField()
    effective_to = models.DateField()
    frequency = models.CharField(
        max_length=30,
        choices=FeeFrequency.choices,
        default=FeeFrequency.QUARTERLY
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['academic_year', 'grade_level', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'grade_level', 'name'],
                name='unique_school_grade_fee_structure'
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.grade_level.name} ({self.academic_year.name})"

    @property
    def total_structure_amount(self):
        return sum([item.amount for item in self.items.all()]) or Decimal('0.00')


class FeeStructureItem(models.Model):
    """
    Individual fee head line items inside a FeeStructure.
    """
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.CASCADE,
        related_name='items'
    )
    fee_head = models.ForeignKey(
        FeeHead,
        on_delete=models.CASCADE,
        related_name='structure_items'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in INR")
    mandatory = models.BooleanField(default=True)
    due_day = models.PositiveSmallIntegerField(
        default=10,
        help_text="Day of month on which installment is due (e.g. 10th)"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fee_structure', 'fee_head'], name='unique_structure_fee_head')
        ]

    def __str__(self):
        return f"{self.fee_head.name}: ₹{self.amount}"


class FeeConcession(TenantModel):
    """
    Configurable concession/scholarship rule (e.g. Sibling Discount, Staff Ward, RTE, Merit).
    """
    name = models.CharField(max_length=150, help_text="e.g. Sibling Concession 20%")
    concession_type = models.CharField(
        max_length=30,
        choices=ConcessionType.choices,
        default=ConcessionType.PERCENTAGE
    )
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Percentage value (e.g. 20.00) or fixed amount in INR (e.g. 5000.00)"
    )
    maximum_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional ceiling cap for percentage concessions in INR"
    )
    applicable_fee_heads = models.ManyToManyField(
        FeeHead,
        blank=True,
        related_name='concessions',
        help_text="Specific fee heads eligible for this concession. If empty, applies to Tuition Fee by default."
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    approval_required = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_concessions'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_concession_type_display()} - {self.value})"


class StudentFeeAssignment(models.Model):
    """
    Assigns a FeeStructure and optional Concession to an individual Student for an Academic Year.
    """
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='fee_assignments'
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.CASCADE,
        related_name='assigned_students'
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='student_fee_assignments'
    )
    concession = models.ForeignKey(
        FeeConcession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    custom_concession_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Additional custom one-off concession amount in INR"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('EXEMPTED', 'Exempted')],
        default='ACTIVE'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'academic_year', 'fee_structure'],
                name='unique_student_year_fee_structure'
            )
        ]

    def __str__(self):
        return f"{self.student} -> {self.fee_structure.name}"


class FeeInstallment(models.Model):
    """
    Individual installment due line (e.g. Q1, Q2, April, May) for a student.
    Tracks payable, paid, and remaining balance deterministically.
    """
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='fee_installments'
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='fee_installments'
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installments'
    )
    installment_name = models.CharField(max_length=150, help_text="e.g. Q1 (Apr-Jun 2026), July 2026")
    due_date = models.DateField()
    
    # Financial values (All in INR Decimals)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    concession_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    late_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(
        max_length=30,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'student']

    def __str__(self):
        return f"{self.student} - {self.installment_name}: Payable ₹{self.payable_amount}, Balance ₹{self.balance_amount}"

    def update_balance_and_status(self):
        """Re-computes balance and status from paid_amount and payable_amount."""
        self.balance_amount = max(Decimal('0.00'), self.payable_amount - self.paid_amount)
        if self.paid_amount >= self.payable_amount:
            self.status = InstallmentStatus.PAID
        elif self.paid_amount > Decimal('0.00'):
            self.status = InstallmentStatus.PARTIAL
        else:
            self.status = InstallmentStatus.PENDING
        self.save(update_fields=['balance_amount', 'paid_amount', 'status', 'updated_at'])


class FeeInvoice(TenantModel):
    """
    Formal Fee Invoice issued to a student with sequential invoice number per school.
    """
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='fee_invoices'
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_invoices'
    )
    invoice_number = models.CharField(max_length=100, db_index=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    concession = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    late_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(
        max_length=30,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PENDING
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-invoice_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['school', 'invoice_number'], name='unique_school_invoice_number')
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.student.name}): ₹{self.total} [{self.get_status_display()}]"

    def update_balance_and_status(self):
        self.balance_amount = max(Decimal('0.00'), self.total - self.paid_amount)
        if self.paid_amount >= self.total:
            self.status = InvoiceStatus.PAID
        elif self.paid_amount > Decimal('0.00'):
            self.status = InvoiceStatus.PARTIAL
        else:
            self.status = InvoiceStatus.PENDING
        self.save(update_fields=['balance_amount', 'paid_amount', 'status', 'updated_at'])


class PaymentTransaction(TenantModel):
    """
    Immutable payment record for both offline (Cash/Cheque/POS) and online (Razorpay/UPI) transactions.
    """
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    invoice = models.ForeignKey(
        FeeInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    transaction_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Unique Gateway ID, Cheque Ref, or Cash Voucher ID"
    )
    gateway = models.CharField(
        max_length=50,
        choices=PaymentGateway.choices,
        default=PaymentGateway.CASH
    )
    payment_method = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED
    )
    gateway_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_payments'
    )

    # Cheque / Demand Draft Specifics
    cheque_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    clearance_status = models.CharField(
        max_length=30,
        choices=ChequeClearanceStatus.choices,
        default=ChequeClearanceStatus.PENDING,
        blank=True
    )
    cleared_at = models.DateTimeField(null=True, blank=True)

    # Razorpay Specifics
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-paid_at', '-created_at']

    def __str__(self):
        return f"Payment #{self.transaction_id} ({self.get_gateway_display()}): ₹{self.amount} [{self.get_status_display()}]"


class PaymentAllocation(models.Model):
    """
    Maps atomic allocations of a single PaymentTransaction against Invoices or Installments.
    """
    payment = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    invoice = models.ForeignKey(
        FeeInvoice,
        on_delete=models.CASCADE,
        related_name='allocations',
        null=True,
        blank=True
    )
    installment = models.ForeignKey(
        FeeInstallment,
        on_delete=models.CASCADE,
        related_name='allocations',
        null=True,
        blank=True
    )
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Allocation ₹{self.allocated_amount} from Payment {self.payment.transaction_id}"


class FeeReceipt(TenantModel):
    """
    Official Tax & Fee Receipt issued to parents/students with sequential receipt number per school.
    """
    receipt_number = models.CharField(max_length=100, db_index=True)
    payment = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='receipt'
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='fee_receipts'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    receipt_date = models.DateField()
    generated_pdf = models.FileField(upload_to='fees/receipts/', blank=True, null=True)
    qr_verification_code = models.CharField(max_length=255, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_receipts'
    )

    class Meta:
        ordering = ['-receipt_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['school', 'receipt_number'], name='unique_school_receipt_number')
        ]

    def __str__(self):
        return f"Receipt {self.receipt_number} ({self.student.name}): ₹{self.amount}"


class FeeAuditLog(models.Model):
    """
    Append-only audit ledger recording every financial transaction and state change.
    """
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='fee_audit_logs'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action = models.CharField(max_length=100, help_text="e.g. INVOICE_CREATED, PAYMENT_RECEIVED, CHEQUE_BOUNCED")
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.action} on {self.model_name} #{self.object_id} by {self.actor}"
