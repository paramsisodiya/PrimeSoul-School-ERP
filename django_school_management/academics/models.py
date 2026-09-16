from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django.db import models, OperationalError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.urls import reverse

from django_school_management.teachers.models import Teacher
from .constants import AcademicsURLConstants
from .utils import model_help_texts


class AcademicYear(ExportModelOperationsMixin('academic_year'), TimeStampedModel):
    """
    Indian K-12 Academic Year (typically April 1 to March 31).
    Scoped per School tenant.
    """
    STATUS_UPCOMING = 'UPCOMING'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_ARCHIVED = 'ARCHIVED'

    STATUS_CHOICES = (
        (STATUS_UPCOMING, 'Upcoming'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='academic_years',
        null=True, blank=True,
        help_text="Tenant school that owns this academic year"
    )
    name = models.CharField(max_length=50, help_text="e.g. 2026-2027")
    start_date = models.DateField(help_text="Start date of academic session (e.g. 2026-04-01)")
    end_date = models.DateField(help_text="End date of academic session (e.g. 2027-03-31)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_current = models.BooleanField(default=False, help_text="Marks this session as the active academic year")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_academic_year')
        ]

    def __str__(self):
        school_name = self.school.name if self.school else 'Global'
        current_str = " [CURRENT]" if self.is_current else ""
        return f"{self.name} ({school_name}){current_str}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})

    def save(self, *args, **kwargs):
        self.clean()
        if self.is_current and self.school:
            AcademicYear.objects.filter(school=self.school, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class GradeLevel(ExportModelOperationsMixin('grade_level'), TimeStampedModel):
    """
    K-12 Class / Grade level (Nursery, LKG, UKG, Class 1 ... Class 12).
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='grade_levels',
        null=True, blank=True
    )
    name = models.CharField(max_length=50, help_text="e.g. Class 10, Nursery")
    code = models.CharField(max_length=20, help_text="e.g. 10, NUR")
    board = models.CharField(max_length=50, blank=True, null=True, default='CBSE', help_text="e.g. CBSE, ICSE, State Board, IB, Cambridge")
    stream_applicable = models.BooleanField(default=False, help_text="True for Classes 11 and 12 with Science/Commerce/Arts streams")
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['display_order', 'code']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code'], name='unique_school_grade_code')
        ]

    def __str__(self):
        return f"{self.name}"


class Section(ExportModelOperationsMixin('section'), TimeStampedModel):
    """
    Section under a GradeLevel (e.g. Section A, Section B).
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='sections',
        null=True, blank=True
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='sections',
        null=True, blank=True
    )
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    name = models.CharField(max_length=20, help_text="e.g. A, B, C, Rose")
    room_number = models.CharField(max_length=50, blank=True)
    max_capacity = models.PositiveIntegerField(default=40)
    class_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_sections'
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['grade_level__display_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['grade_level', 'name'], name='unique_grade_section')
        ]

    def __str__(self):
        return f"{self.grade_level.name} - Section {self.name}"


class AcademicStream(ExportModelOperationsMixin('academic_stream'), TimeStampedModel):
    """
    Stream for Senior Secondary classes (11th-12th): Science (PCM/PCB), Commerce, Arts/Humanities.
    """
    school = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='academic_streams', null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SubjectAssignment(ExportModelOperationsMixin('subject_assignment'), TimeStampedModel):
    """
    Mapping between Academic Year, Grade, Section, Subject, and Teacher.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        null=True, blank=True
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='subject_assignments'
    )
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name='subject_assignments'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subject_assignments',
        help_text="Optional section filter. If null, applies to entire class."
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.CASCADE,
        related_name='subject_assignments'
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subject_assignments'
    )
    periods_per_week = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['grade_level__display_order', 'section__name', 'subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'grade_level', 'section', 'subject'],
                name='unique_academic_subject_assignment'
            )
        ]

    def __str__(self):
        sec_str = f" - {self.section.name}" if self.section else ""
        return f"{self.grade_level.name}{sec_str}: {self.subject.name} ({self.teacher.name if self.teacher else 'Unassigned'})"


class StudentEnrollment(ExportModelOperationsMixin('student_enrollment'), TimeStampedModel):
    """
    Historical and active student enrollment mapping for a specific Academic Year.
    Allows tracking student progression across years (e.g. 2025-26 Class 9A -> 2026-27 Class 10A).
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PROMOTED = 'PROMOTED'
    STATUS_TRANSFERRED = 'TRANSFERRED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_DROPPED = 'DROPPED'

    ENROLLMENT_STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PROMOTED, 'Promoted'),
        (STATUS_TRANSFERRED, 'Transferred'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DROPPED, 'Dropped / Withdrawn'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='student_enrollments',
        null=True, blank=True
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='academic_enrollments'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='student_enrollments'
    )
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name='student_enrollments'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_enrollments'
    )
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default=STATUS_ACTIVE)
    enrollment_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-academic_year__start_date', 'grade_level__display_order', 'roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'student', 'academic_year'],
                name='unique_student_academic_year_enrollment'
            )
        ]

    def __str__(self):
        sec = f"-{self.section.name}" if self.section else ""
        return f"{self.student.name} | {self.academic_year.name} | {self.grade_level.name}{sec} ({self.status})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Sync student current placement if this enrollment is active and for current academic year
        if self.status == self.STATUS_ACTIVE and self.academic_year and self.academic_year.is_current:
            self.student.academic_year = self.academic_year
            self.student.grade_level = self.grade_level
            self.student.section = self.section
            if self.roll_number:
                self.student.roll_number = self.roll_number
            self.student.save(update_fields=['academic_year', 'grade_level', 'section', 'roll_number'])


class ClassTeacherAssignment(ExportModelOperationsMixin('class_teacher_assignment'), TimeStampedModel):
    """
    Historical log of Class Teacher assignments to sections per academic year.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='class_teacher_assignments',
        null=True, blank=True
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='class_teacher_assignments'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='class_teacher_history'
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='class_teacher_history'
    )
    assigned_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-assigned_date']

    def __str__(self):
        return f"{self.section} -> {self.teacher.name} ({self.academic_year.name})"


# ─────────────────────────────────────────────────────────────
# Legacy models (preserved and refactored with tenant scoping)
# ─────────────────────────────────────────────────────────────

class Department(ExportModelOperationsMixin('department'), TimeStampedModel):
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='departments_list'
    )
    name = models.CharField(max_length=255)
    short_name = models.CharField(
        model_help_texts.DEPARTMENT_SHORT_NAME_TEXT,
        max_length=5
    )
    code = models.PositiveIntegerField()
    short_description = models.TextField(
        help_text=model_help_texts.DEPARTMENT_SHORT_DESCRIPTION_TEXT,
        blank=True,
        null=True
    )
    department_icon = models.ImageField(
        help_text=model_help_texts.DEPARTMENT_DEPARTMENT_ICON_TEXT,
        upload_to='department_icon/',
        blank=True,
        null=True
    )
    head = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        blank=True, null=True
    )
    current_batch = models.ForeignKey(
        model_help_texts.DEPARTMENT_CURRENT_BATCH_TEXT, on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='current_batches'
    )
    batches = models.ManyToManyField(
        model_help_texts.DEPARTMENT_BATCHES_TEXT,
        related_name='department_batches',
        blank=True
    )
    establish_date = models.DateField(auto_now_add=True)
    institute = models.ForeignKey(
        'institute.InstituteProfile',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='departments',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_department')
        ]

    def dept_code(self):
        if not self.code:
            return ""
        return self.code

    def __str__(self):
        return str(self.name)
    
    def create_resource(self):
        return reverse(AcademicsURLConstants.create_department)


class AcademicSession(ExportModelOperationsMixin('academic_session'), TimeStampedModel):
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='legacy_sessions'
    )
    year = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'year'], name='unique_school_legacy_session')
        ]

    def __str__(self):
        return '{} - {}'.format(self.year, self.year + 1)
    
    def create_resource(self):
        return reverse(AcademicsURLConstants.create_academic_session)


class Semester(ExportModelOperationsMixin('semester'), TimeStampedModel):
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='legacy_semesters'
    )
    number = models.PositiveIntegerField()
    guide = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        default=None, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True
    )

    class Meta:
        ordering = ['number', ]
        constraints = [
            models.UniqueConstraint(fields=['school', 'number'], name='unique_school_legacy_semester')
        ]

    def __str__(self):
        if self.number == 1:
            return '1st'
        if self.number == 2:
            return '2nd'
        if self.number == 3:
            return '3rd'
        if self.number and 3 < self.number <= 12:
            return '%sth' % self.number
        return '%dth' % self.number
    
    def create_resource(self):
        return reverse(AcademicsURLConstants.create_semester)


class Subject(ExportModelOperationsMixin('subject'), TimeStampedModel):
    TYPE_CORE = 'CORE'
    TYPE_ELECTIVE = 'ELECTIVE'
    TYPE_LANGUAGE = 'LANGUAGE'
    TYPE_SKILL = 'SKILL'
    TYPE_CO_CURRICULAR = 'CO_CURRICULAR'

    SUBJECT_TYPE_CHOICES = (
        (TYPE_CORE, 'Core'),
        (TYPE_ELECTIVE, 'Elective'),
        (TYPE_LANGUAGE, 'Language'),
        (TYPE_SKILL, 'Skill'),
        (TYPE_CO_CURRICULAR, 'Co-Curricular'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subjects'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, blank=True, null=True, help_text="Alphanumeric Subject Code e.g. ENG-101, MATH-10")
    subject_code = models.PositiveIntegerField(null=True, blank=True)
    subject_type = models.CharField(max_length=30, choices=SUBJECT_TYPE_CHOICES, default='CORE')
    max_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=33)
    is_active = models.BooleanField(default=True)
    book_cover = models.ImageField(
        upload_to='subjects/',
        default='subjects/bookcover.png',
        blank=True, null=True
    )
    instructor = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL,
        blank=True, null=True
    )
    theory_marks = models.PositiveIntegerField(default=80, blank=True, null=True)
    practical_marks = models.PositiveIntegerField(default=20, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True)
    subject_template = models.ForeignKey(
        'curriculum.SubjectTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
        help_text='Optional. Link to curriculum library template for this subject.',
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code'], name='unique_school_subject_code_str')
        ]

    def __str__(self):
        display_code = self.code or (str(self.subject_code) if self.subject_code else 'SUB')
        return f"{self.name} ({display_code})"
    
    def create_resource(self):
        return reverse(AcademicsURLConstants.create_subject)

    def save(self, *args, **kwargs):
        if not self.subject_code:
            import random
            self.subject_code = random.randint(10000, 99999)
        if not self.code:
            self.code = f"SUB-{self.subject_code}"
        if self.theory_marks is None:
            self.theory_marks = 80
        if self.practical_marks is None:
            self.practical_marks = 20
        super().save(*args, **kwargs)


class Batch(ExportModelOperationsMixin('batch'), TimeStampedModel):
    year = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    number = models.PositiveIntegerField(model_help_texts.BATCH_NUMBER_TEXT)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Batches'
        unique_together = ['year', 'department', 'number']

    def __str__(self):
        return f'{self.department.name} Batch {self.number} ({self.year})'

    def create_resource(self):
        return reverse(AcademicsURLConstants.create_batch)


class TempSerialID(ExportModelOperationsMixin('temp_serial_id'), TimeStampedModel):
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE,
                                   related_name='student_serial')
    department = models.ForeignKey(Department, on_delete=models.CASCADE,
                                   related_name='temp_serials')
    year = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    serial = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.serial

    def save(self, *args, **kwargs):
        if hasattr(self.student, 'admission_student') and self.student.admission_student and self.student.admission_student.admitted:
            super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def get_serial(self):
        yf = str(getattr(self.student, 'ac_session', ''))[-2:]
        bn = getattr(self.student.batch, 'number', '') if hasattr(self.student, 'batch') and self.student.batch else ''
        dc = self.department.code
        syl = self.serial
        return f'{yf}-{bn}-{dc}-{syl}'
