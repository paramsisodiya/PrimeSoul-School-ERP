from django import forms
from django.db.models import Q
from .models import (
    Announcement, AnnouncementTarget, AnnouncementCategory,
    NotificationTemplate, NotificationPreference
)


class AnnouncementForm(forms.ModelForm):
    """
    Form for creating and editing school announcements with scheduling.
    """
    target_type = forms.ChoiceField(
        choices=AnnouncementTarget.TARGET_CHOICES,
        initial=AnnouncementTarget.TARGET_ALL,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_target_type'})
    )
    grade_level = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_grade_level'})
    )
    section = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_section'})
    )

    class Meta:
        model = Announcement
        fields = [
            'title', 'content', 'category', 'priority', 'status',
            'scheduled_at', 'expires_at', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Annual Sports Day 2026'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter announcement details...'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['category'].queryset = AnnouncementCategory.objects.filter(
                Q(school=school) | Q(school__isnull=True),
                is_active=True
            )
            from django_school_management.academics.models import GradeLevel, Section
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['section'].queryset = Section.objects.filter(school=school)
        else:
            self.fields['category'].queryset = AnnouncementCategory.objects.filter(is_active=True)


class NotificationTemplateForm(forms.ModelForm):
    """
    Form for configuring notification templates.
    """
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'code', 'channel', 'subject', 'body', 'active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Student Absence Notice'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ATTENDANCE_ABSENT'}),
            'channel': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject (for email)'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Use {{placeholders}}...'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NotificationPreferenceForm(forms.ModelForm):
    """
    Form for updating personal alert and channel preferences.
    """
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'sms_enabled', 'whatsapp_enabled',
            'attendance_alerts', 'fee_alerts', 'exam_alerts',
            'transport_alerts', 'library_alerts', 'hr_alerts'
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'sms_enabled': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'whatsapp_enabled': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'attendance_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'fee_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'exam_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'transport_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'library_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'hr_alerts': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
        }
