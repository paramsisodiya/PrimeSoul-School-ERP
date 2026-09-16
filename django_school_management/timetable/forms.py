"""
PrimeSoul Timetable - Modern ERP Forms
Provides validation and styling for working days, periods, classrooms, and timetable entries.
"""
from django import forms
from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, Subject
)
from django_school_management.teachers.models import Teacher


class WorkingDayForm(forms.ModelForm):
    class Meta:
        model = WorkingDay
        fields = ['weekday', 'day_name', 'is_working', 'display_order']
        widgets = {
            'weekday': forms.Select(attrs={'class': 'form-control'}),
            'day_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monday'}),
            'is_working': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['name', 'period_number', 'start_time', 'end_time', 'is_break', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Period 1, Lunch Break'}),
            'period_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1, 2, 3 (Optional for breaks)'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'is_break': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'room_number', 'room_type', 'capacity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 101, Physics Lab'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 101, PLAB'}),
            'room_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '40'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ['working_day', 'time_slot', 'section', 'subject', 'teacher', 'room', 'entry_type', 'notes']
        widgets = {
            'working_day': forms.Select(attrs={'class': 'form-control'}),
            'time_slot': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'entry_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional notes or lesson title'}),
        }

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            ay = academic_year
            self.fields['working_day'].queryset = WorkingDay.objects.filter(
                school=school, academic_year=ay, is_working=True
            ) if ay else WorkingDay.objects.filter(school=school, is_working=True)
            self.fields['time_slot'].queryset = TimeSlot.objects.filter(
                school=school, academic_year=ay, is_active=True
            ) if ay else TimeSlot.objects.filter(school=school, is_active=True)
            self.fields['section'].queryset = Section.objects.filter(school=school, is_active=True)
            self.fields['subject'].queryset = Subject.objects.filter(school=school, is_active=True)
            self.fields['teacher'].queryset = Teacher.objects.filter(school=school)
            self.fields['room'].queryset = Classroom.objects.filter(school=school, is_active=True)

        self.fields['subject'].required = False
        self.fields['teacher'].required = False
        self.fields['room'].required = False


class TimetableCloneForm(forms.Form):
    source_academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Academic session to copy from"
    )
    target_academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Academic session to copy into"
    )
    clone_working_days = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    clone_time_slots = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    clone_entries = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['source_academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
            self.fields['target_academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')


class TimetableGenerateForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Academic session for timetable generation"
    )
    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'}),
        help_text="Leave blank to generate for all sections in the school."
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
            self.fields['sections'].queryset = Section.objects.filter(school=school, is_active=True)
