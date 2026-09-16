import sys
import datetime
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from django_school_management.tenants.models import School, Domain, Subscription
from django_school_management.institute.models import InstituteProfile
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Department, AcademicSession, Batch,
    Subject, SubjectAssignment, StudentEnrollment, ClassTeacherAssignment
)
from django_school_management.teachers.models import Designation, TeacherProfile, Teacher
from django_school_management.students.models import Student, AdmissionStudent
from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeStructureItem, FeeConcession,
    StudentFeeAssignment, FeeInstallment, FeeInvoice, PaymentTransaction,
    FeeHeadCategory, FeeFrequency, ConcessionType, PaymentGateway,
    PaymentStatus, ChequeClearanceStatus, InvoiceStatus
)
from django_school_management.fees.services.installment_service import generate_student_installments
from django_school_management.fees.services.invoice_service import create_fee_invoice
from django_school_management.fees.services.payment_service import record_offline_payment, process_cheque_clearance
from django_school_management.fees.services.receipt_service import generate_fee_receipt
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.examinations.models import (
    AssessmentType, GradeScale, GradeScaleBand, ExaminationSession,
    Exam, ExamSubject, StudentMark, StudentExamResult
)
from django_school_management.examinations.services.result_calculation_service import (
    calculate_exam_results, finalize_exam_results, publish_exam_results
)
from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.transport.models import (
    TransportVehicle, TransportStaff, TransportRoute, TransportStop,
    VehicleRouteAssignment, StudentTransportAssignment
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a complete Indian K-12 Demo School with classes, verified users, and complete fee workflows."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-demo-dangerous',
            action='store_true',
            help='Force execution in production or non-debug environments (DANGEROUS).',
        )

    def handle(self, *args, **options):
        # Production Safety Guard
        is_testing = ('test' in sys.argv) or getattr(settings, 'TESTING', False)
        if not settings.DEBUG and not is_testing and not options.get('force_demo_dangerous'):
            raise CommandError(
                "CRITICAL SECURITY GUARD: 'seed_demo_school' cannot be run in production (DEBUG=False). "
                "Production databases must start clean with real school onboarding. "
                "If this is a staging/test environment, re-run with --force-demo-dangerous."
            )

        self.stdout.write(self.style.NOTICE("Seeding PrimeSoul School ERP Demo Environment..."))

        with transaction.atomic():
            # 1. Demo School Tenant
            school, _ = School.objects.get_or_create(
                slug="dps-rkpuram",
                defaults={
                    "name": "Delhi Public School, R.K. Puram",
                    "subdomain": "dps-rkpuram",
                    "board": "CBSE",
                    "affiliation_number": "CBSE/AFF/2026/1034",
                    "school_code": "DPS-1034",
                    "udise_code": "07010200301",
                    "recognition_number": "DEL-EDU-2026-9921",
                    "address": "Sector 12, R.K. Puram",
                    "city": "New Delhi",
                    "state": "Delhi",
                    "pincode": "110022",
                    "country": "India",
                    "timezone": "Asia/Kolkata",
                    "currency": "INR",
                    "is_active": True,
                    "onboarding_completed": True,
                }
            )
            school.onboarding_completed = True
            school.is_active = True
            school.save()

            # Domain & Subscription
            Domain.objects.get_or_create(
                school=school,
                domain="dps-rkpuram.primesoul.local",
                defaults={"is_primary": True, "is_verified": True}
            )
            Subscription.objects.get_or_create(
                school=school,
                defaults={"plan_name": "Enterprise Plan", "status": "active", "max_students": 5000}
            )

            # Legacy InstituteProfile for backward compatibility (safe lookup to prevent UNIQUE active constraint crash)
            institute = InstituteProfile.objects.filter(active=True).first()
            if not institute:
                institute, _ = InstituteProfile.objects.get_or_create(
                    name="Delhi Public School, R.K. Puram",
                    defaults={
                        "institute_type": "school",
                        "active": True,
                        "onboarding_completed": True,
                        "site_title": "Delhi Public School, R.K. Puram",
                        "site_header": "DPS R.K. Puram ERP",
                    }
                )
            else:
                institute.onboarding_completed = True
                institute.save()

            # 2. Academic Year (Indian April-March cycle)
            ay_start = datetime.date(2026, 4, 1)
            ay_end = datetime.date(2027, 3, 31)
            ay, _ = AcademicYear.objects.get_or_create(
                school=school,
                name="2026-2027",
                defaults={
                    "start_date": ay_start,
                    "end_date": ay_end,
                    "is_current": True,
                    "status": "ACTIVE",
                }
            )
            ay.is_current = True
            ay.status = "ACTIVE"
            ay.save()

            # Legacy AcademicSession
            session, _ = AcademicSession.objects.get_or_create(
                school=school,
                year=2026
            )

            # 3. Grade Levels & Sections
            grades_data = [
                ("Nursery", "NUR", 0, False),
                ("LKG", "LKG", 1, False),
                ("UKG", "UKG", 2, False),
                ("Class 1", "1", 3, False),
                ("Class 2", "2", 4, False),
                ("Class 3", "3", 5, False),
                ("Class 4", "4", 6, False),
                ("Class 5", "5", 7, False),
                ("Class 6", "6", 8, False),
                ("Class 7", "7", 9, False),
                ("Class 8", "8", 10, False),
                ("Class 9", "9", 11, False),
                ("Class 10", "10", 12, False),
                ("Class 11", "11", 13, True),
                ("Class 12", "12", 14, True),
            ]

            grade_map = {}
            for name, code, order, stream in grades_data:
                g, _ = GradeLevel.objects.get_or_create(
                    school=school,
                    code=code,
                    defaults={
                        "name": name,
                        "display_order": order,
                        "stream_applicable": stream,
                        "is_active": True,
                    }
                )
                grade_map[code] = g
                # Create Sections A and B for each grade, linking current academic year
                sec_a, _ = Section.objects.get_or_create(
                    school=school, grade_level=g, name="A",
                    defaults={"academic_year": ay, "room_number": f"{code}01", "is_active": True}
                )
                if not sec_a.academic_year:
                    sec_a.academic_year = ay
                    sec_a.save()
                sec_b, _ = Section.objects.get_or_create(
                    school=school, grade_level=g, name="B",
                    defaults={"academic_year": ay, "room_number": f"{code}02", "is_active": True}
                )
                if not sec_b.academic_year:
                    sec_b.academic_year = ay
                    sec_b.save()

            # Legacy Department & Batch
            dept, _ = Department.objects.get_or_create(
                school=school,
                name="General Academics",
                defaults={"code": 101, "institute": institute}
            )
            Batch.objects.get_or_create(
                year=session,
                department=dept,
                defaults={"number": 2026}
            )

            # 4. Verified Demo Accounts (All verified approval_status='a')
            demo_accounts = [
                ("admin@primesoul.com", "admin_demo", "SCHOOL_ADMIN", "Admin", "User", True, True),
                ("principal@primesoul.com", "principal_demo", "PRINCIPAL", "Dr. Rajesh", "Kapoor", False, False),
                ("accountant@primesoul.com", "accountant_demo", "ACCOUNTANT", "Meenakshi", "Sundaram", False, False),
                ("receptionist@primesoul.com", "receptionist_demo", "RECEPTIONIST", "Pooja", "Bhardwaj", False, False),
                ("teacher@primesoul.com", "teacher_demo", "TEACHER", "Vikram", "Malhotra", False, False),
                ("parent@primesoul.com", "parent_demo", "PARENT", "Suresh", "Sharma", False, False),
                ("student@primesoul.com", "student_demo", "STUDENT", "Aarav", "Sharma", False, False),
            ]

            created_users = {}
            for email, username, role, first, last, is_staff, is_su in demo_accounts:
                user = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
                if not user:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password="demo@123",
                        first_name=first,
                        last_name=last,
                        requested_role=role,
                        approval_status="a",
                        school=school,
                        institute=institute,
                        is_staff=is_staff,
                        is_superuser=is_su
                    )
                else:
                    user.requested_role = role
                    user.approval_status = "a"
                    user.school = school
                    user.institute = institute
                    user.first_name = first
                    user.last_name = last
                    user.is_staff = is_staff or user.is_staff
                    user.is_superuser = is_su or user.is_superuser
                    user.set_password("demo@123")
                    user.save()
                created_users[role] = user

            # Auto-approve current user if logged in with personal email
            active_admin = User.objects.filter(email="paramsisodiya061@gmail.com").first()
            if active_admin:
                active_admin.approval_status = "a"
                active_admin.requested_role = "SCHOOL_ADMIN"
                active_admin.school = school
                active_admin.institute = institute
                active_admin.is_staff = True
                active_admin.is_superuser = True
                active_admin.save()
                self.stdout.write(self.style.SUCCESS(f"Auto-approved active user: {active_admin.email} as School Admin."))

            # 5. Teacher Profiles
            desig_pgt, _ = Designation.objects.get_or_create(school=school, title="PGT Mathematics")
            desig_tgt, _ = Designation.objects.get_or_create(school=school, title="TGT English")
            desig_prt, _ = Designation.objects.get_or_create(school=school, title="PRT Science")

            teacher_user = created_users["TEACHER"]
            teacher_prof, _ = TeacherProfile.objects.get_or_create(
                user=teacher_user,
                defaults={
                    "school": school,
                    "employee_code": "DPS-FAC-014",
                    "first_name": "Vikram",
                    "last_name": "Malhotra",
                    "gender": "M",
                    "designation": desig_pgt,
                    "qualification": "M.Sc Mathematics, B.Ed",
                    "specialization": "Higher Mathematics",
                    "joining_date": datetime.date(2022, 6, 15),
                    "mobile_number": "+91 98765 43210",
                    "email": "teacher@primesoul.com",
                    "is_active": True,
                    "is_class_teacher": True,
                }
            )

            # Legacy Teacher
            teacher_legacy, _ = Teacher.objects.get_or_create(
                employee_id="DPS-FAC-014",
                defaults={
                    "name": "Vikram Malhotra",
                    "designation": desig_pgt,
                    "institute": institute,
                    "school": school,
                    "mobile": "+91 98765 43210",
                    "email": "teacher@primesoul.com",
                    "created_by": created_users["SCHOOL_ADMIN"]
                }
            )

            # Extra Faculty Profiles for rich Academic Assignments
            extra_faculty_data = [
                ("priya.english@primesoul.com", "priya_demo", "Priya Nair", "TGT English", desig_tgt, "M.A. English, B.Ed"),
                ("amit.science@primesoul.com", "amit_demo", "Amit Kumar", "PRT Science", desig_prt, "B.Sc Physics, B.Ed"),
            ]
            teachers_map = {"MATH": teacher_legacy}
            for t_email, t_username, t_full, t_title, t_desig, t_qual in extra_faculty_data:
                u = User.objects.filter(email=t_email).first() or User.objects.filter(username=t_username).first()
                if not u:
                    u = User.objects.create_user(
                        username=t_username,
                        email=t_email,
                        password="demo@123",
                        first_name=t_full.split()[0],
                        last_name=t_full.split()[-1],
                        requested_role="TEACHER",
                        approval_status="a",
                        school=school,
                        institute=institute
                    )
                tp, _ = TeacherProfile.objects.get_or_create(
                    user=u,
                    defaults={
                        "school": school,
                        "employee_code": f"DPS-FAC-{t_username[:4].upper()}",
                        "first_name": t_full.split()[0],
                        "last_name": t_full.split()[-1],
                        "gender": "F" if "Priya" in t_full else "M",
                        "designation": t_desig,
                        "qualification": t_qual,
                        "specialization": t_title,
                        "joining_date": datetime.date(2023, 7, 1),
                        "mobile_number": "+91 98765 11223",
                        "email": t_email,
                        "is_active": True,
                    }
                )
                t_leg, _ = Teacher.objects.get_or_create(
                    employee_id=f"DPS-FAC-{t_username[:4].upper()}",
                    defaults={
                        "name": t_full,
                        "designation": t_desig,
                        "institute": institute,
                        "school": school,
                        "mobile": "+91 98765 11223",
                        "email": t_email,
                        "created_by": created_users["SCHOOL_ADMIN"]
                    }
                )
                key = "ENG" if "English" in t_title else "SCI"
                teachers_map[key] = t_leg

            # Phase 5: CBSE / Indian Curriculum Subjects
            subjects_data = [
                ("Mathematics", "MATH-10", "CORE", 100, 33),
                ("English Language & Literature", "ENG-10", "LANG", 100, 33),
                ("Science", "SCI-10", "CORE", 100, 33),
                ("Social Science", "SST-10", "CORE", 100, 33),
                ("Hindi Course A", "HIN-10", "LANG", 100, 33),
                ("Computer Applications", "CA-10", "SKILL", 100, 33),
                ("Physical Education", "PE-10", "CO_CURRICULAR", 100, 33),
            ]
            seeded_subjects = {}
            for s_name, s_code, s_type, s_max, s_pass in subjects_data:
                subj, _ = Subject.objects.get_or_create(
                    school=school,
                    code=s_code,
                    defaults={
                        "name": s_name,
                        "subject_type": s_type,
                        "max_marks": s_max,
                        "passing_marks": s_pass,
                        "is_active": True,
                    }
                )
                seeded_subjects[s_code] = subj

            # 6. Sample Students & Class Allocation
            c10 = grade_map["10"]
            c9 = grade_map["9"]
            c8 = grade_map["8"]
            sec_10a = Section.objects.get(school=school, grade_level=c10, name="A")
            sec_10b = Section.objects.get(school=school, grade_level=c10, name="B")
            sec_9a = Section.objects.get(school=school, grade_level=c9, name="A")
            sec_8a = Section.objects.get(school=school, grade_level=c8, name="A")

            # Assign Class Teacher for Class 10 Section A
            sec_10a.class_teacher = teacher_legacy
            sec_10a.save()
            ClassTeacherAssignment.objects.get_or_create(
                school=school,
                academic_year=ay,
                section=sec_10a,
                defaults={"teacher": teacher_legacy, "is_active": True}
            )

            # Assign Subject Teachers for Class 10 Section A
            SubjectAssignment.objects.get_or_create(
                school=school,
                academic_year=ay,
                grade_level=c10,
                section=sec_10a,
                subject=seeded_subjects["MATH-10"],
                defaults={"teacher": teachers_map["MATH"], "periods_per_week": 6, "is_active": True}
            )
            if "ENG" in teachers_map:
                SubjectAssignment.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    grade_level=c10,
                    section=sec_10a,
                    subject=seeded_subjects["ENG-10"],
                    defaults={"teacher": teachers_map["ENG"], "periods_per_week": 5, "is_active": True}
                )
            if "SCI" in teachers_map:
                SubjectAssignment.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    grade_level=c10,
                    section=sec_10a,
                    subject=seeded_subjects["SCI-10"],
                    defaults={"teacher": teachers_map["SCI"], "periods_per_week": 6, "is_active": True}
                )

            students_data = [
                ("Aarav", "Sharma", "ADM-2026-0101", "101", c10, sec_10a, "M", "A+", created_users["STUDENT"]),
                ("Diya", "Patel", "ADM-2026-0102", "102", c10, sec_10a, "F", "B+", None),
                ("Rohan", "Gupta", "ADM-2026-0901", "901", c9, sec_9a, "M", "O+", None),
                ("Ananya", "Iyer", "ADM-2026-0801", "801", c8, sec_8a, "F", "AB+", None),
                ("Kabir", "Verma", "ADM-2026-0103", "103", c10, sec_10b, "M", "O-", None),
            ]

            seeded_students = []
            for first, last, adm_no, roll, gr, sec, gen, bg, u in students_data:
                st, _ = Student.objects.get_or_create(
                    school=school,
                    admission_number=adm_no,
                    defaults={
                        "user": u,
                        "first_name": first,
                        "last_name": last,
                        "roll_number": roll,
                        "roll": roll,
                        "grade_level": gr,
                        "section": sec,
                        "academic_year": ay,
                        "gender": gen,
                        "blood_group": bg,
                        "date_of_birth": datetime.date(2010, 5, 12),
                        "nationality": "Indian",
                        "category": "General",
                        "admission_date": datetime.date(2026, 4, 1),
                        "emergency_contact_number": "+91 98111 22233",
                        "current_address": "Flat 402, Green Valley Apartments, New Delhi",
                        "permanent_address": "Flat 402, Green Valley Apartments, New Delhi",
                        "is_active": True,
                    }
                )
                # Phase 5: StudentEnrollment record
                StudentEnrollment.objects.get_or_create(
                    student=st,
                    academic_year=ay,
                    defaults={
                        "school": school,
                        "grade_level": gr,
                        "section": sec,
                        "roll_number": roll,
                        "status": "ENROLLED",
                    }
                )
                seeded_students.append(st)

            # Phase 6: Daily Attendance Records for Demonstration
            today = datetime.date.today()
            # Generate 14 past school working dates (Monday to Friday)
            past_dates = []
            curr_d = today - datetime.timedelta(days=1)
            while len(past_dates) < 14:
                if curr_d.weekday() < 5:  # Mon-Fri
                    past_dates.append(curr_d)
                curr_d -= datetime.timedelta(days=1)
            past_dates.sort()

            # Seed past attendance for all students
            st_aarav = seeded_students[0]
            st_diya = seeded_students[1]
            st_rohan = seeded_students[2]
            st_ananya = seeded_students[3]
            st_kabir = seeded_students[4]

            for idx, d in enumerate(past_dates):
                # Aarav (Class 10-A): High attendance (~90%)
                aarav_status = "LATE" if idx == 4 else ("HALF_DAY" if idx == 9 else "PRESENT")
                AttendanceRecord.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    student=st_aarav,
                    attendance_date=d,
                    defaults={
                        "grade_level": c10,
                        "section": sec_10a,
                        "status": aarav_status,
                        "marked_by": created_users["TEACHER"],
                    }
                )

                # Diya (Class 10-A): Low attendance (~64%, triggers Low Attendance alert)
                diya_status = "ABSENT" if idx in [1, 3, 5, 8, 11] else "PRESENT"
                AttendanceRecord.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    student=st_diya,
                    attendance_date=d,
                    defaults={
                        "grade_level": c10,
                        "section": sec_10a,
                        "status": diya_status,
                        "marked_by": created_users["TEACHER"],
                    }
                )

                # Rohan (Class 9-A)
                AttendanceRecord.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    student=st_rohan,
                    attendance_date=d,
                    defaults={
                        "grade_level": c9,
                        "section": sec_9a,
                        "status": "PRESENT" if idx != 2 else "LATE",
                        "marked_by": created_users["SCHOOL_ADMIN"],
                    }
                )

                # Ananya (Class 8-A)
                AttendanceRecord.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    student=st_ananya,
                    attendance_date=d,
                    defaults={
                        "grade_level": c8,
                        "section": sec_8a,
                        "status": "PRESENT",
                        "marked_by": created_users["SCHOOL_ADMIN"],
                    }
                )

                # Kabir (Class 10-B): Past days marked
                AttendanceRecord.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    student=st_kabir,
                    attendance_date=d,
                    defaults={
                        "grade_level": c10,
                        "section": sec_10b,
                        "status": "PRESENT",
                        "marked_by": created_users["TEACHER"],
                    }
                )

            # Mark TODAY's attendance for Class 10-A (Completed section)
            AttendanceRecord.objects.get_or_create(
                school=school,
                academic_year=ay,
                student=st_aarav,
                attendance_date=today,
                defaults={
                    "grade_level": c10,
                    "section": sec_10a,
                    "status": "PRESENT",
                    "marked_by": created_users["TEACHER"],
                }
            )
            AttendanceRecord.objects.get_or_create(
                school=school,
                academic_year=ay,
                student=st_diya,
                attendance_date=today,
                defaults={
                    "grade_level": c10,
                    "section": sec_10a,
                    "status": "PRESENT",
                    "marked_by": created_users["TEACHER"],
                }
            )
            # Class 10-B is left UNMARKED for TODAY to demonstrate Pending Attendance!

            # 7. Fee Heads
            heads_data = [
                ("Tuition Fee", "TUITION", FeeHeadCategory.TUITION, True, "Standard monthly/quarterly tuition fee"),
                ("Annual Development Charges", "DEVELOPMENT", FeeHeadCategory.DEVELOPMENT, False, "Annual infrastructure and development"),
                ("Computer & Technology Fee", "COMPUTER", FeeHeadCategory.COMPUTER, True, "IT and computer lab facility access"),
                ("Sports & Activity Fee", "ACTIVITY", FeeHeadCategory.ACTIVITY, True, "Co-curricular activities and athletic sports"),
                ("Examination Fee", "EXAM", FeeHeadCategory.EXAM, True, "Terminal evaluation and CBSE board assessment"),
                ("Admission Fee", "ADMISSION", FeeHeadCategory.ADMISSION, False, "One-time registration and admission fee"),
                ("Library Fee", "LIBRARY", FeeHeadCategory.LIBRARY, False, "Annual library and digital journal access"),
            ]

            fee_heads = {}
            for hname, hcode, cat, rec, desc in heads_data:
                fh, _ = FeeHead.objects.get_or_create(
                    school=school,
                    code=hcode,
                    defaults={
                        "name": hname,
                        "category": cat,
                        "is_recurring": rec,
                        "description": desc,
                        "is_active": True
                    }
                )
                fee_heads[hcode] = fh

            # 8. Fee Structures
            # Class 10: ₹48,000 / year (4 Quarterly installments of ₹12,000)
            fs_c10, _ = FeeStructure.objects.get_or_create(
                school=school,
                academic_year=ay,
                grade_level=c10,
                name="Class 10 Standard Fee 2026-27",
                defaults={
                    "effective_from": ay_start,
                    "effective_to": ay_end,
                    "frequency": FeeFrequency.QUARTERLY,
                    "is_active": True
                }
            )
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c10, fee_head=fee_heads["TUITION"], defaults={"amount": Decimal("32000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c10, fee_head=fee_heads["COMPUTER"], defaults={"amount": Decimal("6000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c10, fee_head=fee_heads["ACTIVITY"], defaults={"amount": Decimal("4000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c10, fee_head=fee_heads["DEVELOPMENT"], defaults={"amount": Decimal("6000.00"), "due_day": 10})

            # Class 9: ₹44,000 / year (4 Quarterly installments of ₹11,000)
            fs_c9, _ = FeeStructure.objects.get_or_create(
                school=school,
                academic_year=ay,
                grade_level=c9,
                name="Class 9 Standard Fee 2026-27",
                defaults={
                    "effective_from": ay_start,
                    "effective_to": ay_end,
                    "frequency": FeeFrequency.QUARTERLY,
                    "is_active": True
                }
            )
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c9, fee_head=fee_heads["TUITION"], defaults={"amount": Decimal("28000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c9, fee_head=fee_heads["COMPUTER"], defaults={"amount": Decimal("6000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c9, fee_head=fee_heads["ACTIVITY"], defaults={"amount": Decimal("4000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c9, fee_head=fee_heads["DEVELOPMENT"], defaults={"amount": Decimal("6000.00"), "due_day": 10})

            # Class 8: ₹36,000 / year (4 Quarterly installments of ₹9,000)
            fs_c8, _ = FeeStructure.objects.get_or_create(
                school=school,
                academic_year=ay,
                grade_level=c8,
                name="Middle School (Class 8) Fee 2026-27",
                defaults={
                    "effective_from": ay_start,
                    "effective_to": ay_end,
                    "frequency": FeeFrequency.QUARTERLY,
                    "is_active": True
                }
            )
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c8, fee_head=fee_heads["TUITION"], defaults={"amount": Decimal("24000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c8, fee_head=fee_heads["COMPUTER"], defaults={"amount": Decimal("4000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c8, fee_head=fee_heads["ACTIVITY"], defaults={"amount": Decimal("4000.00"), "due_day": 10})
            FeeStructureItem.objects.get_or_create(fee_structure=fs_c8, fee_head=fee_heads["DEVELOPMENT"], defaults={"amount": Decimal("4000.00"), "due_day": 10})

            # 9. Concessions
            conc_merit, _ = FeeConcession.objects.get_or_create(
                school=school,
                name="Merit Scholarship 25%",
                defaults={
                    "concession_type": ConcessionType.PERCENTAGE,
                    "value": Decimal("25.00"),
                    "is_approved": True,
                    "approved_by": created_users["PRINCIPAL"],
                    "is_active": True
                }
            )
            conc_merit.applicable_fee_heads.add(fee_heads["TUITION"])

            conc_sibling, _ = FeeConcession.objects.get_or_create(
                school=school,
                name="Sibling Discount ₹5,000",
                defaults={
                    "concession_type": ConcessionType.FIXED_AMOUNT,
                    "value": Decimal("5000.00"),
                    "is_approved": True,
                    "approved_by": created_users["PRINCIPAL"],
                    "is_active": True
                }
            )

            conc_staff, _ = FeeConcession.objects.get_or_create(
                school=school,
                name="Staff Child Concession 50%",
                defaults={
                    "concession_type": ConcessionType.PERCENTAGE,
                    "value": Decimal("50.00"),
                    "approval_required": True,
                    "is_approved": False,
                    "is_active": True
                }
            )
            conc_staff.applicable_fee_heads.add(fee_heads["TUITION"])

            # 10. Student Fee Assignments & Installments Generation
            # Deduplicate any past unallocated duplicate installments
            seen_inst = set()
            for inst in FeeInstallment.objects.filter(academic_year=ay).order_by('id'):
                key = (inst.student_id, inst.installment_name)
                if key in seen_inst:
                    if not inst.allocations.exists():
                        inst.delete()
                else:
                    seen_inst.add(key)

            # Student 1: Aarav Sharma (Class 10)
            aarav = seeded_students[0]
            StudentFeeAssignment.objects.update_or_create(
                student=aarav,
                academic_year=ay,
                fee_structure=fs_c10,
                defaults={
                    "concession": None,
                    "custom_concession_amount": Decimal("0.00"),
                    "status": 'ACTIVE',
                }
            )
            if not FeeInstallment.objects.filter(student=aarav, academic_year=ay).exists():
                generate_student_installments(
                    student=aarav,
                    fee_structure=fs_c10,
                    academic_year=ay,
                    actor=created_users["SCHOOL_ADMIN"]
                )

            # Student 2: Diya Patel (Class 10)
            diya = seeded_students[1]
            StudentFeeAssignment.objects.update_or_create(
                student=diya,
                academic_year=ay,
                fee_structure=fs_c10,
                defaults={
                    "concession": None,
                    "custom_concession_amount": Decimal("0.00"),
                    "status": 'ACTIVE',
                }
            )
            if not FeeInstallment.objects.filter(student=diya, academic_year=ay).exists():
                generate_student_installments(
                    student=diya,
                    fee_structure=fs_c10,
                    academic_year=ay,
                    actor=created_users["SCHOOL_ADMIN"]
                )

            # Student 3: Rohan Gupta (Class 9 with Sibling Discount)
            rohan = seeded_students[2]
            StudentFeeAssignment.objects.update_or_create(
                student=rohan,
                academic_year=ay,
                fee_structure=fs_c9,
                defaults={
                    "concession": conc_sibling,
                    "custom_concession_amount": Decimal("0.00"),
                    "status": 'ACTIVE',
                }
            )
            if not FeeInstallment.objects.filter(student=rohan, academic_year=ay).exists():
                generate_student_installments(
                    student=rohan,
                    fee_structure=fs_c9,
                    academic_year=ay,
                    concession=conc_sibling,
                    actor=created_users["SCHOOL_ADMIN"]
                )

            # Student 4: Ananya Iyer (Class 8)
            ananya = seeded_students[3]
            StudentFeeAssignment.objects.update_or_create(
                student=ananya,
                academic_year=ay,
                fee_structure=fs_c8,
                defaults={
                    "concession": None,
                    "custom_concession_amount": Decimal("0.00"),
                    "status": 'ACTIVE',
                }
            )
            if not FeeInstallment.objects.filter(student=ananya, academic_year=ay).exists():
                generate_student_installments(
                    student=ananya,
                    fee_structure=fs_c8,
                    academic_year=ay,
                    actor=created_users["SCHOOL_ADMIN"]
                )

            # Student 5: Kabir Verma (Class 10)
            kabir = seeded_students[4]
            StudentFeeAssignment.objects.update_or_create(
                student=kabir,
                academic_year=ay,
                fee_structure=fs_c10,
                defaults={
                    "concession": None,
                    "custom_concession_amount": Decimal("0.00"),
                    "status": 'ACTIVE',
                }
            )
            if not FeeInstallment.objects.filter(student=kabir, academic_year=ay).exists():
                generate_student_installments(
                    student=kabir,
                    fee_structure=fs_c10,
                    academic_year=ay,
                    actor=created_users["SCHOOL_ADMIN"]
                )

            # 11. Invoices & Payments Flow
            # --- Flow A: Aarav Sharma (Q1 Invoice ₹12,000 -> Paid ₹4,000 Cash (Partial) -> Paid ₹8,000 UPI (Paid) -> 2 Receipts)
            aarav_q1 = FeeInstallment.objects.filter(student=aarav, academic_year=ay).order_by('due_date').first()
            if aarav_q1 and not FeeInvoice.objects.filter(school=school, student=aarav, academic_year=ay).exists():
                inv_aarav = create_fee_invoice(
                    school=school,
                    student=aarav,
                    academic_year=ay,
                    subtotal=aarav_q1.payable_amount,
                    installments=[aarav_q1],
                    due_date=datetime.date(2026, 4, 10),
                    actor=created_users["ACCOUNTANT"]
                )

                # Payment 1: ₹4,000 Cash (Partial)
                p1 = record_offline_payment(
                    school=school,
                    student=aarav,
                    amount=Decimal("4000.00"),
                    gateway=PaymentGateway.CASH,
                    payment_method="Cash",
                    invoice=inv_aarav,
                    installment=aarav_q1,
                    collected_by=created_users["ACCOUNTANT"],
                    notes="Q1 Partial Tuition Cash Payment"
                )
                generate_fee_receipt(p1, issued_by=created_users["ACCOUNTANT"])

                # Payment 2: ₹8,000 UPI (Complete Remaining -> Status PAID)
                p2 = record_offline_payment(
                    school=school,
                    student=aarav,
                    amount=Decimal("8000.00"),
                    gateway=PaymentGateway.UPI,
                    payment_method="UPI / GPay",
                    transaction_id="UPI-20260412-998811",
                    invoice=inv_aarav,
                    installment=aarav_q1,
                    collected_by=created_users["ACCOUNTANT"],
                    notes="Q1 Balance Payment via GooglePay UPI"
                )
                generate_fee_receipt(p2, issued_by=created_users["ACCOUNTANT"])

            # --- Flow B: Diya Patel (Q1 Invoice ₹12,000 -> ₹12,000 Cheque -> Cleared -> Paid -> Receipt)
            diya_q1 = FeeInstallment.objects.filter(student=diya, academic_year=ay).order_by('due_date').first()
            if diya_q1 and not FeeInvoice.objects.filter(school=school, student=diya, academic_year=ay).exists():
                inv_diya = create_fee_invoice(
                    school=school,
                    student=diya,
                    academic_year=ay,
                    subtotal=diya_q1.payable_amount,
                    installments=[diya_q1],
                    due_date=datetime.date(2026, 4, 10),
                    actor=created_users["ACCOUNTANT"]
                )

                p_chq = record_offline_payment(
                    school=school,
                    student=diya,
                    amount=Decimal("12000.00"),
                    gateway=PaymentGateway.CHEQUE,
                    payment_method="Cheque",
                    invoice=inv_diya,
                    installment=diya_q1,
                    collected_by=created_users["ACCOUNTANT"],
                    notes="Q1 Term Fee Cheque Payment",
                    cheque_number="004521",
                    bank_name="HDFC Bank",
                    cheque_date=datetime.date(2026, 4, 5),
                    clearance_status=ChequeClearanceStatus.PENDING
                )
                # Clear the cheque
                cleared_payment = process_cheque_clearance(p_chq, actor=created_users["ACCOUNTANT"])
                generate_fee_receipt(cleared_payment, issued_by=created_users["ACCOUNTANT"])

            # --- Flow C: Rohan Gupta (Q1 Invoice -> Status: PENDING dues)
            rohan_q1 = FeeInstallment.objects.filter(student=rohan, academic_year=ay).order_by('due_date').first()
            if rohan_q1 and not FeeInvoice.objects.filter(school=school, student=rohan, academic_year=ay).exists():
                create_fee_invoice(
                    school=school,
                    student=rohan,
                    academic_year=ay,
                    subtotal=rohan_q1.payable_amount,
                    installments=[rohan_q1],
                    due_date=datetime.date(2026, 4, 10),
                    actor=created_users["ACCOUNTANT"]
                )

            # =========================================================================
            # 10. Phase 7+8 Examination, Grading & Report Cards
            # =========================================================================
            # Assessment Types
            at_hye, _ = AssessmentType.objects.get_or_create(
                school=school,
                code="HYE",
                defaults={"name": "Half Yearly Examination", "is_active": True}
            )
            AssessmentType.objects.get_or_create(
                school=school,
                code="PT",
                defaults={"name": "Periodic Test", "is_active": True}
            )
            AssessmentType.objects.get_or_create(
                school=school,
                code="ANNUAL",
                defaults={"name": "Annual Examination", "is_active": True}
            )

            # Grade Scale (CBSE 8-Point)
            gs_cbse, _ = GradeScale.objects.get_or_create(
                school=school,
                code="CBSE-8P",
                defaults={
                    "name": "CBSE 8-Point Secondary Scale",
                    "is_default": True,
                    "description": "Standard Central Board 8-point grading scheme (A1 to E)"
                }
            )
            cbse_bands = [
                ("A1", Decimal("91.00"), Decimal("100.00"), Decimal("10.0"), True, "Outstanding"),
                ("A2", Decimal("81.00"), Decimal("90.99"), Decimal("9.0"), True, "Excellent"),
                ("B1", Decimal("71.00"), Decimal("80.99"), Decimal("8.0"), True, "Very Good"),
                ("B2", Decimal("61.00"), Decimal("70.99"), Decimal("7.0"), True, "Good"),
                ("C1", Decimal("51.00"), Decimal("60.99"), Decimal("6.0"), True, "Above Average"),
                ("C2", Decimal("41.00"), Decimal("50.99"), Decimal("5.0"), True, "Average"),
                ("D", Decimal("33.00"), Decimal("40.99"), Decimal("4.0"), True, "Pass"),
                ("E", Decimal("0.00"), Decimal("32.99"), Decimal("0.0"), False, "Scope for Improvement"),
            ]
            for b_name, b_min, b_max, b_gp, b_pass, b_rem in cbse_bands:
                GradeScaleBand.objects.get_or_create(
                    scale=gs_cbse,
                    name=b_name,
                    defaults={
                        "min_percentage": b_min,
                        "max_percentage": b_max,
                        "grade_point": b_gp,
                        "is_passing": b_pass,
                        "remarks": b_rem,
                    }
                )

            # Examination Session
            exam_sess, _ = ExaminationSession.objects.get_or_create(
                school=school,
                academic_year=ay,
                code="HYE-2026",
                defaults={
                    "name": "Half Yearly Examination 2026-27",
                    "start_date": datetime.date(2026, 9, 1),
                    "end_date": datetime.date(2026, 9, 15),
                    "status": ExaminationSession.STATUS_COMPLETED,
                    "created_by": created_users["SCHOOL_ADMIN"],
                }
            )

            # Exam 1: Class 10 Section A (PUBLISHED)
            exam_10a, _ = Exam.objects.get_or_create(
                school=school,
                session=exam_sess,
                grade_level=c10,
                section=sec_10a,
                name="Half Yearly Examination - Class 10-A",
                defaults={
                    "academic_year": ay,
                    "assessment_type": at_hye,
                    "grade_scale": gs_cbse,
                    "start_date": datetime.date(2026, 9, 1),
                    "end_date": datetime.date(2026, 9, 10),
                    "ranking_enabled": True,
                    "status": Exam.STATUS_PUBLISHED,
                    "created_by": created_users["SCHOOL_ADMIN"],
                    "updated_by": created_users["SCHOOL_ADMIN"],
                }
            )

            # Exam 2: Class 10 Section B (DRAFT / IN PROGRESS)
            Exam.objects.get_or_create(
                school=school,
                session=exam_sess,
                grade_level=c10,
                section=sec_10b,
                name="Half Yearly Examination - Class 10-B",
                defaults={
                    "academic_year": ay,
                    "assessment_type": at_hye,
                    "grade_scale": gs_cbse,
                    "start_date": datetime.date(2026, 9, 1),
                    "end_date": datetime.date(2026, 9, 10),
                    "ranking_enabled": True,
                    "status": Exam.STATUS_DRAFT,
                    "created_by": created_users["SCHOOL_ADMIN"],
                    "updated_by": created_users["SCHOOL_ADMIN"],
                }
            )

            # Exam Subjects for Exam 10-A
            c10_subjects = Subject.objects.filter(school=school, is_active=True)[:5]
            exam_subj_objs = []
            for idx, subj in enumerate(c10_subjects, 1):
                es, _ = ExamSubject.objects.get_or_create(
                    school=school,
                    exam=exam_10a,
                    subject=subj,
                    defaults={
                        "max_marks": Decimal("100.00"),
                        "passing_marks": Decimal("33.00"),
                        "weightage": Decimal("100.00"),
                        "sequence_order": idx,
                        "is_active": True,
                    }
                )
                exam_subj_objs.append(es)

            # Marks Seeding for Students in Section 10-A
            c10a_students = [
                (st_aarav, [Decimal("92.0"), Decimal("85.0"), Decimal("88.0"), Decimal("84.0"), Decimal("90.0")]),
                (st_diya, [Decimal("74.0"), Decimal("68.0"), Decimal("75.0"), Decimal("70.0"), Decimal("72.0")]),
                (st_rohan, [Decimal("80.0"), None, Decimal("65.0"), Decimal("70.0"), Decimal("60.0")]),
                (st_ananya, [Decimal("96.0"), Decimal("94.0"), Decimal("92.0"), Decimal("95.0"), Decimal("93.0")]),
            ]

            for st_obj, marks_list in c10a_students:
                for idx, es_obj in enumerate(exam_subj_objs):
                    if idx < len(marks_list):
                        score = marks_list[idx]
                        if score is not None:
                            st_status = StudentMark.STATUS_PRESENT
                            st_grade = "A1" if score >= 91 else ("A2" if score >= 81 else ("B1" if score >= 71 else "B2"))
                            st_gp = Decimal("10.0") if score >= 91 else (Decimal("9.0") if score >= 81 else Decimal("8.0"))
                            st_pass = True
                        else:
                            st_status = StudentMark.STATUS_ABSENT
                            st_grade = "AB"
                            st_gp = None
                            st_pass = False

                        StudentMark.objects.get_or_create(
                            school=school,
                            exam=exam_10a,
                            exam_subject=es_obj,
                            student=st_obj,
                            defaults={
                                "academic_year": ay,
                                "status": st_status,
                                "marks_obtained": score,
                                "grade": st_grade,
                                "grade_point": st_gp,
                                "is_passed": st_pass,
                                "entered_by": created_users["TEACHER"],
                                "updated_by": created_users["TEACHER"],
                            }
                        )

            # Calculate and publish results for exam_10a
            try:
                calculate_exam_results(school=school, exam=exam_10a, section=sec_10a, actor=created_users["TEACHER"])
                publish_exam_results(school=school, exam=exam_10a, actor=created_users["SCHOOL_ADMIN"])
            except Exception:
                pass

            # Phase 9: Timetable & Scheduling
            weekdays = [
                (0, 'Monday', True, 0),
                (1, 'Tuesday', True, 1),
                (2, 'Wednesday', True, 2),
                (3, 'Thursday', True, 3),
                (4, 'Friday', True, 4),
                (5, 'Saturday', True, 5),
                (6, 'Sunday', False, 6),
            ]
            demo_days = {}
            for w, name, is_work, order in weekdays:
                d_obj, _ = WorkingDay.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    weekday=w,
                    defaults={'day_name': name, 'is_working': is_work, 'display_order': order}
                )
                demo_days[w] = d_obj

            slots_data = [
                ("Morning Assembly", None, datetime.time(8, 0), datetime.time(8, 20), False, 0),
                ("Period 1", 1, datetime.time(8, 20), datetime.time(9, 5), False, 1),
                ("Period 2", 2, datetime.time(9, 5), datetime.time(9, 50), False, 2),
                ("Morning Recess", None, datetime.time(9, 50), datetime.time(10, 10), True, 3),
                ("Period 3", 3, datetime.time(10, 10), datetime.time(10, 55), False, 4),
                ("Period 4", 4, datetime.time(10, 55), datetime.time(11, 40), False, 5),
                ("Lunch Break", None, datetime.time(11, 40), datetime.time(12, 20), True, 6),
                ("Period 5", 5, datetime.time(12, 20), datetime.time(13, 5), False, 7),
                ("Period 6", 6, datetime.time(13, 5), datetime.time(13, 50), False, 8),
            ]
            demo_slots = {}
            for s_name, p_num, s_start, s_end, is_brk, order in slots_data:
                sl_obj, _ = TimeSlot.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    name=s_name,
                    defaults={
                        'period_number': p_num,
                        'start_time': s_start,
                        'end_time': s_end,
                        'is_break': is_brk,
                        'display_order': order,
                        'is_active': True
                    }
                )
                demo_slots[s_name] = sl_obj

            rooms_data = [
                ("101", "Room 10-A", "CLASSROOM", 40),
                ("102", "Room 10-B", "CLASSROOM", 40),
                ("PLAB-1", "Senior Physics Laboratory", "LAB", 35),
                ("CLAB-1", "Computer Science Lab", "LAB", 40),
            ]
            demo_rooms = {}
            for r_num, r_name, r_type, r_cap in rooms_data:
                rm_obj, _ = Classroom.objects.get_or_create(
                    school=school,
                    room_number=r_num,
                    defaults={'name': r_name, 'room_type': r_type, 'capacity': r_cap, 'is_active': True}
                )
                demo_rooms[r_num] = rm_obj

            p1 = demo_slots.get("Period 1")
            p2 = demo_slots.get("Period 2")
            mon = demo_days.get(0)
            tue = demo_days.get(1)

            if mon and p1 and "MATH-10" in seeded_subjects and "MATH" in teachers_map:
                TimetableEntry.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    working_day=mon,
                    time_slot=p1,
                    section=sec_10a,
                    defaults={
                        'subject': seeded_subjects["MATH-10"],
                        'teacher': teachers_map["MATH"],
                        'room': demo_rooms.get("101"),
                        'entry_type': TimetableEntry.TYPE_CLASS
                    }
                )
            if mon and p2 and "ENG-10" in seeded_subjects and "ENG" in teachers_map:
                TimetableEntry.objects.get_or_create(
                    school=school,
                    academic_year=ay,
                    working_day=mon,
                    time_slot=p2,
                    section=sec_10a,
                    defaults={
                        'subject': seeded_subjects["ENG-10"],
                        'teacher': teachers_map["ENG"],
                        'room': demo_rooms.get("101"),
                        'entry_type': TimetableEntry.TYPE_CLASS
                    }
                )

            # Phase 10: Transport Management
            veh1, _ = TransportVehicle.objects.get_or_create(
                school=school,
                vehicle_number="BUS-01",
                defaults={
                    'registration_number': "DL-01-AB-1234",
                    'vehicle_type': TransportVehicle.TYPE_BUS,
                    'capacity': 42,
                    'is_active': True,
                    'insurance_expiry': datetime.date(2027, 3, 31),
                    'pollution_cert_expiry': datetime.date(2026, 12, 31),
                    'fitness_cert_expiry': datetime.date(2027, 5, 31),
                }
            )
            veh2, _ = TransportVehicle.objects.get_or_create(
                school=school,
                vehicle_number="BUS-02",
                defaults={
                    'registration_number': "DL-01-CD-5678",
                    'vehicle_type': TransportVehicle.TYPE_BUS,
                    'capacity': 42,
                    'is_active': True,
                    'insurance_expiry': datetime.date(2027, 3, 31),
                }
            )
            van1, _ = TransportVehicle.objects.get_or_create(
                school=school,
                vehicle_number="VAN-01",
                defaults={
                    'registration_number': "DL-01-EF-9012",
                    'vehicle_type': TransportVehicle.TYPE_VAN,
                    'capacity': 16,
                    'is_active': True,
                }
            )

            drv1, _ = TransportStaff.objects.get_or_create(
                school=school,
                phone="9876543210",
                defaults={
                    'name': "Rajesh Kumar",
                    'role': TransportStaff.ROLE_DRIVER,
                    'license_number': "DL-1420110012345",
                    'license_expiry': datetime.date(2028, 8, 15),
                    'is_active': True,
                }
            )
            drv2, _ = TransportStaff.objects.get_or_create(
                school=school,
                phone="9876543211",
                defaults={
                    'name': "Suresh Yadav",
                    'role': TransportStaff.ROLE_DRIVER,
                    'license_number': "DL-1420150098765",
                    'license_expiry': datetime.date(2027, 11, 20),
                    'is_active': True,
                }
            )
            att1, _ = TransportStaff.objects.get_or_create(
                school=school,
                phone="9876543212",
                defaults={
                    'name': "Sunita Devi",
                    'role': TransportStaff.ROLE_ATTENDANT,
                    'is_active': True,
                }
            )

            rt1, _ = TransportRoute.objects.get_or_create(
                school=school,
                academic_year=ay,
                code="R-01",
                defaults={
                    'name': "North Delhi Express Corridor",
                    'description': "Rohini Sector 9, Pitampura, Netaji Subhash Place to School Campus",
                    'fare': Decimal("2500.00"),
                    'is_active': True,
                }
            )
            rt2, _ = TransportRoute.objects.get_or_create(
                school=school,
                academic_year=ay,
                code="R-02",
                defaults={
                    'name': "West Delhi Metro Link",
                    'description': "Janakpuri West, Rajouri Garden, Punjabi Bagh to School Campus",
                    'fare': Decimal("2800.00"),
                    'is_active': True,
                }
            )

            stop1, _ = TransportStop.objects.get_or_create(
                school=school,
                route=rt1,
                sequence=1,
                defaults={
                    'name': "Rohini Sector 9 (DC Chowk)",
                    'landmark': "Opposite Mother Dairy Booth",
                    'pickup_time': datetime.time(7, 15),
                    'drop_time': datetime.time(14, 45),
                    'is_active': True,
                }
            )
            stop2, _ = TransportStop.objects.get_or_create(
                school=school,
                route=rt1,
                sequence=2,
                defaults={
                    'name': "Pitampura (Madhuvan Chowk)",
                    'landmark': "Metro Pillar 342",
                    'pickup_time': datetime.time(7, 30),
                    'drop_time': datetime.time(14, 30),
                    'is_active': True,
                }
            )
            stop3, _ = TransportStop.objects.get_or_create(
                school=school,
                route=rt1,
                sequence=3,
                defaults={
                    'name': "Netaji Subhash Place",
                    'landmark': "Max Hospital Gate 1",
                    'pickup_time': datetime.time(7, 45),
                    'drop_time': datetime.time(14, 15),
                    'is_active': True,
                }
            )

            VehicleRouteAssignment.objects.get_or_create(
                school=school,
                academic_year=ay,
                route=rt1,
                defaults={
                    'vehicle': veh1,
                    'driver': drv1,
                    'attendant': att1,
                    'is_active': True,
                }
            )

            if seeded_students:
                aarav_student = seeded_students[0]
                StudentTransportAssignment.objects.get_or_create(
                    academic_year=ay,
                    student=aarav_student,
                    defaults={
                        'school': school,
                        'route': rt1,
                        'pickup_stop': stop1,
                        'drop_stop': stop1,
                        'transport_status': StudentTransportAssignment.STATUS_ACTIVE,
                    }
                )

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("  PRIMESOUL SCHOOL ERP - DEMO ENVIRONMENT SEEDED SUCCESSFULLY!"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(f"School Tenant : {school.name} (Code: {school.school_code}, Board: {school.board})")
        self.stdout.write(f"Academic Year : {ay.name} (Active: {ay.is_current})")
        self.stdout.write(f"Classes Seeded: Nursery to Class 12 (Sections A & B)")
        self.stdout.write(f"Sample Records: {len(seeded_students)} Students, {TeacherProfile.objects.filter(school=school).count()} Faculty members")
        self.stdout.write(f"Fee Structures: {FeeStructure.objects.filter(school=school).count()} Structures, {FeeHead.objects.filter(school=school).count()} Fee Heads")
        self.stdout.write(f"Invoices/Rcpts: {FeeInvoice.objects.filter(school=school).count()} Invoices, {PaymentTransaction.objects.filter(school=school).count()} Payments")
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.NOTICE("DEMO ACCOUNTS (Password: demo@123 for all):"))
        self.stdout.write(f"  • School Admin  : admin@primesoul.com       (Full ERP & System Access)")
        self.stdout.write(f"  • Principal     : principal@primesoul.com   (Academics & Concession Approvals)")
        self.stdout.write(f"  • Accountant    : accountant@primesoul.com  (Fee Invoices, Payments, Receipts)")
        self.stdout.write(f"  • Receptionist  : receptionist@primesoul.com(Fee Collection & Dues)")
        self.stdout.write(f"  • Teacher       : teacher@primesoul.com     (Academics & Class Portal)")
        self.stdout.write(f"  • Parent        : parent@primesoul.com      (Parent Fee Portal)")
        self.stdout.write(f"  • Student       : student@primesoul.com     (Student Fee Portal)")
        self.stdout.write("=" * 70)
