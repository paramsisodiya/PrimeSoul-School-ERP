"""
PrimeSoul School ERP - Enterprise Multi-Tenant CSV Data Import Service
Provides robust, transactional, row-by-row validated CSV bulk imports for
Students, Teachers, Parents, and Non-Teaching Staff / Employees.
"""
import io
import csv
import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from django_school_management.tenants.models import School
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, StudentEnrollment
)
from django_school_management.students.models import (
    Student, ParentProfile, StudentGuardianRelationship
)
from django_school_management.teachers.models import Designation, TeacherProfile, Teacher
from django_school_management.hr.models import Department as HRDepartment, HRDesignation, Employee

User = get_user_model()


class CSVImportResult:
    def __init__(self):
        self.total_rows: int = 0
        self.valid_rows: int = 0
        self.imported_rows: int = 0
        self.errors: List[Dict[str, Any]] = []
        self.duplicates: List[Dict[str, Any]] = []
        self.is_success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "imported_rows": self.imported_rows,
            "errors": self.errors,
            "duplicates": self.duplicates,
            "is_success": self.is_success and len(self.errors) == 0,
        }


def parse_date_safe(date_str: str) -> Optional[datetime.date]:
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


class StudentCSVImporter:
    """
    Imports students with grade level, section placement, and parent profile relationships.
    """
    REQUIRED_COLUMNS = ['admission_number', 'first_name', 'grade_code', 'section_name', 'roll_number']

    @classmethod
    def get_sample_csv(cls) -> str:
        headers = [
            'admission_number', 'first_name', 'last_name', 'grade_code',
            'section_name', 'roll_number', 'gender', 'date_of_birth',
            'mobile_number', 'father_name', 'mother_name', 'address'
        ]
        sample_rows = [
            ['ADM-2026-0001', 'Aarav', 'Sharma', '10', 'A', '101', 'M', '2010-05-12', '9876543210', 'Rajesh Sharma', 'Pooja Sharma', 'New Delhi'],
            ['ADM-2026-0002', 'Diya', 'Patel', '10', 'A', '102', 'F', '2010-08-22', '9876543211', 'Suresh Patel', 'Meena Patel', 'New Delhi'],
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(sample_rows)
        return output.getvalue()

    @classmethod
    def import_csv(cls, school: School, file_content: str, dry_run: bool = False) -> CSVImportResult:
        result = CSVImportResult()
        reader = csv.DictReader(io.StringIO(file_content.strip()))
        
        if not reader.fieldnames:
            result.errors.append({"row": 0, "field": "header", "error": "CSV file is empty or missing headers."})
            return result

        # Validate headers
        normalized_headers = [h.strip().lower() for h in reader.fieldnames if h]
        missing = [req for req in cls.REQUIRED_COLUMNS if req not in normalized_headers]
        if missing:
            result.errors.append({
                "row": 0,
                "field": "headers",
                "error": f"Missing required columns: {', '.join(missing)}"
            })
            return result

        current_ay = AcademicYear.objects.filter(school=school, is_current=True).first()
        sub = getattr(school, 'subscription', None)
        max_allowed = sub.max_students if (sub and sub.status == 'active') else 999999
        current_active = Student.objects.filter(school=school, is_active=True).count()

        rows = list(reader)
        result.total_rows = len(rows)

        seen_admissions_in_file = set()
        seen_rolls_in_file = set()
        valid_items = []

        for idx, row in enumerate(rows, start=2):
            row_data = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items() if k}
            adm_no = row_data.get('admission_number')
            first_name = row_data.get('first_name')
            last_name = row_data.get('last_name', '')
            grade_code = row_data.get('grade_code')
            section_name = row_data.get('section_name')
            roll_number = row_data.get('roll_number')
            gender = (row_data.get('gender') or 'M')[:1].upper()
            dob = parse_date_safe(row_data.get('date_of_birth'))
            mobile = row_data.get('mobile_number', '')
            father_name = row_data.get('father_name', '')
            mother_name = row_data.get('mother_name', '')
            address = row_data.get('address', '')

            # Mandatory field check
            if not adm_no or not first_name or not grade_code or not section_name or not roll_number:
                result.errors.append({
                    "row": idx,
                    "field": "mandatory",
                    "error": f"Row {idx}: Missing mandatory fields."
                })
                continue

            # Duplicate check within file
            if adm_no in seen_admissions_in_file:
                result.duplicates.append({
                    "row": idx,
                    "identifier": adm_no,
                    "message": f"Duplicate admission number '{adm_no}' in import file."
                })
                continue
            seen_admissions_in_file.add(adm_no)

            # Duplicate check in database
            if Student.objects.filter(school=school, admission_number=adm_no).exists():
                result.duplicates.append({
                    "row": idx,
                    "identifier": adm_no,
                    "message": f"Student with admission number '{adm_no}' already exists in {school.name}."
                })
                continue

            # Grade & Section validation
            grade = GradeLevel.objects.filter(school=school, code__iexact=grade_code).first()
            if not grade:
                result.errors.append({
                    "row": idx,
                    "field": "grade_code",
                    "error": f"Grade code '{grade_code}' not found in school."
                })
                continue

            section = Section.objects.filter(school=school, grade_level=grade, name__iexact=section_name).first()
            if not section:
                result.errors.append({
                    "row": idx,
                    "field": "section_name",
                    "error": f"Section '{section_name}' for Grade '{grade.name}' not found."
                })
                continue

            # Roll duplicate check in section
            roll_key = (grade.id, section.id, roll_number)
            if roll_key in seen_rolls_in_file:
                result.duplicates.append({
                    "row": idx,
                    "identifier": f"{grade.code}-{section.name}-{roll_number}",
                    "message": f"Duplicate roll number '{roll_number}' for Grade {grade.name} Section {section.name} in file."
                })
                continue
            seen_rolls_in_file.add(roll_key)

            if Student.objects.filter(school=school, grade_level=grade, section=section, roll_number=roll_number).exists():
                result.duplicates.append({
                    "row": idx,
                    "identifier": f"{grade.code}-{section.name}-{roll_number}",
                    "message": f"Roll number '{roll_number}' already assigned in Section {section.name}."
                })
                continue

            valid_items.append({
                "admission_number": adm_no,
                "first_name": first_name,
                "last_name": last_name,
                "grade_level": grade,
                "section": section,
                "roll_number": roll_number,
                "gender": gender,
                "date_of_birth": dob,
                "emergency_contact_number": mobile,
                "current_address": address,
                "permanent_address": address,
                "father_name": father_name,
                "mother_name": mother_name,
            })

        result.valid_rows = len(valid_items)

        # Subscription limit check
        if current_active + len(valid_items) > max_allowed:
            result.errors.append({
                "row": 0,
                "field": "subscription",
                "error": f"Importing {len(valid_items)} students exceeds subscription limit of {max_allowed} (current: {current_active})."
            })
            return result

        if dry_run or len(result.errors) > 0:
            return result

        # Transactional commit
        with transaction.atomic():
            for item in valid_items:
                st = Student.objects.create(
                    school=school,
                    academic_year=current_ay,
                    admission_number=item["admission_number"],
                    first_name=item["first_name"],
                    last_name=item["last_name"],
                    grade_level=item["grade_level"],
                    section=item["section"],
                    roll_number=item["roll_number"],
                    gender=item["gender"],
                    date_of_birth=item["date_of_birth"],
                    emergency_contact_number=item["emergency_contact_number"],
                    current_address=item["current_address"],
                    permanent_address=item["permanent_address"],
                    is_active=True
                )
                if current_ay:
                    StudentEnrollment.objects.get_or_create(
                        student=st,
                        academic_year=current_ay,
                        defaults={
                            "school": school,
                            "grade_level": item["grade_level"],
                            "section": item["section"],
                            "roll_number": item["roll_number"],
                            "status": "ENROLLED"
                        }
                    )
                # Parent profile linkage if father/mother name supplied
                if item["father_name"] or item["emergency_contact_number"]:
                    parent_name = item["father_name"] or f"Parent of {st.first_name}"
                    parts = parent_name.split()
                    p_first = parts[0]
                    p_last = " ".join(parts[1:]) if len(parts) > 1 else ""
                    parent = ParentProfile.objects.create(
                        school=school,
                        first_name=p_first,
                        last_name=p_last,
                        relationship_type="Father",
                        mobile_number=item["emergency_contact_number"] or "0000000000",
                        address=item["current_address"]
                    )
                    StudentGuardianRelationship.objects.create(
                        student=st,
                        guardian=parent,
                        relationship_type="Father",
                        is_primary_contact=True
                    )
                result.imported_rows += 1

        result.is_success = True
        return result


class TeacherCSVImporter:
    """
    Imports faculty members with designation, credentials, and profile creation.
    """
    REQUIRED_COLUMNS = ['employee_code', 'first_name', 'designation_title', 'email']

    @classmethod
    def get_sample_csv(cls) -> str:
        headers = [
            'employee_code', 'first_name', 'last_name', 'designation_title',
            'email', 'mobile_number', 'gender', 'qualification', 'joining_date'
        ]
        sample_rows = [
            ['DPS-FAC-021', 'Ramesh', 'Sharma', 'PGT Mathematics', 'ramesh.math@dpsschool.org', '9876500001', 'M', 'M.Sc, B.Ed', '2024-06-01'],
            ['DPS-FAC-022', 'Sunita', 'Menon', 'TGT English', 'sunita.eng@dpsschool.org', '9876500002', 'F', 'M.A., B.Ed', '2024-06-01'],
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(sample_rows)
        return output.getvalue()

    @classmethod
    def import_csv(cls, school: School, file_content: str, dry_run: bool = False) -> CSVImportResult:
        result = CSVImportResult()
        reader = csv.DictReader(io.StringIO(file_content.strip()))
        
        if not reader.fieldnames:
            result.errors.append({"row": 0, "field": "header", "error": "CSV file is empty or missing headers."})
            return result

        normalized_headers = [h.strip().lower() for h in reader.fieldnames if h]
        missing = [req for req in cls.REQUIRED_COLUMNS if req not in normalized_headers]
        if missing:
            result.errors.append({
                "row": 0,
                "field": "headers",
                "error": f"Missing required columns: {', '.join(missing)}"
            })
            return result

        rows = list(reader)
        result.total_rows = len(rows)

        seen_codes = set()
        seen_emails = set()
        valid_items = []

        for idx, row in enumerate(rows, start=2):
            row_data = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items() if k}
            emp_code = row_data.get('employee_code')
            first_name = row_data.get('first_name')
            last_name = row_data.get('last_name', '')
            desig_title = row_data.get('designation_title')
            email = row_data.get('email')
            mobile = row_data.get('mobile_number', '')
            gender = (row_data.get('gender') or 'M')[:1].upper()
            qual = row_data.get('qualification', '')
            joining_date = parse_date_safe(row_data.get('joining_date')) or datetime.date.today()

            if not emp_code or not first_name or not desig_title or not email:
                result.errors.append({
                    "row": idx,
                    "field": "mandatory",
                    "error": f"Row {idx}: Missing mandatory fields."
                })
                continue

            if emp_code in seen_codes or TeacherProfile.objects.filter(school=school, employee_code=emp_code).exists():
                result.duplicates.append({
                    "row": idx,
                    "identifier": emp_code,
                    "message": f"Employee code '{emp_code}' already exists."
                })
                continue
            seen_codes.add(emp_code)

            if email in seen_emails or User.objects.filter(email__iexact=email).exists():
                result.duplicates.append({
                    "row": idx,
                    "identifier": email,
                    "message": f"User account with email '{email}' already exists in system."
                })
                continue
            seen_emails.add(email)

            desig, _ = Designation.objects.get_or_create(school=school, title=desig_title)

            valid_items.append({
                "employee_code": emp_code,
                "first_name": first_name,
                "last_name": last_name,
                "designation": desig,
                "email": email,
                "mobile_number": mobile,
                "gender": gender,
                "qualification": qual,
                "joining_date": joining_date,
            })

        result.valid_rows = len(valid_items)

        if dry_run or len(result.errors) > 0:
            return result

        with transaction.atomic():
            for item in valid_items:
                username = item["email"].split('@')[0]
                base_user = User.objects.create_user(
                    username=username,
                    email=item["email"],
                    password="TempPassword@123",
                    first_name=item["first_name"],
                    last_name=item["last_name"],
                    school=school,
                    requested_role="TEACHER",
                    approval_status="a",
                )
                TeacherProfile.objects.create(
                    user=base_user,
                    school=school,
                    employee_code=item["employee_code"],
                    first_name=item["first_name"],
                    last_name=item["last_name"],
                    designation=item["designation"],
                    gender=item["gender"],
                    qualification=item["qualification"],
                    mobile_number=item["mobile_number"],
                    email=item["email"],
                    joining_date=item["joining_date"],
                    is_active=True
                )
                Teacher.objects.create(
                    school=school,
                    name=f"{item['first_name']} {item['last_name']}".strip(),
                    employee_id=item["employee_code"],
                    designation=item["designation"],
                    mobile=item["mobile_number"],
                    email=item["email"]
                )
                result.imported_rows += 1

        result.is_success = True
        return result
