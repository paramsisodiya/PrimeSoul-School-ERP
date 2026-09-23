from crispy_forms.helper import FormHelper

from django import forms as djform
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model, forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django.db import transaction
from .models import CommonUserProfile, SocialLink
from django_school_management.students.models import Student
from django_school_management.teachers.models import TeacherProfile

User = get_user_model()


class StudentModelChoiceField(djform.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name()
        class_sec = f"{obj.grade_level.name if obj.grade_level else ''} {obj.section.name if obj.section else ''}".strip()
        adm = f"Adm: {obj.admission_number}" if obj.admission_number else f"ID: #{obj.pk}"
        roll = f"Roll: {obj.roll_number}" if obj.roll_number else ""
        meta = ", ".join(filter(None, [adm, roll]))
        account_status = f" [Account: @{obj.user.username}]" if getattr(obj, 'user', None) else ""
        return f"{name}{f' — {class_sec}' if class_sec else ''} ({meta}){account_status}"


class TeacherModelChoiceField(djform.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name()
        desig = f" ({obj.designation.title})" if getattr(obj, 'designation', None) else ""
        code = f" [Code: {obj.employee_code}]" if getattr(obj, 'employee_code', None) else ""
        account_status = f" [Account: @{obj.user.username}]" if getattr(obj, 'user', None) else ""
        return f"{name}{desig}{code}{account_status}"


class UserChangeForm(forms.UserChangeForm):
    class Meta(forms.UserChangeForm.Meta):
        model = User
        fields = ('requested_role', )


class UserCreateFormDashboard(forms.UserCreationForm):
    REQUESTED_ACCOUNT_TYPE_CHOICES = (
        ('STUDENT', 'Student'),
        ('TEACHER', 'Teacher'),
        ('SCHOOL_ADMIN', 'School Admin'),
    )

    requested_role = djform.ChoiceField(
        choices=REQUESTED_ACCOUNT_TYPE_CHOICES,
        initial='STUDENT',
        widget=djform.RadioSelect(attrs={'class': 'custom-control-input'}),
        label=_("Account Type / Role")
    )
    student = StudentModelChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=djform.Select(attrs={'class': 'form-control select2'}),
        label=_("Select Existing Student"),
        help_text=_("Choose the onboarded student record to link this login account to.")
    )
    teacher = TeacherModelChoiceField(
        queryset=TeacherProfile.objects.none(),
        required=False,
        widget=djform.Select(attrs={'class': 'form-control select2'}),
        label=_("Select Existing Teacher / Faculty"),
        help_text=_("Choose the faculty profile to link this login account to.")
    )
    first_name = djform.CharField(max_length=150, required=False, widget=djform.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = djform.CharField(max_length=150, required=False, widget=djform.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = djform.EmailField(required=False, widget=djform.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))

    class Meta:
        model = User
        fields = (
            'requested_role', 'student', 'teacher',
            'username', 'first_name', 'last_name', 'email',
            'password1', 'password2'
        )

    def __init__(self, *args, school=None, initial_student=None, initial_teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school

        # Student QuerySet - Scoped to tenant school
        st_qs = Student.objects.select_related('grade_level', 'section', 'academic_year', 'school', 'user')
        if school:
            st_qs = st_qs.filter(school=school)
        self.fields['student'].queryset = st_qs.order_by('grade_level__display_order', 'section__name', 'first_name', 'last_name')

        # Teacher QuerySet - Scoped to tenant school
        tp_qs = TeacherProfile.objects.select_related('designation', 'school', 'user')
        if school:
            tp_qs = tp_qs.filter(school=school)
        self.fields['teacher'].queryset = tp_qs.order_by('first_name', 'last_name')

        if initial_student:
            self.fields['student'].initial = initial_student
            self.fields['requested_role'].initial = 'STUDENT'
            if not self.is_bound:
                if initial_student.first_name:
                    self.fields['first_name'].initial = initial_student.first_name
                if initial_student.last_name:
                    self.fields['last_name'].initial = initial_student.last_name
                if initial_student.admission_number:
                    self.fields['username'].initial = initial_student.admission_number.lower().replace(' ', '_')

        if initial_teacher:
            self.fields['teacher'].initial = initial_teacher
            self.fields['requested_role'].initial = 'TEACHER'
            if not self.is_bound:
                self.fields['first_name'].initial = initial_teacher.first_name
                self.fields['last_name'].initial = initial_teacher.last_name
                if initial_teacher.email:
                    self.fields['email'].initial = initial_teacher.email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('requested_role')
        student = cleaned_data.get('student')
        teacher = cleaned_data.get('teacher')

        if role == 'STUDENT':
            if not student:
                self.add_error('student', _("Please select an existing student record to link this account to."))
            elif student.user and student.user != self.instance:
                self.add_error('student', _(f"Student '{student.get_full_name()}' already has an active login account (@{student.user.username}). Duplicate accounts for the same student are not permitted."))
            elif self.school and student.school and student.school != self.school:
                self.add_error('student', _("Selected student does not belong to the active school tenant."))

        elif role == 'TEACHER':
            if not teacher and self.fields['teacher'].queryset.exists():
                self.add_error('teacher', _("Please select an existing teacher/faculty record to link this account to."))
            elif teacher and getattr(teacher, 'user', None) and teacher.user != self.instance:
                self.add_error('teacher', _(f"Teacher '{teacher.get_full_name()}' already has an active login account (@{teacher.user.username})."))
            elif teacher and self.school and teacher.school and teacher.school != self.school:
                self.add_error('teacher', _("Selected teacher does not belong to the active school tenant."))

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('requested_role')
        student = self.cleaned_data.get('student')
        teacher = self.cleaned_data.get('teacher')

        user.requested_role = role
        user.approval_status = 'a'  # Admin-created user is pre-approved
        if self.school:
            user.school = self.school
        elif student and student.school:
            user.school = student.school
        elif teacher and teacher.school:
            user.school = teacher.school

        if role == 'SCHOOL_ADMIN':
            user.is_staff = True
        else:
            user.is_staff = False

        if commit:
            user.save()
            from django_school_management.accounts.roles import assign_role_to_user
            assign_role_to_user(user, role)
            if role == 'STUDENT' and student:
                student.user = user
                student.save(update_fields=['user'])
            elif role == 'TEACHER' and teacher:
                teacher.user = user
                teacher.save(update_fields=['user'])

        return user


class UserChangeFormDashboard(forms.UserChangeForm):
    password = None

    class Meta(forms.UserChangeForm.Meta):
        model = User
        fields = (
            'username', 'email',
            'first_name', 'last_name',
            'requested_role', 'approval_status',
            'is_staff',
        )


class UserRegistrationForm(forms.UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.template_pack = 'tailwind'

    error_message = forms.UserCreationForm.error_messages.update(
        {
            "duplicate_username": _(
                "This username has already been taken."
            )
        }
    )

    class Meta:
        model = User
        fields = (
            'username', 'email', 'password1', 'password2',
            'requested_role', 'approval_status', 'is_staff', 'is_superuser',)

    def clean_username(self):
        username = self.cleaned_data["username"]

        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username

        raise ValidationError(
            self.error_messages["duplicate_username"]
        )

    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password1'] != cd['password2']:
            raise forms.ValidationError('Password didn\'t match!')
        return cd['password2']


class ProfileCompleteForm(djform.ModelForm):
    class Meta:
        model = User
        fields = [
            'employee_or_student_id',
            'requested_role',
            'email',
            'approval_extra_note']


class ApprovalProfileUpdateForm(djform.ModelForm):
    class Meta:
        model = User
        fields = ['requested_role']


UserProfileSocialLinksFormSet = inlineformset_factory(
    CommonUserProfile, SocialLink,
    fields=('media_name', 'url'),
    extra=4,
    max_num=4
)

from django_countries import countries


class CommonUserProfileForm(djform.ModelForm):
    """Core details of user profile created only after account verification by institute."""
    country = djform.ChoiceField(
        choices=[('', '---------')] + list(countries),
        required=False,
        widget=djform.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CommonUserProfile
        fields = [
            'headline',
            'show_headline_in_bio',
            'country',
            'summary'
        ]