from django.db import models
from django.conf import settings
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django_school_management.utils.india_localization import (
    INDIAN_GRADE_LEVELS, INDIAN_ACADEMIC_STREAMS
)


class AdmissionSession(ExportModelOperationsMixin('admission_session'), TimeStampedModel):
    """
    Intake cycle for student admissions tied to an Academic Year.
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_ARCHIVED = 'ARCHIVED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_OPEN, 'Open for Applications'),
        (STATUS_CLOSED, 'Applications Closed'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_sessions'
    )
    name = models.CharField(max_length=150, help_text="e.g. Academic Session 2026-27 Admissions")
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='admission_sessions'
    )
    application_start = models.DateField()
    application_end = models.DateField()
    admission_start = models.DateField()
    admission_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    application_number_prefix = models.CharField(max_length=20, default='APP-2026')
    admission_number_prefix = models.CharField(max_length=20, default='ADM-2026')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-academic_year__start_date', '-created']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_admission_session_name')
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        return self.status == self.STATUS_OPEN and self.active


class AdmissionClassConfig(ExportModelOperationsMixin('admission_class_config'), TimeStampedModel):
    """
    Seat quota and capacity configuration per Grade Level for an admission intake.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_class_configs'
    )
    admission_session = models.ForeignKey(
        AdmissionSession,
        on_delete=models.CASCADE,
        related_name='class_configs'
    )
    grade_level = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        related_name='admission_configs'
    )
    total_seats = models.PositiveIntegerField(default=40)
    reserved_seats = models.PositiveIntegerField(default=0, help_text="RTE / Quota / Staff ward reserved seats")
    application_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['grade_level__display_order']
        constraints = [
            models.UniqueConstraint(fields=['school', 'admission_session', 'grade_level'], name='unique_session_grade_seat_config')
        ]

    def __str__(self):
        return f"{self.grade_level.name} - Seats: {self.total_seats} ({self.admission_session.name})"


class AdmissionEnquiry(ExportModelOperationsMixin('admission_enquiry'), TimeStampedModel):
    """
    Prospective student enquiry / lead tracking.
    """
    SOURCE_WALK_IN = 'WALK_IN'
    SOURCE_WEBSITE = 'WEBSITE'
    SOURCE_PHONE = 'PHONE'
    SOURCE_REFERRAL = 'REFERRAL'
    SOURCE_SOCIAL_MEDIA = 'SOCIAL_MEDIA'
    SOURCE_OTHER = 'OTHER'

    SOURCE_CHOICES = (
        (SOURCE_WALK_IN, 'Walk-In / Campus Visit'),
        (SOURCE_WEBSITE, 'Website Online Enquiry'),
        (SOURCE_PHONE, 'Telephone Enquiry'),
        (SOURCE_REFERRAL, 'Parent / Staff Referral'),
        (SOURCE_SOCIAL_MEDIA, 'Social Media Campaign'),
        (SOURCE_OTHER, 'Other'),
    )

    STATUS_NEW = 'NEW'
    STATUS_CONTACTED = 'CONTACTED'
    STATUS_FOLLOW_UP = 'FOLLOW_UP'
    STATUS_CONVERTED = 'CONVERTED'
    STATUS_LOST = 'LOST'
    STATUS_CLOSED = 'CLOSED'

    STATUS_CHOICES = (
        (STATUS_NEW, 'New Enquiry'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_FOLLOW_UP, 'Follow-up Scheduled'),
        (STATUS_CONVERTED, 'Converted to Application'),
        (STATUS_LOST, 'Lost / Not Interested'),
        (STATUS_CLOSED, 'Closed'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_enquiries'
    )
    admission_session = models.ForeignKey(
        AdmissionSession,
        on_delete=models.CASCADE,
        related_name='enquiries'
    )
    enquiry_number = models.CharField(max_length=50, db_index=True)
    student_name = models.CharField(max_length=150)
    parent_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=20, help_text="10-digit Indian mobile number")
    email = models.EmailField(blank=True)
    interested_grade = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='enquiries'
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_WALK_IN)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_enquiries'
    )

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(fields=['school', 'enquiry_number'], name='unique_school_enquiry_number')
        ]

    def __str__(self):
        return f"Enquiry #{self.enquiry_number}: {self.student_name} ({self.get_status_display()})"


class AdmissionApplication(ExportModelOperationsMixin('admission_application'), TimeStampedModel):
    """
    Formal Student Admission Application.
    Manages complete applicant lifecycle from submission to admission conversion.
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_UNDER_REVIEW = 'UNDER_REVIEW'
    STATUS_SHORTLISTED = 'SHORTLISTED'
    STATUS_INTERVIEW = 'INTERVIEW'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_WAITLISTED = 'WAITLISTED'
    STATUS_ADMITTED = 'ADMITTED'
    STATUS_WITHDRAWN = 'WITHDRAWN'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_SHORTLISTED, 'Shortlisted'),
        (STATUS_INTERVIEW, 'Interview / Assessment Scheduled'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_WAITLISTED, 'Waitlisted'),
        (STATUS_ADMITTED, 'Admitted / Enrolled'),
        (STATUS_WITHDRAWN, 'Withdrawn by Parent'),
    )

    FEE_NOT_REQUIRED = 'NOT_REQUIRED'
    FEE_PENDING = 'PENDING'
    FEE_PAID = 'PAID'
    FEE_WAIVED = 'WAIVED'

    FEE_STATUS_CHOICES = (
        (FEE_NOT_REQUIRED, 'Not Required'),
        (FEE_PENDING, 'Payment Pending'),
        (FEE_PAID, 'Paid'),
        (FEE_WAIVED, 'Waived'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_applications'
    )
    admission_session = models.ForeignKey(
        AdmissionSession,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    enquiry = models.ForeignKey(
        AdmissionEnquiry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='applications'
    )
    application_number = models.CharField(max_length=50, db_index=True)

    # Student personal information
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=(('M', 'Male'), ('F', 'Female'), ('O', 'Other')))
    blood_group = models.CharField(max_length=10, blank=True)
    nationality = models.CharField(max_length=50, default='Indian')
    category = models.CharField(max_length=50, default='General')
    aadhaar_number = models.CharField(max_length=20, blank=True, help_text="12-digit Indian National Identity")

    # Academic Choice
    requested_grade = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        related_name='admission_applications'
    )
    requested_stream = models.ForeignKey(
        'academics.AcademicStream',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admission_applications'
    )
    previous_school = models.CharField(max_length=255, blank=True)
    previous_school_tc_number = models.CharField(max_length=100, blank=True)
    previous_grade = models.CharField(max_length=50, blank=True)
    previous_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Parent / Guardian Details
    father_name = models.CharField(max_length=150, blank=True)
    father_mobile = models.CharField(max_length=20, blank=True)
    father_email = models.EmailField(blank=True)
    father_occupation = models.CharField(max_length=100, blank=True)
    father_aadhaar = models.CharField(max_length=20, blank=True)

    mother_name = models.CharField(max_length=150, blank=True)
    mother_mobile = models.CharField(max_length=20, blank=True)
    mother_email = models.EmailField(blank=True)
    mother_occupation = models.CharField(max_length=100, blank=True)
    mother_aadhaar = models.CharField(max_length=20, blank=True)

    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_mobile = models.CharField(max_length=20, blank=True)
    guardian_relation = models.CharField(max_length=50, blank=True)

    # Address & Emergency
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True)

    # Workflow & Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    application_fee_status = models.CharField(max_length=20, choices=FEE_STATUS_CHOICES, default=FEE_NOT_REQUIRED)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_admissions'
    )
    rejection_reason = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    # Converted Student Reference
    admitted_student = models.ForeignKey(
        'students.Student',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admission_application'
    )
    admitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(fields=['school', 'admission_session', 'application_number'], name='unique_school_session_app_num')
        ]

    def __str__(self):
        return f"App #{self.application_number}: {self.get_full_name()} ({self.get_status_display()})"

    def get_full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p]).strip() or f"Applicant #{self.pk}"

    @property
    def is_admitted(self) -> bool:
        return self.status == self.STATUS_ADMITTED and bool(self.admitted_student)


class AdmissionDocument(ExportModelOperationsMixin('admission_document'), TimeStampedModel):
    """
    Supporting identification and academic certificates uploaded for an application.
    """
    TYPE_BIRTH_CERTIFICATE = 'birth_certificate'
    TYPE_PREVIOUS_TC = 'transfer_certificate'
    TYPE_MARKSHEET = 'previous_school_certificate'
    TYPE_ADDRESS_PROOF = 'address_proof'
    TYPE_STUDENT_PHOTO = 'student_photo'
    TYPE_PARENT_ID = 'parent_id'
    TYPE_ACADEMIC_DOC = 'academic_document'
    TYPE_OTHER = 'other'

    DOCUMENT_TYPE_CHOICES = (
        (TYPE_BIRTH_CERTIFICATE, 'Birth Certificate'),
        (TYPE_PREVIOUS_TC, 'Transfer Certificate (TC)'),
        (TYPE_MARKSHEET, 'Previous School Report Card / Marksheet'),
        (TYPE_ADDRESS_PROOF, 'Address Proof (Aadhaar / Utility Bill)'),
        (TYPE_STUDENT_PHOTO, 'Student Passport Photograph'),
        (TYPE_PARENT_ID, 'Parent Identity Proof'),
        (TYPE_ACADEMIC_DOC, 'Academic Document / Certificate'),
        (TYPE_OTHER, 'Other Supporting Document'),
    )

    STATUS_PENDING = 'PENDING'
    STATUS_VERIFIED = 'VERIFIED'
    STATUS_REJECTED = 'REJECTED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending Verification'),
        (STATUS_VERIFIED, 'Verified & Approved'),
        (STATUS_REJECTED, 'Rejected / Re-upload Required'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_documents'
    )
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES, default=TYPE_OTHER)
    title = models.CharField(max_length=150, blank=True)
    file = models.FileField(upload_to='admissions/documents/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_admission_documents'
    )
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_document_type_display()} ({self.get_status_display()})"


class AdmissionInterview(ExportModelOperationsMixin('admission_interview'), TimeStampedModel):
    """
    Interview scheduling and interaction notes for student / parent.
    """
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_NO_SHOW = 'NO_SHOW'

    STATUS_CHOICES = (
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'Applicant No Show'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_interviews'
    )
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='interviews'
    )
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, default='Admissions Office')
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conducted_interviews'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    remarks = models.TextField(blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['scheduled_at']

    def __str__(self):
        return f"Interview for App #{self.application.application_number} on {self.scheduled_at}"


class AdmissionAssessment(ExportModelOperationsMixin('admission_assessment'), TimeStampedModel):
    """
    Written / aptitude entrance assessment score recording.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='admission_assessments'
    )
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='assessments'
    )
    subject = models.CharField(max_length=100)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['subject']

    def __str__(self):
        return f"{self.subject}: {self.score}/{self.max_score} for App #{self.application.application_number}"
