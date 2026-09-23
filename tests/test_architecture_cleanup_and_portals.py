"""
PrimeSoul School ERP - Architecture Cleanup & Canonical 3-Portal Verification Tests

Validates the simplified product architecture:
1. SCHOOL ADMIN PORTAL (/dashboard/)
2. STUDENT PORTAL (/portal/student/ - includes Family/Guardian unified experience with child switcher)
3. TEACHER PORTAL (/portal/teacher/)

Enforces:
- Elimination of separate Parent, Accountant, Principal, Staff portals.
- Canonical role resolution: SCHOOL_ADMIN, STUDENT, TEACHER (with PARENT mapping to STUDENT_PORTAL).
- Strict multi-tenant isolation.
- IDOR prevention and child switching.
"""
import datetime
from decimal import Decimal
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

from django_school_management.accounts.roles import (
    Role,
    PortalType,
    get_user_portal,
    normalize_role_name,
    assign_role_to_user,
    user_has_role,
)
from django_school_management.accounts.adapters import AccountAdapter
from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.teachers.models import TeacherProfile
from django_school_management.hr.models import Employee, Department

User = get_user_model()


class ArchitectureCleanupAndPortalTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = AccountAdapter()
        self.client = Client()

        # School A (Primary Tenant)
        self.school_a = School.objects.create(
            name="PrimeSoul Higher Secondary School",
            slug="pshss",
            subdomain="pshss",
            is_active=True
        )

        # School B (Isolated Tenant)
        self.school_b = School.objects.create(
            name="Apex International Academy",
            slug="apex",
            subdomain="apex",
            is_active=True
        )

        # Academic Setup for School A
        self.ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            status='ACTIVE',
            is_current=True
        )
        self.grade_10 = GradeLevel.objects.create(school=self.school_a, name="Class 10", code="10")
        self.grade_8 = GradeLevel.objects.create(school=self.school_a, name="Class 8", code="8")
        self.sec_10a = Section.objects.create(school=self.school_a, grade_level=self.grade_10, name="A")
        self.sec_8a = Section.objects.create(school=self.school_a, grade_level=self.grade_8, name="A")

        # 1. School Admin User
        self.admin_user = User.objects.create_user(
            username="school_admin",
            email="admin@primesoul.edu",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="User"
        )
        self.admin_user.school = self.school_a
        self.admin_user.approval_status = "a"
        self.admin_user.requested_role = Role.SCHOOL_ADMIN
        self.admin_user.is_staff = True
        self.admin_user.save()
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        # 2. Teacher User
        self.teacher_user = User.objects.create_user(
            username="teacher_sharma",
            email="teacher@primesoul.edu",
            password="TeacherPassword123!",
            first_name="Ramesh",
            last_name="Sharma"
        )
        self.teacher_user.school = self.school_a
        self.teacher_user.approval_status = "a"
        self.teacher_user.requested_role = Role.TEACHER
        self.teacher_user.save()
        assign_role_to_user(self.teacher_user, Role.TEACHER)
        self.teacher_profile = TeacherProfile.objects.create(
            school=self.school_a,
            user=self.teacher_user,
            first_name="Ramesh",
            last_name="Sharma",
            email="teacher@primesoul.edu",
            employee_code="TCH-101",
            is_active=True
        )

        # 3. Student User 1 (Aarav)
        self.student_user_1 = User.objects.create_user(
            username="student_aarav",
            email="aarav@primesoul.edu",
            password="StudentPassword123!",
            first_name="Aarav",
            last_name="Verma"
        )
        self.student_user_1.school = self.school_a
        self.student_user_1.approval_status = "a"
        self.student_user_1.requested_role = Role.STUDENT
        self.student_user_1.save()
        assign_role_to_user(self.student_user_1, Role.STUDENT)
        self.student_1 = Student.objects.create(
            school=self.school_a,
            user=self.student_user_1,
            admission_number="ADM-2026-001",
            first_name="Aarav",
            last_name="Verma",
            gender="M"
        )
        StudentEnrollment.objects.create(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay,
            grade_level=self.grade_10,
            section=self.sec_10a,
            roll_number="101",
            status="ACTIVE"
        )

        # 4. Student User 2 (Ananya)
        self.student_user_2 = User.objects.create_user(
            username="student_ananya",
            email="ananya@primesoul.edu",
            password="StudentPassword123!",
            first_name="Ananya",
            last_name="Verma"
        )
        self.student_user_2.school = self.school_a
        self.student_user_2.approval_status = "a"
        self.student_user_2.requested_role = Role.STUDENT
        self.student_user_2.save()
        assign_role_to_user(self.student_user_2, Role.STUDENT)
        self.student_2 = Student.objects.create(
            school=self.school_a,
            user=self.student_user_2,
            admission_number="ADM-2026-002",
            first_name="Ananya",
            last_name="Verma",
            gender="F"
        )
        StudentEnrollment.objects.create(
            school=self.school_a,
            student=self.student_2,
            academic_year=self.ay,
            grade_level=self.grade_8,
            section=self.sec_8a,
            roll_number="801",
            status="ACTIVE"
        )

        # 5. Guardian User (Parent of both Aarav and Ananya)
        self.guardian_user = User.objects.create_user(
            username="guardian_verma",
            email="guardian@primesoul.edu",
            password="GuardianPassword123!",
            first_name="Rajesh",
            last_name="Verma"
        )
        self.guardian_user.school = self.school_a
        self.guardian_user.approval_status = "a"
        self.guardian_user.requested_role = Role.PARENT
        self.guardian_user.save()
        assign_role_to_user(self.guardian_user, Role.PARENT)

        self.guardian_profile = ParentProfile.objects.create(
            school=self.school_a,
            user=self.guardian_user,
            first_name="Rajesh",
            last_name="Verma",
            email="guardian@primesoul.edu"
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_1,
            guardian=self.guardian_profile,
            relationship_type="Father",
            is_primary_contact=True
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_2,
            guardian=self.guardian_profile,
            relationship_type="Father",
            is_primary_contact=False
        )

    # ─────────────────────────────────────────────────────────────
    # 1. CANONICAL PORTAL RESOLUTION TESTS
    # ─────────────────────────────────────────────────────────────

    def test_portal_resolver_resolves_three_canonical_portals(self):
        """Validates that get_user_portal maps to only the 3 canonical portal types."""
        self.assertEqual(get_user_portal(self.admin_user), PortalType.ADMIN_PORTAL)
        self.assertEqual(get_user_portal(self.teacher_user), PortalType.TEACHER_PORTAL)
        self.assertEqual(get_user_portal(self.student_user_1), PortalType.STUDENT_PORTAL)
        self.assertEqual(get_user_portal(self.guardian_user), PortalType.STUDENT_PORTAL)

    def test_legacy_roles_normalize_to_three_product_roles(self):
        """Legacy roles must normalize to SCHOOL_ADMIN, TEACHER, STUDENT, or PARENT."""
        self.assertEqual(normalize_role_name('PRINCIPAL'), Role.SCHOOL_ADMIN)
        self.assertEqual(normalize_role_name('ACCOUNTANT'), Role.SCHOOL_ADMIN)
        self.assertEqual(normalize_role_name('GUARDIAN'), Role.STUDENT)
        self.assertEqual(normalize_role_name('PARENT'), Role.STUDENT)

    def test_strictly_three_product_roles_and_portals(self):
        """Validates that exactly 3 product roles and choices exist across the system."""
        self.assertEqual(set(Role.ALL_ROLES), {'SCHOOL_ADMIN', 'STUDENT', 'TEACHER'})
        self.assertEqual(len(Role.CHOICES), 3)
        self.assertEqual(len(User.REQUESTED_ACCOUNT_TYPE_CHOICES), 3)

    def test_allauth_adapter_redirects_to_canonical_portals(self):
        """Login redirect flows directly to canonical portal routes."""
        req = self.factory.get('/accounts/login/')

        req.user = self.admin_user
        self.assertEqual(self.adapter.get_login_redirect_url(req), reverse('index_view'))

        req.user = self.teacher_user
        self.assertEqual(self.adapter.get_login_redirect_url(req), reverse('portal:teacher_dashboard'))

        req.user = self.student_user_1
        self.assertEqual(self.adapter.get_login_redirect_url(req), reverse('portal:student_dashboard'))

        req.user = self.guardian_user
        self.assertEqual(self.adapter.get_login_redirect_url(req), reverse('portal:student_dashboard'))

    # ─────────────────────────────────────────────────────────────
    # 2. STUDENT & FAMILY GUARDIAN PORTAL EXPERIENCE
    # ─────────────────────────────────────────────────────────────

    def test_student_portal_loads_for_student(self):
        """Student user lands in Student Portal with personal academic data."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/student/dashboard.html')
        self.assertContains(response, "Aarav Verma")
        self.assertNotContains(response, "Total Students")

    def test_student_portal_loads_for_guardian_with_child_switcher(self):
        """Family Guardian lands in Student Portal with linked children and child switcher."""
        self.client.force_login(self.guardian_user)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/student/dashboard.html')
        self.assertContains(response, "Aarav Verma")
        self.assertEqual(response.context['student'].id, self.student_1.id)
        self.assertEqual(len(response.context['children']), 2)

    def test_guardian_child_switching(self):
        """Guardian can switch between children seamlessly within the Student Portal."""
        self.client.force_login(self.guardian_user)
        switch_url = reverse('portal:student_child_switch', kwargs={'student_id': self.student_2.id})
        response = self.client.get(switch_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student'].id, self.student_2.id)
        self.assertContains(response, "Ananya Verma")

    def test_guardian_child_switching_idor_rejected(self):
        """Guardian cannot switch to an unauthorized student from another family or school."""
        other_user = User.objects.create_user(
            username="other_kid", email="other@schoolb.edu", password="Password123!",
            school=self.school_b, requested_role=Role.STUDENT
        )
        other_student = Student.objects.create(
            school=self.school_b, user=other_user, admission_number="ADM-B-001",
            first_name="Foreign", last_name="Student"
        )
        self.client.force_login(self.guardian_user)
        switch_url = reverse('portal:student_child_switch', kwargs={'student_id': other_student.id})
        response = self.client.get(switch_url, follow=True)
        self.assertEqual(response.status_code, 200)
        # Stays on default authorized child
        self.assertEqual(response.context['student'].id, self.student_1.id)
        self.assertNotContains(response, "Foreign Student")

    # ─────────────────────────────────────────────────────────────
    # 3. TEACHER PORTAL EXPERIENCE
    # ─────────────────────────────────────────────────────────────

    def test_teacher_portal_loads_for_teacher(self):
        """Teacher user lands in Teacher Portal with teaching tools."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/teacher/dashboard.html')
        self.assertContains(response, "Ramesh Sharma")

    # ─────────────────────────────────────────────────────────────
    # 4. RBAC & ROUTE AUTHORIZATION ENFORCEMENT
    # ─────────────────────────────────────────────────────────────

    def test_student_and_guardian_blocked_from_admin_dashboard(self):
        """Students and Guardians navigating to /dashboard/ are redirected to Student Portal."""
        self.client.force_login(self.student_user_1)
        response = self.client.get('/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/student/dashboard.html')
        self.assertTemplateNotUsed(response, 'dashboard.html')

        self.client.force_login(self.guardian_user)
        resp_g = self.client.get('/dashboard/', follow=True)
        self.assertEqual(resp_g.status_code, 200)
        self.assertTemplateUsed(resp_g, 'portal/student/dashboard.html')
        self.assertTemplateNotUsed(resp_g, 'dashboard.html')

    def test_teacher_blocked_from_admin_dashboard(self):
        """Teachers navigating to /dashboard/ are redirected to Teacher Portal."""
        self.client.force_login(self.teacher_user)
        response = self.client.get('/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portal/teacher/dashboard.html')
        self.assertTemplateNotUsed(response, 'dashboard.html')

    def test_student_cannot_access_teacher_portal(self):
        """Students are rejected from Teacher Portal."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:teacher_dashboard'))
        self.assertIn(response.status_code, [302, 403])

    def test_teacher_cannot_access_admin_settings(self):
        """Teachers cannot access School Admin Settings."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('account:all_accounts'))
        self.assertIn(response.status_code, [302, 403])

    def test_school_admin_can_access_admin_dashboard(self):
        """School Admin accesses the unified full-control Admin ERP Command Center."""
        self.client.force_login(self.admin_user)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn('total_students', response.context)
        self.assertIn('total_teachers', response.context)
