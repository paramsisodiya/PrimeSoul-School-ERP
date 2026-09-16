import datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django_school_management.academics.models import AcademicYear
from django_school_management.students.models import Student
from django_school_management.utils.india_localization import clean_indian_mobile, is_valid_indian_mobile


class TransportVehicle(ExportModelOperationsMixin('transport_vehicle'), TimeStampedModel):
    """
    Fleet vehicles (Buses, Vans, Cabs) operated or contracted by the school.
    """
    TYPE_BUS = 'BUS'
    TYPE_MINI_BUS = 'MINI_BUS'
    TYPE_VAN = 'VAN'
    TYPE_CAB = 'CAB'
    TYPE_OTHER = 'OTHER'

    VEHICLE_TYPE_CHOICES = (
        (TYPE_BUS, 'Full Size School Bus'),
        (TYPE_MINI_BUS, 'Mini Bus'),
        (TYPE_VAN, 'School Van / Winger'),
        (TYPE_CAB, 'Cab / Car'),
        (TYPE_OTHER, 'Other Transport Vehicle'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='transport_vehicles'
    )
    vehicle_number = models.CharField(
        max_length=50,
        help_text="Institutional identifier (e.g. BUS-01, VAN-03)"
    )
    registration_number = models.CharField(
        max_length=50,
        help_text="RTO Registration number (e.g. DL-01-AB-1234, MH-02-CD-5678)"
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        default=TYPE_BUS
    )
    capacity = models.PositiveIntegerField(
        default=40,
        help_text="Permissible seating capacity"
    )
    is_active = models.BooleanField(default=True)
    insurance_expiry = models.DateField(null=True, blank=True, help_text="Vehicle commercial insurance expiry date")
    pollution_cert_expiry = models.DateField(null=True, blank=True, help_text="PUCC validity expiry date")
    fitness_cert_expiry = models.DateField(null=True, blank=True, help_text="RTO Fitness certificate expiry date")
    notes = models.TextField(blank=True, help_text="Maintenance history, GPS vendor, or contractor notes")

    class Meta:
        ordering = ['vehicle_number']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'vehicle_number'],
                name='unique_school_transport_vehicle_number'
            )
        ]

    def __str__(self):
        return f"{self.vehicle_number} ({self.registration_number}) - Cap: {self.capacity}"

    @property
    def has_expiring_documents(self) -> bool:
        """Returns True if insurance, PUCC, or fitness expires within 30 days or is already expired."""
        today = timezone.now().date()
        threshold = today + datetime.timedelta(days=30)
        dates = [self.insurance_expiry, self.pollution_cert_expiry, self.fitness_cert_expiry]
        return any(d and d <= threshold for d in dates)


class TransportStaff(ExportModelOperationsMixin('transport_staff'), TimeStampedModel):
    """
    Transport personnel (Bus Drivers, Conductors, Attendants/Ayahs).
    """
    ROLE_DRIVER = 'DRIVER'
    ROLE_ATTENDANT = 'ATTENDANT'

    ROLE_CHOICES = (
        (ROLE_DRIVER, 'Bus / Van Driver'),
        (ROLE_ATTENDANT, 'Attendant / Bus Helper'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='transport_staff'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transport_staff_profile',
        help_text="Optional User account if driver logs into ERP"
    )
    name = models.CharField(max_length=150, help_text="Full legal name")
    phone = models.CharField(max_length=20, help_text="10-digit Indian contact mobile number")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DRIVER)
    license_number = models.CharField(
        max_length=50, blank=True,
        help_text="Commercial Driving License number (Mandatory for Drivers)"
    )
    license_expiry = models.DateField(
        null=True, blank=True,
        help_text="Driving License expiration date"
    )
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['role', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}, Ph: {self.phone})"

    def clean(self):
        super().clean()
        if self.phone and not is_valid_indian_mobile(self.phone):
            raise ValidationError({'phone': "Please enter a valid 10-digit Indian mobile number."})
        if self.role == self.ROLE_DRIVER and not self.license_number:
            raise ValidationError({'license_number': "Commercial Driving License number is required for drivers."})

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = clean_indian_mobile(self.phone)
        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_license_expiring_soon(self) -> bool:
        """Returns True if driver license expires within 30 days."""
        if not self.license_expiry:
            return False
        today = timezone.now().date()
        return self.license_expiry <= (today + datetime.timedelta(days=30))

    @property
    def is_license_expired(self) -> bool:
        if not self.license_expiry:
            return False
        return self.license_expiry < timezone.now().date()


class TransportRoute(ExportModelOperationsMixin('transport_route'), TimeStampedModel):
    """
    Designated bus/van route operated for a specific Academic Year.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='transport_routes'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='transport_routes'
    )
    name = models.CharField(max_length=150, help_text="e.g. North City Route 1, Rohini to DPS RKP")
    code = models.CharField(max_length=50, help_text="e.g. R-01, ROUTE-NORTH")
    description = models.TextField(blank=True, help_text="Route coverage areas and key arterial roads")
    fare = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        help_text="Standard monthly transport fee for this route (₹)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'code'],
                name='unique_school_academic_route_code'
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.academic_year.name})"


class TransportStop(ExportModelOperationsMixin('transport_stop'), TimeStampedModel):
    """
    Pick-up and drop-off landmark / bus stop along a TransportRoute.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='transport_stops'
    )
    route = models.ForeignKey(
        TransportRoute,
        on_delete=models.CASCADE,
        related_name='stops'
    )
    name = models.CharField(max_length=150, help_text="e.g. Rohini West Metro Station, Gate 2")
    address = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=150, blank=True)
    sequence = models.PositiveSmallIntegerField(default=1, help_text="Stop order along route (1, 2, 3...)")
    pickup_time = models.TimeField(null=True, blank=True, help_text="Morning pickup timing")
    drop_time = models.TimeField(null=True, blank=True, help_text="Afternoon drop-off timing")
    fare = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        help_text="Stop-specific monthly fare override (₹), 0 to inherit route standard fare"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['route', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['route', 'sequence'],
                name='unique_route_stop_sequence'
            )
        ]

    def __str__(self):
        pickup_str = f" [AM: {self.pickup_time.strftime('%H:%M')}]" if self.pickup_time else ""
        return f"Stop #{self.sequence}: {self.name}{pickup_str}"


class VehicleRouteAssignment(ExportModelOperationsMixin('vehicle_route_assignment'), TimeStampedModel):
    """
    Allocates a specific vehicle, driver, and attendant to a route for an academic year.
    Enforces driver and vehicle collision prevention.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='vehicle_route_assignments'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='vehicle_route_assignments'
    )
    vehicle = models.ForeignKey(
        TransportVehicle,
        on_delete=models.CASCADE,
        related_name='route_assignments'
    )
    route = models.ForeignKey(
        TransportRoute,
        on_delete=models.CASCADE,
        related_name='vehicle_assignments'
    )
    driver = models.ForeignKey(
        TransportStaff,
        on_delete=models.CASCADE,
        limit_choices_to={'role': TransportStaff.ROLE_DRIVER},
        related_name='driver_route_assignments'
    )
    attendant = models.ForeignKey(
        TransportStaff,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': TransportStaff.ROLE_ATTENDANT},
        related_name='attendant_route_assignments'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['route__code']

    def __str__(self):
        attendant_str = f", Attendant: {self.attendant.name}" if self.attendant else ""
        return f"{self.route.code} -> {self.vehicle.vehicle_number} (Driver: {self.driver.name}{attendant_str})"

    def clean(self):
        super().clean()
        if self.school_id:
            if self.vehicle.school_id != self.school_id:
                raise ValidationError({'vehicle': "Vehicle does not belong to the active school tenant."})
            if self.route.school_id != self.school_id:
                raise ValidationError({'route': "Route does not belong to the active school tenant."})
            if self.driver.school_id != self.school_id:
                raise ValidationError({'driver': "Driver does not belong to the active school tenant."})
            if self.attendant and self.attendant.school_id != self.school_id:
                raise ValidationError({'attendant': "Attendant does not belong to the active school tenant."})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class StudentTransportAssignment(ExportModelOperationsMixin('student_transport_assignment'), TimeStampedModel):
    """
    Subscribes a student to school transport with designated pickup and drop-off stops.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_SUSPENDED = 'SUSPENDED'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active Transport User'),
        (STATUS_INACTIVE, 'Inactive / Cancelled'),
        (STATUS_SUSPENDED, 'Suspended'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='student_transport_assignments'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='student_transport_assignments'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='transport_assignments'
    )
    route = models.ForeignKey(
        TransportRoute,
        on_delete=models.CASCADE,
        related_name='student_transport_assignments'
    )
    pickup_stop = models.ForeignKey(
        TransportStop,
        on_delete=models.CASCADE,
        related_name='pickup_student_assignments'
    )
    drop_stop = models.ForeignKey(
        TransportStop,
        on_delete=models.CASCADE,
        related_name='drop_student_assignments'
    )
    transport_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE
    )
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Medical notes, parent pickup authorization, etc.")

    class Meta:
        ordering = ['student__first_name', 'student__last_name']
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'student'],
                name='unique_academic_student_transport'
            )
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} -> {self.route.code} ({self.pickup_stop.name})"

    def clean(self):
        super().clean()
        if self.school_id:
            if self.student.school_id != self.school_id:
                raise ValidationError({'student': "Student belongs to a different school tenant."})
            if self.route.school_id != self.school_id:
                raise ValidationError({'route': "Route belongs to a different school tenant."})
            if self.pickup_stop.route_id != self.route_id:
                raise ValidationError({'pickup_stop': "Pickup stop does not belong to the assigned route."})
            if self.drop_stop.route_id != self.route_id:
                raise ValidationError({'drop_stop': "Drop stop does not belong to the assigned route."})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
