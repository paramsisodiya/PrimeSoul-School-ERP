from django import forms
from django.utils import timezone
from .models import AttendanceRecord
from django_school_management.academics.models import AcademicYear, GradeLevel, Section


class DailyAttendanceFilterForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        empty_label="Select Session",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2', 'id': 'id_academic_year'})
    )
    grade_level = forms.ModelChoiceField(
        queryset=GradeLevel.objects.none(),
        empty_label="Select Class",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2', 'id': 'id_grade_level'})
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(),
        empty_label="Select Section",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2', 'id': 'id_section'})
    )
    attendance_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True).order_by('display_order')
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True).order_by('grade_level__display_order', 'name')
            
            # Default to current year if available
            current_yr = AcademicYear.objects.filter(school=school, is_current=True).first()
            if current_yr and not self.is_bound:
                self.fields['academic_year'].initial = current_yr


class AttendanceCorrectionForm(forms.Form):
    new_status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-sm',
            'rows': 3,
            'placeholder': 'Provide a detailed justification for correcting this attendance record...'
        }),
        required=True,
        help_text="Mandatory audit justification for correcting attendance."
    )


class AttendanceHistoryFilterForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        required=False,
        empty_label="All Sessions",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2'})
    )
    grade_level = forms.ModelChoiceField(
        queryset=GradeLevel.objects.none(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2'})
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(),
        required=False,
        empty_label="All Sections",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm select2'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(AttendanceRecord.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search student name, roll, admission no...'})
    )

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True).order_by('display_order')
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True).order_by('grade_level__display_order', 'name')
