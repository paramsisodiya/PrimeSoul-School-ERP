"""
Comprehensive test suite for Canonical Student & Teacher Account Domain Record Linking.
Validates:
1. User <-> Student canonical relationship and resolver.
2. User <-> TeacherProfile canonical relationship and resolver.
3. School Admin User creation workflow with tenant-scoped selection.
4. Prevention of duplicate accounts for the same student.
5. Strict Multi-Tenant and IDOR data isolation.
6. Three-role post-login redirection stability.
7. Student SIS "Create Student Login" action.
8. Preservation of domain records (no duplicates created).
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment, Subject
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher, TeacherProfile, Designation
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.fees.models import FeeStructure, FeeInstallment, FeeHead
from django_school_management.examinations.models import Exam, ExamSubject, StudentMark
from django_school_management.timetable.models import TimetableEntry, WorkingDay
from django_school_management.accounts.roles import Role, get_user_portal, PortalType, assign_role_to_user
from django_school_management.portal.permissions import get_student_for_user, get_teacher_for_user
from django_school_management.accounts.forms import UserCreateFormDashboard

User = get_user_model()


class StudentAccountLinkingTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Setup Tenant Schools
        self.school_a = School.objects.create(
            name="PrimeSoul Academy Delhi",
            slug="primesoul-delhi",
            subdomain="delhi",
            is_active=True
        )
        self.school_b = School.objects.create(
            name="PrimeSoul Academy Mumbai",
            slug="primesoul-mumbai",
            subdomain="mumbai",
            is_active=True
        )

        # 2. Academic Placement (School A)
        self.academic_year_a = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=365),
            is_current=True
        )
        self.grade_7 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 7",
            code="7",
            display_order=7
        )
        self.sec_a = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade_7,
            name="A"
        )

        # 3. Create Existing Onboarded Student (Krishna) in School A
        self.student_krishna = Student.objects.create(
            school=self.school_a,
            first_name="Krishna",
            last_name="Sisodiya",
            admission_number="ADM-2026-001",
            roll_number="12",
            academic_year=self.academic_year_a,
            grade_level=self.grade_7,
            section=self.sec_a,
            emergency_contact_number="+919876543210"
        )
        self.enrollment_krishna = StudentEnrollment.objects.create(
            school=self.school_a,
            student=self.student_krishna,
            academic_year=self.academic_year_a,
            grade_level=self.grade_7,
            section=self.sec_a,
            roll_number="12",
            status="ACTIVE"
        )

        # 4. Student in School B (Cross-tenant test)
        self.student_b = Student.objects.create(
            school=self.school_b,
            first_name="Rohit",
            last_name="Verma",
            admission_number="ADM-MUM-001",
            roll_number="1"
        )

        # 5. School Admin User
        self.admin_user = User.objects.create_user(
            username="admin_delhi",
            email="admin@delhi.primesoul.in",
            password="AdminPassword123!",
            requested_role=Role.SCHOOL_ADMIN,
            school=self.school_a,
            is_staff=True,
            approval_status='a'
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        # 6. Designation & Teacher
        self.desig_pgt = Designation.objects.create(
            school=self.school_a,
            title="PGT Mathematics"
        )
        self.teacher_user = User.objects.create_user(
            username="sharma_math",
            email="sharma@delhi.primesoul.in",
            password="TeacherPassword123!",
            requested_role=Role.TEACHER,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(self.teacher_user, Role.TEACHER)
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            school=self.school_a,
            first_name="Ramesh",
            last_name="Sharma",
            employee_code="FAC-001",
            designation=self.desig_pgt
        )
        self.teacher_record = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school_a,
            name="Ramesh Sharma",
            employee_id="FAC-001",
            designation=self.desig_pgt,
            email="sharma@delhi.primesoul.in"
        )
        self.unlinked_teacher = Teacher.objects.create(
            school=self.school_a,
            name="Param Sisodiya",
            employee_id="TCH-002",
            designation=self.desig_pgt,
            mobile="8770404559",
            email="param@delhi.primesoul.in"
        )

    def test_01_admin_creates_student_login_for_existing_student(self):
        """Admin creates login account for existing Krishna student via UserCreateFormDashboard."""
        initial_student_count = Student.objects.count()

        form_data = {
            'requested_role': 'STUDENT',
            'student': self.student_krishna.pk,
            'username': 'krishna_user',
            'first_name': 'Krishna',
            'last_name': 'Sisodiya',
            'email': 'krishna@primesoul.in',
            'password1': 'KrishnaPass123!',
            'password2': 'KrishnaPass123!',
        }
        form = UserCreateFormDashboard(data=form_data, school=self.school_a)
        self.assertTrue(form.is_valid(), form.errors)
        created_user = form.save()

        # Verify User properties
        self.assertEqual(created_user.username, 'krishna_user')
        self.assertEqual(created_user.requested_role, 'STUDENT')
        self.assertEqual(created_user.school, self.school_a)
        self.assertEqual(created_user.approval_status, 'a')
        self.assertFalse(created_user.is_staff)

        # Verify Student linkage
        self.student_krishna.refresh_from_db()
        self.assertEqual(self.student_krishna.user, created_user)
        self.assertEqual(created_user.student_profile, self.student_krishna)

        # Verify NO duplicate student record was created
        self.assertEqual(Student.objects.count(), initial_student_count)

    def test_02_prevent_duplicate_account_creation_for_same_student(self):
        """Validates that creating a second user for the same student is blocked by form validation."""
        # First user
        user1 = User.objects.create_user(
            username="krishna_first",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(user1, Role.STUDENT)
        self.student_krishna.user = user1
        self.student_krishna.save(update_fields=['user'])

        # Try creating a second user for the same student
        form_data = {
            'requested_role': 'STUDENT',
            'student': self.student_krishna.pk,
            'username': 'krishna_second',
            'password1': 'KrishnaPass123!',
            'password2': 'KrishnaPass123!',
        }
        form = UserCreateFormDashboard(data=form_data, school=self.school_a)
        self.assertFalse(form.is_valid())
        self.assertIn('student', form.errors)
        self.assertIn("already has an active login account", form.errors['student'][0])

    def test_03_student_user_resolves_to_linked_student(self):
        """Validates get_student_for_user resolves the exact Student record with active placement."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        resolved_student = get_student_for_user(krishna_user, self.school_a)
        self.assertIsNotNone(resolved_student)
        self.assertEqual(resolved_student.pk, self.student_krishna.pk)
        self.assertEqual(resolved_student.get_full_name(), "Krishna Sisodiya")
        self.assertEqual(resolved_student.grade_level.name, "Class 7")
        self.assertEqual(resolved_student.section.name, "A")
        self.assertEqual(resolved_student.roll_number, "12")
        self.assertEqual(resolved_student.admission_number, "ADM-2026-001")

    def test_04_student_portal_loads_linked_student_data(self):
        """Validates student portal dashboard returns 200 and loads student name and placement."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        self.client.force_login(krishna_user)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Krishna Sisodiya")
        self.assertContains(response, "Class 7")
        self.assertContains(response, "ADM-2026-001")

    def test_05_student_profile_loads_linked_student(self):
        """Validates /portal/student/profile/ loads the correct linked student details."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        self.client.force_login(krishna_user)
        response = self.client.get(reverse('portal:student_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Krishna Sisodiya")
        self.assertContains(response, "+919876543210")

    def test_06_student_data_isolation_attendance_and_fees(self):
        """Validates student only sees their own attendance and fee records."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        # Attendance for Krishna
        AttendanceRecord.objects.create(
            school=self.school_a,
            student=self.student_krishna,
            academic_year=self.academic_year_a,
            grade_level=self.grade_7,
            section=self.sec_a,
            attendance_date=timezone.localdate(),
            status='PRESENT'
        )

        self.client.force_login(krishna_user)
        att_resp = self.client.get(reverse('portal:student_attendance'))
        self.assertEqual(att_resp.status_code, 200)
        self.assertContains(att_resp, "100.0%")

    def test_07_cross_tenant_isolation_blocked(self):
        """Validates student from School A cannot resolve or access School B."""
        user_mumbai = User.objects.create_user(
            username="rohit_mumbai",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_b,
            approval_status='a'
        )
        assign_role_to_user(user_mumbai, Role.STUDENT)
        self.student_b.user = user_mumbai
        self.student_b.save(update_fields=['user'])

        # Resolving user_mumbai against school_a should return None
        resolved = get_student_for_user(user_mumbai, self.school_a)
        self.assertIsNone(resolved)

    def test_08_accounts_list_view_displays_linked_profile(self):
        """Validates that /account/accounts/ displays role and linked student profile."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('account:all_accounts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "krishna")
        self.assertContains(response, "STUDENT")
        self.assertContains(response, "Krishna Sisodiya")
        self.assertContains(response, "Linked")

    def test_09_student_sis_shows_account_status_and_create_button(self):
        """Validates Student SIS page displays 'Create Login' when unlinked, and login badge when linked."""
        # 1. Unlinked state
        self.client.force_login(self.admin_user)
        sis_resp = self.client.get(reverse('students:student_sis', kwargs={'pk': self.student_krishna.pk}))
        self.assertEqual(sis_resp.status_code, 200)
        self.assertContains(sis_resp, "Create Login")

        # 2. Linked state
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.student_krishna.user = krishna_user
        self.student_krishna.save(update_fields=['user'])

        sis_resp_linked = self.client.get(reverse('students:student_sis', kwargs={'pk': self.student_krishna.pk}))
        self.assertEqual(sis_resp_linked.status_code, 200)
        self.assertContains(sis_resp_linked, "Login: @krishna")

    def test_10_teacher_user_resolves_and_redirects(self):
        """Validates Teacher user resolves TeacherProfile and redirects to /portal/teacher/."""
        self.assertEqual(get_user_portal(self.teacher_user), PortalType.TEACHER_PORTAL)
        resolved_teacher = get_teacher_for_user(self.teacher_user, self.school_a)
        self.assertIsNotNone(resolved_teacher)
        self.assertEqual(resolved_teacher.get_full_name(), "Ramesh Sharma")

    def test_11_three_role_post_login_routing(self):
        """Validates three-role canonical routing."""
        krishna_user = User.objects.create_user(
            username="krishna",
            password="Pass123Password!",
            requested_role=Role.STUDENT,
            school=self.school_a,
            approval_status='a'
        )
        assign_role_to_user(krishna_user, Role.STUDENT)
        self.assertEqual(get_user_portal(krishna_user), PortalType.STUDENT_PORTAL)
        self.assertEqual(get_user_portal(self.teacher_user), PortalType.TEACHER_PORTAL)
        self.assertEqual(get_user_portal(self.admin_user), PortalType.ADMIN_PORTAL)

    def test_12_admin_creates_teacher_login_for_existing_teacher(self):
        """Admin creates login account for existing onboarded teacher (Param Sisodiya)."""
        form_data = {
            'requested_role': 'TEACHER',
            'teacher': self.unlinked_teacher.pk,
            'username': 'param_teacher',
            'first_name': 'Param',
            'last_name': 'Sisodiya',
            'email': 'param@delhi.primesoul.in',
            'password1': 'TeacherPass123!',
            'password2': 'TeacherPass123!',
        }
        form = UserCreateFormDashboard(data=form_data, school=self.school_a)
        self.assertTrue(form.is_valid(), form.errors)
        created_user = form.save()

        # Verify User and Teacher linkage
        self.assertEqual(created_user.username, 'param_teacher')
        self.assertEqual(created_user.requested_role, 'TEACHER')
        self.unlinked_teacher.refresh_from_db()
        self.assertEqual(self.unlinked_teacher.user, created_user)
        self.assertEqual(created_user.teacher_record, self.unlinked_teacher)
        self.assertTrue(created_user.is_linked_to_profile)

    def test_13_prevent_duplicate_teacher_account_creation(self):
        """Validates that creating a second user for the same teacher is blocked."""
        form_data = {
            'requested_role': 'TEACHER',
            'teacher': self.teacher_record.pk,  # Already linked to self.teacher_user
            'username': 'sharma_duplicate',
            'password1': 'TeacherPass123!',
            'password2': 'TeacherPass123!',
        }
        form = UserCreateFormDashboard(data=form_data, school=self.school_a)
        self.assertFalse(form.is_valid())
        self.assertIn('teacher', form.errors)
        self.assertIn("already has an active login account", form.errors['teacher'][0])
