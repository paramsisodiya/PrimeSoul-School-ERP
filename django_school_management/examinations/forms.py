from django import forms
from .models import (
    ExaminationSession, Exam, ExamSubject, GradeScale, GradeScaleBand,
    StudentMark, AssessmentType
)
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, Subject


class ExaminationSessionForm(forms.ModelForm):
    class Meta:
        model = ExaminationSession
        fields = ['name', 'code', 'academic_year', 'start_date', 'end_date', 'status', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Half Yearly Examination 2026-27'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HYE-2026'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            'session', 'academic_year', 'grade_level', 'section',
            'assessment_type', 'grade_scale', 'name',
            'start_date', 'end_date', 'weightage', 'ranking_enabled', 'status'
        ]
        widgets = {
            'session': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'grade_level': forms.Select(attrs={'class': 'form-select'}),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'assessment_type': forms.Select(attrs={'class': 'form-select'}),
            'grade_scale': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Half Yearly Exam - Class 10'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'weightage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ranking_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['session'].queryset = ExaminationSession.objects.filter(school=school)
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True)
            self.fields['section'].required = False
            self.fields['assessment_type'].queryset = AssessmentType.objects.filter(school=school, is_active=True)
            self.fields['grade_scale'].queryset = GradeScale.objects.filter(school=school)
            self.fields['grade_scale'].required = False


class ExamSubjectForm(forms.ModelForm):
    class Meta:
        model = ExamSubject
        fields = ['subject', 'max_marks', 'passing_marks', 'weightage', 'sequence_order', 'is_optional', 'is_active']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'passing_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'weightage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sequence_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['subject'].queryset = Subject.objects.filter(school=school, is_active=True)


class GradeScaleForm(forms.ModelForm):
    class Meta:
        model = GradeScale
        fields = ['name', 'code', 'is_default', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CBSE 8-Point Secondary Scale'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CBSE-8P'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class GradeScaleBandForm(forms.ModelForm):
    class Meta:
        model = GradeScaleBand
        fields = ['name', 'min_percentage', 'max_percentage', 'grade_point', 'is_passing', 'remarks']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A1'}),
            'min_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'grade_point': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'is_passing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'remarks': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Outstanding'}),
        }


class MarksCorrectionForm(forms.Form):
    new_status = forms.ChoiceField(
        choices=StudentMark.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    new_marks = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'})
    )
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'State mandatory justification for correction (e.g. Re-totalling error, re-evaluation request approval)'})
    )
