from collections.abc import Iterable
from typing import Type

from django.db.models import Model
from django.forms import ModelForm

from django import forms
from django.core.exceptions import ValidationError

from .models import Department, Semester, AcademicSession, Subject, Batch
from ..mixins.institute import get_user_institute


def create_model_form_factory(
        model_class: Type[Model],
        *,
        include_fields: Iterable[str] = None,
        exclude_fields: Iterable[str] = None
) -> Type[ModelForm]:
    class CreatedByExcludedForm(ModelForm):
        class Meta:
            model = model_class
            fields = include_fields if include_fields else '__all__'
            exclude = exclude_fields if exclude_fields else []

    return CreatedByExcludedForm


DepartmentForm = create_model_form_factory(Department, exclude_fields=['created_by', 'institute'])

SemesterForm = create_model_form_factory(Semester, exclude_fields=['created_by',])

AcademicSessionForm = create_model_form_factory(AcademicSession, exclude_fields=['created_by',])

SubjectForm = create_model_form_factory(Subject, exclude_fields=['created_by',])


class SubjectFormCurriculumAware(SubjectForm):
    """Subject form with optional curriculum template; template can prefill name and marks."""

    class Meta(SubjectForm.Meta):
        fields = ['subject_template', 'name', 'subject_code', 'book_cover', 'instructor',
                  'theory_marks', 'practical_marks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django_school_management.curriculum.models import SubjectTemplate
        self.fields['subject_template'].queryset = SubjectTemplate.objects.order_by('name')
        self.fields['subject_template'].required = False
        self.fields['subject_template'].label = 'Link to curriculum template (optional)'
        self.fields['subject_template'].help_text = 'Select a template to prefill name and marks, or create a custom subject.'


BatchForm = create_model_form_factory(Batch, include_fields=['department', 'year', 'number'])


class BatchFormWithLabel(BatchForm):
    """Batch form with department label set from user's institute (Group vs Department)."""

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request and 'department' in self.fields:
            institute = get_user_institute(getattr(request, 'user', None))
            self.fields['department'].label = institute.department_label if institute else 'Department'


class BulkSemesterForm(forms.Form):
    """Form to create multiple semesters at once. Accepts e.g. '1-6' or '1,2,3,4'."""

    numbers = forms.CharField(
        label='Semester numbers',
        help_text='Enter a range (e.g. 1-6) or comma-separated numbers (e.g. 1,2,3,4).',
        widget=forms.TextInput(attrs={'placeholder': '1-6 or 1,2,3,4'}),
    )

    def clean_numbers(self):
        value = self.cleaned_data.get('numbers', '').strip()
        if not value:
            raise ValidationError('Enter at least one semester number.')
        numbers = set()
        for part in value.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    a, b = part.split('-', 1)
                    a, b = int(a.strip()), int(b.strip())
                    if a > b:
                        a, b = b, a
                    for n in range(a, b + 1):
                        if n >= 1:
                            numbers.add(n)
                except ValueError:
                    raise ValidationError(f'Invalid range: {part}. Use e.g. 1-6.')
            else:
                try:
                    n = int(part)
                    if n >= 1:
                        numbers.add(n)
                except ValueError:
                    raise ValidationError(f'Invalid number: {part}.')
        if not numbers:
            raise ValidationError('Enter at least one valid semester number (1 or more).')
        existing = set(Semester.objects.filter(number__in=numbers).values_list('number', flat=True))
        if existing:
            raise ValidationError(f'Semester(s) already exist: {sorted(existing)}. Create only new numbers.')
        return sorted(numbers)


# ─────────────────────────────────────────────────────────────
# Phase 5 — Modern PrimeSoul K-12 Academic Forms
# ─────────────────────────────────────────────────────────────

from .models import AcademicYear, GradeLevel, Section, SubjectAssignment, StudentEnrollment
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'status', 'is_current']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026-2027'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
        }


class GradeLevelForm(forms.ModelForm):
    class Meta:
        model = GradeLevel
        fields = ['name', 'code', 'board', 'stream_applicable', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Class 10, Nursery'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10, NUR'}),
            'board': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CBSE, ICSE'}),
            'stream_applicable': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
        }


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['grade_level', 'academic_year', 'name', 'class_teacher', 'room_number', 'max_capacity', 'is_active']
        widgets = {
            'grade_level': forms.Select(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. A, B, Rose'}),
            'class_teacher': forms.Select(attrs={'class': 'form-control'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 204'}),
            'max_capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['class_teacher'].queryset = Teacher.objects.filter(school=school)


class SubjectModernForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'subject_type', 'max_marks', 'passing_marks', 'instructor', 'theory_marks', 'practical_marks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics, English'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MATH-10, ENG-101'}),
            'subject_type': forms.Select(attrs={'class': 'form-control'}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'passing_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'instructor': forms.Select(attrs={'class': 'form-control'}),
            'theory_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'practical_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['instructor'].queryset = Teacher.objects.filter(school=school)


class SubjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = SubjectAssignment
        fields = ['academic_year', 'grade_level', 'section', 'subject', 'teacher', 'periods_per_week', 'is_active']
        widgets = {
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'grade_level': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'periods_per_week': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ml-1'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True)
            self.fields['subject'].queryset = Subject.objects.filter(school=school, is_active=True)
            self.fields['teacher'].queryset = Teacher.objects.filter(school=school)
            self.fields['section'].required = False


class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = StudentEnrollment
        fields = ['student', 'academic_year', 'grade_level', 'section', 'roll_number', 'status', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'grade_level': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'roll_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 15'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': '2'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True)
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True)
            self.fields['section'].required = False

