import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin


class AttendanceRecord(ExportModelOperationsMixin('attendance_record'), TimeStampedModel):
    """
    Daily Student Attendance Record for PrimeSoul School ERP.
    Scoped by tenant school, academic year, class/grade, section, and calendar date.
    Strictly prevents duplicate attendance records per student per day.
    """
    STATUS_PRESENT = 'PRESENT'
    STATUS_ABSENT = 'ABSENT'
    STATUS_LATE = 'LATE'
    STATUS_HALF_DAY = 'HALF_DAY'
    STATUS_EXCUSED = 'EXCUSED'

    STATUS_CHOICES = (
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_LATE, 'Late'),
        (STATUS_HALF_DAY, 'Half Day'),
        (STATUS_EXCUSED, 'Excused'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True, blank=True
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    attendance_date = models.DateField(db_index=True, default=timezone.localdate)
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    grade_level = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    section = models.ForeignKey(
        'academics.Section',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PRESENT,
        db_index=True
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='marked_attendances'
    )
    marked_at = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_attendances'
    )
    updated_at = models.DateTimeField(auto_now=True)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-attendance_date', 'grade_level__display_order', 'section__name', 'student__roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'student', 'attendance_date'],
                name='unique_student_date_attendance'
            )
        ]
        indexes = [
            models.Index(fields=['school', 'attendance_date']),
            models.Index(fields=['school', 'grade_level', 'section', 'attendance_date']),
            models.Index(fields=['student', 'attendance_date']),
            models.Index(fields=['status', 'attendance_date']),
        ]

    def __str__(self):
        return f"{self.attendance_date} | {self.student.name} ({self.grade_level.name}-{self.section.name}): {self.get_status_display()}"

    def clean(self):
        super().clean()
        # Tenant integrity validation
        if self.school and self.student and self.student.school and self.student.school != self.school:
            raise ValidationError({'student': "Student does not belong to the selected school tenant."})
        if self.school and self.grade_level and self.grade_level.school and self.grade_level.school != self.school:
            raise ValidationError({'grade_level': "Grade level does not belong to the selected school tenant."})
        if self.school and self.section and self.section.school and self.section.school != self.school:
            raise ValidationError({'section': "Section does not belong to the selected school tenant."})
        if self.school and self.academic_year and self.academic_year.school and self.academic_year.school != self.school:
            raise ValidationError({'academic_year': "Academic year does not belong to the selected school tenant."})
        if self.section and self.grade_level and self.section.grade_level != self.grade_level:
            raise ValidationError({'section': f"Section {self.section.name} does not belong to Class {self.grade_level.name}."})


class AttendanceCorrectionLog(ExportModelOperationsMixin('attendance_correction_log'), TimeStampedModel):
    """
    Immutable audit history log of corrections made to attendance records.
    Requires a mandatory justification reason and records previous and new status.
    """
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name='correction_history'
    )
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='attendance_correction_logs',
        null=True, blank=True
    )
    previous_status = models.CharField(max_length=20, choices=AttendanceRecord.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=AttendanceRecord.STATUS_CHOICES)
    reason = models.TextField(help_text="Mandatory explanation/justification for correcting attendance.")
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_corrections'
    )
    corrected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-corrected_at']

    def __str__(self):
        user_name = self.corrected_by.get_full_name() if self.corrected_by else "System"
        return f"{self.attendance_record.attendance_date} | {self.previous_status} -> {self.new_status} by {user_name}"
