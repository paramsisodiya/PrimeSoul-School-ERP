import datetime
from decimal import Decimal
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
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
from django_school_management.attendance.models import AttendanceRecord, AttendanceCorrectionLog
from django_school_management.attendance.services.attendance_service import (
    save_daily_attendance, correct_attendance_record, can_user_mark_section,
    bulk_mark_all_status
)
from django_school_management.attendance.selectors.attendance_selectors import (
    get_attendance_dashboard_metrics, get_daily_attendance_sheet,
    get_attendance_history_queryset, get_student_attendance_summary,
    get_monthly_attendance_summary, get_low_attendance_students,
    get_pending_attendance_sections
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Designation, Teacher, TeacherProfile

User = get_user_model()


class PrimeSoulAttendanceManagementTests(TestCase):
    """
    Phase 6: PrimeSoul ERP Attendance & Daily School Operations Test Suite.
    Verifies daily marking, atomic bulk saves, correction audits, teacher scoping,
    RBAC authorization, tenant isolation, reporting, APIs, and idempotency.
    """

    def setUp(self):
        ensure_system_roles_exist()

        # 1. School Tenant A
        self.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkpuram",
            board="CBSE",
            school_code="DPS-1034",
            is_active=True
        )
        # School Tenant B (for multi-tenant isolation tests)
        self.school_b = School.objects.create(
            name="Modern School, Barakhamba",
            slug="modern-delhi",
            board="CBSE",
            school_code="MOD-5021",
            is_active=True
        )

        # 2. Academic Years
        self.ay_2026_a = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )
        self.ay_2026_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )

        # 3. Classes and Sections for School A
        self.class_10 = GradeLevel.objects.create(
            school=self.school_a, name="Class 10", code="10", display_order=10
        )
        self.class_9 = GradeLevel.objects.create(
            school=self.school_a, name="Class 9", code="9", display_order=9
        )
        self.sec_10a = Section.objects.create(
            school=self.school_a, grade_level=self.class_10, name="A"
        )
        self.sec_10b = Section.objects.create(
            school=self.school_a, grade_level=self.class_10, name="B"
        )
        self.sec_9a = Section.objects.create(
            school=self.school_a, grade_level=self.class_9, name="A"
        )

        # 4. Classes and Sections for School B
        self.class_10_b = GradeLevel.objects.create(
            school=self.school_b, name="Class 10", code="10-B", display_order=10
        )
        self.sec_10a_b = Section.objects.create(
            school=self.school_b, grade_level=self.class_10_b, name="A"
        )

        # 5. Designation & Teachers for School A
        self.desig_tgt = Designation.objects.create(school=self.school_a, title="TGT Teacher")
        
        # Teacher 1: Assigned to 10-A
        self.teacher_user_1 = User.objects.create_user(
            username="teacher_1", email="teacher1@primesoul.com", password="password123",
            first_name="Vikram", last_name="Malhotra", school=self.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user_1, Role.TEACHER)
        self.teacher_profile_1 = TeacherProfile.objects.create(
            user=self.teacher_user_1, school=self.school_a, first_name="Vikram",
            last_name="Malhotra", designation=self.desig_tgt, email=self.teacher_user_1.email
        )
        self.teacher_leg_1 = Teacher.objects.create(
            employee_id="TCH-001", name="Vikram Malhotra", email=self.teacher_user_1.email,
            designation=self.desig_tgt, school=self.school_a
        )
        # Assign as class teacher of 10-A
        self.sec_10a.class_teacher = self.teacher_leg_1
        self.sec_10a.save()
        ClassTeacherAssignment.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a,
            section=self.sec_10a, teacher=self.teacher_leg_1, is_active=True
        )

        # Teacher 2: Unassigned (or assigned only to Class 9-A)
        self.teacher_user_2 = User.objects.create_user(
            username="teacher_2", email="teacher2@primesoul.com", password="password123",
            first_name="Priya", last_name="Nair", school=self.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user_2, Role.TEACHER)
        self.teacher_profile_2 = TeacherProfile.objects.create(
            user=self.teacher_user_2, school=self.school_a, first_name="Priya",
            last_name="Nair", designation=self.desig_tgt, email=self.teacher_user_2.email
        )
        self.teacher_leg_2 = Teacher.objects.create(
            employee_id="TCH-002", name="Priya Nair", email=self.teacher_user_2.email,
            designation=self.desig_tgt, school=self.school_a
        )
        # Assign Teacher 2 to Class 9-A
        self.sec_9a.class_teacher = self.teacher_leg_2
        self.sec_9a.save()

        # 6. Admin, Principal, Accountant, Receptionist Users for School A
        self.admin_user = User.objects.create_user(
            username="admin_a", email="admin@primesoul.com", password="password123",
            first_name="Admin", last_name="User", school=self.school_a, requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.principal_user = User.objects.create_user(
            username="principal_a", email="principal@primesoul.com", password="password123",
            first_name="Principal", last_name="User", school=self.school_a, requested_role=Role.PRINCIPAL
        )
        assign_role_to_user(self.principal_user, Role.PRINCIPAL)

        self.accountant_user = User.objects.create_user(
            username="accountant_a", email="accountant@primesoul.com", password="password123",
            first_name="Accountant", last_name="User", school=self.school_a, requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        self.receptionist_user = User.objects.create_user(
            username="receptionist_a", email="receptionist@primesoul.com", password="password123",
            first_name="Receptionist", last_name="User", school=self.school_a, requested_role=Role.RECEPTIONIST
        )
        assign_role_to_user(self.receptionist_user, Role.RECEPTIONIST)

        # 7. Students for School A
        self.student_user_1 = User.objects.create_user(
            username="student_aarav", email="aarav@primesoul.com", password="password123",
            first_name="Aarav", last_name="Sharma", school=self.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_1, Role.STUDENT)
        self.student_1 = Student.objects.create(
            school=self.school_a, user=self.student_user_1, first_name="Aarav", last_name="Sharma",
            admission_number="ADM-0101", roll_number="101", roll="101",
            grade_level=self.class_10, section=self.sec_10a, academic_year=self.ay_2026_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_1, academic_year=self.ay_2026_a,
            grade_level=self.class_10, section=self.sec_10a, roll_number="101", status="ACTIVE"
        )

        self.student_2 = Student.objects.create(
            school=self.school_a, first_name="Diya", last_name="Patel",
            admission_number="ADM-0102", roll_number="102", roll="102",
            grade_level=self.class_10, section=self.sec_10a, academic_year=self.ay_2026_a, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_a, student=self.student_2, academic_year=self.ay_2026_a,
            grade_level=self.class_10, section=self.sec_10a, roll_number="102", status="ACTIVE"
        )

        # Student for School B
        self.student_b = Student.objects.create(
            school=self.school_b, first_name="Rohan", last_name="Sen",
            admission_number="ADM-B-01", roll_number="1",
            grade_level=self.class_10_b, section=self.sec_10a_b, academic_year=self.ay_2026_b, is_active=True
        )
        StudentEnrollment.objects.create(
            school=self.school_b, student=self.student_b, academic_year=self.ay_2026_b,
            grade_level=self.class_10_b, section=self.sec_10a_b, roll_number="1", status="ACTIVE"
        )

        # Default test date
        self.test_date = datetime.date(2026, 9, 11)

    # =========================================================================
    # 1. ATTENDANCE MODEL & INTEGRITY TESTS
    # =========================================================================

    def test_01_attendance_model_validation(self):
        """AttendanceRecord creates cleanly with valid tenant and date fields."""
        record = AttendanceRecord.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            student=self.student_1,
            attendance_date=self.test_date,
            status=AttendanceRecord.STATUS_PRESENT,
            marked_by=self.teacher_user_1
        )
        self.assertIsNotNone(record.id)
        self.assertEqual(record.status, "PRESENT")
        self.assertIn("Aarav Sharma", str(record))

    def test_02_unique_attendance_per_student_date_year(self):
        """Database constraint prevents duplicate attendance on same date and year."""
        AttendanceRecord.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            student=self.student_1,
            attendance_date=self.test_date,
            status=AttendanceRecord.STATUS_PRESENT
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            AttendanceRecord.objects.create(
                school=self.school_a,
                academic_year=self.ay_2026_a,
                grade_level=self.class_10,
                section=self.sec_10a,
                student=self.student_1,
                attendance_date=self.test_date,
                status=AttendanceRecord.STATUS_ABSENT
            )

    def test_03_status_choices(self):
        """Supports all required Indian K-12 status choices."""
        choices = dict(AttendanceRecord.STATUS_CHOICES)
        self.assertIn("PRESENT", choices)
        self.assertIn("ABSENT", choices)
        self.assertIn("LATE", choices)
        self.assertIn("HALF_DAY", choices)
        self.assertIn("EXCUSED", choices)

    # =========================================================================
    # 2. DAILY WORKFLOW & SERVICE TESTS
    # =========================================================================

    def test_04_save_daily_attendance_service(self):
        """save_daily_attendance records attendance for multiple students atomically."""
        entries = [
            {'student_id': self.student_1.id, 'status': 'PRESENT', 'remarks': 'On time'},
            {'student_id': self.student_2.id, 'status': 'ABSENT', 'remarks': 'Sick leave'},
        ]
        result = save_daily_attendance(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            attendance_date=self.test_date,
            attendance_entries=entries,
            actor=self.teacher_user_1
        )
        self.assertEqual(result['created_count'], 2)
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_date=self.test_date).count(), 2)

    def test_05_bulk_mark_all_present(self):
        """bulk_mark_all_status marks all enrolled students of a section as Present."""
        result = bulk_mark_all_status(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            attendance_date=self.test_date,
            target_status=AttendanceRecord.STATUS_PRESENT,
            actor=self.teacher_user_1
        )
        self.assertEqual(result['created_count'], 2)
        records = AttendanceRecord.objects.filter(section=self.sec_10a, attendance_date=self.test_date)
        for r in records:
            self.assertEqual(r.status, "PRESENT")

    def test_06_load_existing_attendance(self):
        """get_daily_attendance_sheet loads previously recorded attendance accurately."""
        AttendanceRecord.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            student=self.student_1,
            attendance_date=self.test_date,
            status=AttendanceRecord.STATUS_LATE,
            remarks="Bus delayed"
        )
        sheet = get_daily_attendance_sheet(
            self.school_a, self.ay_2026_a, self.class_10, self.sec_10a, self.test_date
        )
        self.assertEqual(len(sheet), 2)
        s1 = next(item for item in sheet if item['student_id'] == self.student_1.id)
        self.assertTrue(s1['is_existing'])
        self.assertEqual(s1['status'], "LATE")
        self.assertEqual(s1['remarks'], "Bus delayed")

        s2 = next(item for item in sheet if item['student_id'] == self.student_2.id)
        self.assertFalse(s2['is_existing'])
        self.assertEqual(s2['status'], "PRESENT")

    # =========================================================================
    # 3. ATTENDANCE CORRECTION & AUDIT LOG TESTS
    # =========================================================================

    def test_07_attendance_correction_records_history(self):
        """Editing an existing attendance record creates an immutable AttendanceCorrectionLog."""
        rec = AttendanceRecord.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            student=self.student_1,
            attendance_date=self.test_date,
            status=AttendanceRecord.STATUS_ABSENT,
            marked_by=self.teacher_user_1
        )
        updated = correct_attendance_record(
            record=rec,
            new_status="PRESENT",
            reason="Student arrived with medical slip",
            actor=self.admin_user
        )
        self.assertEqual(updated.status, "PRESENT")
        self.assertEqual(updated.updated_by, self.admin_user)

        log = AttendanceCorrectionLog.objects.filter(attendance_record=rec).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.previous_status, "ABSENT")
        self.assertEqual(log.new_status, "PRESENT")
        self.assertEqual(log.reason, "Student arrived with medical slip")
        self.assertEqual(log.corrected_by, self.admin_user)

    def test_08_attendance_correction_requires_reason(self):
        """Attendance correction requires a non-empty justification reason."""
        rec = AttendanceRecord.objects.create(
            school=self.school_a,
            academic_year=self.ay_2026_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            student=self.student_1,
            attendance_date=self.test_date,
            status=AttendanceRecord.STATUS_PRESENT,
            marked_by=self.teacher_user_1
        )
        with self.assertRaises(ValidationError):
            correct_attendance_record(rec, "ABSENT", "   ", self.admin_user)

    def test_09_audit_logging_on_attendance_events(self):
        """save_daily_attendance invokes standardized core audit logging."""
        with self.assertLogs('primesoul.audit', level='INFO') as cm:
            save_daily_attendance(
                school=self.school_a,
                academic_year=self.ay_2026_a,
                grade_level=self.class_10,
                section=self.sec_10a,
                attendance_date=self.test_date,
                attendance_entries=[{'student_id': self.student_1.id, 'status': 'PRESENT'}],
                actor=self.teacher_user_1
            )
        self.assertTrue(any('ATTENDANCE' in msg and 'DAILY_ATTENDANCE_SAVED' in msg for msg in cm.output))

    # =========================================================================
    # 4. TEACHER SCOPING & RBAC TESTS
    # =========================================================================

    def test_10_teacher_assigned_class_teacher_can_mark(self):
        """Assigned class teacher has authorization to mark section attendance."""
        self.assertTrue(can_user_mark_section(self.teacher_user_1, self.school_a, self.sec_10a))

    def test_11_teacher_assigned_subject_teacher_can_mark(self):
        """Teacher assigned a subject in a section can mark that section."""
        subj = Subject.objects.create(school=self.school_a, name="Physics", code="PHY-10")
        SubjectAssignment.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10b, subject=subj, teacher=self.teacher_leg_2, is_active=True
        )
        self.assertTrue(can_user_mark_section(self.teacher_user_2, self.school_a, self.sec_10b))

    def test_12_teacher_unassigned_section_denied(self):
        """Teacher cannot mark attendance for an unassigned section."""
        self.assertFalse(can_user_mark_section(self.teacher_user_2, self.school_a, self.sec_10a))
        with self.assertRaises(PermissionDenied):
            save_daily_attendance(
                school=self.school_a,
                academic_year=self.ay_2026_a,
                grade_level=self.class_10,
                section=self.sec_10a,
                attendance_date=self.test_date,
                attendance_entries=[{'student_id': self.student_1.id, 'status': 'PRESENT'}],
                actor=self.teacher_user_2
            )

    def test_13_school_admin_full_access(self):
        """School Admin has full management access across all sections."""
        self.assertTrue(can_user_mark_section(self.admin_user, self.school_a, self.sec_10a))
        self.assertTrue(can_user_mark_section(self.admin_user, self.school_a, self.sec_10b))
        self.assertTrue(can_user_mark_section(self.admin_user, self.school_a, self.sec_9a))

    def test_14_principal_full_access(self):
        """Principal has full access across all sections in the school."""
        self.assertTrue(can_user_mark_section(self.principal_user, self.school_a, self.sec_10a))
        self.assertTrue(can_user_mark_section(self.principal_user, self.school_a, self.sec_9a))

    def test_15_accountant_denied_marking(self):
        """Accountant role cannot mark attendance."""
        self.assertFalse(can_user_mark_section(self.accountant_user, self.school_a, self.sec_10a))

    def test_16_receptionist_read_only(self):
        """Receptionist role cannot mark attendance."""
        self.assertFalse(can_user_mark_section(self.receptionist_user, self.school_a, self.sec_10a))

    def test_17_student_restricted_to_own_attendance(self):
        """Student cannot mark attendance and is restricted in queries."""
        self.assertFalse(can_user_mark_section(self.student_user_1, self.school_a, self.sec_10a))
        client = APIClient()
        client.force_authenticate(user=self.student_user_1)
        # Create records for student 1 and student 2
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_2, attendance_date=self.test_date, status="PRESENT"
        )
        resp = client.get('/api/v1/attendance/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['student'], self.student_1.id)

    def test_18_parent_restricted_to_child_attendance(self):
        """Parent user can only view their registered child's attendance."""
        parent_user = User.objects.create_user(
            username="parent_1", email="parent@primesoul.com", password="password123",
            first_name="Suresh", last_name="Sharma", school=self.school_a, requested_role=Role.PARENT
        )
        assign_role_to_user(parent_user, Role.PARENT)
        from django_school_management.students.models import ParentProfile, StudentGuardianRelationship
        pp = ParentProfile.objects.create(user=parent_user, school=self.school_a, first_name="Suresh", last_name="Sharma")
        StudentGuardianRelationship.objects.create(student=self.student_1, guardian=pp, relationship_type="Father")

        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_2, attendance_date=self.test_date, status="PRESENT"
        )

        client = APIClient()
        client.force_authenticate(user=parent_user)
        resp = client.get('/api/v1/attendance/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['student'], self.student_1.id)

    # =========================================================================
    # 5. TENANT ISOLATION TESTS
    # =========================================================================

    def test_19_tenant_isolation_attendance_queries(self):
        """School A admin cannot view attendance records from School B."""
        AttendanceRecord.objects.create(
            school=self.school_b, academic_year=self.ay_2026_b, grade_level=self.class_10_b,
            section=self.sec_10a_b, student=self.student_b, attendance_date=self.test_date, status="PRESENT"
        )
        qs = get_attendance_history_queryset(self.school_a)
        self.assertEqual(qs.count(), 0)

    def test_20_tenant_isolation_cross_tenant_rejection(self):
        """Attempting to record attendance for a student belonging to another school fails."""
        with self.assertRaises(ValidationError):
            save_daily_attendance(
                school=self.school_a,
                academic_year=self.ay_2026_a,
                grade_level=self.class_10,
                section=self.sec_10a,
                attendance_date=self.test_date,
                attendance_entries=[{'student_id': self.student_b.id, 'status': 'PRESENT'}],
                actor=self.admin_user
            )

    def test_21_invalid_student_enrollment_rejected(self):
        """Rejects attendance for a student not enrolled in that specific class/section."""
        # student_1 belongs to Class 10 Section A, try marking in Class 9 Section A
        with self.assertRaises(ValidationError):
            save_daily_attendance(
                school=self.school_a,
                academic_year=self.ay_2026_a,
                grade_level=self.class_9,
                section=self.sec_9a,
                attendance_date=self.test_date,
                attendance_entries=[{'student_id': self.student_1.id, 'status': 'PRESENT'}],
                actor=self.admin_user
            )

    # =========================================================================
    # 6. ATTENDANCE METRICS, PERCENTAGE & REPORTING TESTS
    # =========================================================================

    def test_22_attendance_percentage_calculation(self):
        """Attendance percentage weights Present as 1.0, Late as 1.0, Half-Day as 0.5."""
        # 4 days: 2 Present, 1 Late, 1 Half Day => 2 + 1 + 0.5 = 3.5 / 4 = 87.5%
        dates = [
            datetime.date(2026, 9, 1),
            datetime.date(2026, 9, 2),
            datetime.date(2026, 9, 3),
            datetime.date(2026, 9, 4),
        ]
        statuses = ["PRESENT", "PRESENT", "LATE", "HALF_DAY"]
        for d, s in zip(dates, statuses):
            AttendanceRecord.objects.create(
                school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
                section=self.sec_10a, student=self.student_1, attendance_date=d, status=s
            )

        summary = get_student_attendance_summary(self.school_a, self.student_1, self.ay_2026_a)
        self.assertEqual(summary['total_records'], 4)
        self.assertEqual(summary['present_count'], 2)
        self.assertEqual(summary['late_count'], 1)
        self.assertEqual(summary['half_day_count'], 1)
        self.assertEqual(summary['percentage'], 87.5)

    def test_23_student_attendance_summary_selector(self):
        """get_student_attendance_summary aggregates accurate counts and recent records."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        summary = get_student_attendance_summary(self.school_a, self.student_1)
        self.assertEqual(summary['total_records'], 1)
        self.assertEqual(summary['present_count'], 1)
        self.assertEqual(len(summary['recent_records']), 1)

    def test_24_monthly_attendance_summary_selector(self):
        """get_monthly_attendance_summary aggregates attendance matrix for an entire class."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=datetime.date(2026, 9, 1), status="PRESENT"
        )
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_2, attendance_date=datetime.date(2026, 9, 1), status="ABSENT"
        )
        matrix = get_monthly_attendance_summary(self.school_a, self.ay_2026_a, self.class_10, self.sec_10a, 2026, 9)
        self.assertEqual(len(matrix), 2)
        s1 = next(m for m in matrix if m['student_id'] == self.student_1.id)
        s2 = next(m for m in matrix if m['student_id'] == self.student_2.id)
        self.assertEqual(s1['present_days'], 1)
        self.assertEqual(s2['absent_days'], 1)

    def test_25_low_attendance_detection(self):
        """get_low_attendance_students flags students below statutory threshold."""
        # 10 days: Student 1 has 9 Present (90%), Student 2 has 4 Present (40%)
        for i in range(1, 11):
            d = datetime.date(2026, 9, i)
            AttendanceRecord.objects.create(
                school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
                section=self.sec_10a, student=self.student_1, attendance_date=d,
                status="PRESENT" if i < 10 else "ABSENT"
            )
            AttendanceRecord.objects.create(
                school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
                section=self.sec_10a, student=self.student_2, attendance_date=d,
                status="PRESENT" if i <= 4 else "ABSENT"
            )

        low_list = get_low_attendance_students(self.school_a, self.ay_2026_a, threshold=75.0)
        self.assertEqual(len(low_list), 1)
        self.assertEqual(low_list[0]['student'].id, self.student_2.id)
        self.assertEqual(low_list[0]['percentage'], 40.0)

    def test_26_pending_attendance_detection(self):
        """get_pending_attendance_sections identifies sections with no attendance marked on target date."""
        # Mark attendance for Section 10-A only
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        sections_status = get_pending_attendance_sections(self.school_a, self.ay_2026_a, self.test_date)
        sec_10a_item = next(s for s in sections_status if s['section'].id == self.sec_10a.id)
        sec_10b_item = next(s for s in sections_status if s['section'].id == self.sec_10b.id)

        self.assertTrue(sec_10a_item['is_marked'])
        self.assertFalse(sec_10b_item['is_marked'])

    def test_27_pending_attendance_teacher_scoped(self):
        """When teacher_user is supplied, pending list only contains teacher's assigned sections."""
        # Teacher 1 is only assigned to Section 10-A
        sections_status = get_pending_attendance_sections(
            self.school_a, self.ay_2026_a, self.test_date, teacher_user=self.teacher_user_1
        )
        self.assertEqual(len(sections_status), 1)
        self.assertEqual(sections_status[0]['section'].id, self.sec_10a.id)

    # =========================================================================
    # 7. CSV EXPORT TESTS
    # =========================================================================

    def test_28_csv_export_daily(self):
        """export_daily_csv generates valid CSV with correct student status rows."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        self.client.force_login(self.admin_user)
        url = f"/attendance/export/daily-csv/?academic_year={self.ay_2026_a.id}&grade_level={self.class_10.id}&section={self.sec_10a.id}&attendance_date={self.test_date}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn("Aarav Sharma", resp.content.decode())

    def test_29_csv_export_monthly(self):
        """export_monthly_csv generates monthly matrix CSV."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=datetime.date(2026, 9, 1), status="PRESENT"
        )
        self.client.force_login(self.admin_user)
        url = f"/attendance/export/monthly-csv/?academic_year={self.ay_2026_a.id}&grade_level={self.class_10.id}&section={self.sec_10a.id}&year=2026&month=9"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Roll No,Student Name,Total Days", resp.content.decode())

    def test_30_csv_export_low_attendance(self):
        """export_low_attendance_csv downloads report for students below threshold."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_2, attendance_date=self.test_date, status="ABSENT"
        )
        self.client.force_login(self.admin_user)
        resp = self.client.get('/attendance/export/low-attendance-csv/?threshold=75')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Diya Patel", resp.content.decode())

    # =========================================================================
    # 8. REST API ENDPOINT TESTS
    # =========================================================================

    def test_31_api_list_records_tenant_scoped(self):
        """GET /api/v1/attendance/ returns tenant-scoped records."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        resp = client.get('/api/v1/attendance/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['student_name'], "Aarav Sharma")

    def test_32_api_bulk_mark(self):
        """POST /api/v1/attendance/bulk-mark/ processes atomic bulk marking."""
        client = APIClient()
        client.force_authenticate(user=self.teacher_user_1)
        payload = {
            "academic_year": self.ay_2026_a.id,
            "grade_level": self.class_10.id,
            "section": self.sec_10a.id,
            "attendance_date": str(self.test_date),
            "entries": [
                {"student_id": self.student_1.id, "status": "PRESENT", "remarks": "Prompt"},
                {"student_id": self.student_2.id, "status": "LATE", "remarks": "Rain delay"},
            ]
        }
        resp = client.post('/api/v1/attendance/bulk-mark/', payload, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created_count'], 2)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_date=self.test_date).count(), 2)

    def test_33_api_correction_endpoint(self):
        """POST /api/v1/attendance/<id>/correct/ modifies status with justification reason."""
        rec = AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="ABSENT"
        )
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        resp = client.post(f'/api/v1/attendance/{rec.id}/correct/', {
            "new_status": "EXCUSED",
            "reason": "Medical certificate submitted to principal office"
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        rec.refresh_from_db()
        self.assertEqual(rec.status, "EXCUSED")

    def test_34_api_dashboard_summary(self):
        """GET /api/v1/attendance/summary/ returns real-time calculated KPI metrics."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_2026_a, grade_level=self.class_10,
            section=self.sec_10a, student=self.student_1, attendance_date=self.test_date, status="PRESENT"
        )
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        resp = client.get(f'/api/v1/attendance/summary/?date={self.test_date}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_today'], 1)
        self.assertEqual(resp.data['present_today'], 1)
        self.assertEqual(resp.data['today_percentage'], 100.0)

    def test_35_api_pending_endpoint(self):
        """GET /api/v1/attendance/pending/ lists section roll submission statuses."""
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        resp = client.get(f'/api/v1/attendance/pending/?date={self.test_date}')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('sections' in resp.data)
        self.assertGreaterEqual(len(resp.data['sections']), 1)

    def test_36_api_unauthorized_access_denied(self):
        """Anonymous API request is rejected with 401 or 403."""
        client = APIClient()
        resp = client.get('/api/v1/attendance/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # =========================================================================
    # 9. SEED IDEMPOTENCY TEST
    # =========================================================================

    def test_37_seed_idempotency_attendance(self):
        """Running attendance creation logic multiple times does not create duplicates."""
        initial_count = AttendanceRecord.objects.count()
        # Seed record
        AttendanceRecord.objects.get_or_create(
            school=self.school_a, academic_year=self.ay_2026_a, student=self.student_1,
            attendance_date=self.test_date,
            defaults={"grade_level": self.class_10, "section": self.sec_10a, "status": "PRESENT"}
        )
        count_1 = AttendanceRecord.objects.count()
        # Re-run same seed
        AttendanceRecord.objects.get_or_create(
            school=self.school_a, academic_year=self.ay_2026_a, student=self.student_1,
            attendance_date=self.test_date,
            defaults={"grade_level": self.class_10, "section": self.sec_10a, "status": "PRESENT"}
        )
        count_2 = AttendanceRecord.objects.count()
        self.assertEqual(count_1, count_2)
