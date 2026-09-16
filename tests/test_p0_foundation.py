import datetime
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.http import HttpResponse
from django.urls import reverse

from django_school_management.tenants.models import School, Domain, Subscription
from django_school_management.tenants.middleware import TenantMiddleware
from django_school_management.tenants.context import get_current_school, set_current_school, clear_current_school
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user, user_has_role
from django_school_management.accounts.permissions import (
    require_school_access, user_has_permission, role_required,
    school_admin_required, teacher_required
)
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, AcademicStream, Department
)
from django_school_management.students.models import (
    Student, AdmissionStudent, ParentProfile, StudentGuardianRelationship
)
from django_school_management.teachers.models import Designation, Teacher, TeacherProfile

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['*'],
    STRIPE_WEBHOOK_SECRET='whsec_test_secret_for_primesoul_erp_123'
)
class PrimeSoulP0FoundationTests(TestCase):
    def setUp(self):
        clear_current_school()
        ensure_system_roles_exist()
        self.factory = RequestFactory()

        # Create Primary School Tenant
        self.school_a = School.objects.create(
            name="Delhi Public School R.K. Puram",
            slug="dps-rkp",
            subdomain="dpsrkp",
            custom_domain="dpsrkp.edu.in",
            board="CBSE",
            affiliation_number="CBSE-DEL-10293",
            school_code="DEL102",
            udise_code="07010203040",
            recognition_number="REC-2024-DEL-01",
            city="New Delhi",
            state="Delhi",
            pincode="110022",
            country="India",
            timezone="Asia/Kolkata",
            currency="INR",
            is_active=True,
            onboarding_completed=True
        )

        # Create Secondary School Tenant for cross-tenant isolation testing
        self.school_b = School.objects.create(
            name="The Mother's International School",
            slug="mis-delhi",
            subdomain="misdelhi",
            board="CBSE",
            city="New Delhi",
            state="Delhi",
            country="India",
            is_active=True
        )

        # Create Users
        self.platform_admin = User.objects.create_superuser(
            username="platform_admin",
            email="superadmin@primesoul.in",
            password="SecurePassword123!"
        )
        self.platform_admin.requested_role = Role.PLATFORM_SUPER_ADMIN
        self.platform_admin.save()

        self.school_admin_a = User.objects.create_user(
            username="dps_admin",
            email="admin@dpsrkp.edu.in",
            password="SecurePassword123!",
            school=self.school_a
        )
        assign_role_to_user(self.school_admin_a, Role.SCHOOL_ADMIN)

        self.teacher_user_a = User.objects.create_user(
            username="dps_teacher",
            email="teacher@dpsrkp.edu.in",
            password="SecurePassword123!",
            school=self.school_a
        )
        assign_role_to_user(self.teacher_user_a, Role.TEACHER)

        self.school_admin_b = User.objects.create_user(
            username="mis_admin",
            email="admin@misdelhi.edu.in",
            password="SecurePassword123!",
            school=self.school_b
        )
        assign_role_to_user(self.school_admin_b, Role.SCHOOL_ADMIN)

    def tearDown(self):
        clear_current_school()

    # 1. School creation
    def test_01_school_creation(self):
        school = School.objects.get(slug="dps-rkp")
        self.assertEqual(school.name, "Delhi Public School R.K. Puram")
        self.assertEqual(school.board, "CBSE")
        self.assertEqual(school.currency, "INR")
        self.assertEqual(school.timezone, "Asia/Kolkata")
        self.assertTrue(school.is_active)
        self.assertEqual(school.udise_code, "07010203040")

    # 2. User-school relationship
    def test_02_user_school_relationship(self):
        self.assertEqual(self.school_admin_a.school, self.school_a)
        self.assertEqual(self.teacher_user_a.school, self.school_a)
        self.assertIn(self.school_admin_a, self.school_a.users.all())

    # 3. Platform Super Admin without school
    def test_03_platform_super_admin_without_school(self):
        self.assertIsNone(self.platform_admin.school)
        self.assertTrue(self.platform_admin.is_superuser)
        self.assertTrue(require_school_access(self.platform_admin, self.school_a))
        self.assertTrue(require_school_access(self.platform_admin, self.school_b))

    # 4. School user requires school
    def test_04_school_user_requires_school(self):
        self.assertTrue(require_school_access(self.school_admin_a, self.school_a))
        self.assertFalse(require_school_access(self.school_admin_a, self.school_b))
        self.assertFalse(require_school_access(None, self.school_a))

    # 5. Tenant middleware resolution
    def test_05_tenant_middleware_resolution(self):
        middleware = TenantMiddleware(lambda req: HttpResponse("OK"))
        
        # Test resolution from authenticated user
        request = self.factory.get('/')
        request.user = self.school_admin_a
        middleware.process_request(request)
        self.assertEqual(request.tenant, self.school_a)
        self.assertEqual(get_current_school(), self.school_a)
        
        # Test clean thread-local teardown
        middleware.process_response(request, HttpResponse("OK"))
        self.assertIsNone(get_current_school())

        # Test resolution from subdomain header
        request2 = self.factory.get('/', HTTP_HOST='dpsrkp.primesoul.in')
        request2.user = AnonymousUser()
        middleware.process_request(request2)
        self.assertEqual(request2.tenant, self.school_a)

    # 6. Cross-tenant access rejection
    def test_06_cross_tenant_access_rejection(self):
        middleware = TenantMiddleware(lambda req: HttpResponse("OK"))
        
        # User from School A trying to access School B via host header
        request = self.factory.get('/', HTTP_HOST='misdelhi.primesoul.in')
        request.user = self.school_admin_a
        response = middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

    # 7. Tenant-aware uniqueness
    def test_07_tenant_aware_uniqueness(self):
        # Department with same name in two different schools must succeed
        dept_a = Department.objects.create(school=self.school_a, name="Mathematics", code=101)
        dept_b = Department.objects.create(school=self.school_b, name="Mathematics", code=101)
        self.assertNotEqual(dept_a.pk, dept_b.pk)

        # Department with same name in SAME school must fail unique constraint
        with self.assertRaises(IntegrityError):
            Department.objects.create(school=self.school_a, name="Mathematics", code=102)

    # 8. Academic year
    def test_08_academic_year(self):
        ay26 = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.assertTrue(ay26.is_current)

        # Creating next year with is_current=True must reset previous year for that school
        ay27 = AcademicYear.objects.create(
            school=self.school_a,
            name="2027-2028",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
            is_current=True
        )
        ay26.refresh_from_db()
        self.assertFalse(ay26.is_current)
        self.assertTrue(ay27.is_current)

    # 9. Grade level
    def test_09_grade_level(self):
        class10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="10",
            display_order=10
        )
        self.assertEqual(str(class10), "Class 10")
        
        # Duplicate grade code in same school should raise IntegrityError
        with self.assertRaises(IntegrityError):
            GradeLevel.objects.create(
                school=self.school_a,
                name="Class 10 Secondary",
                code="10"
            )

    # 10. Section
    def test_10_section(self):
        class10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="10",
            display_order=10
        )
        sec_a = Section.objects.create(
            school=self.school_a,
            grade_level=class10,
            name="A",
            max_capacity=45
        )
        self.assertEqual(str(sec_a), "Class 10 - Section A")
        self.assertEqual(sec_a.max_capacity, 45)

    # 11. Student roll uniqueness
    def test_11_student_roll_uniqueness(self):
        ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        grade10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="10",
            display_order=10
        )
        sec_a = Section.objects.create(school=self.school_a, grade_level=grade10, name="A")
        sec_b = Section.objects.create(school=self.school_a, grade_level=grade10, name="B")

        # Student 1 in Section A, Roll 1
        stu1 = Student.objects.create(
            school=self.school_a,
            first_name="Aarav",
            last_name="Sharma",
            academic_year=ay,
            grade_level=grade10,
            section=sec_a,
            roll_number="1",
            admission_number="ADM-2026-001",
            aadhaar_number="123456789012"
        )
        self.assertIsNotNone(stu1.pk)

        # Student 2 in Section B with Roll 1 is ALLOWED (different section)
        stu2 = Student.objects.create(
            school=self.school_a,
            first_name="Vivaan",
            last_name="Gupta",
            academic_year=ay,
            grade_level=grade10,
            section=sec_b,
            roll_number="1",
            admission_number="ADM-2026-002"
        )
        self.assertIsNotNone(stu2.pk)

        # Student 3 in Section A with Roll 1 MUST FAIL (duplicate roll in same section)
        with self.assertRaises(IntegrityError):
            Student.objects.create(
                school=self.school_a,
                first_name="Aditya",
                last_name="Verma",
                academic_year=ay,
                grade_level=grade10,
                section=sec_a,
                roll_number="1",
                admission_number="ADM-2026-003"
            )

    # 12. Parent/student relationship
    def test_12_parent_student_relationship(self):
        stu = Student.objects.create(
            school=self.school_a,
            first_name="Ananya",
            last_name="Sharma",
            admission_number="ADM-2026-001"
        )
        father = ParentProfile.objects.create(
            school=self.school_a,
            first_name="Rajesh",
            last_name="Sharma",
            relationship_type="Father",
            mobile_number="+919876543210",
            email="rajesh.sharma@example.com"
        )
        rel = StudentGuardianRelationship.objects.create(
            student=stu,
            guardian=father,
            relationship_type="Father",
            is_primary_contact=True
        )
        self.assertEqual(stu.guardian_relationships.first().guardian, father)
        self.assertEqual(father.student_relationships.first().student, stu)

    # 13. Teacher/user relationship
    def test_13_teacher_user_relationship(self):
        desig = Designation.objects.create(school=self.school_a, title="Senior PGT Mathematics")
        profile = TeacherProfile.objects.create(
            user=self.teacher_user_a,
            school=self.school_a,
            employee_code="DPS-FAC-101",
            first_name="Sunita",
            last_name="Rao",
            designation=desig,
            joining_date=datetime.date(2020, 7, 15),
            mobile_number="+919123456789"
        )
        self.assertEqual(self.teacher_user_a.teacher_profile, profile)
        self.assertEqual(profile.employee_code, "DPS-FAC-101")
        self.assertEqual(profile.joining_date, datetime.date(2020, 7, 15))

    # 14. Permission enforcement
    def test_14_permission_enforcement(self):
        @school_admin_required
        def admin_view(request):
            return HttpResponse("Admin Access Granted")

        @teacher_required
        def teacher_view(request):
            return HttpResponse("Teacher Access Granted")

        # Admin User calling admin view -> Allowed
        req_admin = self.factory.get('/admin-dashboard/')
        req_admin.user = self.school_admin_a
        req_admin.tenant = self.school_a
        resp1 = admin_view(req_admin)
        self.assertEqual(resp1.status_code, 200)

        # Teacher User calling admin view -> Blocked
        req_teacher = self.factory.get('/admin-dashboard/')
        req_teacher.user = self.teacher_user_a
        req_teacher.tenant = self.school_a
        with self.assertRaises(Exception):  # PermissionDenied
            admin_view(req_teacher)

    # 15. Payment webhook cannot be spoofed & success URL does not mutate payment state
    def test_15_payment_security(self):
        applicant = AdmissionStudent.objects.create(
            name="Rahul Mehra",
            paid=False
        )
        self.assertFalse(applicant.paid)

        # 15a: Visiting success URL directly MUST NOT mark applicant as paid
        response = self.client.get(reverse('pages:stripe_payment_success', kwargs={'pk': applicant.pk}))
        self.assertEqual(response.status_code, 200)
        applicant.refresh_from_db()
        self.assertFalse(applicant.paid, "Visiting success URL must never mark payment as paid!")

        # 15b: Webhook without valid signature must be rejected
        webhook_response = self.client.post(
            reverse('pages:stripe_webhook'),
            data=b'{"id": "evt_test"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_fake_signature"
        )
        self.assertIn(webhook_response.status_code, [400, 500])
        applicant.refresh_from_db()
        self.assertFalse(applicant.paid)

    # 16. Protected student endpoint
    def test_16_protected_student_endpoint(self):
        # Anonymous lookup to find student must redirect to login or deny access
        response = self.client.get(reverse('result:find_student', kwargs={'student_id': '101'}))
        self.assertIn(response.status_code, [302, 401, 403])

    # 17. GET deletion blocked
    def test_17_get_deletion_blocked(self):
        desig = Designation.objects.create(school=self.school_a, title="Teacher")
        legacy_teacher = Teacher.objects.create(
            school=self.school_a,
            name="Test Teacher",
            designation=desig,
            employee_id="T001"
        )
        self.client.force_login(self.school_admin_a)
        
        # GET request to delete teacher must return 405 Method Not Allowed
        response = self.client.get(reverse('teachers:delete_teacher', kwargs={'pk': legacy_teacher.pk}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Teacher.objects.filter(pk=legacy_teacher.pk).exists())
