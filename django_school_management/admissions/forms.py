from django import forms
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from django_school_management.academics.models import GradeLevel, Section, AcademicStream, AcademicYear
from django_school_management.utils.india_localization import (
    is_valid_indian_mobile, clean_indian_mobile
)


class AdmissionSessionForm(forms.ModelForm):
    class Meta:
        model = AdmissionSession
        fields = [
            'name', 'academic_year', 'application_start', 'application_end',
            'admission_start', 'admission_end', 'status',
            'application_number_prefix', 'admission_number_prefix', 'active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Session 2026-27 Admissions'}),
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'application_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'application_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'admission_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'admission_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'application_number_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'admission_number_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(
                school=school,
                status__in=[AcademicYear.STATUS_ACTIVE, AcademicYear.STATUS_UPCOMING]
            )


class AdmissionClassConfigForm(forms.ModelForm):
    class Meta:
        model = AdmissionClassConfig
        fields = ['admission_session', 'grade_level', 'total_seats', 'reserved_seats', 'application_fee', 'active']
        widgets = {
            'admission_session': forms.Select(attrs={'class': 'form-control'}),
            'grade_level': forms.Select(attrs={'class': 'form-control'}),
            'total_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'reserved_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'application_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['admission_session'].queryset = AdmissionSession.objects.filter(school=school, active=True)
            self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school, is_active=True)


class AdmissionEnquiryForm(forms.ModelForm):
    class Meta:
        model = AdmissionEnquiry
        fields = [
            'admission_session', 'student_name', 'parent_name', 'mobile',
            'email', 'interested_grade', 'source', 'notes', 'status'
        ]
        widgets = {
            'admission_session': forms.Select(attrs={'class': 'form-control'}),
            'student_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name of applicant'}),
            'parent_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Parent / Guardian name'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Indian mobile number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address (optional)'}),
            'interested_grade': forms.Select(attrs={'class': 'form-control'}),
            'source': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Interaction notes...'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['admission_session'].queryset = AdmissionSession.objects.filter(school=school, active=True)
            self.fields['interested_grade'].queryset = GradeLevel.objects.filter(school=school, is_active=True)

    def clean_mobile(self):
        ph = self.cleaned_data.get('mobile')
        if not is_valid_indian_mobile(ph):
            raise forms.ValidationError("Please provide a valid 10-digit Indian mobile number.")
        return clean_indian_mobile(ph)


class AdmissionApplicationForm(forms.ModelForm):
    class Meta:
        model = AdmissionApplication
        fields = [
            'admission_session', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'blood_group', 'nationality', 'category', 'aadhaar_number',
            'requested_grade', 'requested_stream', 'previous_school', 'previous_school_tc_number',
            'previous_grade', 'previous_percentage',
            'father_name', 'father_mobile', 'father_email', 'father_occupation', 'father_aadhaar',
            'mother_name', 'mother_mobile', 'mother_email', 'mother_occupation', 'mother_aadhaar',
            'guardian_name', 'guardian_mobile', 'guardian_relation',
            'current_address', 'permanent_address', 'emergency_contact_name', 'emergency_contact_number',
            'status', 'application_fee_status', 'remarks'
        ]
        widgets = {
            'admission_session': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'blood_group': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. O+'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit UIDAI'}),
            'requested_grade': forms.Select(attrs={'class': 'form-control'}),
            'requested_stream': forms.Select(attrs={'class': 'form-control'}),
            'previous_school': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_school_tc_number': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_grade': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'father_aadhaar': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'mother_occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_aadhaar': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_relation': forms.TextInput(attrs={'class': 'form-control'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'permanent_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'application_fee_status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['admission_session'].queryset = AdmissionSession.objects.filter(school=school, active=True)
            self.fields['requested_grade'].queryset = GradeLevel.objects.filter(school=school, is_active=True)
            self.fields['requested_stream'].queryset = AcademicStream.objects.filter(school=school)

    def clean_father_mobile(self):
        ph = self.cleaned_data.get('father_mobile')
        if ph:
            if not is_valid_indian_mobile(ph):
                raise forms.ValidationError("Invalid 10-digit Indian mobile number.")
            return clean_indian_mobile(ph)
        return ""

    def clean_mother_mobile(self):
        ph = self.cleaned_data.get('mother_mobile')
        if ph:
            if not is_valid_indian_mobile(ph):
                raise forms.ValidationError("Invalid 10-digit Indian mobile number.")
            return clean_indian_mobile(ph)
        return ""


class PublicAdmissionApplicationForm(forms.ModelForm):
    """
    Public-safe online application form submitted by external parents.
    """
    class Meta:
        model = AdmissionApplication
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'blood_group', 'category', 'aadhaar_number',
            'requested_grade', 'previous_school', 'previous_grade', 'previous_percentage',
            'father_name', 'father_mobile', 'father_email', 'father_occupation',
            'mother_name', 'mother_mobile', 'mother_email',
            'current_address', 'emergency_contact_number'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name', 'required': 'true'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': 'true'}),
            'gender': forms.Select(attrs={'class': 'form-control', 'required': 'true'}),
            'blood_group': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. B+'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'General / OBC / SC / ST'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit Aadhaar UIDAI'}),
            'requested_grade': forms.Select(attrs={'class': 'form-control', 'required': 'true'}),
            'previous_school': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Previous School Name'}),
            'previous_grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Class Passed'}),
            'previous_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Score %'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Father Full Name'}),
            'father_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Mobile', 'required': 'true'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Father Email'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Occupation'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mother Full Name'}),
            'mother_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Mobile'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Mother Email'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Residential Address', 'required': 'true'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency Phone'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['requested_grade'].queryset = GradeLevel.objects.filter(school=school, is_active=True)

    def clean_father_mobile(self):
        ph = self.cleaned_data.get('father_mobile')
        if not is_valid_indian_mobile(ph):
            raise forms.ValidationError("Please provide a valid 10-digit Indian mobile number.")
        return clean_indian_mobile(ph)


class AdmissionDocumentForm(forms.ModelForm):
    class Meta:
        model = AdmissionDocument
        fields = ['document_type', 'title', 'file']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Document Title / Description'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }


class AdmissionInterviewForm(forms.ModelForm):
    class Meta:
        model = AdmissionInterview
        fields = ['scheduled_at', 'location', 'interviewer', 'status', 'remarks', 'score']
        widgets = {
            'scheduled_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'interviewer': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }


class AdmissionAssessmentForm(forms.ModelForm):
    class Meta:
        model = AdmissionAssessment
        fields = ['subject', 'max_score', 'score', 'remarks']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject / Topic'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AdmissionReviewForm(forms.Form):
    status = forms.ChoiceField(
        choices=AdmissionApplication.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Evaluation remarks...'})
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Reason for rejection (if applicable)...'})
    )


class AdmissionConvertForm(forms.Form):
    section = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    roll_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional roll number'})
    )

    def __init__(self, *args, school=None, grade_level=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school and grade_level:
            self.fields['section'].queryset = Section.objects.filter(school=school, grade_level=grade_level)
        elif school:
            self.fields['section'].queryset = Section.objects.filter(school=school)
        else:
            self.fields['section'].queryset = Section.objects.none()
