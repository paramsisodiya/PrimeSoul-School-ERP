"""
PrimeSoul Transport - REST API Serializers
"""
from rest_framework import serializers
from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.students.models import Student


class TransportVehicleSerializer(serializers.ModelSerializer):
    has_expiring_documents = serializers.BooleanField(read_only=True)

    class Meta:
        model = TransportVehicle
        fields = [
            'id', 'school', 'vehicle_number', 'registration_number',
            'vehicle_type', 'capacity', 'is_active',
            'insurance_expiry', 'pollution_cert_expiry', 'fitness_cert_expiry',
            'notes', 'has_expiring_documents'
        ]
        read_only_fields = ['id', 'school']


class TransportStaffSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    is_license_expiring_soon = serializers.BooleanField(read_only=True)
    is_license_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = TransportStaff
        fields = [
            'id', 'school', 'user', 'name', 'phone', 'role', 'role_display',
            'license_number', 'license_expiry', 'address', 'is_active',
            'is_license_expiring_soon', 'is_license_expired'
        ]
        read_only_fields = ['id', 'school']


class TransportStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportStop
        fields = [
            'id', 'school', 'route', 'name', 'address', 'landmark',
            'sequence', 'pickup_time', 'drop_time', 'fare',
            'latitude', 'longitude', 'is_active'
        ]
        read_only_fields = ['id', 'school']


class TransportRouteSerializer(serializers.ModelSerializer):
    stops = TransportStopSerializer(many=True, read_only=True)
    stops_count = serializers.IntegerField(source='stops.count', read_only=True)

    class Meta:
        model = TransportRoute
        fields = [
            'id', 'school', 'academic_year', 'name', 'code',
            'description', 'fare', 'is_active', 'stops_count', 'stops'
        ]
        read_only_fields = ['id', 'school']


class VehicleRouteAssignmentSerializer(serializers.ModelSerializer):
    vehicle_number = serializers.CharField(source='vehicle.vehicle_number', read_only=True)
    route_code = serializers.CharField(source='route.code', read_only=True)
    driver_name = serializers.CharField(source='driver.name', read_only=True)
    attendant_name = serializers.CharField(source='attendant.name', read_only=True, default='')

    class Meta:
        model = VehicleRouteAssignment
        fields = [
            'id', 'school', 'academic_year', 'vehicle', 'vehicle_number',
            'route', 'route_code', 'driver', 'driver_name',
            'attendant', 'attendant_name', 'start_date', 'end_date', 'is_active'
        ]
        read_only_fields = ['id', 'school']


class StudentTransportAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True, default='')
    route_code = serializers.CharField(source='route.code', read_only=True)
    pickup_stop_name = serializers.CharField(source='pickup_stop.name', read_only=True)
    drop_stop_name = serializers.CharField(source='drop_stop.name', read_only=True)

    class Meta:
        model = StudentTransportAssignment
        fields = [
            'id', 'school', 'academic_year', 'student', 'student_name',
            'admission_number', 'route', 'route_code', 'pickup_stop',
            'pickup_stop_name', 'drop_stop', 'drop_stop_name',
            'transport_status', 'start_date', 'end_date', 'notes'
        ]
        read_only_fields = ['id', 'school']
