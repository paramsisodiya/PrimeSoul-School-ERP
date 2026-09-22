import re
from datetime import date

from django import forms
from django.core.validators import FileExtensionValidator
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import Tab, TabHolder
from crispy_forms.layout import (
    Layout, Field, ButtonHolder, Submit
)

from django_school_management.institute.models import EducationBoard
from django_school_management.institute.education_boards import (
    COUNTRY_BD,
    COUNTRY_IN,
    IN_GROUPS,
    BD_GROUPS,
    APPLYING_FOR_CLASS_MIN,
    APPLYING_FOR_CLASS_MAX,
    APPLYING_FOR_CLASS_JSC_START,
)
from .models import AdmissionStudent, CounselingComment, Student

MAX_UPLOAD_SIZE_MB = 5


def _is_bd(institute):
    """True if institute has country set to Bangladesh."""
    if not institute or not getattr(institute, 'country', None):
        return False
    code = getattr(institute.country, 'code', institute.country) or str(institute.country)
    return code == COUNTRY_BD


class StudentForm(forms.ModelForm):
    """Admission form. When institute is school/madrasah, academic fields are optional."""

    class Meta:
        model = AdmissionStudent
        fields = [
            'name',
            'fathers_name',
            'mothers_name',
            'date_of_birth',
            'gender',
            'city',
            'current_address',
            'permanent_address',
            'mobile_number',
            'guardian_mobile_number',
            'email',
            'tribal_status',
            'department_choice',
            'applying_for_class',
            'board',
            'ssc_roll',
            'ssc_registration',
            'gpa',
            'exam_name',
            'passing_year',
            'group',
            'photo',
            'marksheet_image',
            'admission_policy_agreement',
            'admit_to_semester',
        ]
        widgets = {
            'date_of_birth': forms.TextInput({'type': 'date'}),
            'gpa': forms.NumberInput(attrs={'min': '0', 'max': '5', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.institute = kwargs.pop('institute', None)
        super().__init__(*args, **kwargs)
        # Gender: required for all
        if 'gender' in self.fields:
            self.fields['gender'].required = True

        # Determine if institute is polytechnic or school/madrasah
        is_poly = bool(self.institute and getattr(self.institute, 'is_polytechnic', False))
        is_school = not is_poly  # Default to school for K-12

        if is_poly:
            self.fields.pop('applying_for_class', None)
            if 'admit_to_semester' in self.fields:
                self.fields['admit_to_semester'].required = False
                self.fields['admit_to_semester'].widget = forms.Select(
                    choices=[('', '---------'), (1, '1st Semester'), (4, '4th Semester (direct)')]
                )
        else:
            self.fields.pop('admit_to_semester', None)
            if 'applying_for_class' in self.fields:
                self.fields['applying_for_class'].required = False
                self.fields['applying_for_class'].widget = forms.Select(
                    choices=[('', '---------')] + [(i, f'Class {i}') for i in range(APPLYING_FOR_CLASS_MIN, APPLYING_FOR_CLASS_MAX + 1)]
                )

        if self.institute:
            if 'department_choice' in self.fields:
                self.fields['department_choice'].queryset = (
                    self.fields['department_choice'].queryset.filter(institute=self.institute)
                )
                self.fields['department_choice'].label = (
                    self.institute.department_label or 'Class / Department'
                )

        if is_school:
            for f in ('exam_name', 'passing_year', 'group', 'board',
                      'ssc_roll', 'ssc_registration', 'gpa', 'marksheet_image'):
                if f in self.fields:
                    self.fields[f].required = False

            # Set up boards (India boards by default)
            country_code = getattr(self.institute, 'country', 'IN') if self.institute else 'IN'
            code = getattr(country_code, 'code', country_code) or 'IN'
            boards_qs = EducationBoard.get_boards_for_country(code)
            if 'board' in self.fields:
                self.fields['board'].widget = forms.Select(
                    choices=[('', '---------')] + [(b.name, b.name) for b in boards_qs]
                )
                self.fields['board'].label = 'Previous Board / School Board'
            if 'group' in self.fields:
                self.fields['group'].widget = forms.Select(
                    choices=[('', '---------')] + list(IN_GROUPS)
                )

    def clean_gpa(self):
        gpa = self.cleaned_data.get('gpa')
        if gpa is not None and (gpa < 0 or gpa > 10):
            raise forms.ValidationError("GPA / Marks percentage must be between 0.00 and 10.00.")
        return gpa

    def clean_mobile_number(self):
        value = self.cleaned_data.get('mobile_number', '')
        if value:
            clean_digits = re.sub(r'[^\d+]', '', value)
            if clean_digits.startswith('+91'):
                digits = clean_digits[3:]
            elif clean_digits.startswith('0') and len(clean_digits) == 11:
                digits = clean_digits[1:]
            else:
                digits = clean_digits.lstrip('+')
            
            # Support 10-digit Indian numbers starting with 6-9, or legacy 11-digit
            if not (len(digits) == 10 and digits[0] in '6789') and not (len(digits) == 11):
                raise forms.ValidationError("Enter a valid 10-digit Indian mobile number (e.g. 9876543210 or +91 9876543210).")
        return value

    def clean_guardian_mobile_number(self):
        value = self.cleaned_data.get('guardian_mobile_number', '')
        if value:
            clean_digits = re.sub(r'[^\d+]', '', value)
            if clean_digits.startswith('+91'):
                digits = clean_digits[3:]
            elif clean_digits.startswith('0') and len(clean_digits) == 11:
                digits = clean_digits[1:]
            else:
                digits = clean_digits.lstrip('+')
            
            if not (len(digits) == 10 and digits[0] in '6789') and not (len(digits) == 11):
                raise forms.ValidationError("Enter a valid 10-digit Indian mobile number (e.g. 9876543210 or +91 9876543210).")
        return value

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob >= date.today():
            raise forms.ValidationError("Date of birth must be in the past.")
        return dob

    def _check_file_size(self, field_name):
        f = self.cleaned_data.get(field_name)
        if f and hasattr(f, 'size') and f.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f"File must be under {MAX_UPLOAD_SIZE_MB} MB.")
        return f

    def clean_photo(self):
        return self._check_file_size('photo')

    def clean_marksheet_image(self):
        return self._check_file_size('marksheet_image')

    def clean(self):
        data = super().clean()
        if not data:
            return data
        # BD school/madrasah: require JSC/JDC fields when applying for class 9 or 10
        if _is_bd(self.institute) and self.institute and self.institute.is_school_or_madrasah:
            applying = data.get('applying_for_class')
            if applying is not None:
                try:
                    applying = int(applying)
                except (TypeError, ValueError):
                    applying = None
            if applying is not None and applying >= APPLYING_FOR_CLASS_JSC_START:
                for f in ('ssc_roll', 'ssc_registration', 'gpa', 'board'):
                    if f in self.fields and not data.get(f):
                        self.add_error(f, forms.ValidationError('This field is required for Class 9/10 admission.'))
        # BD polytechnic: admit_to_semester 4 only valid when HSC Science
        if _is_bd(self.institute) and self.institute and self.institute.is_polytechnic:
            admit_sem = data.get('admit_to_semester')
            if admit_sem is not None:
                try:
                    admit_sem = int(admit_sem)
                except (TypeError, ValueError):
                    admit_sem = None
            if admit_sem == 4:
                if data.get('exam_name') != 'HSC' or data.get('group') != 'Science':
                    self.add_error('admit_to_semester', forms.ValidationError(
                        'Direct admission to 4th semester is only for HSC Science passers.'
                    ))
        return data

    def clean_admit_to_semester(self):
        val = self.cleaned_data.get('admit_to_semester')
        if val is not None and val != '':
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
        return None

    def clean_applying_for_class(self):
        val = self.cleaned_data.get('applying_for_class')
        if val is not None and val != '':
            try:
                n = int(val)
                if APPLYING_FOR_CLASS_MIN <= n <= APPLYING_FOR_CLASS_MAX:
                    return n
            except (TypeError, ValueError):
                pass
        return None


class AdmissionForm(forms.ModelForm):
    """Admit form: set choosen_department (polytechnic counselling)."""

    class Meta:
        model = AdmissionStudent
        fields = [
            'choosen_department',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.department_choice_id:
            institute = getattr(self.instance.department_choice, 'institute', None)
            if institute:
                self.fields['choosen_department'].queryset = (
                    self.fields['choosen_department'].queryset.filter(institute=institute)
                )


class StudentRegistrantUpdateForm(forms.ModelForm):
    class Meta:
        model = AdmissionStudent
        fields = [
            'name',
            'photo',
            'fathers_name',
            'mothers_name',
            'date_of_birth',
            'gender',
            'current_address',
            'permanent_address',
            'mobile_number',
            'email',
            'choosen_department',
            'admitted',
            'paid',
            'rejected',
        ]
        widgets = {
            'date_of_birth': forms.TextInput({'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        show_choosen_department = kwargs.pop('show_choosen_department', True)
        super().__init__(*args, **kwargs)
        if not show_choosen_department and 'choosen_department' in self.fields:
            self.fields.pop('choosen_department')


class CounselingDataForm(forms.ModelForm):
    class Meta:
        model = CounselingComment
        fields = ['comment', ]


class StudentUpdateForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = (
            'first_name',
            'last_name',
            'admission_number',
            'roll_number',
            'grade_level',
            'section',
            'academic_year',
            'emergency_contact_number',
            'roll',
            'registration_number',
            'semester',
            'guardian_mobile',
            'is_alumni',
            'is_dropped'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django_school_management.academics.models import GradeLevel, Section, AcademicYear
        if self.instance and self.instance.school_id:
            school = self.instance.school
            if 'grade_level' in self.fields:
                self.fields['grade_level'].queryset = GradeLevel.objects.filter(school=school)
            if 'section' in self.fields:
                self.fields['section'].queryset = Section.objects.filter(school=school)
            if 'academic_year' in self.fields:
                self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
        for f in ['roll', 'registration_number', 'semester', 'guardian_mobile', 'grade_level', 'section', 'academic_year', 'emergency_contact_number']:
            if f in self.fields:
                self.fields[f].required = False

