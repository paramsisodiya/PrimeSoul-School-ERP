import datetime
from decimal import Decimal
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School, Domain
from django_school_management.tenants.context import set_current_school, clear_current_school
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject, SubjectAssignment,
    StudentEnrollment, ClassTeacherAssignment
)
from django_school_management.academics.services.academic_service import (
    set_current_academic_year, create_or_update_grade_level,
    create_or_update_section, assign_class_teacher,
    create_or_update_subject, assign_subject_to_teacher,
    enroll_student
)
from django_school_management.academics.services.promotion_service import execute_promotion
from django_school_management.academics.selectors.academic_selectors import (
    get_academic_dashboard_metrics, get_academic_years_list, get_classes_list,
    get_sections_list, get_subjects_list, get_subject_assignments_list, get_student_enrollments_list
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Designation, Teacher, TeacherProfile

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['*'])
class PrimeSoulAcademicManagementTests(TestCase):
    def setUp(self):
        clear_current_school()
        ensure_system_roles_exist()
        self.factory = RequestFactory()
        self.api_client = APIClient()

        # School A (Primary Tenant)
        self.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkp",
            subdomain="dpsrkp",
            board="CBSE",
            school_code="DPS-101",
            city="New Delhi",
            state="Delhi",
            country="India",
            is_active=True,
            onboarding_completed=True
        )

        # School B (Secondary Tenant for Isolation Testing)
        self.school_b = School.objects.create(
            name="Modern School, Barakhamba",
            slug="modern-delhi",
            subdomain="moderndelhi",
            board="CBSE",
            school_code="MOD-202",
            city="New Delhi",
            state="Delhi",
            country="India",
            is_active=True,
            onboarding_completed=True
        )

        # Users for School A
        self.admin_user = User.objects.create_user(
            username="schooladmin_a",
            email="admin_a@primesoul.com",
            password="password123",
            first_name="Rajiv",
            last_name="Bansal",
            school=self.school_a,
            requested_role="SCHOOL_ADMIN",
            approval_status="a"
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.teacher_user = User.objects.create_user(
            username="teacher_a",
            email="teacher_a@primesoul.com",
            password="password123",
            first_name="Vikram",
            last_name="Malhotra",
            school=self.school_a,
            requested_role="TEACHER",
            approval_status="a"
        )
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        self.accountant_user = User.objects.create_user(
            username="accountant_a",
            email="accountant_a@primesoul.com",
            password="password123",
            first_name="Meenakshi",
            last_name="Sundaram",
            school=self.school_a,
            requested_role="ACCOUNTANT",
            approval_status="a"
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        # Users for School B
        self.admin_b = User.objects.create_user(
            username="schooladmin_b",
            email="admin_b@primesoul.com",
            password="password123",
            first_name="Sanjay",
            last_name="Mehta",
            school=self.school_b,
            requested_role="SCHOOL_ADMIN",
            approval_status="a"
        )
        assign_role_to_user(self.admin_b, Role.SCHOOL_ADMIN)

        # Teacher Legacy & Profile
        self.desig_pgt = Designation.objects.create(school=self.school_a, title="PGT Mathematics")
        self.teacher_a = Teacher.objects.create(
            school=self.school_a,
            employee_id="DPS-T-01",
            name="Vikram Malhotra",
            email="teacher_a@primesoul.com",
            designation=self.desig_pgt
        )
        self.teacher_prof_a = TeacherProfile.objects.create(
            user=self.teacher_user,
            school=self.school_a,
            employee_code="DPS-T-01",
            first_name="Vikram",
            last_name="Malhotra",
            designation=self.desig_pgt
        )

        # Teacher in School B
        self.desig_b = Designation.objects.create(school=self.school_b, title="TGT Science")
        self.teacher_b = Teacher.objects.create(
            school=self.school_b,
            employee_id="MOD-T-99",
            name="Anita Sharma",
            email="teacher_b@primesoul.com",
            designation=self.desig_b
        )

        # Academic Years for School A
        self.ay_2025 = AcademicYear.objects.create(
            school=self.school_a,
            name="2025-2026",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
            is_current=False,
            status=AcademicYear.STATUS_ARCHIVED
        )
        self.ay_2026 = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )

        # Classes in School A
        self.class_9 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 9",
            code="9",
            display_order=9,
            board="CBSE",
            is_active=True
        )
        self.class_10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="10",
            display_order=10,
            board="CBSE",
            is_active=True
        )

        # Sections in School A
        self.sec_9a = Section.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026,
            grade_level=self.class_9,
            name="A",
            max_capacity=40,
            room_number="901"
        )
        self.sec_10a = Section.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026,
            grade_level=self.class_10,
            name="A",
            max_capacity=40,
            room_number="1001",
            class_teacher=self.teacher_a
        )

        # Students in School A
        self.student_1 = Student.objects.create(
            school=self.school_a,
            first_name="Aarav",
            last_name="Sharma",
            admission_number="ADM-2026-001",
            roll_number="101",
            grade_level=self.class_9,
            section=self.sec_9a,
            academic_year=self.ay_2026,
            gender="M"
        )
        self.student_2 = Student.objects.create(
            school=self.school_a,
            first_name="Diya",
            last_name="Patel",
            admission_number="ADM-2026-002",
            roll_number="102",
            grade_level=self.class_9,
            section=self.sec_9a,
            academic_year=self.ay_2026,
            gender="F"
        )

    def tearDown(self):
        clear_current_school()

    # =========================================================================
    # 1. ACADEMIC YEAR TESTS
    # =========================================================================

    def test_01_academic_year_crud(self):
        """Verify AcademicYear creation and retrieval with Indian April-March dates."""
        ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2027-2028",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
            status=AcademicYear.STATUS_UPCOMING
        )
        self.assertIn("2027-2028", str(ay))
        self.assertEqual(ay.status, "UPCOMING")
        self.assertFalse(ay.is_current)

    def test_02_academic_year_date_validation(self):
        """Verify clean() prevents start_date >= end_date."""
        invalid_ay = AcademicYear(
            school=self.school_a,
            name="2028-2027",
            start_date=datetime.date(2028, 4, 1),
            end_date=datetime.date(2027, 3, 31)
        )
        with self.assertRaises(ValidationError):
            invalid_ay.clean()

    def test_03_academic_year_single_current_exclusive(self):
        """Setting is_current=True on a new year unsets is_current on existing year."""
        self.assertTrue(self.ay_2026.is_current)
        new_ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2027-2028",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
            is_current=True
        )
        self.ay_2026.refresh_from_db()
        self.assertFalse(self.ay_2026.is_current)
        self.assertTrue(new_ay.is_current)

    def test_04_academic_year_tenant_scoped_current(self):
        """Setting is_current in School B does not affect School A's current academic year."""
        ay_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.ay_2026.refresh_from_db()
        self.assertTrue(self.ay_2026.is_current)
        self.assertTrue(ay_b.is_current)

    def test_05_academic_year_unique_name_per_school(self):
        """Unique constraint on school + name prevents duplicate years in same school."""
        with self.assertRaises(IntegrityError):
            AcademicYear.objects.create(
                school=self.school_a,
                name="2026-2027",
                start_date=datetime.date(2026, 4, 1),
                end_date=datetime.date(2027, 3, 31)
            )

    # =========================================================================
    # 2. CLASS / GRADE MANAGEMENT TESTS
    # =========================================================================

    def test_06_grade_level_crud_and_ordering(self):
        """Grade levels can be created and are ordered by display_order."""
        nur = GradeLevel.objects.create(school=self.school_a, name="Nursery", code="NUR", display_order=0)
        c1 = GradeLevel.objects.create(school=self.school_a, name="Class 1", code="1", display_order=1)
        grades = list(GradeLevel.objects.filter(school=self.school_a).order_by('display_order'))
        self.assertEqual(grades[0].name, "Nursery")
        self.assertEqual(grades[1].name, "Class 1")

    def test_07_grade_level_activate_deactivate(self):
        """Can deactivate a grade level without deleting historical data."""
        self.class_9.is_active = False
        self.class_9.save()
        self.class_9.refresh_from_db()
        self.assertFalse(self.class_9.is_active)
        self.assertTrue(Student.objects.filter(grade_level=self.class_9).exists())

    def test_08_grade_level_tenant_isolation(self):
        """School B cannot view or modify School A grade levels."""
        GradeLevel.objects.create(school=self.school_b, name="Standard X", code="X", display_order=10)
        grades_a = GradeLevel.objects.filter(school=self.school_a)
        grades_b = GradeLevel.objects.filter(school=self.school_b)
        self.assertNotIn("Standard X", [g.name for g in grades_a])
        self.assertEqual(grades_b.count(), 1)

    # =========================================================================
    # 3. SECTION MANAGEMENT TESTS
    # =========================================================================

    def test_09_section_crud(self):
        """Create section under class + academic year with capacity and room number."""
        sec_b = Section.objects.create(
            school=self.school_a,
            grade_level=self.class_9,
            academic_year=self.ay_2026,
            name="B",
            room_number="902",
            max_capacity=35
        )
        self.assertEqual(str(sec_b), "Class 9 - Section B")
        self.assertEqual(sec_b.max_capacity, 35)

    def test_10_section_unique_within_grade(self):
        """Section name must be unique within grade level."""
        with self.assertRaises(IntegrityError):
            Section.objects.create(
                school=self.school_a,
                grade_level=self.class_9,
                academic_year=self.ay_2026,
                name="A"
            )

    def test_11_section_tenant_isolation(self):
        """Sections are strictly scoped to their tenant school."""
        sec_b_tenant = Section.objects.create(
            school=self.school_b,
            grade_level=GradeLevel.objects.create(school=self.school_b, name="Grade 1", code="G1", display_order=1),
            name="A"
        )
        self.assertEqual(Section.objects.filter(school=self.school_a).filter(pk=sec_b_tenant.pk).count(), 0)

    # =========================================================================
    # 4. CLASS TEACHER ASSIGNMENT TESTS
    # =========================================================================

    def test_12_class_teacher_assignment(self):
        """Assign class teacher safely and record in ClassTeacherAssignment history."""
        cta = assign_class_teacher(
            section=self.sec_9a,
            teacher=self.teacher_a,
            academic_year=self.ay_2026,
            actor=self.admin_user
        )
        self.assertEqual(cta.teacher, self.teacher_a)
        self.sec_9a.refresh_from_db()
        self.assertEqual(self.sec_9a.class_teacher, self.teacher_a)
        history = ClassTeacherAssignment.objects.filter(section=self.sec_9a, academic_year=self.ay_2026)
        self.assertTrue(history.exists())
        self.assertEqual(history.first().teacher, self.teacher_a)

    def test_13_class_teacher_cross_tenant_denial(self):
        """Cannot assign a School B teacher to a School A section."""
        with self.assertRaises(ValidationError):
            assign_class_teacher(
                section=self.sec_9a,
                teacher=self.teacher_b,
                academic_year=self.ay_2026,
                actor=self.admin_user
            )

    # =========================================================================
    # 5. SUBJECT MANAGEMENT TESTS
    # =========================================================================

    def test_14_subject_crud(self):
        """Create subjects with code, subject_type, and marks."""
        subj = Subject.objects.create(
            school=self.school_a,
            name="Mathematics",
            code="MATH-09",
            subject_type=Subject.TYPE_CORE,
            max_marks=100,
            passing_marks=33
        )
        self.assertEqual(subj.code, "MATH-09")
        self.assertEqual(subj.subject_type, "CORE")
        self.assertTrue(subj.is_active)

    def test_15_subject_unique_code_per_school(self):
        """Subject code must be unique per school."""
        Subject.objects.create(school=self.school_a, name="Science 1", code="SCI-01")
        with self.assertRaises(IntegrityError):
            Subject.objects.create(school=self.school_a, name="Science 2", code="SCI-01")

    # =========================================================================
    # 6. SUBJECT ASSIGNMENT TESTS
    # =========================================================================

    def test_16_subject_assignment_to_teacher(self):
        """Map Academic Year + Grade + Section + Subject + Teacher."""
        math = Subject.objects.create(school=self.school_a, name="Mathematics", code="MATH-10A")
        assignment = assign_subject_to_teacher(
            school=self.school_a,
            academic_year=self.ay_2026,
            grade_level=self.class_10,
            subject=math,
            section=self.sec_10a,
            teacher=self.teacher_a,
            periods_per_week=6,
            actor=self.admin_user
        )
        self.assertEqual(assignment.teacher, self.teacher_a)
        self.assertEqual(assignment.periods_per_week, 6)

    def test_17_subject_assignment_duplicate_prevention(self):
        """Cannot assign duplicate subject to same year + grade + section."""
        math = Subject.objects.create(school=self.school_a, name="Mathematics", code="MATH-DUP")
        assign_subject_to_teacher(
            school=self.school_a,
            academic_year=self.ay_2026,
            grade_level=self.class_10,
            subject=math,
            section=self.sec_10a,
            teacher=self.teacher_a
        )
        with self.assertRaises(ValidationError):
            assign_subject_to_teacher(
                school=self.school_a,
                academic_year=self.ay_2026,
                grade_level=self.class_10,
                subject=math,
                section=self.sec_10a,
                teacher=self.teacher_a
            )

    def test_18_subject_assignment_cross_tenant_denial(self):
        """Cross-tenant teacher or subject assignment is blocked."""
        subj_b = Subject.objects.create(school=self.school_b, name="Math B", code="M-B")
        with self.assertRaises(ValidationError):
            assign_subject_to_teacher(
                school=self.school_a,
                academic_year=self.ay_2026,
                grade_level=self.class_10,
                subject=subj_b,
                section=self.sec_10a,
                teacher=self.teacher_a
            )

    # =========================================================================
    # 7. STUDENT ENROLLMENT & HISTORICAL MAPPING TESTS
    # =========================================================================

    def test_19_student_enrollment_creation(self):
        """Enroll student with grade, section, roll number and academic year."""
        enrollment = enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2026,
            grade_level=self.class_9,
            section=self.sec_9a,
            roll_number="01",
            actor=self.admin_user
        )
        self.assertEqual(enrollment.status, StudentEnrollment.STATUS_ACTIVE)
        self.assertEqual(enrollment.roll_number, "01")

    def test_20_student_enrollment_unique_per_year(self):
        """Student cannot be enrolled twice in the same academic year."""
        enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2026,
            grade_level=self.class_9,
            section=self.sec_9a,
            roll_number="01"
        )
        with self.assertRaises(ValidationError):
            enroll_student(
                school=self.school_a,
                student=self.student_1,
                academic_year=self.ay_2026,
                grade_level=self.class_9,
                section=self.sec_9a,
                roll_number="02",
                allow_update=False
            )

    def test_21_student_enrollment_sync_with_student_model(self):
        """Active enrollment for current year automatically updates Student model fields."""
        enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2026,
            grade_level=self.class_9,
            section=self.sec_9a,
            roll_number="99"
        )
        self.student_1.refresh_from_db()
        self.assertEqual(self.student_1.roll_number, "99")
        self.assertEqual(self.student_1.section, self.sec_9a)

    def test_22_student_multi_year_history(self):
        """Student maintains distinct historical enrollments across different academic years."""
        # 2025-26 Enrollment (Class 8)
        c8 = GradeLevel.objects.create(school=self.school_a, name="Class 8", code="8", display_order=8)
        sec_8a = Section.objects.create(school=self.school_a, grade_level=c8, name="A")
        enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2025,
            grade_level=c8,
            section=sec_8a,
            roll_number="50"
        )
        # 2026-27 Enrollment (Class 9)
        enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2026,
            grade_level=self.class_9,
            section=self.sec_9a,
            roll_number="12"
        )
        history = StudentEnrollment.objects.filter(student=self.student_1).order_by('academic_year__start_date')
        self.assertEqual(history.count(), 2)
        self.assertEqual(history[0].grade_level.name, "Class 8")
        self.assertEqual(history[1].grade_level.name, "Class 9")

    # =========================================================================
    # 8. PROMOTION WORKFLOW TESTS
    # =========================================================================

    def test_23_promotion_workflow_single_student(self):
        """Promote student from Class 9 Section A to Class 10 Section A into target year."""
        # Setup source enrollment in ay_2025
        source_enr = enroll_student(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_2025,
            grade_level=self.class_9,
            section=self.sec_9a,
            roll_number="01"
        )
        result = execute_promotion(
            school=self.school_a,
            source_year=self.ay_2025,
            target_year=self.ay_2026,
            source_grade=self.class_9,
            target_grade=self.class_10,
            source_section=self.sec_9a,
            target_section=self.sec_10a,
            student_ids=[self.student_1.id],
            actor=self.admin_user
        )
        self.assertEqual(result['promoted_count'], 1)
        self.assertEqual(len(result['failed']), 0)

        # Old enrollment status updated to PROMOTED
        source_enr.refresh_from_db()
        self.assertEqual(source_enr.status, StudentEnrollment.STATUS_PROMOTED)

        # New enrollment created in ay_2026
        target_enr = StudentEnrollment.objects.get(student=self.student_1, academic_year=self.ay_2026)
        self.assertEqual(target_enr.grade_level, self.class_10)
        self.assertEqual(target_enr.section, self.sec_10a)
        self.assertEqual(target_enr.status, StudentEnrollment.STATUS_ACTIVE)

    def test_24_promotion_workflow_bulk_students(self):
        """Atomically promote multiple students at once."""
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2025, grade_level=self.class_9, section=self.sec_9a)
        enroll_student(school=self.school_a, student=self.student_2, academic_year=self.ay_2025, grade_level=self.class_9, section=self.sec_9a)

        result = execute_promotion(
            school=self.school_a,
            source_year=self.ay_2025,
            target_year=self.ay_2026,
            source_grade=self.class_9,
            target_grade=self.class_10,
            source_section=self.sec_9a,
            target_section=self.sec_10a,
            student_ids=[self.student_1.id, self.student_2.id],
            actor=self.admin_user
        )
        self.assertEqual(result['promoted_count'], 2)
        self.assertEqual(StudentEnrollment.objects.filter(academic_year=self.ay_2026, grade_level=self.class_10).count(), 2)

    def test_25_promotion_duplicate_target_year_rejected(self):
        """Cannot promote student if already enrolled in the target academic year."""
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2025, grade_level=self.class_9, section=self.sec_9a)
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2026, grade_level=self.class_10, section=self.sec_10a)

        result = execute_promotion(
            school=self.school_a,
            source_year=self.ay_2025,
            target_year=self.ay_2026,
            source_grade=self.class_9,
            target_grade=self.class_10,
            source_section=self.sec_9a,
            target_section=self.sec_10a,
            student_ids=[self.student_1.id],
            actor=self.admin_user
        )
        self.assertEqual(result['promoted_count'], 0)
        self.assertEqual(len(result['failed']), 1)
        self.assertIn("already enrolled", result['failed'][0]['reason'].lower())

    def test_26_promotion_invalid_tenant_rejected(self):
        """Promotion rejects target section belonging to another school."""
        sec_b = Section.objects.create(
            school=self.school_b,
            grade_level=GradeLevel.objects.create(school=self.school_b, name="Class X", code="X", display_order=10),
            name="A"
        )
        with self.assertRaises(ValidationError):
            execute_promotion(
                school=self.school_a,
                source_year=self.ay_2025,
                target_year=self.ay_2026,
                source_grade=self.class_9,
                target_grade=self.class_10,
                student_ids=[self.student_1.id],
                target_section=sec_b
            )

    # =========================================================================
    # 9. ACADEMIC DASHBOARD METRICS TESTS
    # =========================================================================

    def test_27_academic_dashboard_metrics(self):
        """Dashboard selector aggregates correct counts and health metrics."""
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2026, grade_level=self.class_9, section=self.sec_9a)
        Subject.objects.create(school=self.school_a, name="Physics", code="PHY-01", is_active=True)

        metrics = get_academic_dashboard_metrics(self.school_a)
        self.assertEqual(metrics['current_year'], self.ay_2026)
        self.assertEqual(metrics['total_classes'], 2)
        self.assertEqual(metrics['total_sections'], 2)
        self.assertEqual(metrics['total_subjects'], 1)
        self.assertEqual(metrics['total_teachers'], 1)
        self.assertEqual(metrics['total_enrolled_students'], 1)
        # sec_9a has no class teacher
        self.assertEqual(metrics['sections_without_class_teacher'], 1)

    # =========================================================================
    # 10. RBAC & PERMISSIONS TESTS
    # =========================================================================

    def test_28_academic_views_access_rbac_admin(self):
        """School Admin has full access to academic management views."""
        set_current_school(self.school_a)
        self.client.force_login(self.admin_user)

        routes = [
            'academics:dashboard',
            'academics:academic_years',
            'academics:classes',
            'academics:sections',
            'academics:subjects_directory',
            'academics:assignments',
            'academics:enrollments',
            'academics:promotions',
        ]
        for route_name in routes:
            url = reverse(route_name)
            response = self.client.get(url, HTTP_HOST='dpsrkp.example.com')
            self.assertEqual(response.status_code, 200, f"Failed for route {route_name}")

    def test_29_academic_views_access_rbac_accountant_denied(self):
        """Accountant role is denied access to academic management views."""
        set_current_school(self.school_a)
        self.client.force_login(self.accountant_user)

        url = reverse('academics:academic_years')
        response = self.client.get(url, HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, 403)

    def test_30_academic_views_access_rbac_teacher(self):
        """Teacher can access academic dashboard and view assignments."""
        set_current_school(self.school_a)
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('academics:dashboard'), HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, 200)

    # =========================================================================
    # 11. REST API ENDPOINTS TESTS
    # =========================================================================

    def test_31_api_academic_years_list(self):
        """API /api/v1/academics/years/ returns tenant-scoped academic years."""
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)
        response = self.api_client.get('/api/v1/academics/years/', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 2 years created in setUp for School A
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)

    def test_32_api_classes_and_sections(self):
        """API /api/v1/academics/classes/ and /sections/ return tenant records."""
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)

        res_classes = self.api_client.get('/api/v1/academics/classes/', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(res_classes.status_code, status.HTTP_200_OK)
        classes_data = res_classes.data.get('results', res_classes.data)
        self.assertEqual(len(classes_data), 2)

        res_sections = self.api_client.get('/api/v1/academics/sections/', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(res_sections.status_code, status.HTTP_200_OK)
        sections_data = res_sections.data.get('results', res_sections.data)
        self.assertEqual(len(sections_data), 2)

    def test_33_api_subjects_and_assignments(self):
        """API /api/v1/academics/subjects/ and /assignments/."""
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)

        # Create Subject via API
        payload = {
            "name": "Social Studies",
            "code": "SST-09",
            "subject_type": "CORE",
            "max_marks": 100,
            "passing_marks": 33,
            "is_active": True
        }
        res = self.api_client.post('/api/v1/academics/subjects/', payload, format='json', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['code'], "SST-09")

    def test_34_api_student_enrollments(self):
        """API /api/v1/academics/enrollments/ lists student enrollments."""
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2026, grade_level=self.class_9, section=self.sec_9a)
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)

        response = self.api_client.get('/api/v1/academics/enrollments/', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)

    def test_35_api_promotion_execute(self):
        """API /api/v1/academics/promotions/execute/ executes promotion workflow."""
        enroll_student(school=self.school_a, student=self.student_1, academic_year=self.ay_2025, grade_level=self.class_9, section=self.sec_9a)
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)

        payload = {
            "source_year": self.ay_2025.id,
            "target_year": self.ay_2026.id,
            "source_grade": self.class_9.id,
            "target_grade": self.class_10.id,
            "source_section": self.sec_9a.id,
            "target_section": self.sec_10a.id,
            "student_ids": [self.student_1.id],
        }
        response = self.api_client.post('/api/v1/academics/promotions/execute/', payload, format='json', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['promoted_count'], 1)

    def test_36_api_dashboard_summary(self):
        """API /api/v1/academics/dashboard/summary/ returns KPI counts."""
        set_current_school(self.school_a)
        self.api_client.force_authenticate(user=self.admin_user)

        response = self.api_client.get('/api/v1/academics/dashboard/summary/', HTTP_HOST='dpsrkp.example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_classes', response.data)
        self.assertIn('total_sections', response.data)
        self.assertIn('total_subjects', response.data)

    def test_37_audit_logging_academic_events(self):
        """Academic operations produce structured audit trail records."""
        with self.assertLogs('primesoul.audit', level='INFO') as cm:
            assign_class_teacher(
                section=self.sec_9a,
                teacher=self.teacher_a,
                academic_year=self.ay_2026,
                actor=self.admin_user
            )
            self.assertTrue(any('ASSIGN_CLASS_TEACHER' in msg for msg in cm.output))
