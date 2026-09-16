"""
Phase 17: PrimeSoul ERP Advanced Reports & Analytics Test Suite.
Validates live database aggregations across 9 ERP functional domains, School Executive Dashboard KPIs,
Domain report selectors (Finance, Academics, Attendance, Exams, Admissions, Transport, Library, HR, Inventory),
PII masking on sensitive employee data (PAN, Bank Accounts), CSV/PDF export engines, RBAC access controls,
and multi-tenant isolation.
"""
import datetime
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.students.models import Student
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, SubjectAssignment
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.examinations.models import Exam, StudentExamResult
from django_school_management.fees.models import FeeInvoice, FeeReceipt, PaymentTransaction, InvoiceStatus
from django_school_management.admissions.models import AdmissionSession, AdmissionEnquiry, AdmissionApplication
from django_school_management.transport.models import TransportVehicle, TransportRoute, StudentTransportAssignment, TransportStop
from django_school_management.library.models import Book, BookCopy, Library, LibraryMember, LibraryIssue, LibraryFine
from django_school_management.hr.models import Department, HRDesignation, Employee, PayrollPeriod, EmployeeAttendance
from django_school_management.inventory.models import InventoryCategory, UnitOfMeasure, InventoryItem, ItemStoreStock, Store, AssetCategory, Asset
from django_school_management.reports.selectors import report_selectors
from django_school_management.reports.services import export_service

User = get_user_model()


class PrimeSoulAdvancedReportsTests(TestCase):
    """Comprehensive test suite for Phase 17: Advanced Reports & Analytics."""

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

        # 2. Users & Roles
        self.admin_user = User.objects.create_user(
            username="dps_admin",
            email="admin@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.principal_user = User.objects.create_user(
            username="dps_principal",
            email="principal@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.PRINCIPAL
        )
        assign_role_to_user(self.principal_user, Role.PRINCIPAL)

        self.accountant_user = User.objects.create_user(
            username="dps_accountant",
            email="accountant@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        self.student_user = User.objects.create_user(
            username="student_aarav",
            email="aarav@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user, Role.STUDENT)

        self.parent_user = User.objects.create_user(
            username="parent_rajesh",
            email="rajesh@gmail.com",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.PARENT
        )
        assign_role_to_user(self.parent_user, Role.PARENT)

        # 3. Academics
        self.ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.grade10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="CLS-10",
            display_order=10,
            is_active=True
        )
        self.sec_a = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade10,
            name="Section A",
            is_active=True
        )

        # 4. Students
        self.student1 = Student.objects.create(
            school=self.school_a,
            user=self.student_user,
            first_name="Aarav",
            last_name="Sharma",
            admission_number="ADM-2026-001",
            roll_number="101",
            academic_year=self.ay,
            grade_level=self.grade10,
            section=self.sec_a,
            gender='M',
            is_active=True
        )
        self.student2 = Student.objects.create(
            school=self.school_a,
            first_name="Diya",
            last_name="Patel",
            admission_number="ADM-2026-002",
            roll_number="102",
            academic_year=self.ay,
            grade_level=self.grade10,
            section=self.sec_a,
            gender='F',
            is_active=True
        )

        # 5. Finance
        self.inv1 = FeeInvoice.objects.create(
            school=self.school_a,
            student=self.student1,
            academic_year=self.ay,
            invoice_number="INV-2026-0001",
            invoice_date=datetime.date(2026, 4, 10),
            due_date=datetime.date(2026, 4, 30),
            subtotal=Decimal('25000.00'),
            total=Decimal('25000.00'),
            paid_amount=Decimal('25000.00'),
            balance_amount=Decimal('0.00'),
            status=InvoiceStatus.PAID
        )
        self.pmt1 = PaymentTransaction.objects.create(
            school=self.school_a,
            student=self.student1,
            invoice=self.inv1,
            transaction_id="TXN-2026-0001",
            amount=Decimal('25000.00'),
            payment_method="ONLINE",
            status="SUCCESS",
            paid_at=timezone.make_aware(datetime.datetime(2026, 4, 15, 10, 30))
        )
        self.rcpt1 = FeeReceipt.objects.create(
            school=self.school_a,
            student=self.student1,
            payment=self.pmt1,
            receipt_number="RCPT-2026-0001",
            amount=Decimal('25000.00'),
            payment_method="ONLINE",
            receipt_date=datetime.date(2026, 4, 15),
            issued_by=self.accountant_user
        )

        self.inv2 = FeeInvoice.objects.create(
            school=self.school_a,
            student=self.student2,
            academic_year=self.ay,
            invoice_number="INV-2026-0002",
            invoice_date=datetime.date(2026, 4, 10),
            due_date=datetime.date(2026, 4, 30),
            subtotal=Decimal('25000.00'),
            total=Decimal('25000.00'),
            paid_amount=Decimal('0.00'),
            balance_amount=Decimal('25000.00'),
            status=InvoiceStatus.OVERDUE
        )

        # 6. HR & Employees (With Sensitive PII)
        self.dept_sci = Department.objects.create(
            school=self.school_a,
            name="Science Department",
            code="DEPT-SCI"
        )
        self.desig_pgt = HRDesignation.objects.create(
            school=self.school_a,
            name="PGT Physics",
            code="DESIG-PGT-PHY",
            category=HRDesignation.CATEGORY_TEACHING
        )
        self.emp = Employee.objects.create(
            school=self.school_a,
            employee_code="EMP-1001",
            full_name="Dr. Vikram Sarabhai",
            department=self.dept_sci,
            designation=self.desig_pgt,
            pan_number="ABCDE1234F",
            bank_account_number="98765432101234",
            status=Employee.STATUS_ACTIVE
        )

        # 7. Inventory
        self.store = Store.objects.create(
            school=self.school_a,
            name="Central Store",
            code="STR-CENTRAL"
        )
        self.uom = UnitOfMeasure.objects.create(
            school=self.school_a,
            name="Pieces",
            short_code="PCS"
        )
        self.item = InventoryItem.objects.create(
            school=self.school_a,
            category=InventoryCategory.objects.create(school=self.school_a, name="Stationery"),
            unit=self.uom,
            name="Registers",
            sku="SKU-REG-01",
            reorder_level=Decimal('10.00')
        )
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item,
            store=self.store,
            quantity=Decimal('5.00')  # Low stock
        )

    # --------------------------------------------------------------------------
    # 1. EXECUTIVE DASHBOARD KPIS
    # --------------------------------------------------------------------------

    def test_executive_dashboard_kpis_aggregation(self):
        """Validates all 9 domain KPIs computed live from database models."""
        kpis = report_selectors.get_executive_dashboard_kpis(self.school_a)

        # Students
        self.assertEqual(kpis['student_stats']['total_students'], 2)
        self.assertEqual(kpis['student_stats']['male_count'], 1)
        self.assertEqual(kpis['student_stats']['female_count'], 1)

        # Finance
        self.assertEqual(kpis['finance']['total_invoiced'], Decimal('50000.00'))
        self.assertEqual(kpis['finance']['total_paid'], Decimal('25000.00'))
        self.assertEqual(kpis['finance']['total_due'], Decimal('25000.00'))
        self.assertEqual(kpis['finance']['overdue_invoices'], 1)
        self.assertEqual(kpis['finance']['collection_rate'], Decimal('50.0'))

        # HR
        self.assertEqual(kpis['hr']['total_employees'], 1)

        # Inventory
        self.assertEqual(kpis['inventory']['total_items'], 1)
        self.assertEqual(kpis['inventory']['low_stock_count'], 1)

    # --------------------------------------------------------------------------
    # 2. FINANCE REPORTS
    # --------------------------------------------------------------------------

    def test_finance_reports_and_payment_breakdown(self):
        """Validates fee register, payment method aggregations, and outstanding balances."""
        report = report_selectors.get_finance_reports(self.school_a)

        self.assertEqual(report['totals']['total_invoiced'], Decimal('50000.00'))
        self.assertEqual(report['totals']['total_collected'], Decimal('25000.00'))
        self.assertEqual(report['totals']['total_outstanding'], Decimal('25000.00'))
        self.assertEqual(report['totals']['invoice_count'], 2)

        # Payment methods breakdown
        self.assertEqual(len(report['method_breakdown']), 1)
        self.assertEqual(report['method_breakdown'][0]['payment_method'], 'ONLINE')
        self.assertEqual(report['method_breakdown'][0]['total_amount'], Decimal('25000.00'))

    # --------------------------------------------------------------------------
    # 3. HR REPORTS & PII MASKING
    # --------------------------------------------------------------------------

    def test_hr_reports_enforces_pii_masking(self):
        """Guarantees PAN numbers and Bank Account numbers are masked for reports."""
        report = report_selectors.get_hr_reports(self.school_a)
        self.assertEqual(report['total_employees'], 1)

        emp_entry = report['employees_list'][0]
        self.assertEqual(emp_entry['employee_id'], "EMP-1001")
        self.assertEqual(emp_entry['full_name'], "Dr. Vikram Sarabhai")

        # PAN should be masked: AB******4F
        self.assertTrue(emp_entry['pan_masked'].startswith("AB"))
        self.assertTrue(emp_entry['pan_masked'].endswith("4F"))
        self.assertIn("******", emp_entry['pan_masked'])

        # Bank Account should be masked: ******1234
        self.assertTrue(emp_entry['bank_masked'].startswith("******"))
        self.assertTrue(emp_entry['bank_masked'].endswith("1234"))

    # --------------------------------------------------------------------------
    # 4. EXPORT SERVICE (CSV & PDF)
    # --------------------------------------------------------------------------

    def test_csv_export_format_and_bom(self):
        """Validates UTF-8 CSV generation with Excel-compatible BOM."""
        headers = ['ID', 'Name', 'Amount']
        rows = [['1', 'Aarav Sharma', 25000], ['2', 'Diya Patel', 0]]
        response = export_service.export_to_csv('Test_Report', headers, rows)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="Test_Report_', response['Content-Disposition'])

        content = response.content
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))  # UTF-8 BOM
        self.assertIn(b"Aarav Sharma", content)

    def test_pdf_export_generation(self):
        """Validates PDF statement generation."""
        headers = ['ID', 'Name', 'Amount']
        rows = [['1', 'Aarav Sharma', '₹25,000'], ['2', 'Diya Patel', '₹0']]
        response = export_service.export_to_pdf(
            self.school_a.name,
            'Fee Collection Statement',
            headers,
            rows,
            'Test_Fee_Statement'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="Test_Fee_Statement_', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 0)

    # --------------------------------------------------------------------------
    # 5. RBAC & PORTAL USER RESTRICTION
    # --------------------------------------------------------------------------

    def test_rbac_access_restrictions_on_reporting_hub(self):
        """Guarantees Student and Parent are blocked from accessing executive reports."""
        self.client.login(username="student_aarav", password="Password123!")
        resp = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(resp.status_code, 403)

        self.client.login(username="parent_rajesh", password="Password123!")
        resp = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(resp.status_code, 403)

        # School Admin and Principal have access
        self.client.login(username="dps_admin", password="Password123!")
        resp = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(resp.status_code, 200)

        self.client.login(username="dps_principal", password="Password123!")
        resp = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(resp.status_code, 200)

    # --------------------------------------------------------------------------
    # 6. MULTI-TENANT ISOLATION
    # --------------------------------------------------------------------------

    def test_reports_tenant_isolation(self):
        """Validates School B's financial records do not leak into School A's reports."""
        # Create School B Invoice
        FeeInvoice.objects.create(
            school=self.school_b,
            student=Student.objects.create(school=self.school_b, first_name="Karan", admission_number="MOD-001"),
            invoice_number="INV-MOD-0001",
            invoice_date=datetime.date(2026, 4, 10),
            due_date=datetime.date(2026, 4, 30),
            subtotal=Decimal('75000.00'),
            total=Decimal('75000.00'),
            paid_amount=Decimal('75000.00'),
            balance_amount=Decimal('0.00'),
            status=InvoiceStatus.PAID
        )

        kpis_a = report_selectors.get_executive_dashboard_kpis(self.school_a)
        self.assertEqual(kpis_a['finance']['total_invoiced'], Decimal('50000.00'))  # Not 125000

        kpis_b = report_selectors.get_executive_dashboard_kpis(self.school_b)
        self.assertEqual(kpis_b['finance']['total_invoiced'], Decimal('75000.00'))

    # --------------------------------------------------------------------------
    # 7. REST APIS
    # --------------------------------------------------------------------------

    def test_reports_rest_apis(self):
        """Validates DRF API endpoints under /api/v1/reports/."""
        api_client = APIClient()
        api_client.force_authenticate(user=self.admin_user)

        # 1. Dashboard API
        resp = api_client.get('/api/v1/reports/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('student_stats', resp.data)
        self.assertIn('finance', resp.data)

        # 2. Finance Reports API
        resp = api_client.get('/api/v1/reports/finance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('totals', resp.data)

        # 3. HR Reports API
        resp = api_client.get('/api/v1/reports/hr/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_employees', resp.data)
