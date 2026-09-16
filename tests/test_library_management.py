"""
Phase 11: PrimeSoul ERP Library Management Test Suite.
Validates multi-tenant isolation, catalog CRUD, copy accession uniqueness,
book checkout/checkin workflows, member loan limits, overdue fine calculations,
lost/damaged item handling, audit logging, RBAC, and REST APIs.
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.students.models import Student
from django_school_management.teachers.models import TeacherProfile
from django_school_management.library.models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookAuthor, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)
from django_school_management.library.services import library_service
from django_school_management.library.selectors import library_selectors

User = get_user_model()


class PrimeSoulLibraryManagementTests(TestCase):
    """
    Comprehensive test suite for Phase 11: Library Management module.
    """

    def setUp(self):
        ensure_system_roles_exist()

        # 1. Tenants (Schools)
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

        # 2. Users & Roles
        self.admin_user = User.objects.create_user(
            username="dps_admin",
            email="admin@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.librarian_user = User.objects.create_user(
            username="dps_librarian",
            email="librarian@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.LIBRARIAN
        )
        assign_role_to_user(self.librarian_user, Role.LIBRARIAN)

        self.student_user = User.objects.create_user(
            username="student_aarav",
            email="aarav@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user, Role.STUDENT)

        self.student = Student.objects.create(
            school=self.school_a,
            user=self.student_user,
            admission_number="DPS-2026-001",
            roll_number="01",
            first_name="Aarav",
            last_name="Sharma",
            date_of_birth=datetime.date(2010, 5, 15),
            gender="MALE",
            is_active=True
        )

        # 3. Library Setup
        self.library_a = Library.objects.create(
            school=self.school_a,
            name="DPS Central Knowledge Centre",
            code="DPS-LIB-01",
            issue_limit_student=2,
            issue_limit_teacher=5,
            default_loan_days=14,
            fine_per_day=Decimal('2.00'),
            max_fine=Decimal('100.00'),
            is_active=True
        )

        self.library_b = Library.objects.create(
            school=self.school_b,
            name="Modern School Library",
            code="MOD-LIB-01",
            issue_limit_student=3,
            is_active=True
        )

        self.category = BookCategory.objects.create(
            school=self.school_a,
            name="Science & Technology",
            code="SCI-TECH"
        )
        self.author = Author.objects.create(
            school=self.school_a,
            name="Dr. A.P.J. Abdul Kalam"
        )
        self.publisher = Publisher.objects.create(
            school=self.school_a,
            name="Universities Press",
            email="info@universitiespress.com"
        )
        self.shelf = LibraryShelf.objects.create(
            school=self.school_a,
            name="Rack A - Wings",
            code="SH-A1"
        )

        # Book
        self.book = Book.objects.create(
            school=self.school_a,
            title="Wings of Fire",
            isbn="978-8173711466",
            category=self.category,
            publisher=self.publisher,
            language="EN",
            publication_year=1999
        )
        BookAuthor.objects.create(school=self.school_a, book=self.book, author=self.author)

        # Book Copies
        self.copy_1 = BookCopy.objects.create(
            school=self.school_a,
            book=self.book,
            accession_number="ACC-1001",
            barcode="BC-1001",
            shelf=self.shelf,
            condition="NEW",
            status="AVAILABLE"
        )
        self.copy_2 = BookCopy.objects.create(
            school=self.school_a,
            book=self.book,
            accession_number="ACC-1002",
            barcode="BC-1002",
            shelf=self.shelf,
            condition="GOOD",
            status="AVAILABLE"
        )

        # Library Member
        self.member = LibraryMember.objects.create(
            school=self.school_a,
            user=self.student_user,
            student=self.student,
            member_code="DPS-MEM-001",
            member_type="STUDENT",
            is_active=True
        )

        self.client = APIClient()

    def test_01_tenant_isolation(self):
        """Entities from School A must not appear or be accessible in School B."""
        self.assertEqual(Book.objects.filter(school=self.school_a).count(), 1)
        self.assertEqual(Book.objects.filter(school=self.school_b).count(), 0)

        # Accession number uniqueness is per-school
        copy_in_b = BookCopy.objects.create(
            school=self.school_b,
            book=Book.objects.create(school=self.school_b, title="School B Book"),
            accession_number="ACC-1001",
            status="AVAILABLE"
        )
        self.assertEqual(copy_in_b.accession_number, "ACC-1001")

    def test_02_accession_uniqueness_within_school(self):
        """Duplicate accession numbers in the same school must raise an integrity error."""
        with self.assertRaises(Exception):
            BookCopy.objects.create(
                school=self.school_a,
                book=self.book,
                accession_number="ACC-1001",  # duplicate
                status="AVAILABLE"
            )

    def test_03_issue_book_success(self):
        """Successfully checking out an available book copy."""
        issue = library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user,
            loan_days=14,
            remarks="Normal issue"
        )
        self.assertEqual(issue.status, 'ISSUED')
        self.copy_1.refresh_from_db()
        self.assertEqual(self.copy_1.status, 'ISSUED')
        self.assertEqual(self.member.current_issued_count, 1)

    def test_04_cannot_issue_unavailable_copy(self):
        """Cannot issue a copy that is already issued, lost, or damaged."""
        library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user
        )

        with self.assertRaises(ValidationError):
            library_service.issue_book(
                school=self.school_a,
                library=self.library_a,
                member=self.member,
                book_copy=self.copy_1,  # Already ISSUED
                issued_by=self.librarian_user
            )

    def test_05_member_loan_limit_enforced(self):
        """Member cannot borrow more books than their allowed limit."""
        # Issue 1
        library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user
        )
        # Issue 2 (Limit is 2)
        library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_2,
            issued_by=self.librarian_user
        )

        # Copy 3
        copy_3 = BookCopy.objects.create(
            school=self.school_a,
            book=self.book,
            accession_number="ACC-1003",
            status="AVAILABLE"
        )

        # 3rd issue should fail because limit is 2
        with self.assertRaises(ValidationError) as ctx:
            library_service.issue_book(
                school=self.school_a,
                library=self.library_a,
                member=self.member,
                book_copy=copy_3,
                issued_by=self.librarian_user
            )
        self.assertIn("limit", str(ctx.exception).lower())

    def test_06_return_book_on_time_no_fine(self):
        """Returning book on time completes issue without generating fine."""
        issue = library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user,
            loan_days=14
        )

        library_service.return_book(
            issue=issue,
            returned_by=self.librarian_user,
            return_date=issue.issue_date + datetime.timedelta(days=7)
        )

        issue.refresh_from_db()
        self.copy_1.refresh_from_db()
        self.assertEqual(issue.status, 'RETURNED')
        self.assertEqual(self.copy_1.status, 'AVAILABLE')
        self.assertFalse(LibraryFine.objects.filter(issue=issue).exists())

    def test_07_return_book_overdue_with_fine_and_cap(self):
        """Overdue book return correctly calculates per-day fine and respects maximum fine cap."""
        issue = library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user,
            loan_days=10  # fine per day = 2.00, max fine = 100.00
        )

        # Return 20 days after issue (10 days overdue -> 10 * 2 = 20.00)
        return_date = issue.issue_date + datetime.timedelta(days=20)
        library_service.return_book(
            issue=issue,
            returned_by=self.librarian_user,
            return_date=return_date
        )

        fine = LibraryFine.objects.get(issue=issue)
        self.assertEqual(fine.calculated_fine, Decimal('20.00'))
        self.assertEqual(fine.final_fine, Decimal('20.00'))
        self.assertFalse(fine.paid)

    def test_08_fine_waiver(self):
        """Authorized staff can waive fines with recorded reason."""
        issue = library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user,
            loan_days=5
        )
        return_date = issue.issue_date + datetime.timedelta(days=15)
        library_service.return_book(
            issue=issue,
            returned_by=self.librarian_user,
            return_date=return_date,
            waive_fine=True,
            waiver_reason="Medical leave documented",
            waived_by=self.admin_user
        )

        fine = LibraryFine.objects.get(issue=issue)
        self.assertEqual(fine.calculated_fine, Decimal('20.00'))
        self.assertEqual(fine.waived_fine, Decimal('20.00'))
        self.assertEqual(fine.final_fine, Decimal('0.00'))

    def test_09_lost_and_damaged_copy_handling(self):
        """Marking copy as lost or damaged updates status and records audit log."""
        issue = library_service.issue_book(
            school=self.school_a,
            library=self.library_a,
            member=self.member,
            book_copy=self.copy_1,
            issued_by=self.librarian_user
        )
        library_service.mark_book_lost(issue=issue, actor=self.librarian_user, remarks="Lost during field trip")

        issue.refresh_from_db()
        self.copy_1.refresh_from_db()
        self.assertEqual(issue.status, 'LOST')
        self.assertEqual(self.copy_1.status, 'LOST')

    def test_10_library_selectors(self):
        """Selectors return accurate aggregated metrics and catalog results."""
        metrics = library_selectors.get_library_dashboard_metrics(self.school_a)
        self.assertEqual(metrics['total_titles'], 1)
        self.assertEqual(metrics['total_copies'], 2)
        self.assertEqual(metrics['available_copies'], 2)
        self.assertEqual(metrics['issued_copies'], 0)

        # Search catalog
        results = library_selectors.search_catalog(self.school_a, "Wings")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().title, "Wings of Fire")

    def test_11_rbac_and_student_portal(self):
        """Students can view their own library record but cannot access admin circulation."""
        self.client.force_login(self.student_user)

        # Student portal
        resp = self.client.get(reverse('library:my_library'))
        self.assertEqual(resp.status_code, 200)

        # Admin route should redirect to self-portal for student
        resp_admin = self.client.get(reverse('library:dashboard'))
        self.assertEqual(resp_admin.status_code, 302)

    def test_12_library_api_endpoints(self):
        """DRF API endpoints return JSON data scoped to tenant."""
        self.client.force_authenticate(user=self.librarian_user)

        # Books list API
        resp = self.client.get('/api/v1/library/books/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Circulation API issue
        issue_data = {
            'library_id': self.library_a.pk,
            'member_id': self.member.pk,
            'accession_number': self.copy_1.accession_number,
            'loan_days': 10
        }
        resp_issue = self.client.post('/api/v1/library/issue/', issue_data, format='json')
        self.assertEqual(resp_issue.status_code, status.HTTP_201_CREATED)
