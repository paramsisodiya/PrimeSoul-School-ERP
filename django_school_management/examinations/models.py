import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject, StudentEnrollment
)
from django_school_management.students.models import Student


class AssessmentType(ExportModelOperationsMixin('assessment_type'), TimeStampedModel):
    """
    Configurable assessment types (e.g. Unit Test, Periodic Test, Half Yearly, Annual, Practical).
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='assessment_types'
    )
    name = models.CharField(max_length=100, help_text="e.g. Periodic Test, Half Yearly, Annual Examination")
    code = models.CharField(max_length=30, help_text="e.g. PT, HY, ANN, PRAC")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'code'],
                name='unique_school_assessment_type_code'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class GradeScale(ExportModelOperationsMixin('grade_scale'), TimeStampedModel):
    """
    Grading scheme configuration (CBSE 8-Point, ICSE Standard, 10-Point CGPA, etc.).
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='grade_scales'
    )
    name = models.CharField(max_length=100, help_text="e.g. CBSE 8-Point Scale, ICSE Secondary Scale")
    code = models.CharField(max_length=30, help_text="e.g. CBSE-8P, ICSE-STD")
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False, help_text="Use this scale by default for new exams")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'code'],
                name='unique_school_grade_scale_code'
            )
        ]

    def __str__(self):
        default_label = " [DEFAULT]" if self.is_default else ""
        return f"{self.name} ({self.code}){default_label}"

    def save(self, *args, **kwargs):
        if self.is_default and self.school_id:
            GradeScale.objects.filter(school_id=self.school_id, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class GradeScaleBand(ExportModelOperationsMixin('grade_scale_band'), TimeStampedModel):
    """
    Individual grade thresholds within a GradeScale (e.g. A1: 91-100%, Grade Point 10.0).
    """
    scale = models.ForeignKey(
        GradeScale,
        on_delete=models.CASCADE,
        related_name='bands'
    )
    name = models.CharField(max_length=10, help_text="e.g. A1, A2, B1, B2, C1, C2, D, E")
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Lower percentage bound (inclusive)")
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Upper percentage bound (inclusive)")
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="e.g. 10.0, 9.0, 0.0")
    is_passing = models.BooleanField(default=True, help_text="Uncheck for failing grades (e.g. E / Below 33%)")
    remarks = models.CharField(max_length=100, blank=True, help_text="e.g. Outstanding, Excellent, Good, Scope for Improvement")

    class Meta:
        ordering = ['-min_percentage']
        constraints = [
            models.UniqueConstraint(
                fields=['scale', 'name'],
                name='unique_scale_band_name'
            )
        ]

    def __str__(self):
        pass_str = "" if self.is_passing else " [FAIL]"
        return f"{self.name}: {self.min_percentage}% - {self.max_percentage}% (GP: {self.grade_point}){pass_str}"

    def clean(self):
        super().clean()
        if self.min_percentage is not None and self.max_percentage is not None:
            if self.min_percentage > self.max_percentage:
                raise ValidationError({"min_percentage": "Minimum percentage cannot exceed maximum percentage."})


class ExaminationSession(ExportModelOperationsMixin('examination_session'), TimeStampedModel):
    """
    Master session grouping examinations within an Academic Year (e.g. Half Yearly 2026-27).
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_ONGOING = 'ONGOING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_ARCHIVED = 'ARCHIVED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_ONGOING, 'Ongoing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='examination_sessions'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='examination_sessions'
    )
    name = models.CharField(max_length=100, help_text="e.g. Half Yearly Examinations 2026-27")
    code = models.CharField(max_length=30, help_text="e.g. HYE-2026")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-start_date', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'code'],
                name='unique_school_academic_year_session_code'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code}) [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})


class Exam(ExportModelOperationsMixin('exam'), TimeStampedModel):
    """
    Class/Section-level examination (e.g. Half Yearly Examination - Class 10).
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_ONGOING = 'ONGOING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FINALIZED = 'FINALIZED'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_LOCKED = 'LOCKED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_ONGOING, 'Ongoing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FINALIZED, 'Finalized'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_LOCKED, 'Locked'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='k12_exams'
    )
    session = models.ForeignKey(
        ExaminationSession,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='k12_exams'
    )
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='exams',
        help_text="Optional. Leave blank to apply to all sections in this class."
    )
    assessment_type = models.ForeignKey(
        AssessmentType,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    grade_scale = models.ForeignKey(
        GradeScale,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exams',
        help_text="Grading scale used for calculating subject and overall grades."
    )
    name = models.CharField(max_length=150, help_text="e.g. Half Yearly Exam - Class 10")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    weightage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'), help_text="Weightage percentage towards composite evaluation")
    ranking_enabled = models.BooleanField(default=True, help_text="Calculate student class and section ranks")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_exams'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_exams'
    )

    class Meta:
        ordering = ['-academic_year__start_date', 'grade_level__display_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'session', 'grade_level', 'section', 'name'],
                name='unique_exam_per_class_section'
            )
        ]

    def __str__(self):
        sec_str = f" - Section {self.section.name}" if self.section else " (All Sections)"
        return f"{self.name} | {self.grade_level.name}{sec_str} [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})


class ExamSubject(ExportModelOperationsMixin('exam_subject'), TimeStampedModel):
    """
    Configures subject under an Exam with max marks, passing marks, weightage and sequence order.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='configured_exam_subjects'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='exam_instances'
    )
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('100.00'))
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('33.00'))
    weightage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    sequence_order = models.PositiveIntegerField(default=1)
    is_optional = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sequence_order', 'subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['exam', 'subject'],
                name='unique_exam_subject_configuration'
            )
        ]

    def __str__(self):
        return f"{self.exam.name} - {self.subject.name} (Max: {self.max_marks}, Pass: {self.passing_marks})"

    def clean(self):
        super().clean()
        if self.passing_marks is not None and self.max_marks is not None:
            if self.passing_marks > self.max_marks:
                raise ValidationError({"passing_marks": "Passing marks cannot exceed maximum marks."})
            if self.passing_marks < 0:
                raise ValidationError({"passing_marks": "Passing marks cannot be negative."})
            if self.max_marks <= 0:
                raise ValidationError({"max_marks": "Maximum marks must be greater than zero."})


class StudentMark(ExportModelOperationsMixin('student_mark'), TimeStampedModel):
    """
    Individual student marks entry for an ExamSubject.
    """
    STATUS_PRESENT = 'PRESENT'
    STATUS_ABSENT = 'ABSENT'
    STATUS_NOT_ENTERED = 'NOT_ENTERED'

    STATUS_CHOICES = (
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_NOT_ENTERED, 'Not Entered'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='student_marks'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='student_marks'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='marks'
    )
    exam_subject = models.ForeignKey(
        ExamSubject,
        on_delete=models.CASCADE,
        related_name='student_marks'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='exam_marks'
    )
    enrollment = models.ForeignKey(
        StudentEnrollment,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exam_marks'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NOT_ENTERED)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=10, blank=True)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    is_passed = models.BooleanField(default=True)
    remarks = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='entered_marks'
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_marks'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__roll_number', 'student__first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'exam', 'exam_subject', 'student'],
                name='unique_student_exam_subject_mark'
            )
        ]
        indexes = [
            models.Index(fields=['school', 'exam', 'student']),
            models.Index(fields=['exam_subject', 'student']),
            models.Index(fields=['exam', 'status']),
        ]

    def __str__(self):
        status_disp = f" ({self.marks_obtained})" if self.status == self.STATUS_PRESENT else f" [{self.status}]"
        return f"{self.student.name} | {self.exam_subject.subject.name}{status_disp}"

    def clean(self):
        super().clean()
        if self.status == self.STATUS_PRESENT:
            if self.marks_obtained is None:
                raise ValidationError({"marks_obtained": "Marks obtained is required when status is Present."})
            if self.marks_obtained < Decimal('0.00'):
                raise ValidationError({"marks_obtained": "Marks obtained cannot be negative."})
            if self.exam_subject_id and self.marks_obtained > self.exam_subject.max_marks:
                raise ValidationError({"marks_obtained": f"Marks cannot exceed maximum marks ({self.exam_subject.max_marks})."})
        elif self.status == self.STATUS_ABSENT:
            self.marks_obtained = None
            self.is_passed = False

    def save(self, *args, **kwargs):
        if not self.school_id and self.exam_id:
            self.school = self.exam.school
        if not self.academic_year_id and self.exam_id:
            self.academic_year = self.exam.academic_year
        super().save(*args, **kwargs)


class StudentExamResult(ExportModelOperationsMixin('student_exam_result'), TimeStampedModel):
    """
    Overall aggregated result for a student in an Examination.
    Powers Report Cards, Marksheets, Ranking, and Result Verification.
    """
    RESULT_PASSED = 'PASSED'
    RESULT_FAILED = 'FAILED'
    RESULT_COMPARTMENT = 'COMPARTMENT'
    RESULT_ABSENT = 'ABSENT'
    RESULT_WITHHELD = 'WITHHELD'

    RESULT_STATUS_CHOICES = (
        (RESULT_PASSED, 'Passed'),
        (RESULT_FAILED, 'Failed'),
        (RESULT_COMPARTMENT, 'Compartment / Eligible for Re-exam'),
        (RESULT_ABSENT, 'Absent in All Subjects'),
        (RESULT_WITHHELD, 'Result Withheld'),
    )

    STATUS_DRAFT = 'DRAFT'
    STATUS_CALCULATED = 'CALCULATED'
    STATUS_FINALIZED = 'FINALIZED'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_LOCKED = 'LOCKED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_CALCULATED, 'Calculated'),
        (STATUS_FINALIZED, 'Finalized'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_LOCKED, 'Locked'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='student_exam_results'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='student_exam_results'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='student_results'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='exam_results'
    )
    enrollment = models.ForeignKey(
        StudentEnrollment,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exam_results'
    )

    # Marks & Percentage
    total_marks_obtained = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'))
    total_max_marks = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'))
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    overall_grade = models.CharField(max_length=10, blank=True)
    overall_grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    result_status = models.CharField(max_length=20, choices=RESULT_STATUS_CHOICES, default=RESULT_PASSED)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Subject counts
    subjects_passed = models.PositiveIntegerField(default=0)
    subjects_failed = models.PositiveIntegerField(default=0)

    # Ranks (conditional)
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    section_rank = models.PositiveIntegerField(null=True, blank=True)

    # Attendance Integration
    attendance_working_days = models.PositiveIntegerField(default=0)
    attendance_present_days = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Remarks
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)

    # Tamper-Evident Verification Code
    verification_code = models.CharField(max_length=64, unique=True, db_index=True)

    # Audit & Status Timestamps
    calculated_at = models.DateTimeField(null=True, blank=True)
    calculated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='calculated_results')
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='finalized_results')
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='published_results')
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_results')

    class Meta:
        ordering = ['class_rank', '-percentage', 'student__roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'exam', 'student'],
                name='unique_student_exam_overall_result'
            )
        ]
        indexes = [
            models.Index(fields=['school', 'exam', 'status']),
            models.Index(fields=['exam', 'percentage']),
            models.Index(fields=['verification_code']),
        ]

    def __str__(self):
        return f"{self.student.name} | {self.exam.name} | {self.percentage}% ({self.overall_grade}) [{self.get_result_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.school_id and self.exam_id:
            self.school = self.exam.school
        if not self.academic_year_id and self.exam_id:
            self.academic_year = self.exam.academic_year
        if not self.verification_code:
            self.verification_code = f"PRIME-RES-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)


class MarksCorrectionLog(ExportModelOperationsMixin('marks_correction_log'), TimeStampedModel):
    """
    Immutable audit trail for any mark modified after save, finalization, or locking.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='marks_correction_logs'
    )
    mark_record = models.ForeignKey(
        StudentMark,
        on_delete=models.CASCADE,
        related_name='corrections'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='marks_corrections'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='marks_corrections'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='marks_corrections'
    )
    previous_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    previous_status = models.CharField(max_length=20)
    new_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    new_status = models.CharField(max_length=20)
    reason = models.TextField(help_text="Mandatory justification for mark correction")
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-corrected_at']

    def __str__(self):
        return f"Correction on {self.student.name} - {self.subject.name}: {self.previous_marks} -> {self.new_marks}"
