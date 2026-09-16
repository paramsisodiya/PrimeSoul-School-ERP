from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django.core.exceptions import ValidationError
from django.db import (
    models, OperationalError, 
    IntegrityError, transaction
)
from django.conf import settings
from django_school_management.academics.models import (
    Department, Semester,
    AcademicSession, Batch, 
    TempSerialID, AcademicYear,
    GradeLevel, Section, AcademicStream
)
from django_school_management.institute.models import City
from django_school_management.teachers.models import Teacher
from .utils import model_help_texts


class StudentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            is_alumni=False,
            is_dropped=False
        )


class AlumniManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            is_alumni=True
        )


class StudentBase(TimeStampedModel):
    TRIBAL_STATUS = (
        (1, 'Yes'),
        (0, 'No'),
    )
    CHILDREN_OF_FREEDOM_FIGHTER = (
        (1, 'Yes'),
        (0, 'No'),
    )
    name = models.CharField(model_help_texts.STUDENT_BASE_NAME, max_length=100)
    photo = models.ImageField(upload_to='students/applicant/', blank=True, null=True)
    fathers_name = models.CharField(model_help_texts.STUDENT_BASE_FATHER_NAME, max_length=100, blank=True)
    mothers_name = models.CharField(model_help_texts.STUDENT_BASE_MOTHER_NAME, max_length=100, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    email = models.EmailField(blank=True)
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students',
    )
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    mobile_number = models.CharField(max_length=20, blank=True)
    guardian_mobile_number = models.CharField(max_length=20, blank=True)
    tribal_status = models.PositiveSmallIntegerField(
        choices=TRIBAL_STATUS, default=0
    )
    children_of_freedom_fighter = models.PositiveSmallIntegerField(
        choices=TRIBAL_STATUS, default=0
    )
    department_choice = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class CounselingComment(ExportModelOperationsMixin('counseling_comment'), TimeStampedModel):
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, null=True
    )
    registrant_student = models.ForeignKey(
        'AdmissionStudent',
        on_delete=models.CASCADE, null=True
    )
    comment = models.CharField(max_length=150)

    def __str__(self):
        return self.comment
    
    class Meta:
        ordering = ['-created', ]


class AdmissionStudent(ExportModelOperationsMixin('admission_student'), StudentBase):
    APPLICATION_TYPE_CHOICE = (
        ('1', 'Online'),
        ('2', 'Offline')
    )
    EXAM_NAMES = (
        ('CBSE_10', 'CBSE Class X'),
        ('CBSE_12', 'CBSE Class XII'),
        ('ICSE_10', 'ICSE Class X'),
        ('ISC_12', 'ISC Class XII'),
        ('STATE_10', 'State Board Class X'),
        ('STATE_12', 'State Board Class XII'),
        ('HSC', 'Higher Secondary Certificate (Legacy)'),
        ('SSC', 'Secondary School Certificate (Legacy)'),
        ('DAKHIL', 'Dakhil Exam (Legacy)'),
        ('VOCATIONAL', 'Vocational (Legacy)'),
    )
    gender = models.CharField(
        max_length=1,
        choices=(('M', 'Male'), ('F', 'Female'), ('O', 'Other')),
        blank=True,
        null=True,
        help_text='Gender (Male/Female/Other).',
    )
    counseling_by = models.ForeignKey(
        Teacher, related_name='counselors',
        on_delete=models.SET_NULL, null=True, blank=True
    )
    counsel_comment = models.ManyToManyField(
        CounselingComment, blank=True
    )
    choosen_department = models.ForeignKey(
        Department, related_name='admission_students',
        on_delete=models.SET_NULL,
        blank=True, null=True
    )
    exam_name = models.CharField(
        choices=EXAM_NAMES,
        max_length=20,
        blank=True,
        null=True,
    )
    passing_year = models.CharField(max_length=4, blank=True, null=True)
    group = models.CharField(max_length=50, blank=True, null=True)
    board = models.CharField(max_length=100, blank=True, null=True)
    ssc_roll = models.CharField(max_length=50, blank=True, null=True)
    ssc_registration = models.CharField(max_length=50, blank=True, null=True)
    gpa = models.DecimalField(
        decimal_places=2,
        max_digits=4,
        blank=True,
        null=True,
    )
    marksheet_image = models.ImageField(
        model_help_texts.ADMISSION_STUDENT_MARKSHEET_IMAGE,
        upload_to='students/applicants/marksheets/',
        blank=True, null=True
    )
    admission_policy_agreement = models.BooleanField(
        model_help_texts.ADMISSION_STUDENT_ADMISSION_POLICY_AGGREMENT_TEXT,
        default=False
    )
    admitted = models.BooleanField(default=False)
    admission_date = models.DateField(blank=True, null=True)
    paid = models.BooleanField(default=False)
    application_type = models.CharField(
        max_length=1,
        choices=APPLICATION_TYPE_CHOICE,
        default='1'
    )
    migration_status = models.CharField(
        max_length=255,
        blank=True, null=True
    )
    rejected = models.BooleanField(default=False)
    assigned_as_student = models.BooleanField(default=False)
    applying_for_class = models.PositiveSmallIntegerField(
        blank=True, null=True,
        help_text='Class level (1-12) applying for.',
    )
    admit_to_semester = models.PositiveSmallIntegerField(
        blank=True, null=True,
        help_text='Legacy semester placement.',
    )

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class Student(ExportModelOperationsMixin('student'), TimeStampedModel):
    """
    Indian K-12 Student Model.
    Scoped to a School tenant, AcademicYear, GradeLevel, and Section.
    """
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    BLOOD_GROUP_CHOICES = (
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
    )
    CATEGORY_CHOICES = (
        ('General', 'General'),
        ('OBC', 'Other Backward Class (OBC-NCL)'),
        ('SC', 'Scheduled Caste (SC)'),
        ('ST', 'Scheduled Tribe (ST)'),
        ('EWS', 'Economically Weaker Section (EWS)'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='k12_students',
        null=True, blank=True,
        help_text="Tenant school that owns this student record"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_profile'
    )

    # Identifiers
    admission_number = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="School Admission / Scholar Number")
    roll_number = models.CharField(max_length=20, blank=True, null=True, db_index=True, help_text="Class Roll Number")
    
    # Personal details
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, blank=True)
    nationality = models.CharField(max_length=50, default='Indian')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General')

    # Indian Statutory Identifiers (Government compliance)
    aadhaar_number = models.CharField(max_length=20, blank=True, help_text="12-digit Indian National Unique ID")
    pen_number = models.CharField(max_length=50, blank=True, help_text="Permanent Education Number (PEN) from Ministry of Education")
    apaar_id = models.CharField(max_length=50, blank=True, help_text="Automated Permanent Academic Account Registry (APAAR ID)")

    # Academic Placement
    admission_date = models.DateField(blank=True, null=True)
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students'
    )
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students'
    )
    stream = models.ForeignKey(
        AcademicStream,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students'
    )

    # Address & Contact
    emergency_contact_number = models.CharField(max_length=20, blank=True)
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)

    # Transfer / Previous School
    previous_school = models.CharField(max_length=255, blank=True)
    previous_school_tc_number = models.CharField(max_length=100, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_alumni = models.BooleanField(default=False)
    is_dropped = models.BooleanField(default=False)

    # Legacy fields preserved for backward compatibility
    admission_student = models.ForeignKey(
        AdmissionStudent,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    roll = models.CharField(max_length=50, blank=True, null=True)
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    temp_serial = models.CharField(max_length=50, blank=True, null=True)
    temporary_id = models.CharField(max_length=50, blank=True, null=True)
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE,
        null=True, blank=True
    )
    ac_session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE,
        blank=True, null=True
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE,
        blank=True, null=True, related_name='students'
    )
    guardian_mobile = models.CharField(max_length=20, blank=True, null=True)
    admitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    # Managers
    objects = StudentManager()
    alumnus = AlumniManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['grade_level__display_order', 'section__name', 'roll_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'grade_level', 'section', 'roll_number'],
                name='unique_student_roll_per_section'
            ),
            models.UniqueConstraint(
                fields=['school', 'admission_number'],
                name='unique_school_admission_number'
            ),
        ]

    def __str__(self):
        full_name = self.get_full_name()
        if self.grade_level and self.section:
            return f"{full_name} ({self.grade_level.name} - {self.section.name}, Roll: {self.roll_number})"
        if self.admission_student:
            return f"{self.admission_student.name}"
        return full_name or f"Student #{self.pk}"

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        name = " ".join([p for p in parts if p]).strip()
        if not name and self.admission_student:
            return self.admission_student.name
        return name or f"Student {self.admission_number or self.pk}"

    @property
    def name(self):
        return self.get_full_name()

    def get_temp_id(self):
        if self.temporary_id:
            return self.temporary_id
        return f"STU-{self.school.slug if self.school else 'GEN'}-{self.pk or '0'}"

    def clean(self):
        super().clean()
        if self.pk is None and self.school_id:
            sub = getattr(self.school, 'subscription', None)
            if sub and sub.status == 'active' and sub.max_students > 0:
                active_count = Student.objects.filter(school=self.school, is_active=True).count()
                if active_count >= sub.max_students:
                    raise ValidationError(
                        f"Subscription student limit of {sub.max_students} exceeded for {self.school.name}. "
                        f"Please upgrade your SaaS plan to enroll additional students."
                    )

    def save(self, *args, **kwargs):
        if not self.first_name and self.admission_student:
            self.first_name = self.admission_student.name
        super().save(*args, **kwargs)


class ParentProfile(ExportModelOperationsMixin('parent_profile'), TimeStampedModel):
    """
    Indian K-12 Parent / Guardian Profile.
    Can be linked to multiple student siblings across grade levels.
    """
    RELATION_CHOICES = (
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Guardian', 'Guardian / Foster Parent'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='parent_profiles',
        null=True, blank=True
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='parent_profile'
    )
    relationship_type = models.CharField(max_length=20, choices=RELATION_CHOICES, default='Father')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    mobile_number = models.CharField(max_length=20, help_text="+91 E.164 phone number for WhatsApp / SMS alerts")
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    aadhaar_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.relationship_type})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class StudentGuardianRelationship(ExportModelOperationsMixin('student_guardian_relationship'), TimeStampedModel):
    """
    Maps many-to-many relationship between Students and Parents/Guardians.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardian_relationships')
    guardian = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name='student_relationships')
    relationship_type = models.CharField(max_length=50, default='Parent')
    is_primary_contact = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'guardian'], name='unique_student_guardian')
        ]

    def __str__(self):
        return f"{self.guardian} -> {self.student}"


class RegularStudent(ExportModelOperationsMixin('regular_student'), TimeStampedModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE,
        null=True, blank=True
    )

    def __str__(self):
        return f"{self.student.name} {self.semester}"
