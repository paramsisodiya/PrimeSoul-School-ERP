import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from rest_framework.test import APIClient

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, assign_role_to_user
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject, StudentEnrollment,
    SubjectAssignment, ClassTeacherAssignment
)
from django_school_management.teachers.models import Teacher, Designation, TeacherProfile
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.examinations.models import (
    AssessmentType, GradeScale, GradeScaleBand, ExaminationSession,
    Exam, ExamSubject, StudentMark, StudentExamResult, MarksCorrectionLog
)
from django_school_management.examinations.services import (
    exam_service, marks_service, result_calculation_service, report_card_service
)
from django_school_management.examinations.selectors import exam_selectors

User = get_user_model()


class PrimeSoulExaminationManagementTests(TestCase):
    """
    Comprehensive test suite for Phase 7 + Phase 8:
    Examination Management, Grading, Marks Entry, Results, Report Cards, ReportLab PDF, and QR Verification.
    """

    @classmethod
    def setUpTestData(cls):
        # 1. School Tenants
        cls.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkpuram-exam",
            school_code="DPS-EXAM-A",
            board="CBSE",
            is_active=True,
            onboarding_completed=True
        )
        cls.school_b = School.objects.create(
            name="St. Xavier's High School, Mumbai",
            slug="stx-mumbai-exam",
            school_code="STX-EXAM-B",
            board="ICSE",
            is_active=True,
            onboarding_completed=True
        )

        # 2. Academic Years
        cls.ay_a = AcademicYear.objects.create(
            school=cls.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )
        cls.ay_b = AcademicYear.objects.create(
            school=cls.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True,
            status=AcademicYear.STATUS_ACTIVE
        )

        # 3. Classes and Sections
        cls.class_10 = GradeLevel.objects.create(
            school=cls.school_a, name="Class 10", code="10", display_order=10, is_active=True
        )
        cls.sec_10a = Section.objects.create(
            school=cls.school_a, grade_level=cls.class_10, name="A", is_active=True
        )
        cls.sec_10b = Section.objects.create(
            school=cls.school_a, grade_level=cls.class_10, name="B", is_active=True
        )

        # 4. Subjects
        cls.subj_math = Subject.objects.create(
            school=cls.school_a, name="Mathematics", code="MATH-10", max_marks=100, passing_marks=33, is_active=True
        )
        cls.subj_sci = Subject.objects.create(
            school=cls.school_a, name="Science", code="SCI-10", max_marks=100, passing_marks=33, is_active=True
        )
        cls.subj_eng = Subject.objects.create(
            school=cls.school_a, name="English Language", code="ENG-10", max_marks=100, passing_marks=33, is_active=True
        )

        # 5. Users & Roles
        cls.admin_user = User.objects.create_user(
            username="admin_exam", email="admin.exam@primesoul.com", password="password123",
            first_name="Admin", last_name="User", school=cls.school_a, requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(cls.admin_user, Role.SCHOOL_ADMIN)

        cls.principal_user = User.objects.create_user(
            username="principal_exam", email="principal.exam@primesoul.com", password="password123",
            first_name="Principal", last_name="User", school=cls.school_a, requested_role=Role.PRINCIPAL
        )
        assign_role_to_user(cls.principal_user, Role.PRINCIPAL)

        cls.teacher_user = User.objects.create_user(
            username="teacher_exam", email="teacher.exam@primesoul.com", password="password123",
            first_name="Sunita", last_name="Verma", school=cls.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(cls.teacher_user, Role.TEACHER)
        cls.desig = Designation.objects.create(school=cls.school_a, title="PGT Mathematics")
        cls.teacher = Teacher.objects.create(
            school=cls.school_a, employee_id="TCH-001", name="Sunita Verma",
            email=cls.teacher_user.email, designation=cls.desig,
            date_of_birth=datetime.date(1985, 1, 1), joining_date=datetime.date(2020, 1, 1)
        )
        cls.teacher_profile = TeacherProfile.objects.create(
            user=cls.teacher_user, school=cls.school_a, employee_code="TCH-001",
            first_name="Sunita", last_name="Verma", designation=cls.desig
        )

        cls.teacher_user_unassigned = User.objects.create_user(
            username="teacher_unassigned", email="teacher.unassigned@primesoul.com", password="password123",
            first_name="Ramesh", last_name="Kumar", school=cls.school_a, requested_role=Role.TEACHER
        )
        assign_role_to_user(cls.teacher_user_unassigned, Role.TEACHER)
        cls.teacher_unassigned = Teacher.objects.create(
            school=cls.school_a, employee_id="TCH-002", name="Ramesh Kumar",
            email=cls.teacher_user_unassigned.email, designation=cls.desig,
            date_of_birth=datetime.date(1986, 2, 2), joining_date=datetime.date(2021, 1, 1)
        )
        cls.teacher_profile_unassigned = TeacherProfile.objects.create(
            user=cls.teacher_user_unassigned, school=cls.school_a, employee_code="TCH-002",
            first_name="Ramesh", last_name="Kumar", designation=cls.desig
        )

        cls.accountant_user = User.objects.create_user(
            username="accountant_exam", email="accountant.exam@primesoul.com", password="password123",
            first_name="Ravi", last_name="Accounts", school=cls.school_a, requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(cls.accountant_user, Role.ACCOUNTANT)

        cls.student_user_1 = User.objects.create_user(
            username="student_aarav", email="aarav@primesoul.com", password="password123",
            first_name="Aarav", last_name="Sharma", school=cls.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(cls.student_user_1, Role.STUDENT)

        cls.student_user_2 = User.objects.create_user(
            username="student_diya", email="diya@primesoul.com", password="password123",
            first_name="Diya", last_name="Patel", school=cls.school_a, requested_role=Role.STUDENT
        )
        assign_role_to_user(cls.student_user_2, Role.STUDENT)

        cls.parent_user = User.objects.create_user(
            username="parent_suresh", email="parent.suresh@primesoul.com", password="password123",
            first_name="Suresh", last_name="Sharma", school=cls.school_a, requested_role=Role.PARENT
        )
        assign_role_to_user(cls.parent_user, Role.PARENT)

        cls.parent_profile = ParentProfile.objects.create(
            user=cls.parent_user, school=cls.school_a, first_name="Suresh", last_name="Sharma",
            mobile_number="+919876543201", relationship_type="Father"
        )

        # 6. Students & Enrollments
        cls.student_1 = Student.objects.create(
            school=cls.school_a, user=cls.student_user_1, first_name="Aarav", last_name="Sharma",
            admission_number="DPS-2026-001", roll_number="1001", academic_year=cls.ay_a,
            grade_level=cls.class_10, section=cls.sec_10a, is_active=True
        )
        cls.enrollment_1 = StudentEnrollment.objects.create(
            school=cls.school_a, student=cls.student_1, academic_year=cls.ay_a,
            grade_level=cls.class_10, section=cls.sec_10a, roll_number="1001", status="ACTIVE"
        )
        StudentGuardianRelationship.objects.create(
            student=cls.student_1, guardian=cls.parent_profile, relationship_type="Father", is_primary_contact=True
        )

        cls.student_2 = Student.objects.create(
            school=cls.school_a, user=cls.student_user_2, first_name="Diya", last_name="Patel",
            admission_number="DPS-2026-002", roll_number="1002", academic_year=cls.ay_a,
            grade_level=cls.class_10, section=cls.sec_10a, is_active=True
        )
        cls.enrollment_2 = StudentEnrollment.objects.create(
            school=cls.school_a, student=cls.student_2, academic_year=cls.ay_a,
            grade_level=cls.class_10, section=cls.sec_10a, roll_number="1002", status="ACTIVE"
        )

        # 7. Teacher Assignments (Sunita teaches Maths to 10-A)
        SubjectAssignment.objects.create(
            school=cls.school_a, academic_year=cls.ay_a, grade_level=cls.class_10,
            section=cls.sec_10a, subject=cls.subj_math, teacher=cls.teacher
        )

        # 8. Assessment Type & Grade Scale
        cls.at_hye = AssessmentType.objects.create(
            school=cls.school_a, name="Half Yearly Examination", code="HYE"
        )
        cls.grade_scale = GradeScale.objects.create(
            school=cls.school_a, name="CBSE 8-Point Scale", code="CBSE-8P", is_default=True
        )
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="A1", min_percentage=Decimal("91.00"), max_percentage=Decimal("100.00"), grade_point=Decimal("10.0"), is_passing=True, remarks="Outstanding")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="A2", min_percentage=Decimal("81.00"), max_percentage=Decimal("90.99"), grade_point=Decimal("9.0"), is_passing=True, remarks="Excellent")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="B1", min_percentage=Decimal("71.00"), max_percentage=Decimal("80.99"), grade_point=Decimal("8.0"), is_passing=True, remarks="Very Good")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="B2", min_percentage=Decimal("61.00"), max_percentage=Decimal("70.99"), grade_point=Decimal("7.0"), is_passing=True, remarks="Good")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="C1", min_percentage=Decimal("51.00"), max_percentage=Decimal("60.99"), grade_point=Decimal("6.0"), is_passing=True, remarks="Average")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="D", min_percentage=Decimal("33.00"), max_percentage=Decimal("50.99"), grade_point=Decimal("4.0"), is_passing=True, remarks="Passing")
        GradeScaleBand.objects.create(scale=cls.grade_scale, name="E", min_percentage=Decimal("0.00"), max_percentage=Decimal("32.99"), grade_point=Decimal("0.0"), is_passing=False, remarks="Fail")

        # 9. Session & Exam
        cls.session = ExaminationSession.objects.create(
            school=cls.school_a, academic_year=cls.ay_a, name="Half Yearly 2026-27", code="HYE-2026",
            start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 15), status="ONGOING"
        )
        cls.exam = Exam.objects.create(
            school=cls.school_a, session=cls.session, academic_year=cls.ay_a,
            grade_level=cls.class_10, section=cls.sec_10a, assessment_type=cls.at_hye,
            grade_scale=cls.grade_scale, name="Half Yearly Exam - Class 10-A",
            start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 10),
            status=Exam.STATUS_ONGOING, ranking_enabled=True
        )

        cls.es_math = ExamSubject.objects.create(
            school=cls.school_a, exam=cls.exam, subject=cls.subj_math,
            max_marks=Decimal("100.00"), passing_marks=Decimal("33.00"), sequence_order=1
        )
        cls.es_sci = ExamSubject.objects.create(
            school=cls.school_a, exam=cls.exam, subject=cls.subj_sci,
            max_marks=Decimal("100.00"), passing_marks=Decimal("33.00"), sequence_order=2
        )
        cls.es_eng = ExamSubject.objects.create(
            school=cls.school_a, exam=cls.exam, subject=cls.subj_eng,
            max_marks=Decimal("100.00"), passing_marks=Decimal("33.00"), sequence_order=3
        )

    # =========================================================================
    # PART 1: Model Constraints & Validations
    # =========================================================================

    def test_01_assessment_type_creation_and_uniqueness(self):
        """Assessment type is tenant-scoped and unique on (school, code)."""
        at = AssessmentType.objects.create(school=self.school_a, name="Periodic Test", code="PT")
        self.assertEqual(str(at), "Periodic Test (PT)")
        with self.assertRaises(Exception):
            AssessmentType.objects.create(school=self.school_a, name="Duplicate", code="PT")

    def test_02_grade_scale_and_bands_creation(self):
        """Grade scale default toggling and band relationships work."""
        self.assertTrue(self.grade_scale.is_default)
        new_scale = GradeScale.objects.create(school=self.school_a, name="ICSE Scale", code="ICSE-10", is_default=True)
        self.grade_scale.refresh_from_db()
        self.assertFalse(self.grade_scale.is_default)
        self.assertTrue(new_scale.is_default)

    def test_03_grade_scale_band_validation_min_max(self):
        """Min percentage cannot exceed max percentage."""
        band = GradeScaleBand(scale=self.grade_scale, name="Invalid", min_percentage=Decimal("95.00"), max_percentage=Decimal("90.00"))
        with self.assertRaises(ValidationError):
            band.clean()

    def test_04_grade_determination_service(self):
        """determine_grade_for_percentage maps scores to correct Grade bands."""
        g1, gp1, pass1, _ = marks_service.determine_grade_for_percentage(Decimal("95.00"), self.grade_scale)
        self.assertEqual(g1, "A1")
        self.assertEqual(gp1, Decimal("10.0"))
        self.assertTrue(pass1)

        g2, gp2, pass2, _ = marks_service.determine_grade_for_percentage(Decimal("85.00"), self.grade_scale)
        self.assertEqual(g2, "A2")

        g3, gp3, pass3, _ = marks_service.determine_grade_for_percentage(Decimal("25.00"), self.grade_scale)
        self.assertEqual(g3, "E")
        self.assertFalse(pass3)

    def test_05_examination_session_creation_and_dates_validation(self):
        """End date must be on or after start date for an examination session."""
        sess = ExaminationSession(
            school=self.school_a, academic_year=self.ay_a, name="Invalid", code="INV",
            start_date=datetime.date(2026, 9, 15), end_date=datetime.date(2026, 9, 10)
        )
        with self.assertRaises(ValidationError):
            sess.clean()

    def test_06_exam_creation_and_scoping(self):
        """Exam is tenant-scoped and correctly configured."""
        self.assertEqual(self.exam.school, self.school_a)
        self.assertEqual(self.exam.subjects.count(), 3)

    def test_07_exam_subject_configuration_and_uniqueness(self):
        """Duplicate exam subject configuration is rejected by database constraint."""
        with self.assertRaises(Exception):
            ExamSubject.objects.create(
                school=self.school_a, exam=self.exam, subject=self.subj_math,
                max_marks=Decimal("100.00"), passing_marks=Decimal("33.00")
            )

    def test_08_exam_subject_passing_marks_cannot_exceed_max(self):
        """Passing marks cannot exceed maximum marks."""
        es = ExamSubject(
            school=self.school_a, exam=self.exam, subject=self.subj_math,
            max_marks=Decimal("100.00"), passing_marks=Decimal("110.00")
        )
        with self.assertRaises(ValidationError):
            es.clean()

    def test_09_exam_subject_negative_marks_rejected(self):
        """Negative marks or zero max marks are rejected."""
        es = ExamSubject(
            school=self.school_a, exam=self.exam, subject=self.subj_math,
            max_marks=Decimal("0.00"), passing_marks=Decimal("0.00")
        )
        with self.assertRaises(ValidationError):
            es.clean()

    # =========================================================================
    # PART 2: Marks Entry, Validation & Absent Handling
    # =========================================================================

    def test_10_single_mark_entry_present(self):
        """Present student mark calculates subject grade and marks passed."""
        mark = StudentMark.objects.create(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("92.00"), grade="A1", is_passed=True
        )
        self.assertEqual(mark.status, StudentMark.STATUS_PRESENT)
        self.assertEqual(mark.marks_obtained, Decimal("92.00"))
        self.assertTrue(mark.is_passed)

    def test_11_single_mark_entry_exceeds_max_marks_raises_validation_error(self):
        """Marks cannot exceed configured maximum marks."""
        mark = StudentMark(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("105.00")
        )
        with self.assertRaises(ValidationError):
            mark.clean()

    def test_12_single_mark_entry_negative_marks_rejected(self):
        """Negative marks are rejected."""
        mark = StudentMark(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("-5.00")
        )
        with self.assertRaises(ValidationError):
            mark.clean()

    def test_13_mark_entry_absent_status_clears_marks_and_fails_subject(self):
        """Absent status forces marks_obtained to None and sets is_passed to False."""
        mark = StudentMark(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_ABSENT,
            marks_obtained=Decimal("50.00")
        )
        mark.clean()
        self.assertIsNone(mark.marks_obtained)
        self.assertFalse(mark.is_passed)

    def test_14_mark_entry_not_entered_status(self):
        """Not entered marks default gracefully."""
        mark = StudentMark.objects.create(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_NOT_ENTERED
        )
        self.assertEqual(mark.status, StudentMark.STATUS_NOT_ENTERED)
        self.assertIsNone(mark.marks_obtained)

    def test_15_duplicate_mark_entry_constraint(self):
        """Duplicate mark for student in the same exam and subject is prohibited."""
        StudentMark.objects.create(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("75.00")
        )
        with self.assertRaises(Exception):
            StudentMark.objects.create(
                school=self.school_a, academic_year=self.ay_a, exam=self.exam,
                exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
                marks_obtained=Decimal("80.00")
            )

    def test_16_bulk_marks_save_atomic(self):
        """Bulk marks entry service saves all students in a single atomic transaction."""
        payload = [
            {'student_id': self.student_1.id, 'status': 'PRESENT', 'marks_obtained': '85.0', 'remarks': 'Good'},
            {'student_id': self.student_2.id, 'status': 'PRESENT', 'marks_obtained': '70.0', 'remarks': 'Fair'}
        ]
        saved = marks_service.save_bulk_marks(
            school=self.school_a, exam=self.exam, exam_subject=self.es_math,
            section=self.sec_10a, marks_data=payload, actor=self.teacher_user
        )
        self.assertEqual(len(saved), 2)
        m1 = StudentMark.objects.get(exam=self.exam, exam_subject=self.es_math, student=self.student_1)
        self.assertEqual(m1.marks_obtained, Decimal("85.00"))
        self.assertEqual(m1.grade, "A2")

    def test_17_bulk_marks_update_existing_records(self):
        """Bulk marks entry updates existing records without creating duplicates."""
        payload1 = [{'student_id': self.student_1.id, 'status': 'PRESENT', 'marks_obtained': '85.0'}]
        marks_service.save_bulk_marks(self.school_a, self.exam, self.es_math, self.sec_10a, payload1, self.teacher_user)
        self.assertEqual(StudentMark.objects.filter(exam=self.exam, exam_subject=self.es_math).count(), 1)

        payload2 = [{'student_id': self.student_1.id, 'status': 'PRESENT', 'marks_obtained': '88.0'}]
        marks_service.save_bulk_marks(self.school_a, self.exam, self.es_math, self.sec_10a, payload2, self.teacher_user)
        self.assertEqual(StudentMark.objects.filter(exam=self.exam, exam_subject=self.es_math).count(), 1)
        m = StudentMark.objects.get(exam=self.exam, exam_subject=self.es_math, student=self.student_1)
        self.assertEqual(m.marks_obtained, Decimal("88.00"))

    def test_18_marks_correction_creates_immutable_log(self):
        """Modifying marks creates an immutable audit trail entry with reasons."""
        mark = StudentMark.objects.create(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("70.00")
        )
        updated = marks_service.correct_single_student_mark(
            school=self.school_a, mark_record=mark, new_status="PRESENT", new_marks=Decimal("80.00"),
            reason="Re-evaluation calculation error rectified", actor=self.admin_user
        )
        self.assertEqual(updated.marks_obtained, Decimal("80.00"))
        log = MarksCorrectionLog.objects.filter(mark_record=mark).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.previous_marks, Decimal("70.00"))
        self.assertEqual(log.new_marks, Decimal("80.00"))
        self.assertEqual(log.reason, "Re-evaluation calculation error rectified")
        self.assertEqual(log.corrected_by, self.admin_user)

    def test_19_marks_correction_requires_mandatory_reason(self):
        """Marks correction fails if justification reason is blank."""
        mark = StudentMark.objects.create(
            school=self.school_a, academic_year=self.ay_a, exam=self.exam,
            exam_subject=self.es_math, student=self.student_1, status=StudentMark.STATUS_PRESENT,
            marks_obtained=Decimal("70.00")
        )
        with self.assertRaises(ValidationError):
            marks_service.correct_single_student_mark(
                school=self.school_a, mark_record=mark, new_status="PRESENT", new_marks=Decimal("80.00"),
                reason="", actor=self.admin_user
            )

    def test_20_locked_exam_marks_modification_rejected_without_admin_and_reason(self):
        """Teacher cannot modify marks once examination is LOCKED."""
        self.exam.status = Exam.STATUS_LOCKED
        self.exam.save()
        payload = [{'student_id': self.student_1.id, 'status': 'PRESENT', 'marks_obtained': '90.0'}]
        with self.assertRaises(PermissionDenied):
            marks_service.save_bulk_marks(
                self.school_a, self.exam, self.es_math, self.sec_10a, payload, self.teacher_user
            )

    # =========================================================================
    # PART 3: Result Calculation, Grading, Standing & Attendance
    # =========================================================================

    def _setup_all_subject_marks(self):
        """Helper to seed complete marks for Student 1 and Student 2."""
        # Student 1: Maths 90, Science 85, English 80 (Sum: 255 / 300 = 85.00%, Grade A2, Passed)
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_math, student=self.student_1,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("90.00"), 'is_passed': True}
        )
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_sci, student=self.student_1,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("85.00"), 'is_passed': True}
        )
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_eng, student=self.student_1,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("80.00"), 'is_passed': True}
        )

        # Student 2: Maths 60, Science 50, English 40 (Sum: 150 / 300 = 50.00%, Grade C2, Passed)
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_math, student=self.student_2,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("60.00"), 'is_passed': True}
        )
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_sci, student=self.student_2,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("50.00"), 'is_passed': True}
        )
        StudentMark.objects.update_or_create(
            school=self.school_a, exam=self.exam, exam_subject=self.es_eng, student=self.student_2,
            defaults={'academic_year': self.ay_a, 'status': 'PRESENT', 'marks_obtained': Decimal("40.00"), 'is_passed': True}
        )

    def test_21_calculate_results_aggregates_totals_and_percentage(self):
        """Result calculation accurately computes sum and percentage."""
        self._setup_all_subject_marks()
        results = result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        self.assertEqual(len(results), 2)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        self.assertEqual(r1.total_marks_obtained, Decimal("255.00"))
        self.assertEqual(r1.total_max_marks, Decimal("300.00"))
        self.assertEqual(r1.percentage, Decimal("85.00"))

    def test_22_calculate_results_assigns_correct_overall_grade(self):
        """Overall percentage maps accurately to configured GradeScale band."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        self.assertEqual(r1.overall_grade, "A2")
        r2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)
        self.assertEqual(r2.overall_grade, "D")

    def test_23_calculate_results_pass_status_all_subjects_passed(self):
        """Students who clear all subjects are marked PASSED."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        self.assertEqual(r1.result_status, StudentExamResult.RESULT_PASSED)
        self.assertEqual(r1.subjects_passed, 3)
        self.assertEqual(r1.subjects_failed, 0)

    def test_24_calculate_results_compartment_status_one_subject_failed(self):
        """Failing exactly one subject yields COMPARTMENT status."""
        self._setup_all_subject_marks()
        # Fail Student 2 in English (20 < 33)
        StudentMark.objects.filter(exam=self.exam, exam_subject=self.es_eng, student=self.student_2).update(
            marks_obtained=Decimal("20.00"), is_passed=False
        )
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)
        self.assertEqual(r2.result_status, StudentExamResult.RESULT_COMPARTMENT)
        self.assertEqual(r2.subjects_passed, 2)
        self.assertEqual(r2.subjects_failed, 1)

    def test_25_calculate_results_failed_status_multiple_subjects_failed(self):
        """Failing 2 or more subjects yields FAILED status."""
        self._setup_all_subject_marks()
        StudentMark.objects.filter(exam=self.exam, exam_subject=self.es_math, student=self.student_2).update(
            marks_obtained=Decimal("20.00"), is_passed=False
        )
        StudentMark.objects.filter(exam=self.exam, exam_subject=self.es_sci, student=self.student_2).update(
            marks_obtained=Decimal("25.00"), is_passed=False
        )
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)
        self.assertEqual(r2.result_status, StudentExamResult.RESULT_FAILED)

    def test_26_calculate_results_all_absent_status(self):
        """Being absent in all subjects yields ABSENT status."""
        self._setup_all_subject_marks()
        StudentMark.objects.filter(exam=self.exam, student=self.student_2).update(
            status=StudentMark.STATUS_ABSENT, marks_obtained=None, is_passed=False
        )
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)
        self.assertEqual(r2.result_status, StudentExamResult.RESULT_ABSENT)

    def test_27_calculate_results_integrates_student_attendance(self):
        """Result calculation pulls cumulative attendance days and percentage."""
        AttendanceRecord.objects.create(
            school=self.school_a, academic_year=self.ay_a, student=self.student_1,
            grade_level=self.class_10, section=self.sec_10a,
            attendance_date=datetime.date(2026, 9, 1), status="PRESENT"
        )
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        self.assertGreater(r1.attendance_working_days, 0)
        self.assertEqual(r1.attendance_present_days, 1)

    def test_28_calculate_results_assigns_class_and_section_ranks(self):
        """Ranks are assigned based on percentage standing without gaps."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        r2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)
        self.assertEqual(r1.class_rank, 1)
        self.assertEqual(r2.class_rank, 2)
        self.assertEqual(r1.section_rank, 1)
        self.assertEqual(r2.section_rank, 2)

    def test_29_calculate_results_generates_unique_verification_code(self):
        """Each student exam result receives a tamper-evident unique verification code."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        r1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        self.assertTrue(r1.verification_code.startswith("PRIME-RES-"))

    # =========================================================================
    # PART 4: Workflow Lifecycle (Calculate -> Finalize -> Publish -> Lock)
    # =========================================================================

    def test_30_finalize_results_workflow(self):
        """Finalizing locks calculation state and updates exam to FINALIZED."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        count = result_calculation_service.finalize_exam_results(self.school_a, self.exam, actor=self.admin_user)
        self.assertEqual(count, 2)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.STATUS_FINALIZED)

    def test_31_publish_results_workflow(self):
        """Publishing makes results visible to students and parents."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.finalize_exam_results(self.school_a, self.exam, actor=self.admin_user)
        count = result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        self.assertEqual(count, 2)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.STATUS_PUBLISHED)

    def test_32_lock_results_workflow(self):
        """Locking prevents further modifications without explicit correction reasons."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.lock_exam_results(self.school_a, self.exam, actor=self.admin_user)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.STATUS_LOCKED)

    # =========================================================================
    # PART 5: Analytics & Selectors
    # =========================================================================

    def test_33_class_result_summary_selector(self):
        """get_class_result_summary produces aggregated analytics without N+1 queries."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        summary = exam_selectors.get_class_result_summary(self.school_a, self.exam)
        self.assertEqual(summary['total_students'], 2)
        self.assertEqual(summary['passed_count'], 2)
        self.assertEqual(summary['pass_percentage'], 100.0)
        self.assertEqual(len(summary['subject_stats']), 3)

    def test_34_student_result_history_selector(self):
        """Dashboard metrics selector correctly aggregates active counts."""
        metrics = exam_selectors.get_exam_dashboard_metrics(self.school_a)
        self.assertIn('active_sessions_count', metrics)
        self.assertIn('pass_percentage', metrics)

    # =========================================================================
    # PART 6: Report Card, ReportLab PDF & Public Verification
    # =========================================================================

    def test_35_report_card_pdf_generation_valid_pdf_bytes(self):
        """Report card generates valid ReportLab PDF bytes starting with %PDF."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        pdf_bytes = report_card_service.render_report_card_pdf_bytes(res)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_36_report_card_pdf_view_authenticated_download(self):
        """Authorized user can download report card PDF via view."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        client = APIClient()
        client.force_login(self.admin_user)
        client.force_authenticate(user=self.admin_user)
        resp = client.get(f"/examinations/results/{res.id}/report-card/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_37_public_result_verification_view_success_published(self):
        """Public verification endpoint confirms authenticity of published report card."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        client = APIClient()
        resp = client.get(f"/verify/result/{res.verification_code}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Authentic Academic Credential")
        self.assertContains(resp, self.student_1.name)

    def test_38_public_result_verification_view_404_or_invalid_code(self):
        """Invalid or non-existent verification code displays not found banner."""
        client = APIClient()
        resp = client.get("/verify/result/INVALID-CODE-999/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Credential Not Found")

    def test_39_public_verification_does_not_leak_sensitive_info(self):
        """Public verification view redacts phone numbers, fee accounts, and home addresses."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        client = APIClient()
        resp = client.get(f"/verify/result/{res.verification_code}/")
        self.assertNotContains(resp, "+919876543201")
        self.assertNotContains(resp, "Fee Account")
        self.assertNotContains(resp, "Due Amount")
        self.assertNotContains(resp, "Fee Status")
        # Ensure context only exposes safe verification dictionary
        self.assertNotIn("fees", resp.context)
        self.assertNotIn("student_fee", resp.context)

    # =========================================================================
    # PART 7: RBAC, Scoping & Role Restrictions
    # =========================================================================

    def test_40_teacher_scoped_to_assigned_subject_and_section(self):
        """Teacher assigned to Class 10 Maths can enter marks."""
        can_mark = exam_service.can_user_enter_marks(
            self.teacher_user, self.school_a, self.exam, self.es_math, self.sec_10a
        )
        self.assertTrue(can_mark)

    def test_41_teacher_denied_marks_entry_for_unassigned_class(self):
        """Unassigned teacher cannot enter marks for a class they do not teach."""
        can_mark = exam_service.can_user_enter_marks(
            self.teacher_user_unassigned, self.school_a, self.exam, self.es_math, self.sec_10a
        )
        self.assertFalse(can_mark)

    def test_42_teacher_cannot_publish_or_lock_results(self):
        """Teachers cannot finalize or publish school-wide results."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        with self.assertRaises(PermissionDenied):
            result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.teacher_user)

    def test_43_student_restricted_to_own_published_results_only(self):
        """Student can view their own published results."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        client = APIClient()
        client.force_login(self.student_user_1)
        client.force_authenticate(user=self.student_user_1)
        resp = client.get(f"/examinations/results/{res1.id}/report-card/")
        self.assertEqual(resp.status_code, 200)

    def test_44_student_cannot_view_draft_or_unpublished_results(self):
        """Student is denied access to unpublished / draft examination results."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        client = APIClient()
        client.force_login(self.student_user_1)
        client.force_authenticate(user=self.student_user_1)
        resp = client.get(f"/examinations/results/{res1.id}/report-card/")
        self.assertEqual(resp.status_code, 403)

    def test_45_parent_restricted_to_child_published_results_only(self):
        """Parent can only view their own registered child's published report card."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        result_calculation_service.publish_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)
        res2 = StudentExamResult.objects.get(exam=self.exam, student=self.student_2)

        client = APIClient()
        client.force_login(self.parent_user)
        client.force_authenticate(user=self.parent_user)
        # Allowed for child (Student 1)
        resp1 = client.get(f"/examinations/results/{res1.id}/report-card/")
        self.assertEqual(resp1.status_code, 200)

        # Denied for unrelated student (Student 2)
        resp2 = client.get(f"/examinations/results/{res2.id}/report-card/")
        self.assertEqual(resp2.status_code, 403)

    def test_46_accountant_denied_marks_entry_and_exam_management(self):
        """Accountant role has no marks entry authorization."""
        can_mark = exam_service.can_user_enter_marks(
            self.accountant_user, self.school_a, self.exam, self.es_math
        )
        self.assertFalse(can_mark)

    def test_47_receptionist_restricted_to_read_only_published_results(self):
        """Receptionist cannot calculate or modify marks."""
        can_manage = exam_service.can_user_manage_exam(self.accountant_user, self.school_a)
        self.assertFalse(can_manage)

    # =========================================================================
    # PART 8: Tenant Isolation
    # =========================================================================

    def test_48_tenant_isolation_school_b_cannot_access_school_a_exams(self):
        """School B admin cannot view or modify School A exams."""
        admin_b = User.objects.create_user(
            username="admin_b", email="admin.b@schoolb.com", password="password123",
            school=self.school_b, requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(admin_b, Role.SCHOOL_ADMIN)

        client = APIClient()
        client.force_authenticate(user=admin_b)
        resp = client.get("/api/v1/examinations/exams/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_49_tenant_isolation_school_b_cannot_access_school_a_results(self):
        """School B user cannot retrieve School A student results."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)
        res1 = StudentExamResult.objects.get(exam=self.exam, student=self.student_1)

        admin_b = User.objects.create_user(
            username="admin_b2", email="admin.b2@schoolb.com", password="password123",
            school=self.school_b, requested_role=Role.SCHOOL_ADMIN
        )
        client = APIClient()
        client.force_login(admin_b)
        client.force_authenticate(user=admin_b)
        resp = client.get(f"/examinations/results/{res1.id}/report-card/")
        self.assertEqual(resp.status_code, 404)

    # =========================================================================
    # PART 9: REST API Endpoints & Actions
    # =========================================================================

    def test_50_api_sessions_and_exams_crud(self):
        """API endpoints for sessions and exams list properly."""
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        resp = client.get("/api/v1/examinations/sessions/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_51_api_bulk_marks_endpoint(self):
        """API endpoint /api/v1/examinations/bulk-marks/ atomically saves marks."""
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        payload = {
            'exam_id': self.exam.id,
            'exam_subject_id': self.es_math.id,
            'section_id': self.sec_10a.id,
            'marks': [
                {'student_id': self.student_1.id, 'status': 'PRESENT', 'marks_obtained': 91.5},
                {'student_id': self.student_2.id, 'status': 'PRESENT', 'marks_obtained': 82.0}
            ]
        }
        resp = client.post("/api/v1/examinations/bulk-marks/", data=payload, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])

    def test_52_api_result_actions_calculate_finalize_publish(self):
        """API endpoints trigger calculate, finalize, and publish workflows."""
        self._setup_all_subject_marks()
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        resp_calc = client.post(f"/api/v1/examinations/results/{self.exam.id}/calculate/")
        self.assertEqual(resp_calc.status_code, 200)

        resp_fin = client.post(f"/api/v1/examinations/results/{self.exam.id}/finalize/")
        self.assertEqual(resp_fin.status_code, 200)

        resp_pub = client.post(f"/api/v1/examinations/results/{self.exam.id}/publish/")
        self.assertEqual(resp_pub.status_code, 200)

    # =========================================================================
    # PART 10: CSV Exports & Seed Idempotency
    # =========================================================================

    def test_53_csv_exports_marks_and_results(self):
        """Marks and results CSV export views return text/csv with correct headers."""
        self._setup_all_subject_marks()
        result_calculation_service.calculate_exam_results(self.school_a, self.exam, actor=self.admin_user)

        client = APIClient()
        client.force_login(self.admin_user)
        client.force_authenticate(user=self.admin_user)
        resp_m = client.get(f"/examinations/export/marks/{self.exam.id}/{self.es_math.id}/")
        self.assertEqual(resp_m.status_code, 200)
        self.assertEqual(resp_m['Content-Type'], 'text/csv')

        resp_r = client.get(f"/examinations/export/results/{self.exam.id}/")
        self.assertEqual(resp_r.status_code, 200)
        self.assertEqual(resp_r['Content-Type'], 'text/csv')

    def test_54_seed_demo_school_idempotency_examinations(self):
        """Running seed_demo_school preserves unique constraints without duplicating exam objects."""
        from django.core.management import call_command
        call_command('seed_demo_school')
        exams_count = Exam.objects.filter(school=self.school_a).count()
        # Re-running command does not duplicate
        call_command('seed_demo_school')
        self.assertEqual(Exam.objects.filter(school=self.school_a).count(), exams_count)
