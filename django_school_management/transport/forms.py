"""
PrimeSoul Transport - Modern ERP Forms
"""
from django import forms
from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.academics.models import AcademicYear
from django_school_management.students.models import Student
from django_school_management.utils.india_localization import clean_indian_mobile, is_valid_indian_mobile


class TransportVehicleForm(forms.ModelForm):
    class Meta:
        model = TransportVehicle
        fields = [
            'vehicle_number', 'registration_number', 'vehicle_type', 'capacity',
            'insurance_expiry', 'pollution_cert_expiry', 'fitness_cert_expiry', 'notes', 'is_active'
        ]
        widgets = {
            'vehicle_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BUS-01, VAN-02'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DL-01-AB-1234'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '40'}),
            'insurance_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pollution_cert_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fitness_cert_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional maintenance remarks'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TransportRouteForm(forms.ModelForm):
    class Meta:
        model = TransportRoute
        fields = ['academic_year', 'name', 'code', 'description', 'fare', 'is_active']
        widgets = {
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. North Delhi Route 1'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. R-01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Coverage landmarks'}),
            'fare': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')


class TransportStopForm(forms.ModelForm):
    class Meta:
        model = TransportStop
        fields = [
            'name', 'address', 'landmark', 'sequence',
            'pickup_time', 'drop_time', 'fare', 'latitude', 'longitude', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Metro Gate 2'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional street address'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Near HDFC Bank'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1, 2, 3'}),
            'pickup_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'drop_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'fare': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 28.6139'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 77.2090'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TransportStaffForm(forms.ModelForm):
    class Meta:
        model = TransportStaff
        fields = ['name', 'phone', 'role', 'license_number', 'license_expiry', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full legal name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit mobile number'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DL-1420110012345'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_phone(self):
        ph = self.cleaned_data.get('phone', '').strip()
        if not is_valid_indian_mobile(ph):
            raise forms.ValidationError("Please provide a valid 10-digit Indian mobile number.")
        return clean_indian_mobile(ph)


class VehicleRouteAssignmentForm(forms.ModelForm):
    class Meta:
        model = VehicleRouteAssignment
        fields = ['vehicle', 'route', 'driver', 'attendant', 'start_date', 'end_date']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-control'}),
            'route': forms.Select(attrs={'class': 'form-control'}),
            'driver': forms.Select(attrs={'class': 'form-control'}),
            'attendant': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['vehicle'].queryset = TransportVehicle.objects.filter(school=school, is_active=True)
            self.fields['route'].queryset = TransportRoute.objects.filter(school=school, academic_year=academic_year, is_active=True) if academic_year else TransportRoute.objects.filter(school=school, is_active=True)
            self.fields['driver'].queryset = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_DRIVER, is_active=True)
            self.fields['attendant'].queryset = TransportStaff.objects.filter(school=school, role=TransportStaff.ROLE_ATTENDANT, is_active=True)
        self.fields['attendant'].required = False


class StudentTransportAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentTransportAssignment
        fields = ['student', 'route', 'pickup_stop', 'drop_stop', 'transport_status', 'start_date', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'route': forms.Select(attrs={'class': 'form-control'}),
            'pickup_stop': forms.Select(attrs={'class': 'form-control'}),
            'drop_stop': forms.Select(attrs={'class': 'form-control'}),
            'transport_status': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional instructions or medical notes'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True)
            self.fields['route'].queryset = TransportRoute.objects.filter(school=school, is_active=True)
            self.fields['pickup_stop'].queryset = TransportStop.objects.filter(school=school, is_active=True)
            self.fields['drop_stop'].queryset = TransportStop.objects.filter(school=school, is_active=True)
