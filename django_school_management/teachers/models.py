from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin
from taggit.managers import TaggableManager


class Designation(ExportModelOperationsMixin('designation'), TimeStampedModel):
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='designations',
        null=True, blank=True
    )
    title = models.CharField(max_length=255)
    created = models.DateField(auto_now_add=True)

    def __str__(self):
        return str(self.title)


class TeacherProfile(ExportModelOperationsMixin('teacher_profile'), TimeStampedModel):
    """
    Teacher & Staff Profile for PrimeSoul School ERP.
    Linked One-to-One with User model for authentication, RBAC, and portal access.
    """
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        help_text="User account associated with this teacher"
    )
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='teacher_profiles',
        null=True, blank=True,
        help_text="Tenant school where this teacher is employed"
    )
    employee_code = models.CharField(max_length=50, blank=True, db_index=True, help_text="Institutional Employee / Staff ID")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='teachers/photos/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    designation = models.ForeignKey(
        Designation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='teacher_profiles'
    )
    department_wing = models.CharField(
        max_length=100, blank=True,
        help_text="Academic wing (e.g. Primary, Middle, Secondary, Senior Secondary)"
    )
    qualification = models.CharField(
        max_length=255, blank=True,
        help_text="Highest educational degrees (e.g. M.Sc Mathematics, B.Ed, CTET)"
    )
    specialization = models.CharField(
        max_length=255, blank=True,
        help_text="Primary subjects / specialization area"
    )
    joining_date = models.DateField(null=True, blank=True, help_text="Date of joining the institution")
    mobile_number = models.CharField(max_length=20, blank=True, help_text="+91 E.164 contact phone number")
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        desig = f" ({self.designation.title})" if self.designation else ""
        return f"{full_name}{desig}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ─────────────────────────────────────────────────────────────
# Legacy Teacher model preserved for backwards compatibility
# ─────────────────────────────────────────────────────────────

class Teacher(ExportModelOperationsMixin('teacher'), TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='teacher_record',
        help_text="User login account associated with this teacher"
    )
    employee_id = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=150)
    photo = models.ImageField(upload_to='teachers', default='teacheravatar.jpg')
    date_of_birth = models.DateField(blank=True, null=True)
    designation = models.ForeignKey(
        Designation,
        on_delete=models.CASCADE,
        related_name='resources'
    )
    expertise = TaggableManager(blank=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    # Fixed: normal DateField instead of buggy auto_now=True
    joining_date = models.DateField(null=True, blank=True)
    institute = models.ForeignKey(
        'institute.InstituteProfile',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='teachers',
    )
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='legacy_teachers'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return '{} ({})'.format(self.name, self.designation)

    def get_full_name(self):
        return self.name
