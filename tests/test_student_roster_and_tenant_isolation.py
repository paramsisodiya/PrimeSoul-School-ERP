from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, Department, Semester, AcademicSession
from django_school_management.students.models import Student, AdmissionStudent
from django_school_management.institute.models import InstituteProfile
from django_school_management.core.services.csv_import_service import StudentCSVImporter

User = get_user_model()


class StudentRosterAndTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # School A
        self.school_a = School.objects.create(
            name="PrimeSoul Higher Secondary School",
            slug="primesoul-hss",
            is_active=True
        )
        self.ay_a = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_current=True
        )
        self.grade10_a = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="10",
            display_order=10
        )
        self.sec_a = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade10_a,
            name="A"
        )

        # Admin user for School A
        self.admin_a = User.objects.create_superuser(
            username="admin_a",
            email="admin.a@example.com",
            password="adminpassword123"
        )
        self.admin_a.school = self.school_a
        self.admin_a.requested_role = "admin"
        self.admin_a.approval_status = "a"
        self.admin_a.save()

        # School B
        self.school_b = School.objects.create(
            name="Other Academy",
            slug="other-academy",
            is_active=True
        )
        self.ay_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_current=True
        )
        self.grade10_b = GradeLevel.objects.create(
            school=self.school_b,
            name="Class 10",
            code="10",
            display_order=10
        )
        self.sec_b = Section.objects.create(
            school=self.school_b,
            grade_level=self.grade10_b,
            name="A"
        )

        # Admin user for School B
        self.admin_b = User.objects.create_user(
            username="admin_b",
            email="admin.b@example.com",
            password="adminpassword123"
        )
        self.admin_b.school = self.school_b
        self.admin_b.requested_role = "admin"
        self.admin_b.approval_status = "a"
        self.admin_b.is_staff = True
        self.admin_b.save()

    def test_modern_school_students_appear_in_roster(self):
        """A. Modern school students with admission_student=NULL appear in /students/all/."""
        stu1 = Student.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade10_a,
            section=self.sec_a,
            first_name="Aarav",
            last_name="Sharma",
            roll_number="101",
            admission_number="ADM-001",
            is_active=True
        )
        self.assertIsNone(stu1.admission_student)

        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("students:all_student"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aarav Sharma")
        self.assertContains(response, "ADM-001")
        self.assertContains(response, "Class 10 - Section A")
        self.assertEqual(len(response.context["students"]), 1)

    def test_legacy_students_remain_compatible(self):
        """B. Legacy students with admission_student and institute linkage remain visible in roster."""
        inst = InstituteProfile.objects.create(
            name="Legacy Institute",
            active=True
        )
        dept = Department.objects.create(
            name="Computer Science",
            code="101",
            institute=inst
        )
        adm_stu = AdmissionStudent.objects.create(
            name="Legacy Student",
            department_choice=dept,
            choosen_department=dept,
            admitted=True,
            paid=True
        )
        sem = Semester.objects.create(number=1)
        sess = AcademicSession.objects.create(year=2026)
        legacy_stu = Student.objects.create(
            admission_student=adm_stu,
            semester=sem,
            ac_session=sess,
            temporary_id="LEG-999",
            roll="55"
        )

        legacy_admin = User.objects.create_user(
            username="legacy_admin",
            email="legacy.admin@example.com",
            password="adminpassword123"
        )
        legacy_admin.institute = inst
        legacy_admin.requested_role = "admin"
        legacy_admin.approval_status = "a"
        legacy_admin.is_staff = True
        legacy_admin.save()

        self.client.force_login(legacy_admin)
        response = self.client.get(reverse("students:all_student"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legacy Student")
        self.assertContains(response, "LEG-999")

    def test_tenant_isolation_school_a_vs_school_b(self):
        """C. A student from School A does not appear in School B's roster."""
        stu_a = Student.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade10_a,
            section=self.sec_a,
            first_name="SchoolAStudent",
            admission_number="ADM-A-01",
            is_active=True
        )
        stu_b = Student.objects.create(
            school=self.school_b,
            academic_year=self.ay_b,
            grade_level=self.grade10_b,
            section=self.sec_b,
            first_name="SchoolBStudent",
            admission_number="ADM-B-01",
            is_active=True
        )

        # Admin B sees only School B students
        self.client.force_login(self.admin_b)
        response_b = self.client.get(reverse("students:all_student"))
        self.assertEqual(response_b.status_code, 200)
        self.assertContains(response_b, "SchoolBStudent")
        self.assertNotContains(response_b, "SchoolAStudent")

        # Admin A sees only School A students
        self.client.force_login(self.admin_a)
        response_a = self.client.get(reverse("students:all_student"))
        self.assertEqual(response_a.status_code, 200)
        self.assertContains(response_a, "SchoolAStudent")
        self.assertNotContains(response_a, "SchoolBStudent")

    def test_student_sis_works_when_admission_student_is_null(self):
        """D. Student SIS profile loads without AttributeError when admission_student is NULL."""
        stu = Student.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade10_a,
            section=self.sec_a,
            first_name="Rohan",
            last_name="Verma",
            admission_number="ADM-100",
            roll_number="12",
            emergency_contact_number="+919876543210",
            is_active=True
        )
        self.assertIsNone(stu.admission_student)

        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("students:student_sis", kwargs={"pk": stu.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rohan Verma")
        self.assertContains(response, "Class 10 (Section A)")
        self.assertContains(response, "ADM-100")
        self.assertContains(response, "Session 2026-2027")

    def test_student_deletion_respects_tenant_boundary(self):
        """E. Admin of School B cannot delete School A's student."""
        stu_a = Student.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade10_a,
            section=self.sec_a,
            first_name="ProtectedStudent",
            admission_number="ADM-PROT-1",
            is_active=True
        )

        self.client.force_login(self.admin_b)
        response = self.client.get(reverse("students:delete_student", kwargs={"pk": stu_a.pk}))
        # Must return 404 because student is not in School B
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Student.objects.filter(pk=stu_a.pk).exists())

        # Admin A can delete their own student
        self.client.force_login(self.admin_a)
        response_del = self.client.get(reverse("students:delete_student", kwargs={"pk": stu_a.pk}))
        self.assertEqual(response_del.status_code, 302)
        self.assertFalse(Student.objects.filter(pk=stu_a.pk).exists())

    def test_dashboard_and_roster_count_agree_after_csv_import(self):
        """F. 5 students imported via CSV bulk import agree between Dashboard and Roster."""
        csv_data = """admission_number,first_name,last_name,grade_code,section_name,roll_number,gender,date_of_birth,mobile_number,father_name,mother_name,address
ADM-2026-0001,Aarav,Sharma,10,A,101,M,2010-05-12,9876543210,Rajesh Sharma,Pooja Sharma,New Delhi
ADM-2026-0002,Diya,Patel,10,A,102,F,2010-08-22,9876543211,Suresh Patel,Meena Patel,New Delhi
ADM-2026-0003,Ishaan,Verma,10,A,103,M,2010-03-15,9876543212,Anil Verma,Sunita Verma,New Delhi
ADM-2026-0004,Ananya,Singh,10,A,104,F,2010-11-05,9876543213,Vikram Singh,Kavita Singh,New Delhi
ADM-2026-0005,Kabir,Mehta,10,A,105,M,2010-07-19,9876543214,Rakesh Mehta,Anita Mehta,New Delhi
"""
        result = StudentCSVImporter.import_csv(school=self.school_a, file_content=csv_data)
        self.assertEqual(result.imported_rows, 5)
        self.assertEqual(len(result.errors), 0)

        # 1. Check Dashboard count
        self.client.force_login(self.admin_a)
        dash_response = self.client.get(reverse("index_view"))
        self.assertEqual(dash_response.status_code, 200)
        self.assertEqual(dash_response.context["total_students"], 5)

        # 2. Check Students Roster count and content
        roster_response = self.client.get(reverse("students:all_student"))
        self.assertEqual(roster_response.status_code, 200)
        self.assertEqual(len(roster_response.context["students"]), 5)
        self.assertContains(roster_response, "Aarav Sharma")
        self.assertContains(roster_response, "Diya Patel")
        self.assertContains(roster_response, "Ishaan Verma")
        self.assertContains(roster_response, "Ananya Singh")
        self.assertContains(roster_response, "Kabir Mehta")
        self.assertNotContains(roster_response, "No Student Data Found")
