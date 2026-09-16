from django.contrib import admin
from .models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)


@admin.register(TransportVehicle)
class TransportVehicleAdmin(admin.ModelAdmin):
    list_display = ('school', 'vehicle_number', 'registration_number', 'vehicle_type', 'capacity', 'is_active')
    list_filter = ('school', 'vehicle_type', 'is_active')
    search_fields = ('vehicle_number', 'registration_number')


@admin.register(TransportStaff)
class TransportStaffAdmin(admin.ModelAdmin):
    list_display = ('school', 'name', 'phone', 'role', 'license_number', 'license_expiry', 'is_active')
    list_filter = ('school', 'role', 'is_active')
    search_fields = ('name', 'phone', 'license_number')


class TransportStopInline(admin.TabularInline):
    model = TransportStop
    extra = 1
    fields = ('sequence', 'name', 'landmark', 'pickup_time', 'drop_time', 'fare', 'is_active')


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'code', 'name', 'fare', 'is_active')
    list_filter = ('school', 'academic_year', 'is_active')
    search_fields = ('name', 'code')
    inlines = [TransportStopInline]


@admin.register(TransportStop)
class TransportStopAdmin(admin.ModelAdmin):
    list_display = ('school', 'route', 'sequence', 'name', 'pickup_time', 'drop_time', 'fare', 'is_active')
    list_filter = ('school', 'route', 'is_active')
    search_fields = ('name', 'address', 'landmark')


@admin.register(VehicleRouteAssignment)
class VehicleRouteAssignmentAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'route', 'vehicle', 'driver', 'attendant', 'is_active')
    list_filter = ('school', 'academic_year', 'is_active')


@admin.register(StudentTransportAssignment)
class StudentTransportAssignmentAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'student', 'route', 'pickup_stop', 'drop_stop', 'transport_status')
    list_filter = ('school', 'academic_year', 'transport_status')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')
