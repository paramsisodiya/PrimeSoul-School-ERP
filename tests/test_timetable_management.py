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
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject, SubjectAssignment,
    StudentEnrollment
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Designation, Teacher, TeacherProfile
from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.timetable.services.conflict_service import (
    validate_timetable_entry_conflicts
)
from django_school_management.timetable.services.timetable_service import (
    create_timetable_entry, update_timetable_entry, delete_timetable_entry,
    clone_timetable, clear_timetable, export_timetable_csv
)
from django_school_management.timetable.services.generator_service import (
    generate_automated_timetable
)
from django_school_management.timetable.selectors.timetable_selectors import (
    get_timetable_dashboard_metrics, get_class_timetable_matrix,
    get_teacher_timetable_matrix, get_room_timetable_matrix,
    get_weekly_timetable_grid
)

User = get_user_model()


class PrimeSoulTimetableManagementTests(TestCase):
    """
    Phase 9: PrimeSoul ERP Timetable & Scheduling Test Suite.
    Validates tenant isolation, configurable working days/periods, multi-dimensional
    collision rejection (teacher, section, room, invalid teacher assignment),
    auto-generation engine, matrices, RBAC, and REST APIs.
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
        self.ay_next = AcademicYear.objects.create(
            school=self.school_a,
            name="2027-2028",
            start_date=datetime.date(2027, 4, 1),
            end_date=datetime.date(2028, 3, 31),
            is_current=False,
            status=AcademicYear.STATUS_UPCOMING
        )
        self.ay_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )

        # 3. Grade levels and sections for School A
        self.grade_10 = GradeLevel.objects.create(
            school=self.school_a, name="Class 10", code="10", display_order=10
        )
        self.grade_9 = GradeLevel.objects.create(
            school=self.school_a, name="Class 9", code="9", display_order=9
        )
        self.sec_10a = Section.objects.create(
            school=self.school_a, grade_level=self.grade_10, name="A"
        )
        self.sec_10b = Section.objects.create(
            school=self.school_a, grade_level=self.grade_10, name="B"
        )
        self.sec_9a = Section.objects.create(
            school=self.school_a, grade_level=self.grade_9, name="A"
        )

        # Grade level and section for School B
        self.grade_10_b = GradeLevel.objects.create(
            school=self.school_b, name="Class 10", code="10-B", display_order=10
        )
        self.sec_10a_b = Section.objects.create(
            school=self.school_b, grade_level=self.grade_10_b, name="A"
        )

        # 4. Subjects
        self.sub_math = Subject.objects.create(
            school=self.school_a, name="Mathematics", code="MATH10", subject_type=Subject.TYPE_CORE
        )
        self.sub_sci = Subject.objects.create(
            school=self.school_a, name="Science", code="SCI10", subject_type=Subject.TYPE_CORE
        )
        self.sub_eng = Subject.objects.create(
            school=self.school_a, name="English", code="ENG10", subject_type=Subject.TYPE_CORE
        )

        # 5. Faculty / Teachers
        self.desig = Designation.objects.create(school=self.school_a, title="Senior Faculty")

        self.teacher_user_1 = User.objects.create_user(
            username="teacher_sharma", email="sharma@primesoul.com", password="password123",
            first_name="Ramesh", last_name="Sharma", school=self.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user_1, Role.TEACHER)
        self.teacher_profile_1 = TeacherProfile.objects.create(
            user=self.teacher_user_1, school=self.school_a, first_name="Ramesh",
            last_name="Sharma", designation=self.desig, email="sharma@primesoul.com"
        )
        self.teacher_leg_1 = Teacher.objects.create(
            employee_id="EMP-010", name="Ramesh Sharma", email="sharma@primesoul.com",
            designation=self.desig, school=self.school_a
        )

        self.teacher_user_2 = User.objects.create_user(
            username="teacher_kapoor", email="kapoor@primesoul.com", password="password123",
            first_name="Anita", last_name="Kapoor", school=self.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user_2, Role.TEACHER)
        self.teacher_profile_2 = TeacherProfile.objects.create(
            user=self.teacher_user_2, school=self.school_a, first_name="Anita",
            last_name="Kapoor", designation=self.desig, email="kapoor@primesoul.com"
        )
        self.teacher_leg_2 = Teacher.objects.create(
            employee_id="EMP-011", name="Anita Kapoor", email="kapoor@primesoul.com",
            designation=self.desig, school=self.school_a
        )

        # 6. Subject Assignments
        # Sharma teaches Math to 10-A and 10-B
        SubjectAssignment.objects.create(
            school=self.school_a, academic_year=self.ay_a, grade_level=self.grade_10,
            subject=self.sub_math, teacher=self.teacher_leg_1, section=self.sec_10a, is_active=True
        )
        SubjectAssignment.objects.create(
            school=self.school_a, academic_year=self.ay_a, grade_level=self.grade_10,
            subject=self.sub_math, teacher=self.teacher_leg_1, section=self.sec_10b, is_active=True
        )
        # Kapoor teaches Science to 10-A
        SubjectAssignment.objects.create(
            school=self.school_a, academic_year=self.ay_a, grade_level=self.grade_10,
            subject=self.sub_sci, teacher=self.teacher_leg_2, section=self.sec_10a, is_active=True
        )

        # 7. Classrooms
        self.room_101 = Classroom.objects.create(
            school=self.school_a, name="Room 101", room_number="101",
            capacity=40, room_type='CLASSROOM'
        )
        self.room_lab = Classroom.objects.create(
            school=self.school_a, name="Science Lab 1", room_number="LAB-1",
            capacity=35, room_type='LAB'
        )

        # 8. Working Days (Configurable: Monday to Friday)
        self.w_mon = WorkingDay.objects.create(
            school=self.school_a, academic_year=self.ay_a, weekday=WorkingDay.MONDAY,
            is_working=True, display_order=1
        )
        self.w_tue = WorkingDay.objects.create(
            school=self.school_a, academic_year=self.ay_a, weekday=WorkingDay.TUESDAY,
            is_working=True, display_order=2
        )
        self.w_wed = WorkingDay.objects.create(
            school=self.school_a, academic_year=self.ay_a, weekday=WorkingDay.WEDNESDAY,
            is_working=True, display_order=3
        )
        self.w_thu = WorkingDay.objects.create(
            school=self.school_a, academic_year=self.ay_a, weekday=WorkingDay.THURSDAY,
            is_working=True, display_order=4
        )
        self.w_fri = WorkingDay.objects.create(
            school=self.school_a, academic_year=self.ay_a, weekday=WorkingDay.FRIDAY,
            is_working=True, display_order=5
        )

        # 9. Time Slots / Periods
        self.slot_p1 = TimeSlot.objects.create(
            school=self.school_a, academic_year=self.ay_a, name="Period 1",
            period_number=1, start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            is_break=False, display_order=1
        )
        self.slot_p2 = TimeSlot.objects.create(
            school=self.school_a, academic_year=self.ay_a, name="Period 2",
            period_number=2, start_time=datetime.time(8, 45), end_time=datetime.time(9, 30),
            is_break=False, display_order=2
        )
        self.slot_break = TimeSlot.objects.create(
            school=self.school_a, academic_year=self.ay_a, name="Morning Recess",
            period_number=3, start_time=datetime.time(9, 30), end_time=datetime.time(9, 50),
            is_break=True, display_order=3
        )
        self.slot_p3 = TimeSlot.objects.create(
            school=self.school_a, academic_year=self.ay_a, name="Period 3",
            period_number=4, start_time=datetime.time(9, 50), end_time=datetime.time(10, 35),
            is_break=False, display_order=4
        )

        # 10. Users & Roles for RBAC
        self.admin_user = User.objects.create_user(
            username="school_admin_a", email="admin@dps.com", password="password123",
            first_name="Admin", last_name="User", school=self.school_a, requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.accountant_user = User.objects.create_user(
            username="accountant_a", email="accountant@dps.com", password="password123",
            first_name="Accountant", last_name="User", school=self.school_a, requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        self.student_user = User.objects.create_user(
            username="student_rahul", email="rahul@dps.com", password="password123",
            first_name="Rahul", last_name="Verma", school=self.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user, Role.STUDENT)
        self.student_1 = Student.objects.create(
            school=self.school_a, user=self.student_user, first_name="Rahul", last_name="Verma",
            admission_number="ADM-101", roll_number="1", roll="1",
            grade_level=self.grade_10, section=self.sec_10a, academic_year=self.ay_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_1, academic_year=self.ay_a,
            grade_level=self.grade_10, section=self.sec_10a, roll_number="1", status="ACTIVE"
        )

        # Set tenant context
        set_current_school(self.school_a)

    def tearDown(self):
        clear_current_school()

    # =========================================================================
    # 1. TENANT ISOLATION
    # =========================================================================

    def test_tenant_isolation_models(self):
        """School B cannot view or access School A's timetable models."""
        set_current_school(self.school_b)
        self.assertEqual(WorkingDay.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(TimeSlot.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(Classroom.objects.filter(school=self.school_b).count(), 0)
        self.assertEqual(TimetableEntry.objects.filter(school=self.school_b).count(), 0)

        # Cross-tenant conflict validation returns false with tenant boundary error
        is_valid, conflicts = validate_timetable_entry_conflicts(
            school=self.school_b,
            academic_year=self.ay_b,
            working_day=self.w_mon,  # Belongs to School A!
            time_slot=self.slot_p1,   # Belongs to School A!
            section=self.sec_10a_b,
            subject=self.sub_math,    # Belongs to School A!
            teacher=self.teacher_leg_1
        )
        self.assertFalse(is_valid)
        self.assertTrue(any("does not belong" in c for c in conflicts))

    # =========================================================================
    # 2. CONFLICT DETECTION ENGINE
    # =========================================================================

    def test_section_double_booking_rejected(self):
        """Cannot schedule two different subjects for the same section at the same period."""
        # Book Period 1 on Monday for 10-A with Math
        entry1 = create_timetable_entry(
            school=self.school_a,
            academic_year=self.ay_a,
            working_day=self.w_mon,
            time_slot=self.slot_p1,
            section=self.sec_10a,
            subject=self.sub_math,
            teacher=self.teacher_leg_1,
            room=self.room_101
        )
        self.assertIsNotNone(entry1.id)

        # Try to schedule Science for 10-A on Monday at Period 1
        with self.assertRaises(ValidationError) as ctx:
            create_timetable_entry(
                school=self.school_a,
                academic_year=self.ay_a,
                working_day=self.w_mon,
                time_slot=self.slot_p1,
                section=self.sec_10a,
                subject=self.sub_sci,
                teacher=self.teacher_leg_2,
                room=self.room_lab
            )
        self.assertIn("Section Double Booking", str(ctx.exception))

    def test_teacher_double_booking_rejected(self):
        """Teacher cannot be scheduled in two different sections at the same period."""
        # Book Sharma for 10-A at Period 1 on Monday
        create_timetable_entry(
            school=self.school_a,
            academic_year=self.ay_a,
            working_day=self.w_mon,
            time_slot=self.slot_p1,
            section=self.sec_10a,
            subject=self.sub_math,
            teacher=self.teacher_leg_1,
            room=self.room_101
        )

        # Try to book Sharma for 10-B at Period 1 on Monday
        with self.assertRaises(ValidationError) as ctx:
            create_timetable_entry(
                school=self.school_a,
                academic_year=self.ay_a,
                working_day=self.w_mon,
                time_slot=self.slot_p1,
                section=self.sec_10b,
                subject=self.sub_math,
                teacher=self.teacher_leg_1,
                room=self.room_lab
            )
        self.assertIn("Teacher Double Booking", str(ctx.exception))

    def test_room_double_booking_rejected(self):
        """Cannot assign two different classes to the same room at the same period."""
        # Room 101 booked for 10-A
        create_timetable_entry(
            school=self.school_a,
            academic_year=self.ay_a,
            working_day=self.w_mon,
            time_slot=self.slot_p1,
            section=self.sec_10a,
            subject=self.sub_math,
            teacher=self.teacher_leg_1,
            room=self.room_101
        )

        # Try to assign Room 101 to 10-B with Anita Kapoor at Period 1
        with self.assertRaises(ValidationError) as ctx:
            create_timetable_entry(
                school=self.school_a,
                academic_year=self.ay_a,
                working_day=self.w_mon,
                time_slot=self.slot_p1,
                section=self.sec_10b,
                subject=self.sub_sci,
                teacher=self.teacher_leg_2,
                room=self.room_101
            )
        self.assertIn("Room Double Booking", str(ctx.exception))

    def test_invalid_teacher_subject_assignment_rejected(self):
        """Teacher must actually be assigned to teach that subject/section in SubjectAssignment."""
        # Anita Kapoor is NOT assigned to teach Math
        with self.assertRaises(ValidationError) as ctx:
            create_timetable_entry(
                school=self.school_a,
                academic_year=self.ay_a,
                working_day=self.w_mon,
                time_slot=self.slot_p1,
                section=self.sec_10a,
                subject=self.sub_math,
                teacher=self.teacher_leg_2,  # Kapoor is Science teacher, not Math!
                strict_assignment=True
            )
        self.assertIn("Invalid Teacher Assignment", str(ctx.exception))

    def test_break_slot_scheduling_handling(self):
        """Scheduling instruction during a designated break period is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            create_timetable_entry(
                school=self.school_a,
                academic_year=self.ay_a,
                working_day=self.w_mon,
                time_slot=self.slot_break,
                section=self.sec_10a,
                subject=self.sub_math,
                teacher=self.teacher_leg_1,
                entry_type=TimetableEntry.TYPE_CLASS
            )
        self.assertIn("break / recess", str(ctx.exception))

    # =========================================================================
    # 3. TIMETABLE CRUD, CLONE & CLEAR
    # =========================================================================

    def test_timetable_update_and_delete(self):
        """Updating and deleting timetable entries behaves correctly."""
        entry = create_timetable_entry(
            school=self.school_a,
            academic_year=self.ay_a,
            working_day=self.w_mon,
            time_slot=self.slot_p1,
            section=self.sec_10a,
            subject=self.sub_math,
            teacher=self.teacher_leg_1,
            room=self.room_101
        )
        self.assertEqual(entry.notes, "")

        # Update note
        updated = update_timetable_entry(entry, notes="Updated syllabus unit")
        self.assertEqual(updated.notes, "Updated syllabus unit")

        # Soft delete
        delete_timetable_entry(entry, hard_delete=False)
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)

    def test_clone_timetable_service(self):
        """Cloning timetable configuration from source to target academic session."""
        create_timetable_entry(
            school=self.school_a, academic_year=self.ay_a, working_day=self.w_mon,
            time_slot=self.slot_p1, section=self.sec_10a, subject=self.sub_math,
            teacher=self.teacher_leg_1
        )
        create_timetable_entry(
            school=self.school_a, academic_year=self.ay_a, working_day=self.w_mon,
            time_slot=self.slot_p2, section=self.sec_10a, subject=self.sub_sci,
            teacher=self.teacher_leg_2
        )

        res = clone_timetable(
            school=self.school_a,
            source_academic_year=self.ay_a,
            target_academic_year=self.ay_next,
            clone_working_days=True,
            clone_time_slots=True,
            clone_entries=True
        )
        self.assertGreaterEqual(res['working_days_created'], 1)
        self.assertGreaterEqual(res['time_slots_created'], 1)
        self.assertEqual(res['entries_created'], 2)

    def test_clear_timetable_service(self):
        """Clearing timetable deactivates all active entries for section or school."""
        create_timetable_entry(
            school=self.school_a, academic_year=self.ay_a, working_day=self.w_mon,
            time_slot=self.slot_p1, section=self.sec_10a, subject=self.sub_math,
            teacher=self.teacher_leg_1
        )
        cleared = clear_timetable(self.school_a, self.ay_a, section=self.sec_10a)
        self.assertEqual(cleared, 1)
        self.assertEqual(TimetableEntry.objects.filter(section=self.sec_10a, is_active=True).count(), 0)

    # =========================================================================
    # 4. TIMETABLE GENERATION ALGORITHM
    # =========================================================================

    def test_generate_automated_timetable(self):
        """Automated timetable generator places subject assignments and reports results."""
        result = generate_automated_timetable(
            school=self.school_a,
            academic_year=self.ay_a,
            section_ids=[self.sec_10a.id]
        )
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["placed_count"], 1)

    # =========================================================================
    # 5. SELECTORS & DASHBOARD
    # =========================================================================

    def test_timetable_selectors_matrices(self):
        """Matrices for class, teacher, room, and dashboard return structured grids."""
        create_timetable_entry(
            school=self.school_a, academic_year=self.ay_a, working_day=self.w_mon,
            time_slot=self.slot_p1, section=self.sec_10a, subject=self.sub_math,
            teacher=self.teacher_leg_1, room=self.room_101
        )

        metrics = get_timetable_dashboard_metrics(self.school_a, self.ay_a)
        self.assertEqual(metrics["scheduled_entries_count"], 1)
        self.assertEqual(metrics["classrooms_count"], 2)
        self.assertEqual(metrics["working_days_count"], 5)

        class_matrix = get_class_timetable_matrix(self.school_a, self.sec_10a, self.ay_a)
        self.assertIn("grid_rows", class_matrix)
        self.assertEqual(class_matrix["total_entries"], 1)

        teacher_matrix = get_teacher_timetable_matrix(self.school_a, self.teacher_leg_1, self.ay_a)
        self.assertIn("grid_rows", teacher_matrix)
        self.assertEqual(teacher_matrix["total_entries"], 1)

        room_matrix = get_room_timetable_matrix(self.school_a, self.room_101, self.ay_a)
        self.assertIn("grid_rows", room_matrix)
        self.assertEqual(room_matrix["total_entries"], 1)

    # =========================================================================
    # 6. RBAC & PERMISSION CHECKS
    # =========================================================================

    def test_rbac_admin_full_access(self):
        """School admin can access timetable dashboard, setup, and generation."""
        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse("timetable:dashboard"))
        self.assertEqual(resp.status_code, 200)

        resp_setup = self.client.get(reverse("timetable:setup"))
        self.assertEqual(resp_setup.status_code, 200)

    def test_rbac_accountant_forbidden(self):
        """Accountant is forbidden from accessing timetable setup or generation."""
        self.client.force_login(self.accountant_user)
        resp = self.client.get(reverse("timetable:setup"))
        self.assertEqual(resp.status_code, 403)

        resp_gen = self.client.get(reverse("timetable:generate"))
        self.assertEqual(resp_gen.status_code, 403)

    def test_rbac_teacher_read_only(self):
        """Teacher can view timetable but cannot access setup or generation."""
        self.client.force_login(self.teacher_user_1)
        resp_view = self.client.get(reverse("timetable:teacher_timetable", kwargs={"teacher_id": self.teacher_leg_1.id}))
        self.assertEqual(resp_view.status_code, 200)

        resp_setup = self.client.get(reverse("timetable:setup"))
        self.assertEqual(resp_setup.status_code, 403)

    def test_rbac_student_own_view_only(self):
        """Student can view their own section's timetable but not setup."""
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("timetable:class_timetable", kwargs={"section_id": self.sec_10a.id}))
        self.assertEqual(resp.status_code, 200)

        resp_setup = self.client.get(reverse("timetable:setup"))
        self.assertEqual(resp_setup.status_code, 403)

    # =========================================================================
    # 7. REST API ENDPOINTS
    # =========================================================================

    def test_timetable_api_endpoints(self):
        """DRF APIs under /api/v1/timetable/ are tenant-safe and require authentication."""
        api_client = APIClient()

        # Unauthenticated request rejected
        resp = api_client.get('/api/v1/timetable/working-days/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Authenticated as School Admin
        api_client.force_authenticate(user=self.admin_user)
        resp_wd = api_client.get('/api/v1/timetable/working-days/')
        self.assertEqual(resp_wd.status_code, status.HTTP_200_OK)
        # DRF pagination may wrap results; verify non-empty response with working day data
        wd_data = resp_wd.data.get("results", resp_wd.data.get("data", resp_wd.data))
        if isinstance(wd_data, list):
            self.assertGreaterEqual(len(wd_data), 4)
        else:
            # Paginated response with count
            self.assertGreaterEqual(resp_wd.data.get("count", 0), 4)

        # Validate Conflict API
        conflict_payload = {
            "academic_year_id": self.ay_a.id,
            "working_day_id": self.w_mon.id,
            "time_slot_id": self.slot_p1.id,
            "section_id": self.sec_10a.id,
            "subject_id": self.sub_math.id,
            "teacher_id": self.teacher_leg_1.id,
            "room_id": self.room_101.id
        }
        resp_conflict = api_client.post('/api/v1/timetable/validate/', conflict_payload, format="json")
        self.assertEqual(resp_conflict.status_code, status.HTTP_200_OK)
        self.assertIn("is_valid", resp_conflict.data)

