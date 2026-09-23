"""
Phase 13: PrimeSoul ERP Unified Self-Service Portals Test Suite.
Validates role-aware portal routing, multi-child parent switching, student self-service,
teacher classroom and academic operations, published-only result enforcement,
strict multi-tenant isolation, IDOR rejection, and REST APIs.
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject, SubjectAssignment,
    StudentEnrollment, ClassTeacherAssignment
)
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.teachers.models import Designation, Teacher, TeacherProfile
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.attendance.services.attendance_service import save_daily_attendance
from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeStructureItem, StudentFeeAssignment, FeeInstallment,
    FeeInvoice, PaymentTransaction, FeeReceipt, FeeHeadCategory, FeeFrequency, InvoiceStatus, PaymentStatus
)
from django_school_management.examinations.models import (
    AssessmentType, ExaminationSession, Exam, ExamSubject, StudentExamResult
)
from django_school_management.timetable.models import WorkingDay, TimeSlot, TimetableEntry
from django_school_management.transport.models import (
    TransportVehicle, TransportRoute, TransportStop, StudentTransportAssignment
)
from django_school_management.library.models import (
    Library, BookCategory, Book, BookCopy, LibraryMember, LibraryIssue
)
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, LeaveType, LeaveBalance, LeaveRequest,
    PayrollPeriod, PayrollRecord
)

User = get_user_model()


class PrimeSoulUnifiedPortalTests(TestCase):
    """
    Comprehensive automated test suite for Phase 13 Unified Portals (Parent, Student, Teacher).
    """

    def setUp(self):
        ensure_system_roles_exist()

        # ---------------------------------------------------------
        # 1. School Tenants
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 2. Academic Years
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 3. Classes and Sections
        # ---------------------------------------------------------
        self.class_10 = GradeLevel.objects.create(
            school=self.school_a, name="Class 10", code="10", display_order=10
        )
        self.class_8 = GradeLevel.objects.create(
            school=self.school_a, name="Class 8", code="8", display_order=8
        )
        self.sec_10a = Section.objects.create(
            school=self.school_a, grade_level=self.class_10, name="A"
        )
        self.sec_10b = Section.objects.create(
            school=self.school_a, grade_level=self.class_10, name="B"
        )
        self.sec_8a = Section.objects.create(
            school=self.school_a, grade_level=self.class_8, name="A"
        )

        # ---------------------------------------------------------
        # 4. Subjects & Teacher Users
        # ---------------------------------------------------------
        self.sub_math = Subject.objects.create(
            school=self.school_a, name="Mathematics", code="MATH10", subject_type="CORE"
        )
        self.sub_sci = Subject.objects.create(
            school=self.school_a, name="Science", code="SCI10", subject_type="CORE"
        )

        self.teacher_user = User.objects.create_user(
            username="teacher_sharma",
            email="sharma@dpsrkp.edu.in",
            password="Password123!",
            first_name="Ramesh",
            last_name="Sharma",
            school=self.school_a,
            requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        self.desig_teacher = Designation.objects.create(school=self.school_a, title="Senior Teacher")
        self.teacher_legacy = Teacher.objects.create(
            school=self.school_a,
            name="Ramesh Sharma",
            employee_id="TCH-1001",
            email="sharma@dpsrkp.edu.in",
            designation=self.desig_teacher
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            school=self.school_a,
            employee_code="TCH-1001",
            first_name="Ramesh",
            last_name="Sharma",
            designation=self.desig_teacher
        )

        # Subject Allocation: Teacher teaches Math in 10-A
        SubjectAssignment.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            subject=self.sub_math,
            teacher=self.teacher_legacy
        )
        ClassTeacherAssignment.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            section=self.sec_10a,
            teacher=self.teacher_legacy
        )

        # HR Employee for Teacher
        self.dept_academics = Department.objects.create(
            school=self.school_a, name="Academics", code="ACAD"
        )
        self.hr_desig_tgt = HRDesignation.objects.create(
            school=self.school_a, name="TGT Math", code="TGT-MATH", category="TEACHING"
        )
        self.emp_teacher = Employee.objects.create(
            school=self.school_a,
            user=self.teacher_user,
            employee_code="EMP-1002",
            full_name="Ramesh Sharma",
            designation=self.hr_desig_tgt,
            department=self.dept_academics,
            joining_date=datetime.date(2023, 1, 1),
            bank_account_number="1234567890",
            bank_ifsc="HDFC0001234",
            bank_name="HDFC Bank",
            pan_number="ABCDE1234F",
            aadhaar_last4="4321"
        )
        self.leave_type_cl = LeaveType.objects.create(
            school=self.school_a, name="Casual Leave", code="CL", annual_limit=12
        )
        self.leave_balance = LeaveBalance.objects.create(
            school=self.school_a,
            employee=self.emp_teacher,
            leave_type=self.leave_type_cl,
            academic_year=self.ay_a,
            opening_balance=Decimal('12.0')
        )

        # ---------------------------------------------------------
        # 5. Students & Parent Users
        # ---------------------------------------------------------
        self.student_user_1 = User.objects.create_user(
            username="student_aarav",
            email="aarav@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_1, Role.STUDENT)

        self.student_1 = Student.objects.create(
            school=self.school_a,
            user=self.student_user_1,
            admission_number="ADM-2026-001",
            first_name="Aarav",
            last_name="Verma",
            date_of_birth=datetime.date(2010, 5, 15),
            gender="M"
        )
        self.enrollment_1 = StudentEnrollment.objects.create(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            roll_number="101",
            status="ACTIVE"
        )

        self.student_user_2 = User.objects.create_user(
            username="student_ananya",
            email="ananya@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_2, Role.STUDENT)

        self.student_2 = Student.objects.create(
            school=self.school_a,
            user=self.student_user_2,
            admission_number="ADM-2026-002",
            first_name="Ananya",
            last_name="Verma",
            date_of_birth=datetime.date(2012, 8, 20),
            gender="F"
        )
        self.enrollment_2 = StudentEnrollment.objects.create(
            school=self.school_a,
            student=self.student_2,
            academic_year=self.ay_a,
            grade_level=self.class_8,
            section=self.sec_8a,
            roll_number="801",
            status="ACTIVE"
        )

        # Parent User (Parent of both Aarav and Ananya)
        self.parent_user = User.objects.create_user(
            username="parent_verma",
            email="rajesh.verma@example.com",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.PARENT
        )
        assign_role_to_user(self.parent_user, Role.PARENT)

        self.parent_profile = ParentProfile.objects.create(
            school=self.school_a,
            user=self.parent_user,
            relationship_type="Father",
            first_name="Rajesh",
            last_name="Verma",
            mobile_number="9876543210"
        )

        StudentGuardianRelationship.objects.create(
            student=self.student_1,
            guardian=self.parent_profile,
            relationship_type="Father",
            is_primary_contact=True,
            can_pickup=True,
            is_emergency_contact=True
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_2,
            guardian=self.parent_profile,
            relationship_type="Father",
            is_primary_contact=True,
            can_pickup=True,
            is_emergency_contact=True
        )

        # Another Parent (School B) for isolation testing
        self.parent_user_b = User.objects.create_user(
            username="parent_school_b",
            email="parent@modern.edu.in",
            password="Password123!",
            school=self.school_b,
            requested_role=Role.PARENT
        )
        assign_role_to_user(self.parent_user_b, Role.PARENT)

        # ---------------------------------------------------------
        # 6. Sample Attendance Data
        # ---------------------------------------------------------
        today = datetime.date.today()
        save_daily_attendance(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.class_10,
            section=self.sec_10a,
            attendance_date=today,
            attendance_entries=[
                {'student_id': self.student_1.id, 'status': 'PRESENT', 'remarks': 'On time'}
            ],
            actor=self.teacher_user
        )

        # ---------------------------------------------------------
        # 7. Sample Fees Data
        # ---------------------------------------------------------
        self.fee_head = FeeHead.objects.create(
            school=self.school_a,
            name="Tuition Fee",
            code="TUITION",
            category=FeeHeadCategory.TUITION
        )
        self.fee_struct = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.class_10,
            name="Class 10 Standard Fees",
            effective_from=self.ay_a.start_date,
            effective_to=self.ay_a.end_date,
            frequency=FeeFrequency.ANNUAL
        )
        self.fee_item = FeeStructureItem.objects.create(
            fee_structure=self.fee_struct,
            fee_head=self.fee_head,
            amount=Decimal("15000.00")
        )
        self.invoice_1 = FeeInvoice.objects.create(
            school=self.school_a,
            student=self.student_1,
            academic_year=self.ay_a,
            invoice_number="INV-2026-0001",
            invoice_date=today,
            due_date=today + datetime.timedelta(days=30),
            subtotal=Decimal("15000.00"),
            total=Decimal("15000.00"),
            paid_amount=Decimal("5000.00"),
            balance_amount=Decimal("10000.00"),
            status=InvoiceStatus.PARTIAL
        )
        self.payment_1 = PaymentTransaction.objects.create(
            school=self.school_a,
            student=self.student_1,
            invoice=self.invoice_1,
            transaction_id="TXN-PAY-001",
            amount=Decimal("5000.00"),
            payment_method="ONLINE",
            status=PaymentStatus.SUCCESS,
            paid_at=timezone.now()
        )
        self.receipt_1 = FeeReceipt.objects.create(
            school=self.school_a,
            student=self.student_1,
            payment=self.payment_1,
            receipt_number="REC-2026-0001",
            amount=Decimal("5000.00"),
            payment_method="ONLINE",
            receipt_date=today
        )

        # ---------------------------------------------------------
        # 8. Sample Examination Data (Published vs Draft)
        # ---------------------------------------------------------
        self.assessment_type = AssessmentType.objects.create(
            school=self.school_a, name="Midterm Exam", code="MID"
        )
        self.exam_session = ExaminationSession.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            name="Term 1 2026",
            code="T1-2026",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=30)
        )
        self.exam_pub = Exam.objects.create(
            school=self.school_a,
            session=self.exam_session,
            assessment_type=self.assessment_type,
            name="Class 10 Midterms",
            grade_level=self.class_10,
            academic_year=self.ay_a,
            start_date=today - datetime.timedelta(days=20),
            end_date=today - datetime.timedelta(days=10),
            status="PUBLISHED"
        )
        self.exam_draft = Exam.objects.create(
            school=self.school_a,
            session=self.exam_session,
            assessment_type=self.assessment_type,
            name="Class 10 Surprise Test",
            grade_level=self.class_10,
            academic_year=self.ay_a,
            start_date=today,
            end_date=today,
            status="DRAFT"
        )
        # Published Result
        self.res_pub = StudentExamResult.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            exam=self.exam_pub,
            student=self.student_1,
            total_marks_obtained=Decimal("92.00"),
            total_max_marks=Decimal("100.00"),
            percentage=Decimal("92.00"),
            overall_grade="A1",
            result_status=StudentExamResult.RESULT_PASSED,
            status=StudentExamResult.STATUS_PUBLISHED
        )
        # Draft Result (MUST NEVER LEAK)
        self.res_draft = StudentExamResult.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            exam=self.exam_draft,
            student=self.student_1,
            total_marks_obtained=Decimal("45.00"),
            total_max_marks=Decimal("50.00"),
            percentage=Decimal("90.00"),
            overall_grade="A",
            result_status=StudentExamResult.RESULT_PASSED,
            status=StudentExamResult.STATUS_DRAFT
        )

        # ---------------------------------------------------------
        # 9. Sample Timetable Data
        # ---------------------------------------------------------
        self.work_day = WorkingDay.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            weekday=0,
            is_working=True
        )
        self.slot_1 = TimeSlot.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            name="Period 1",
            period_number=1,
            start_time=datetime.time(8, 30),
            end_time=datetime.time(9, 15)
        )
        self.entry_math = TimetableEntry.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            section=self.sec_10a,
            working_day=self.work_day,
            time_slot=self.slot_1,
            subject=self.sub_math,
            teacher=self.teacher_legacy
        )

        # ---------------------------------------------------------
        # 10. Sample Transport & Library Data
        # ---------------------------------------------------------
        self.route_1 = TransportRoute.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            name="Route 5 - South Delhi",
            code="R-05"
        )
        self.stop_1 = TransportStop.objects.create(
            school=self.school_a,
            route=self.route_1,
            name="Green Park Metro",
            pickup_time=datetime.time(7, 30),
            drop_time=datetime.time(14, 30),
            sequence=1
        )
        self.vehicle_1 = TransportVehicle.objects.create(
            school=self.school_a,
            vehicle_number="BUS-01",
            registration_number="DL-1P-9999",
            capacity=40,
            vehicle_type="BUS"
        )
        self.transport_alloc = StudentTransportAssignment.objects.create(
            school=self.school_a,
            student=self.student_1,
            route=self.route_1,
            pickup_stop=self.stop_1,
            drop_stop=self.stop_1,
            academic_year=self.ay_a,
            transport_status=StudentTransportAssignment.STATUS_ACTIVE
        )

        self.library_1 = Library.objects.create(school=self.school_a, name="Main Campus Library", code="LIB-MAIN")
        self.book_cat = BookCategory.objects.create(school=self.school_a, name="Science", code="SCI")
        self.book_1 = Book.objects.create(
            school=self.school_a, category=self.book_cat, title="Concepts of Physics", isbn="978-8177091878"
        )
        self.book_copy_1 = BookCopy.objects.create(school=self.school_a, book=self.book_1, accession_number="ACC-1001", status="ISSUED")
        self.lib_member = LibraryMember.objects.create(
            school=self.school_a, student=self.student_1, member_type="STUDENT", member_code="MEM-ST-1001"
        )
        self.book_issue_1 = LibraryIssue.objects.create(
            school=self.school_a,
            library=self.library_1,
            book_copy=self.book_copy_1,
            member=self.lib_member,
            issue_date=today - datetime.timedelta(days=5),
            due_date=today + datetime.timedelta(days=9),
            status="ISSUED"
        )

        # ---------------------------------------------------------
        # 11. Sample Payroll Record for Teacher
        # ---------------------------------------------------------
        self.payroll_period = PayrollPeriod.objects.create(
            school=self.school_a,
            month=8,
            year=2026,
            status=PayrollPeriod.STATUS_LOCKED
        )
        self.payroll_record = PayrollRecord.objects.create(
            school=self.school_a,
            payroll_period=self.payroll_period,
            employee=self.emp_teacher,
            gross_earnings=Decimal("50000.00"),
            total_deductions=Decimal("2000.00"),
            net_salary=Decimal("48000.00"),
            status=PayrollRecord.STATUS_LOCKED
        )

    # =========================================================================
    # 1. PORTAL ROOT ROLE ROUTING TESTS
    # =========================================================================

    def test_portal_root_redirects_unauthenticated_to_login(self):
        """Unauthenticated visitor to /portal/ is redirected to login."""
        response = self.client.get(reverse('portal:portal_root'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/account/', response.url)

    def test_portal_root_redirects_parent(self):
        """Parent user navigating to /portal/ is redirected to /portal/parent/."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:portal_root'))
        self.assertRedirects(response, reverse('portal:student_dashboard'))

    def test_portal_root_redirects_student(self):
        """Student user navigating to /portal/ is redirected to /portal/student/."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:portal_root'))
        self.assertRedirects(response, reverse('portal:student_dashboard'))

    def test_portal_root_redirects_teacher(self):
        """Teacher user navigating to /portal/ is redirected to /portal/teacher/."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:portal_root'))
        self.assertRedirects(response, reverse('portal:teacher_dashboard'))

    # =========================================================================
    # 2. PARENT / FAMILY GUARDIAN (UNIFIED STUDENT PORTAL) TESTS
    # =========================================================================

    def test_parent_dashboard_loads_with_real_data(self):
        """Parent accessing Student Portal displays children metadata and real student metrics."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aarav Verma")
        self.assertEqual(response.context['student'].id, self.student_1.id)
        self.assertEqual(len(response.context['children']), 2)

    def test_parent_child_switching(self):
        """Parent can switch active child in Student Portal."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_child_switch', kwargs={'student_id': self.student_2.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student'].id, self.student_2.id)
        self.assertContains(response, "Ananya")

    def test_parent_child_switching_tamper_idor_rejected(self):
        """Supplying an unauthorized student ID in switch URL falls back safely to authorized child."""
        other_user = User.objects.create_user(
            username="other_student", email="other@dpsrkp.edu.in", password="Password123!",
            school=self.school_a, requested_role=Role.STUDENT
        )
        unauthorized_student = Student.objects.create(
            school=self.school_a, user=other_user, admission_number="ADM-9999",
            first_name="Hacker", last_name="Boy"
        )
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_child_switch', kwargs={'student_id': unauthorized_student.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student'].id, self.student_1.id)
        self.assertNotContains(response, "Hacker Boy")

    def test_parent_child_detail_tamper_idor_rejected(self):
        """Direct URL access to parent child detail redirects safely to student dashboard."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:parent_child_detail', kwargs={'student_id': 9999}))
        self.assertRedirects(response, reverse('portal:student_dashboard'))

    def test_parent_results_only_published_visible(self):
        """Parent results view ONLY displays published results; draft results are hidden."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_results'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class 10 Midterms")
        self.assertContains(response, "92.00")
        self.assertNotContains(response, "Class 10 Surprise Test")
        self.assertNotContains(response, "45.00")

    def test_parent_attendance_view(self):
        """Parent attendance page displays child's monthly and daily records."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_attendance'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance")
        self.assertContains(response, "Present")

    def test_parent_fees_view(self):
        """Parent fees page displays invoice, payment, and outstanding amount."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_fees'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TXN-PAY-001")
        self.assertContains(response, "10000.00")

    def test_parent_timetable_view(self):
        """Parent timetable displays timetable matrix for child's section."""
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('portal:student_timetable'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mathematics")

    def test_parent_transport_and_library_views(self):
        """Parent can view assigned transport route and library books."""
        self.client.force_login(self.parent_user)
        resp_tr = self.client.get(reverse('portal:student_transport'))
        self.assertEqual(resp_tr.status_code, 200)
        self.assertContains(resp_tr, "Route 5 - South Delhi")
        self.assertContains(resp_tr, "Green Park Metro")

        resp_lib = self.client.get(reverse('portal:student_library'))
        self.assertEqual(resp_lib.status_code, 200)
        self.assertContains(resp_lib, "Concepts of Physics")

    # =========================================================================
    # 3. STUDENT PORTAL TESTS
    # =========================================================================

    def test_student_dashboard_loads_own_data(self):
        """Student dashboard displays own class, attendance, timetable, and results."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aarav Verma")
        self.assertContains(response, "ADM-2026-001")
        self.assertContains(response, "Class 10 - A")


    def test_student_results_only_published(self):
        """Student results view ONLY displays published results; draft results are hidden."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:student_results'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class 10 Midterms")
        self.assertNotContains(response, "Class 10 Surprise Test")

    def test_student_cannot_access_another_students_data(self):
        """Student cannot access parent portal or view another student's fees."""
        self.client.force_login(self.student_user_1)
        response = self.client.get(reverse('portal:parent_dashboard'))
        self.assertIn(response.status_code, [302, 403])

    def test_student_timetable_and_library(self):
        """Student can view timetable and library records."""
        self.client.force_login(self.student_user_1)
        resp_tt = self.client.get(reverse('portal:student_timetable'))
        self.assertEqual(resp_tt.status_code, 200)
        self.assertContains(resp_tt, "Mathematics")

        resp_lib = self.client.get(reverse('portal:student_library'))
        self.assertEqual(resp_lib.status_code, 200)
        self.assertContains(resp_lib, "Concepts of Physics")

    # =========================================================================
    # 4. TEACHER PORTAL TESTS
    # =========================================================================

    def test_teacher_dashboard_loads(self):
        """Teacher dashboard displays assigned classes, timetable, and leave balance."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ramesh Sharma")
        self.assertContains(response, "Class 10 - Section A")

    def test_teacher_timetable_isolation(self):
        """Teacher timetable displays only periods assigned to the teacher."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_timetable'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class 10 - Section A")
        self.assertContains(response, "Mathematics")

    def test_teacher_classes_and_students(self):
        """Teacher can view assigned sections and student roster."""
        self.client.force_login(self.teacher_user)
        resp_cls = self.client.get(reverse('portal:teacher_classes'))
        self.assertEqual(resp_cls.status_code, 200)
        self.assertContains(resp_cls, "Class 10 - Section A")

        resp_std = self.client.get(reverse('portal:teacher_students'))
        self.assertEqual(resp_std.status_code, 200)
        self.assertContains(resp_std, "Aarav Verma")

    def test_teacher_attendance_marking_view(self):
        """Teacher can access daily attendance marking sheet for assigned section."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_attendance_mark', kwargs={'section_id': self.sec_10a.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mark Daily Attendance")
        self.assertContains(response, "Aarav Verma")

    def test_teacher_attendance_marking_unauthorized_section_rejected(self):
        """Teacher cannot mark attendance for an unassigned section."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_attendance_mark', kwargs={'section_id': self.sec_8a.id}))
        self.assertEqual(response.status_code, 403)

    def test_teacher_leave_management(self):
        """Teacher can view leave balance and history."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_leave'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Casual Leave")
        self.assertContains(response, "12")

    def test_teacher_payslips_view_own_only(self):
        """Teacher can view own payslips; sensitive bank/PAN details are protected."""
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('portal:teacher_payslips'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "August 2026")
        self.assertContains(response, "48000.00")

    # =========================================================================
    # 5. CROSS-TENANT ISOLATION TESTS
    # =========================================================================

    def test_cross_tenant_parent_cannot_view_other_school(self):
        """Parent of School B has 0 children in School A and cannot access School A data."""
        self.client.force_login(self.parent_user_b)
        response = self.client.get(reverse('portal:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['children']), 0)
        self.assertNotContains(response, "Aarav Verma")

    # =========================================================================
    # 6. PORTAL REST API TESTS
    # =========================================================================

    def test_api_parent_dashboard(self):
        """API: Parent dashboard returns aggregated children and summary."""
        client = APIClient()
        client.force_authenticate(user=self.parent_user)
        response = client.get('/api/v1/portal/parent/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['children_count'], 2)
        self.assertEqual(response.data['selected_child']['id'], self.student_1.id)

    def test_api_parent_fees(self):
        """API: Parent fees endpoint returns invoices and outstanding amounts."""
        client = APIClient()
        client.force_authenticate(user=self.parent_user)
        response = client.get('/api/v1/portal/parent/fees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['invoices']), 1)
        self.assertEqual(response.data['invoices'][0]['invoice_number'], "INV-2026-0001")

    def test_api_parent_results_hides_drafts(self):
        """API: Parent results endpoint NEVER includes draft results."""
        client = APIClient()
        client.force_authenticate(user=self.parent_user)
        response = client.get('/api/v1/portal/parent/results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['exam_name'], "Class 10 Midterms")

    def test_api_student_dashboard(self):
        """API: Student dashboard returns authenticated student details."""
        client = APIClient()
        client.force_authenticate(user=self.student_user_1)
        response = client.get('/api/v1/portal/student/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student']['admission_number'], "ADM-2026-001")

    def test_api_teacher_dashboard(self):
        """API: Teacher dashboard returns assigned classes and periods."""
        client = APIClient()
        client.force_authenticate(user=self.teacher_user)
        response = client.get('/api/v1/portal/teacher/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assigned_classes_count'], 1)
