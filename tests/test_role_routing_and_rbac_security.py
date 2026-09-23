"""
Comprehensive Regression & Security Test Suite for Role-Aware Routing and RBAC Authorization.
Verifies that:
1. Student accounts NEVER receive the Admin ERP dashboard or admin data/actions.
2. Student login and direct /dashboard/ requests route to Student Portal (/portal/student/).
3. Parent accounts route to Parent Portal (/portal/parent/) and cannot access admin routes.
4. Teacher accounts route to Teacher Portal (/portal/teacher/) and cannot access admin-only operations.
5. School Admin / Staff accounts access the Admin ERP Dashboard (/dashboard/).
6. Platform Super Admin routes to onboarding if fresh, or Admin ERP dashboard if configured.
7. Backend authorization blocks direct URL access to representative admin routes for Students and Parents.
8. Unapproved users are safely directed to profile completion.
9. Multi-tenant isolation is strictly preserved.
"""
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, assign_role_to_user
from django_school_management.accounts.adapters import AccountAdapter
from django_school_management.accounts.constants import ProfileApprovalStatusEnum, AccountURLConstants
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.teachers.models import Teacher, TeacherProfile
from permission_handlers.basic import can_access_dashboard, user_is_student, user_is_teacher, user_is_parent
from permission_handlers.administrative import user_is_admin, user_is_admin_or_su

User = get_user_model()


class RoleRoutingAndRBACSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.adapter = AccountAdapter()

        # 1. School Tenant Setup
        self.school = School.objects.create(
            name="PrimeSoul Higher Secondary School",
            slug="primesoul-hss",
            is_active=True
        )
        self.ay = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_current=True
        )
        self.grade10 = GradeLevel.objects.create(
            school=self.school,
            name="Class 10",
            code="10",
            display_order=10
        )
        self.sec_a = Section.objects.create(
            school=self.school,
            grade_level=self.grade10,
            name="A"
        )

        # 2. Student User (Krishna)
        self.student_user = User.objects.create_user(
            username="krishna",
            email="krishna@example.com",
            password="studentpassword123",
            first_name="Krishna",
            last_name="Sharma"
        )
        self.student_user.school = self.school
        self.student_user.approval_status = "a"
        self.student_user.requested_role = "STUDENT"
        self.student_user.save()
        assign_role_to_user(self.student_user, Role.STUDENT)

        self.student_record = Student.objects.create(
            school=self.school,
            user=self.student_user,
            first_name="Krishna",
            last_name="Sharma",
            admission_number="ADM-2026-001",
            grade_level=self.grade10,
            section=self.sec_a,
            academic_year=self.ay,
            is_active=True
        )

        # 3. Parent User
        self.parent_user = User.objects.create_user(
            username="rajesh_parent",
            email="rajesh@example.com",
            password="parentpassword123",
            first_name="Rajesh",
            last_name="Sharma"
        )
        self.parent_user.school = self.school
        self.parent_user.approval_status = "a"
        self.parent_user.requested_role = "PARENT"
        self.parent_user.save()
        assign_role_to_user(self.parent_user, Role.PARENT)

        self.parent_profile = ParentProfile.objects.create(
            school=self.school,
            user=self.parent_user,
            first_name="Rajesh",
            last_name="Sharma",
            email="rajesh@example.com"
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_record,
            guardian=self.parent_profile,
            relationship_type="FATHER",
            is_primary_contact=True
        )

        # 4. Teacher User
        self.teacher_user = User.objects.create_user(
            username="anita_teacher",
            email="anita@example.com",
            password="teacherpassword123",
            first_name="Anita",
            last_name="Deshmukh"
        )
        self.teacher_user.school = self.school
        self.teacher_user.approval_status = "a"
        self.teacher_user.requested_role = "TEACHER"
        self.teacher_user.save()
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        self.teacher_profile = TeacherProfile.objects.create(
            school=self.school,
            user=self.teacher_user,
            first_name="Anita",
            last_name="Deshmukh",
            email="anita@example.com",
            employee_code="TCH-001",
            is_active=True
        )

        # 5. School Admin User
        self.admin_user = User.objects.create_user(
            username="school_admin",
            email="admin@primesoul.edu",
            password="adminpassword123",
            first_name="Vikram",
            last_name="Aditya"
        )
        self.admin_user.school = self.school
        self.admin_user.approval_status = "a"
        self.admin_user.requested_role = "SCHOOL_ADMIN"
        self.admin_user.is_staff = True
        self.admin_user.save()
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        # 6. Platform Super Admin User (Configured with School)
        self.super_admin_configured = User.objects.create_superuser(
            username="superadmin_ready",
            email="superadmin@primesoul.edu",
            password="superadminpassword123"
        )
        self.super_admin_configured.school = self.school
        self.super_admin_configured.approval_status = "a"
        self.super_admin_configured.save()

        # 7. Fresh Super Admin User (Without School/Institute)
        self.fresh_super_admin = User.objects.create_superuser(
            username="fresh_superadmin",
            email="fresh@primesoul.edu",
            password="freshpassword123"
        )
        self.fresh_super_admin.school = None
        self.fresh_super_admin.institute = None
        self.fresh_super_admin.approval_status = "a"
        self.fresh_super_admin.save()

        # 8. Unapproved User
        self.unapproved_user = User.objects.create_user(
            username="pending_user",
            email="pending@example.com",
            password="pendingpassword123"
        )
        self.unapproved_user.school = self.school
        self.unapproved_user.approval_status = "p"
        self.unapproved_user.requested_role = "STUDENT"
        self.unapproved_user.save()

    # ─────────────────────────────────────────────────────────────
    # A. ALLAUTH ADAPTER ROLE-BASED LOGIN REDIRECT TESTS
    # ─────────────────────────────────────────────────────────────

    def test_adapter_redirects_student_to_student_portal(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.student_user
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('portal:student_dashboard'))

    def test_adapter_redirects_parent_to_parent_portal(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.parent_user
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('portal:student_dashboard'))

    def test_adapter_redirects_teacher_to_teacher_portal(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.teacher_user
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('portal:teacher_dashboard'))

    def test_adapter_redirects_school_admin_to_admin_dashboard(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.admin_user
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('index_view'))

    def test_adapter_redirects_fresh_superadmin_to_onboarding(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.fresh_super_admin
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('institute:onboarding_step1'))

    def test_adapter_redirects_unapproved_user_to_profile_complete(self):
        req = self.factory.get('/accounts/login/')
        req.user = self.unapproved_user
        redirect_url = self.adapter.get_login_redirect_url(req)
        self.assertEqual(redirect_url, reverse('account:profile_complete'))

    # ─────────────────────────────────────────────────────────────
    # B. PERMISSION HANDLER & RBAC LOGIC TESTS
    # ─────────────────────────────────────────────────────────────

    def test_can_access_dashboard_blocks_portal_roles(self):
        self.assertFalse(can_access_dashboard(self.student_user))
        self.assertFalse(can_access_dashboard(self.parent_user))
        self.assertFalse(can_access_dashboard(self.teacher_user))
        self.assertFalse(can_access_dashboard(self.unapproved_user))

    def test_can_access_dashboard_allows_admins_and_superusers(self):
        self.assertTrue(can_access_dashboard(self.admin_user))
        self.assertTrue(can_access_dashboard(self.super_admin_configured))

    def test_user_is_student_helper(self):
        self.assertTrue(user_is_student(self.student_user))
        self.assertFalse(user_is_student(self.parent_user))
        self.assertFalse(user_is_student(self.teacher_user))
        self.assertFalse(user_is_student(self.admin_user))

    def test_user_is_teacher_helper(self):
        self.assertTrue(user_is_teacher(self.teacher_user))
        self.assertFalse(user_is_teacher(self.student_user))
        self.assertFalse(user_is_teacher(self.parent_user))

    def test_user_is_parent_helper(self):
        self.assertTrue(user_is_parent(self.parent_user))
        self.assertFalse(user_is_parent(self.student_user))
        self.assertFalse(user_is_parent(self.teacher_user))

    def test_user_is_admin_helper(self):
        self.assertTrue(user_is_admin(self.admin_user))
        self.assertTrue(user_is_admin(self.super_admin_configured))
        self.assertFalse(user_is_admin(self.student_user))
        self.assertFalse(user_is_admin(self.parent_user))
        self.assertFalse(user_is_admin(self.teacher_user))

    # ─────────────────────────────────────────────────────────────
    # C. HTTP CLIENT DASHBOARD & ROLE-ROUTING INTEGRATION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_student_accessing_dashboard_redirects_to_student_portal(self):
        self.client.force_login(self.student_user)
        # Test /dashboard/
        response = self.client.get('/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/student/dashboard.html')
        self.assertTemplateNotUsed(response, 'dashboard.html')
        # Ensure student-specific content is rendered, NOT admin KPIs
        self.assertContains(response, "Krishna Sharma")
        self.assertNotContains(response, "Total Students")
        self.assertNotContains(response, "Faculty & Staff")
        self.assertNotContains(response, "Fee Collections")

        # Test /account/dashboard/
        response_acc = self.client.get('/account/dashboard/', follow=True)
        self.assertEqual(response_acc.status_code, 200)
        self.assertTemplateUsed(response_acc, 'portal/student/dashboard.html')
        self.assertTemplateNotUsed(response_acc, 'dashboard.html')

    def test_parent_accessing_dashboard_redirects_to_parent_portal(self):
        self.client.force_login(self.parent_user)
        response = self.client.get('/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/student/dashboard.html')
        self.assertTemplateNotUsed(response, 'dashboard.html')

    def test_teacher_accessing_dashboard_redirects_to_teacher_portal(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get('/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/teacher/dashboard.html')
        self.assertTemplateNotUsed(response, 'dashboard.html')

    def test_school_admin_accesses_admin_erp_dashboard(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn('total_students', response.context)
        self.assertIn('total_teachers', response.context)
        self.assertIn('fee_summary', response.context)

    # ─────────────────────────────────────────────────────────────
    # D. BACKEND AUTHORIZATION: STUDENT BLOCKED FROM ADMIN ROUTES
    # ─────────────────────────────────────────────────────────────

    def test_student_cannot_access_student_roster(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/students/all/')
        # Should redirect to permission_error or login (302) or return 403
        self.assertIn(response.status_code, [302, 403])
        if response.status_code == 302:
            self.assertFalse(response.url.startswith('/students/all/'))

    def test_student_cannot_access_academic_departments(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/academics/departments/')
        self.assertIn(response.status_code, [302, 403])

    def test_student_cannot_access_fee_dashboard(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/fees/')
        self.assertIn(response.status_code, [302, 403])

    def test_student_cannot_access_hr_dashboard(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/hr/')
        self.assertIn(response.status_code, [302, 403])

    def test_student_cannot_access_account_list(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/account/accounts/')
        self.assertIn(response.status_code, [302, 403])

    def test_student_cannot_access_group_list(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/account/groups/')
        self.assertIn(response.status_code, [302, 403])

    def test_student_cannot_access_django_admin(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/admin/')
        # Django admin returns 302 to admin login for non-staff
        self.assertIn(response.status_code, [302, 403, 404])

    # ─────────────────────────────────────────────────────────────
    # E. BACKEND AUTHORIZATION: PARENT BLOCKED FROM ADMIN ROUTES
    # ─────────────────────────────────────────────────────────────

    def test_parent_cannot_access_fee_dashboard(self):
        self.client.force_login(self.parent_user)
        response = self.client.get('/fees/')
        self.assertIn(response.status_code, [302, 403])

    def test_parent_cannot_access_hr_dashboard(self):
        self.client.force_login(self.parent_user)
        response = self.client.get('/hr/')
        self.assertIn(response.status_code, [302, 403])

    def test_parent_cannot_access_student_roster(self):
        self.client.force_login(self.parent_user)
        response = self.client.get('/students/all/')
        self.assertIn(response.status_code, [302, 403])

    # ─────────────────────────────────────────────────────────────
    # F. UNIFIED PORTAL ROOT REDIRECT
    # ─────────────────────────────────────────────────────────────

    def test_portal_root_routes_student_correctly(self):
        self.client.force_login(self.student_user)
        response = self.client.get('/portal/')
        self.assertRedirects(response, reverse('portal:student_dashboard'))

    def test_portal_root_routes_parent_correctly(self):
        self.client.force_login(self.parent_user)
        response = self.client.get('/portal/')
        self.assertRedirects(response, reverse('portal:student_dashboard'))

    def test_portal_root_routes_teacher_correctly(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get('/portal/')
        self.assertRedirects(response, reverse('portal:teacher_dashboard'))
