from django_countries.fields import CountryField
from ckeditor_uploader.fields import RichTextUploadingField
from django_prometheus.models import ExportModelOperationsMixin

from django.db import models
from django.db.models.signals import pre_save
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.conf import settings
from django.urls import reverse

from .utils import model_help_texts


class User(ExportModelOperationsMixin('user'), AbstractUser):
    REQUESTED_ACCOUNT_TYPE_CHOICES = (
        ('SCHOOL_ADMIN', 'School Admin'),
        ('STUDENT', 'Student'),
        ('TEACHER', 'Teacher'),
    )
    APPROVAL_CHOICES = (
        ('n', 'Not Requested For Approval'),
        ('p', 'Approval Application is Pending'),
        ('d', 'Approval Request Declined'),
        ('a', 'Verified')
    )
    approval_status = models.CharField(
        max_length=2,
        choices=APPROVAL_CHOICES,
        default='n',
    )
    employee_or_student_id = models.CharField(
        max_length=50,
        blank=True, null=True
    )
    requested_role = models.CharField(
        choices=REQUESTED_ACCOUNT_TYPE_CHOICES,
        max_length=50,
        default='SCHOOL_ADMIN'
    )
    approval_extra_note = models.TextField(
        blank=True, null=True
    )
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='users',
        help_text="Tenant school this user belongs to. Platform Super Admins may have this blank."
    )
    # Legacy field preserved for backwards compatibility during migration
    institute = models.ForeignKey(
        'institute.InstituteProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='legacy_users',
    )

    def get_author_url(self):
        return reverse(
            'articles:author_profile',
            args=[self.username,])

    @property
    def linked_profile_display(self):
        """Returns human-readable linked domain record summary."""
        st = getattr(self, 'student_profile', None)
        if st:
            class_sec = f"{st.grade_level.name if st.grade_level else ''} {st.section.name if st.section else ''}".strip()
            adm = f"Adm: {st.admission_number}" if st.admission_number else f"ID: #{st.pk}"
            roll = f"Roll: {st.roll_number}" if st.roll_number else ""
            meta = ", ".join(filter(None, [adm, roll]))
            return f"{st.get_full_name()}{f' — {class_sec}' if class_sec else ''} ({meta})"
        tr = getattr(self, 'teacher_record', None)
        if tr:
            desig = f" ({tr.designation.title})" if tr.designation else ""
            code = f" [ID: {tr.employee_id}]" if tr.employee_id else ""
            return f"{tr.name}{desig}{code}"
        tp = getattr(self, 'teacher_profile', None)
        if tp:
            desig = f" ({tp.designation.title})" if tp.designation else ""
            code = f" [Code: {tp.employee_code}]" if tp.employee_code else ""
            return f"{tp.get_full_name()}{desig}{code}"
        if self.is_superuser:
            return "Platform Super Admin"
        if self.is_staff or self.requested_role == 'SCHOOL_ADMIN':
            return "School Administrator"
        return "Not Linked"

    @property
    def is_linked_to_profile(self):
        if self.requested_role == 'STUDENT':
            return hasattr(self, 'student_profile') and self.student_profile is not None
        if self.requested_role == 'TEACHER':
            return (hasattr(self, 'teacher_record') and self.teacher_record is not None) or (hasattr(self, 'teacher_profile') and self.teacher_profile is not None)
        return True



class CustomGroup(ExportModelOperationsMixin('custom_group'), Group):
    group_creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)

    def display_group(self):
        return f'{self.name} created by {self.group_creator}'


class SocialLink(ExportModelOperationsMixin('social_link'), models.Model):
    user_profile = models.ForeignKey(
        'CommonUserProfile',
        on_delete=models.CASCADE
    )
    media_name = models.CharField(
        max_length=50
    )
    url = models.URLField()

    def __str__(self):
        return self.media_name


class CommonUserProfile(ExportModelOperationsMixin('common_user_profile'), models.Model):
    """Core details of user profile created only after account verification by institute."""
    user = models.OneToOneField(
        User,
        related_name='profile',
        on_delete=models.SET_NULL,
        null=True
    )
    profile_picture = models.ImageField(
        upload_to='profile-pictures',
        blank=True,
        null=True
    )
    cover_picture = models.ImageField(
        upload_to='cover-pictures',
        blank=True,
        null=True
    )
    headline = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    show_headline_in_bio = models.BooleanField(
        help_text=model_help_texts.COMMON_USER_PROFILE_SHOW_HEADLINE_IN_BIO_TEXT,
        default=False
    )
    summary = RichTextUploadingField(
        help_text=model_help_texts.COMMON_USER_PROFILE_SUMMARY_TEXT,
        blank=True,
        null=True
    )
    country = CountryField(
        blank=True,
        null=True
    )
    social_links = models.ManyToManyField(
        SocialLink,
        related_name='social_links',
        blank=True
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user}\'s profile'
