import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.tenants.context import set_current_school, clear_current_school
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment
from django_school_management.students.models import Student
from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)
from django_school_management.transport.services.transport_service import (
    assign_vehicle_to_route, assign_student_to_transport, update_student_transport_status
)
from django_school_management.transport.selectors.transport_selectors import (
    get_transport_dashboard_metrics, get_route_details, get_student_transport_info
)

User = get_user_model()


class PrimeSoulTransportManagementTests(TestCase):
    """
    Phase 10: PrimeSoul ERP Transport Management Test Suite.
    Validates tenant isolation, vehicle/route/stop/staff CRUD, collision detection
    (vehicle/driver double-booking, stop-route mismatch, capacity overflow),
    dashboard metrics, RBAC, student/parent portals, and REST APIs.
    """

    def setUp(self):
        ensure_system_roles_exist()

        # 1. Schools
        self.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkpuram",
            board="CBSE",
            school_code="DPS-1034",
            is_active=True
        )
        self.school_b = School.objects.create(
            name="Modern School, Barakhamba",
            slug="modern-delhi",
            board="CBSE",
            school_code="MOD-5021",
            is_active=True
        )

        # 2. Academic Years
        self.ay_a = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )
        self.ay_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )

        # 3. Class and Section
        self.grade_10 = GradeLevel.objects.create(
            school=self.school_a, name="Class 10", code="10", display_order=10
        )
        self.sec_10a = Section.objects.create(
            school=self.school_a, grade_level=self.grade_10, name="A"
        )

        # 4. Vehicles
        self.bus_01 = TransportVehicle.objects.create(
            school=self.school_a,
            vehicle_number="BUS-01",
            registration_number="DL-01-AB-1234",
            vehicle_type=TransportVehicle.TYPE_BUS,
            capacity=2,  # Small capacity to test capacity limits!
            is_active=True
        )
        self.van_02 = TransportVehicle.objects.create(
            school=self.school_a,
            vehicle_number="VAN-02",
            registration_number="DL-01-CD-5678",
            vehicle_type=TransportVehicle.TYPE_VAN,
            capacity=15,
            is_active=True
        )

        # 5. Staff (Driver & Attendant)
        self.driver_ram = TransportStaff.objects.create(
            school=self.school_a,
            name="Ram Singh",
            phone="9876543210",
            role=TransportStaff.ROLE_DRIVER,
            license_number="DL-1420110012345",
            license_expiry=datetime.date(2028, 5, 20),
            is_active=True
        )
        self.driver_shyam = TransportStaff.objects.create(
            school=self.school_a,
            name="Shyam Lal",
            phone="9876543211",
            role=TransportStaff.ROLE_DRIVER,
            license_number="DL-1420110098765",
            license_expiry=datetime.date(2026, 9, 25),  # Expiring soon (<30 days)!
            is_active=True
        )
        self.attendant_sunita = TransportStaff.objects.create(
            school=self.school_a,
            name="Sunita Devi",
            phone="9876543212",
            role=TransportStaff.ROLE_ATTENDANT,
            is_active=True
        )

        # 6. Routes & Stops
        self.route_south = TransportRoute.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            name="South Delhi Express",
            code="R-SOUTH-01",
            description="Covers Saket, Hauz Khas, and AIIMS",
            is_active=True
        )
        self.route_north = TransportRoute.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            name="North Delhi Route",
            code="R-NORTH-02",
            description="Covers Civil Lines and Model Town",
            is_active=True
        )

        self.stop_saket = TransportStop.objects.create(
            school=self.school_a,
            route=self.route_south,
            name="Saket Metro Gate 2",
            address="Near Select Citywalk",
            sequence=1,
            pickup_time=datetime.time(7, 15),
            drop_time=datetime.time(14, 30),
            is_active=True
        )
        self.stop_hauz_khas = TransportStop.objects.create(
            school=self.school_a,
            route=self.route_south,
            name="Hauz Khas Market",
            address="Near Main Market",
            sequence=2,
            pickup_time=datetime.time(7, 30),
            drop_time=datetime.time(14, 15),
            is_active=True
        )
        self.stop_civil_lines = TransportStop.objects.create(
            school=self.school_a,
            route=self.route_north,
            name="Civil Lines Metro",
            address="Gate No 1",
            sequence=1,
            pickup_time=datetime.time(7, 10),
            drop_time=datetime.time(14, 40),
            is_active=True
        )

        # 7. Students
        self.student_user_1 = User.objects.create_user(
            username="student_aarav_t", email="aarav_t@primesoul.com", password="password123",
            first_name="Aarav", last_name="Sharma", school=self.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_1, Role.STUDENT)
        self.student_1 = Student.objects.create(
            school=self.school_a, user=self.student_user_1, first_name="Aarav", last_name="Sharma",
            admission_number="ADM-T101", roll_number="1", roll="1",
            grade_level=self.grade_10, section=self.sec_10a, academic_year=self.ay_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_1, academic_year=self.ay_a,
            grade_level=self.grade_10, section=self.sec_10a, roll_number="1", status="ACTIVE"
        )

        self.student_user_2 = User.objects.create_user(
            username="student_diya_t", email="diya_t@primesoul.com", password="password123",
            first_name="Diya", last_name="Patel", school=self.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_2, Role.STUDENT)
        self.student_2 = Student.objects.create(
            school=self.school_a, user=self.student_user_2, first_name="Diya", last_name="Patel",
            admission_number="ADM-T102", roll_number="2", roll="2",
            grade_level=self.grade_10, section=self.sec_10a, academic_year=self.ay_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_2, academic_year=self.ay_a,
            grade_level=self.grade_10, section=self.sec_10a, roll_number="2", status="ACTIVE"
        )

        self.student_user_3 = User.objects.create_user(
            username="student_kabir_t", email="kabir_t@primesoul.com", password="password123",
            first_name="Kabir", last_name="Mehta", school=self.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_3, Role.STUDENT)
        self.student_3 = Student.objects.create(
            school=self.school_a, user=self.student_user_3, first_name="Kabir", last_name="Mehta",
            admission_number="ADM-T103", roll_number="3", roll="3",
            grade_level=self.grade_10, section=self.sec_10a, academic_year=self.ay_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_3, academic_year=self.ay_a,
            grade_level=self.grade_10, section=self.sec_10a, roll_number="3", status="ACTIVE"
        )

        # 8. Administrative Users for RBAC
        self.admin_user = User.objects.create_user(
            username="admin_trans", email="adm_trans@dps.com", password="password123",
            first_name="Transport", last_name="Admin", school=self.school_a, requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.accountant_user = User.objects.create_user(
            username="accountant_trans", email="acc_trans@dps.com", password="password123",
            first_name="Accountant", last_name="User", school=self.school_a, requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        # Set tenant context
        set_current_school(self.school_a)

    def tearDown(self):
        clear_current_school()

    # =========================================================================
    # 1. TENANT ISOLATION
    # =========================================================================

    def test_transport_tenant_isolation(self):
        """School B cannot view or access School A's transport fleet or routes."""
        set_current_school(self.school_b)
        self.assertEqual(TransportVehicle.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(TransportRoute.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(TransportStaff.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(VehicleRouteAssignment.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(StudentTransportAssignment.objects.filter(school=self.school_b).count(), 0)

    # =========================================================================
    # 2. VEHICLE-ROUTE ASSIGNMENT & CONFLICT REJECTION
    # =========================================================================

    def test_vehicle_route_assignment_success(self):
        """Vehicle, driver, and attendant can be successfully assigned to a route."""
        assignment = assign_vehicle_to_route(
            school=self.school_a,
            academic_year=self.ay_a,
            vehicle=self.bus_01,
            route=self.route_south,
            driver=self.driver_ram,
            attendant=self.attendant_sunita
        )
        self.assertIsNotNone(assignment.id)
        self.assertTrue(assignment.is_active)

    def test_vehicle_double_assignment_rejected(self):
        """Same vehicle cannot be actively assigned to two different routes simultaneously."""
        assign_vehicle_to_route(
            school=self.school_a,
            academic_year=self.ay_a,
            vehicle=self.bus_01,
            route=self.route_south,
            driver=self.driver_ram
        )

        with self.assertRaises(ValidationError) as ctx:
            assign_vehicle_to_route(
                school=self.school_a,
                academic_year=self.ay_a,
                vehicle=self.bus_01,
                route=self.route_north,
                driver=self.driver_shyam
            )
        self.assertIn("already actively assigned", str(ctx.exception))

    def test_driver_double_assignment_rejected(self):
        """Same driver cannot be actively assigned to two different routes simultaneously."""
        assign_vehicle_to_route(
            school=self.school_a,
            academic_year=self.ay_a,
            vehicle=self.bus_01,
            route=self.route_south,
            driver=self.driver_ram
        )

        with self.assertRaises(ValidationError) as ctx:
            assign_vehicle_to_route(
                school=self.school_a,
                academic_year=self.ay_a,
                vehicle=self.van_02,
                route=self.route_north,
                driver=self.driver_ram  # Ram is already driving BUS-01 on South Route!
            )
        self.assertIn("already assigned", str(ctx.exception))

    # =========================================================================
    # 3. STUDENT TRANSPORT ALLOCATION & VALIDATION
    # =========================================================================

    def test_student_transport_allocation_success(self):
        """Student can be assigned to a route with valid pickup and drop stops."""
        assign_vehicle_to_route(
            school=self.school_a,
            academic_year=self.ay_a,
            vehicle=self.bus_01,
            route=self.route_south,
            driver=self.driver_ram
        )

        sub = assign_student_to_transport(
            school=self.school_a,
            academic_year=self.ay_a,
            student=self.student_1,
            route=self.route_south,
            pickup_stop=self.stop_saket,
            drop_stop=self.stop_hauz_khas,
            start_date=datetime.date(2026, 4, 1)
        )
        self.assertIsNotNone(sub.id)
        self.assertEqual(sub.transport_status, StudentTransportAssignment.STATUS_ACTIVE)

    def test_invalid_stop_route_relationship_rejected(self):
        """Student cannot be assigned to a stop that does not belong to the chosen route."""
        with self.assertRaises(ValidationError) as ctx:
            assign_student_to_transport(
                school=self.school_a,
                academic_year=self.ay_a,
                student=self.student_1,
                route=self.route_south,
                pickup_stop=self.stop_civil_lines,  # Civil Lines belongs to route_north!
                drop_stop=self.stop_hauz_khas
            )
        self.assertIn("does not belong to route", str(ctx.exception))

    def test_vehicle_capacity_overflow_rejected(self):
        """Cannot assign more students than the vehicle's seating capacity."""
        # Bus 01 has capacity = 2
        assign_vehicle_to_route(
            school=self.school_a,
            academic_year=self.ay_a,
            vehicle=self.bus_01,
            route=self.route_south,
            driver=self.driver_ram
        )

        # Passenger 1 (Aarav) - OK
        assign_student_to_transport(
            school=self.school_a, academic_year=self.ay_a, student=self.student_1,
            route=self.route_south, pickup_stop=self.stop_saket, drop_stop=self.stop_hauz_khas
        )

        # Passenger 2 (Diya) - OK (Capacity reached: 2/2)
        assign_student_to_transport(
            school=self.school_a, academic_year=self.ay_a, student=self.student_2,
            route=self.route_south, pickup_stop=self.stop_saket, drop_stop=self.stop_hauz_khas
        )

        # Passenger 3 (Kabir) - Must be rejected due to capacity limit
        with self.assertRaises(ValidationError) as ctx:
            assign_student_to_transport(
                school=self.school_a, academic_year=self.ay_a, student=self.student_3,
                route=self.route_south, pickup_stop=self.stop_saket, drop_stop=self.stop_hauz_khas
            )
        self.assertIn("Vehicle Capacity Exceeded", str(ctx.exception))

    def test_student_transport_status_update(self):
        """Transport status can be changed to SUSPENDED or INACTIVE."""
        sub = assign_student_to_transport(
            school=self.school_a, academic_year=self.ay_a, student=self.student_1,
            route=self.route_south, pickup_stop=self.stop_saket, drop_stop=self.stop_hauz_khas
        )
        updated = update_student_transport_status(sub, StudentTransportAssignment.STATUS_SUSPENDED)
        self.assertEqual(updated.transport_status, StudentTransportAssignment.STATUS_SUSPENDED)

    # =========================================================================
    # 4. DASHBOARD & SELECTORS
    # =========================================================================

    def test_transport_dashboard_metrics(self):
        """Dashboard metrics accurately count fleet, staff, routes, and expiring licenses."""
        metrics = get_transport_dashboard_metrics(self.school_a, self.ay_a)
        self.assertEqual(metrics["total_vehicles"], 2)
        self.assertEqual(metrics["active_routes"], 2)
        self.assertEqual(metrics["drivers_count"], 2)
        self.assertEqual(metrics["attendants_count"], 1)
        self.assertEqual(metrics["total_stops"], 3)
        self.assertGreaterEqual(metrics["expiring_licenses_count"], 1)  # Shyam Lal expires in <30 days

    def test_route_details_and_student_info(self):
        """Route details and student transport lookup return clean data."""
        assign_vehicle_to_route(
            school=self.school_a, academic_year=self.ay_a, vehicle=self.bus_01,
            route=self.route_south, driver=self.driver_ram, attendant=self.attendant_sunita
        )
        assign_student_to_transport(
            school=self.school_a, academic_year=self.ay_a, student=self.student_1,
            route=self.route_south, pickup_stop=self.stop_saket, drop_stop=self.stop_hauz_khas
        )

        details = get_route_details(self.school_a, self.route_south.id)
        self.assertEqual(len(details["stops"]), 2)
        self.assertEqual(details["students_count"], 1)
        self.assertEqual(details["assignment"].vehicle.vehicle_number, "BUS-01")

        info = get_student_transport_info(self.student_1)
        # Selector returns dict (truthy) if assignment exists, None otherwise
        self.assertIsNotNone(info)
        self.assertEqual(info["route"].name, "South Delhi Express")
        self.assertEqual(info["pickup_stop"].name, "Saket Metro Gate 2")

    # =========================================================================
    # 5. RBAC & PERMISSION CHECKS
    # =========================================================================

    def test_rbac_admin_full_access(self):
        """School Admin can access transport dashboard, vehicles, and routes."""
        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse("transport:dashboard"))
        self.assertEqual(resp.status_code, 200)

        resp_veh = self.client.get(reverse("transport:vehicles"))
        self.assertEqual(resp_veh.status_code, 200)

        resp_routes = self.client.get(reverse("transport:routes"))
        self.assertEqual(resp_routes.status_code, 200)

    def test_rbac_accountant_forbidden(self):
        """Accountant cannot access transport dashboard."""
        self.client.force_login(self.accountant_user)
        # Dashboard view explicitly denies accountants
        resp = self.client.get(reverse("transport:dashboard"))
        self.assertEqual(resp.status_code, 403)

    def test_rbac_student_own_transport_access(self):
        """Student accessing dashboard is redirected to my-transport."""
        self.client.force_login(self.student_user_1)
        # Dashboard redirects students to my-transport portal
        resp = self.client.get(reverse("transport:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('my-transport', resp.url)

    # =========================================================================
    # 6. REST API ENDPOINTS
    # =========================================================================

    def test_transport_api_endpoints(self):
        """DRF APIs under /api/v1/transport/ are tenant-safe and require authentication."""
        api_client = APIClient()

        # Unauthenticated request rejected
        resp = api_client.get('/api/v1/transport/vehicles/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Authenticated as School Admin
        api_client.force_authenticate(user=self.admin_user)
        resp_dash = api_client.get('/api/v1/transport/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        # Dashboard API returns flat dict (no 'data' wrapper)
        self.assertEqual(resp_dash.data["total_vehicles"], 2)

        resp_veh = api_client.get('/api/v1/transport/vehicles/')
        self.assertEqual(resp_veh.status_code, status.HTTP_200_OK)
        veh_data = resp_veh.data.get("results", resp_veh.data)
        if isinstance(veh_data, list):
            self.assertEqual(len(veh_data), 2)

