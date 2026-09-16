"""
Phase 15: PrimeSoul ERP Admissions Management Test Suite.
Validates complete Indian K-12 admissions lifecycle: Intake Sessions, Class Seat Quotas, Enquiries,
Applications, Document Verification, Review Workflows, Interview Scheduling, Assessment,
Capacity Checks, Concurrency-Safe Number Generation, Atomic Conversion to Student + ParentProfile + Enrollment,
Public Application Flows, and REST APIs.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from django_school_management.admissions.services.admission_service import (
    generate_application_number, generate_admission_number,
    create_admission_enquiry, create_admission_application,
    transition_application_status, verify_admission_document,
    schedule_admission_interview, record_assessment,
    approve_and_admit_student
)
from django_school_management.admissions.selectors.admissions_selectors import (
    get_admissions_dashboard_metrics, get_class_seat_availability,
    get_applications_list, get_application_detail, get_active_admission_session
)

User = get_user_model()


class PrimeSoulAdmissionsTests(TestCase):
    """
    Comprehensive test suite for Phase 15: Admissions Management.
    """

    def setUp(self):
        ensure_system_roles_exist()

        # 1. Tenants
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

        # 2. Academic Setup
        self.ay_2026 = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_current=True
        )
        self.grade_nursery = GradeLevel.objects.create(
            school=self.school_a,
            name="Nursery",
            code="NUR",
            display_order=0,
            is_active=True
        )
        self.grade_1 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 1",
            code="CLASS-1",
            display_order=1,
            is_active=True
        )
        self.sec_1a = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade_1,
            name="A"
        )

        # 3. Staff Users
        self.admin_user = User.objects.create_user(
            username="admissions_officer",
            email="admissions@dps.edu",
            password="Password123!",
            first_name="Anita",
            last_name="Deshmukh"
        )
        self.admin_user.school = self.school_a
        self.admin_user.save()
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.school_b_admin = User.objects.create_user(
            username="admin_modern",
            email="admin@modern.edu",
            password="Password123!",
            first_name="Rohan",
            last_name="Kapoor"
        )
        self.school_b_admin.school = self.school_b
        self.school_b_admin.save()
        assign_role_to_user(self.school_b_admin, Role.SCHOOL_ADMIN)

        # 4. Admission Session & Class Config
        self.session_2026 = AdmissionSession.objects.create(
            school=self.school_a,
            name="Academic Session 2026-27 Admissions",
            academic_year=self.ay_2026,
            application_start="2025-12-01",
            application_end="2026-03-15",
            admission_start="2026-01-10",
            admission_end="2026-03-31",
            status=AdmissionSession.STATUS_OPEN,
            application_number_prefix="APP-2026",
            admission_number_prefix="ADM-2026",
            active=True
        )

        self.config_grade_1 = AdmissionClassConfig.objects.create(
            school=self.school_a,
            admission_session=self.session_2026,
            grade_level=self.grade_1,
            total_seats=2,  # Configured to 2 for quota limit testing
            reserved_seats=0,
            application_fee=Decimal("500.00"),
            active=True
        )

        # API Client
        self.client = APIClient()

    def test_01_admission_session_lifecycle(self):
        """Validates admission session creation, date ranges, and is_open property."""
        session = AdmissionSession.objects.create(
            school=self.school_a,
            name="Session 2027-28 Draft",
            academic_year=self.ay_2026,
            application_start="2026-12-01",
            application_end="2027-03-15",
            admission_start="2027-01-10",
            admission_end="2027-03-31",
            status=AdmissionSession.STATUS_DRAFT,
            active=True
        )
        self.assertFalse(session.is_open)
        session.status = AdmissionSession.STATUS_OPEN
        session.save()
        self.assertTrue(session.is_open)

    def test_02_class_seat_configuration(self):
        """Validates seat quotas and fee configuration per class."""
        config = AdmissionClassConfig.objects.create(
            school=self.school_a,
            admission_session=self.session_2026,
            grade_level=self.grade_nursery,
            total_seats=45,
            reserved_seats=10,
            application_fee=Decimal("1000.00"),
            active=True
        )
        self.assertEqual(config.total_seats, 45)
        self.assertEqual(config.reserved_seats, 10)
        self.assertEqual(config.application_fee, Decimal("1000.00"))

    def test_03_enquiry_creation_and_mobile_validation(self):
        """Enquiry creation validates 10-digit Indian mobile and rejects invalid strings."""
        enquiry = create_admission_enquiry(
            school=self.school_a,
            admission_session=self.session_2026,
            student_name="Vivaan Sharma",
            parent_name="Rohit Sharma",
            mobile="9876543210",
            interested_grade=self.grade_1,
            email="rohit@example.com",
            source=AdmissionEnquiry.SOURCE_WALK_IN,
            notes="Interested in Class 1 CBSE."
        )
        self.assertEqual(enquiry.student_name, "Vivaan Sharma")
        self.assertEqual(enquiry.mobile, "9876543210")
        self.assertTrue(enquiry.enquiry_number.startswith("ENQ-"))

        # Invalid phone raises ValidationError
        with self.assertRaises(ValidationError):
            create_admission_enquiry(
                school=self.school_a,
                admission_session=self.session_2026,
                student_name="Invalid Phone Child",
                parent_name="Parent",
                mobile="12345",  # Invalid
                interested_grade=self.grade_1
            )

    def test_04_enquiry_status_transition(self):
        """Enquiry status updates correctly across follow-ups."""
        enquiry = create_admission_enquiry(
            school=self.school_a,
            admission_session=self.session_2026,
            student_name="Siddharth Roy",
            parent_name="Anil Roy",
            mobile="9876543212",
            interested_grade=self.grade_1
        )
        self.assertEqual(enquiry.status, AdmissionEnquiry.STATUS_NEW)

        enquiry.status = AdmissionEnquiry.STATUS_CONTACTED
        enquiry.save()
        self.assertEqual(enquiry.status, AdmissionEnquiry.STATUS_CONTACTED)

    def test_05_application_creation_and_unique_app_number(self):
        """Application creation generates consecutive unique application numbers."""
        app1 = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Ananya",
            last_name="Gupta",
            date_of_birth="2020-05-15",
            gender="F",
            requested_grade=self.grade_1,
            father_name="Suresh Gupta",
            father_mobile="9876543213",
            father_email="suresh@example.com"
        )
        app2 = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Kabir",
            last_name="Sen",
            date_of_birth="2020-08-20",
            gender="M",
            requested_grade=self.grade_1,
            father_name="Vikram Sen",
            father_mobile="9876543214"
        )

        self.assertEqual(app1.application_number, "APP-2026-00001")
        self.assertEqual(app2.application_number, "APP-2026-00002")
        self.assertNotEqual(app1.application_number, app2.application_number)

    def test_06_document_upload_and_verification(self):
        """Documents can be uploaded and verified or rejected with audit remarks."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Pooja",
            last_name="Hegde",
            date_of_birth="2020-03-10",
            gender="F",
            requested_grade=self.grade_1,
            father_mobile="9876543215"
        )
        doc = AdmissionDocument.objects.create(
            school=self.school_a,
            application=app,
            document_type=AdmissionDocument.TYPE_BIRTH_CERTIFICATE,
            title="Municipal Birth Certificate",
            file="admissions/documents/test_bc.pdf",
            status=AdmissionDocument.STATUS_PENDING
        )
        self.assertEqual(doc.status, AdmissionDocument.STATUS_PENDING)

        verify_admission_document(doc, is_verified=True, user=self.admin_user)
        doc.refresh_from_db()
        self.assertEqual(doc.status, AdmissionDocument.STATUS_VERIFIED)
        self.assertEqual(doc.verified_by, self.admin_user)
        self.assertIsNotNone(doc.verified_at)

    def test_07_review_workflow_valid_transitions(self):
        """Application transitions smoothly across valid workflow stages."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Rohan",
            last_name="Bose",
            date_of_birth="2020-01-12",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543216"
        )
        self.assertEqual(app.status, AdmissionApplication.STATUS_SUBMITTED)

        # Submitted -> Under Review
        transition_application_status(app, AdmissionApplication.STATUS_UNDER_REVIEW, user=self.admin_user, remarks="Documents verified.")
        app.refresh_from_db()
        self.assertEqual(app.status, AdmissionApplication.STATUS_UNDER_REVIEW)

        # Under Review -> Shortlisted
        transition_application_status(app, AdmissionApplication.STATUS_SHORTLISTED, user=self.admin_user, remarks="Eligible for interview.")
        app.refresh_from_db()
        self.assertEqual(app.status, AdmissionApplication.STATUS_SHORTLISTED)

        # Shortlisted -> Approved
        transition_application_status(app, AdmissionApplication.STATUS_APPROVED, user=self.admin_user, remarks="Selected for admission.")
        app.refresh_from_db()
        self.assertEqual(app.status, AdmissionApplication.STATUS_APPROVED)

    def test_08_review_workflow_invalid_transition_prevention(self):
        """State machine rejects invalid transitions (e.g. Draft -> Admitted directly)."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Test",
            last_name="Child",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543217",
            status=AdmissionApplication.STATUS_DRAFT
        )
        with self.assertRaises(ValidationError):
            transition_application_status(app, AdmissionApplication.STATUS_ADMITTED, user=self.admin_user)

    def test_09_interview_scheduling_and_interaction(self):
        """Scheduling an interview creates interview record and updates status."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Isha",
            last_name="Patel",
            date_of_birth="2020-02-14",
            gender="F",
            requested_grade=self.grade_1,
            father_mobile="9876543218"
        )
        scheduled_time = timezone.now() + timezone.timedelta(days=3)
        interview = schedule_admission_interview(
            application=app,
            scheduled_at=scheduled_time,
            location="Admissions Room 101",
            interviewer=self.admin_user,
            user=self.admin_user
        )
        self.assertEqual(interview.application, app)
        self.assertEqual(interview.status, AdmissionInterview.STATUS_SCHEDULED)
        app.refresh_from_db()
        self.assertEqual(app.status, AdmissionApplication.STATUS_INTERVIEW)

    def test_10_assessment_score_recording(self):
        """Entrance assessment scores can be recorded."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Reyansh",
            last_name="Nair",
            date_of_birth="2020-07-11",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543219"
        )
        asm = record_assessment(
            application=app,
            subject="English Aptitude",
            score=Decimal("88.5"),
            max_score=Decimal("100.0"),
            user=self.admin_user,
            remarks="Excellent vocabulary."
        )
        self.assertEqual(asm.subject, "English Aptitude")
        self.assertEqual(asm.score, Decimal("88.5"))

    def test_11_seat_quota_enforcement(self):
        """Admission conversion enforces seat capacity limits configured in AdmissionClassConfig."""
        # Class 1 total seats configured to 2 in setUp
        # Admit Student 1
        app1 = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Seat1",
            last_name="Child",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_name="Father 1",
            father_mobile="9876543201"
        )
        approve_and_admit_student(app1, section=self.sec_1a, user=self.admin_user)

        # Admit Student 2
        app2 = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Seat2",
            last_name="Child",
            date_of_birth="2020-02-02",
            gender="F",
            requested_grade=self.grade_1,
            father_name="Father 2",
            father_mobile="9876543202"
        )
        approve_and_admit_student(app2, section=self.sec_1a, user=self.admin_user)

        # Attempting Student 3 should raise ValidationError (quota full: 2/2)
        app3 = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Seat3",
            last_name="Child",
            date_of_birth="2020-03-03",
            gender="M",
            requested_grade=self.grade_1,
            father_name="Father 3",
            father_mobile="9876543203"
        )
        with self.assertRaises(ValidationError) as cm:
            approve_and_admit_student(app3, section=self.sec_1a, user=self.admin_user)
        self.assertIn("quota for Class 1 is full", str(cm.exception))

    def test_12_duplicate_admission_prevention(self):
        """Prevent admitting an already admitted applicant."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Arjun",
            last_name="Reddy",
            date_of_birth="2020-04-04",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543220"
        )
        approve_and_admit_student(app, section=self.sec_1a, user=self.admin_user)

        # Attempting to admit again raises ValidationError
        with self.assertRaises(ValidationError):
            approve_and_admit_student(app, section=self.sec_1a, user=self.admin_user)

    def test_13_atomic_student_creation_on_admission(self):
        """Admitting an applicant creates Student, ParentProfile, GuardianRelationship, and Enrollment atomically."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Diya",
            middle_name="Kumari",
            last_name="Singh",
            date_of_birth="2020-09-09",
            gender="F",
            blood_group="B+",
            nationality="Indian",
            category="General",
            aadhaar_number="123456789012",
            requested_grade=self.grade_1,
            father_name="Ramesh Singh",
            father_mobile="9876543221",
            father_email="ramesh@example.com",
            father_occupation="Engineer",
            mother_name="Sunita Singh",
            mother_mobile="9876543222",
            current_address="Flat 402, Green Valley Apartments, Delhi"
        )

        student = approve_and_admit_student(
            application=app,
            section=self.sec_1a,
            roll_number="15",
            user=self.admin_user
        )

        # 1. Student verification
        self.assertIsNotNone(student)
        self.assertEqual(student.first_name, "Diya")
        self.assertEqual(student.last_name, "Singh")
        self.assertEqual(student.grade_level, self.grade_1)
        self.assertEqual(student.section, self.sec_1a)
        self.assertEqual(student.roll_number, "15")
        self.assertEqual(student.aadhaar_number, "123456789012")
        self.assertTrue(student.admission_number.startswith("ADM-2026-"))

        # 2. ParentProfile verification
        father_profile = ParentProfile.objects.filter(school=self.school_a, mobile_number="9876543221").first()
        self.assertIsNotNone(father_profile)
        self.assertEqual(father_profile.first_name, "Ramesh Singh")

        # 3. StudentGuardianRelationship verification
        rel = StudentGuardianRelationship.objects.filter(student=student, guardian=father_profile).first()
        self.assertIsNotNone(rel)
        self.assertTrue(rel.is_primary_contact)

        # 4. StudentEnrollment verification
        enrollment = StudentEnrollment.objects.filter(student=student, academic_year=self.ay_2026).first()
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.status, StudentEnrollment.STATUS_ACTIVE)
        self.assertEqual(enrollment.grade_level, self.grade_1)
        self.assertEqual(enrollment.section, self.sec_1a)

        # 5. Application status verification
        app.refresh_from_db()
        self.assertEqual(app.status, AdmissionApplication.STATUS_ADMITTED)
        self.assertEqual(app.admitted_student, student)

    def test_14_tenant_isolation_in_admissions(self):
        """School A applications are strictly hidden from School B."""
        app_a = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Child A",
            last_name="DPS",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543223"
        )

        ay_b = AcademicYear.objects.create(school=self.school_b, name="2026-2027", start_date="2026-04-01", end_date="2027-03-31")
        grade_b = GradeLevel.objects.create(school=self.school_b, name="Class 1", code="C1", display_order=1)
        session_b = AdmissionSession.objects.create(
            school=self.school_b,
            name="Modern School Session 2026",
            academic_year=ay_b,
            application_start="2025-12-01",
            application_end="2026-03-15",
            admission_start="2026-01-10",
            admission_end="2026-03-31",
            status=AdmissionSession.STATUS_OPEN
        )
        app_b = create_admission_application(
            school=self.school_b,
            admission_session=session_b,
            first_name="Child B",
            last_name="Modern",
            date_of_birth="2020-01-01",
            gender="F",
            requested_grade=grade_b,
            father_mobile="9876543224"
        )

        apps_a = get_applications_list(self.school_a)
        apps_b = get_applications_list(self.school_b)

        self.assertIn(app_a, apps_a)
        self.assertNotIn(app_b, apps_a)
        self.assertIn(app_b, apps_b)
        self.assertNotIn(app_a, apps_b)

    def test_15_admissions_dashboard_metrics(self):
        """Aggregated admissions metrics reflect accurate counts and conversion rates."""
        create_admission_enquiry(
            school=self.school_a,
            admission_session=self.session_2026,
            student_name="Enquiry 1",
            parent_name="Parent 1",
            mobile="9876543225",
            interested_grade=self.grade_1
        )
        create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="App 1",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543226"
        )

        metrics = get_admissions_dashboard_metrics(self.school_a)
        self.assertEqual(metrics['total_enquiries'], 1)
        self.assertEqual(metrics['total_applications'], 1)
        self.assertEqual(metrics['total_configured_seats'], 2)
        self.assertEqual(metrics['seats_remaining'], 2)

    def test_16_public_admission_apply_workflow(self):
        """Public online application creates application without staff authentication."""
        resp = self.client.post('/api/v1/admissions/public/apply/', {
            'first_name': 'Aanya',
            'last_name': 'Mehta',
            'date_of_birth': '2020-06-12',
            'gender': 'F',
            'requested_grade': self.grade_1.id,
            'father_name': 'Sunil Mehta',
            'father_mobile': '9876543227',
            'current_address': 'Sector 14, Gurugram'
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('application_number', resp.data)
        self.assertEqual(resp.data['student_name'], 'Aanya Mehta')

    def test_17_public_admission_status_lookup(self):
        """Public status lookup succeeds with correct application number and date of birth."""
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Navya",
            last_name="Kapoor",
            date_of_birth="2020-11-25",
            gender="F",
            requested_grade=self.grade_1,
            father_mobile="9876543228"
        )
        resp = self.client.get(f'/api/v1/admissions/public/status/?app_num={app.application_number}&dob=2020-11-25')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['application_number'], app.application_number)
        self.assertEqual(resp.data['status'], AdmissionApplication.STATUS_SUBMITTED)

        # Invalid DOB returns 404
        resp_bad = self.client.get(f'/api/v1/admissions/public/status/?app_num={app.application_number}&dob=2019-01-01')
        self.assertEqual(resp_bad.status_code, status.HTTP_404_NOT_FOUND)

    def test_18_admissions_rest_api_endpoints(self):
        """Validates DRF endpoints for admissions session, enquiries, applications, and conversion."""
        self.client.force_authenticate(user=self.admin_user)

        # 1. Sessions List
        resp = self.client.get('/api/v1/admissions/sessions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Enquiries List
        resp = self.client.get('/api/v1/admissions/enquiries/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 3. Applications List
        resp = self.client.get('/api/v1/admissions/applications/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 4. Review Application API
        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="API",
            last_name="Student",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543229"
        )
        resp = self.client.post(f'/api/v1/admissions/applications/{app.pk}/review/', {
            'status': AdmissionApplication.STATUS_APPROVED,
            'remarks': 'Approved via API.'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], AdmissionApplication.STATUS_APPROVED)

        # 5. Convert Application API
        resp_conv = self.client.post(f'/api/v1/admissions/applications/{app.pk}/convert/', {
            'section_id': self.sec_1a.id,
            'roll_number': '20'
        }, format='json')
        self.assertEqual(resp_conv.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_conv.data['status'], 'admitted')
        self.assertIn('admission_number', resp_conv.data)

    def test_19_enquiry_converted_on_application_creation(self):
        """When an application is created with a linked enquiry, the enquiry status updates to CONVERTED."""
        enq = create_admission_enquiry(
            school=self.school_a,
            admission_session=self.session_2026,
            student_name="Linked Child",
            parent_name="Linked Parent",
            mobile="9876543230",
            interested_grade=self.grade_1
        )
        self.assertEqual(enq.status, AdmissionEnquiry.STATUS_NEW)

        app = create_admission_application(
            school=self.school_a,
            admission_session=self.session_2026,
            first_name="Linked",
            last_name="Child",
            date_of_birth="2020-01-01",
            gender="M",
            requested_grade=self.grade_1,
            father_mobile="9876543230",
            enquiry=enq
        )
        enq.refresh_from_db()
        self.assertEqual(enq.status, AdmissionEnquiry.STATUS_CONVERTED)
