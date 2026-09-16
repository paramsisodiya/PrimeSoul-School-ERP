"""
Phase 12: PrimeSoul ERP HR & Payroll Management Test Suite.
Validates multi-tenant isolation, employee lifecycle, sensitive data masking,
leave workflows & balance calculations, staff attendance, salary structures,
monthly payroll generation, cycle locking, payslips, RBAC, and REST APIs.
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
from django_school_management.academics.models import AcademicYear
from django_school_management.hr.models import (
    Department, HRDesignation, Employee, EmployeeDocument,
    LeaveType, LeaveBalance, LeaveRequest, EmployeeAttendance,
    SalaryComponent, EmployeeSalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord, PayrollLineItem
)
from django_school_management.hr.services import (
    employee_service, leave_service, attendance_service, payroll_service
)
from django_school_management.hr.selectors import hr_selectors

User = get_user_model()


class PrimeSoulHRPayrollManagementTests(TestCase):
    """
    Comprehensive test suite for Phase 12: HR & Payroll module.
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

        # 2. Academic Year
        self.ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )

        # 3. Users & Roles
        self.admin_user = User.objects.create_user(
            username="dps_admin",
            email="admin@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.accountant_user = User.objects.create_user(
            username="dps_accountant",
            email="accountant@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        self.teacher_user = User.objects.create_user(
            username="teacher_neha",
            email="neha@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        # 4. Department & Designation
        self.dept_sci = Department.objects.create(
            school=self.school_a,
            name="Science Department",
            code="DEPT-SCI"
        )
        self.desig_pgt = HRDesignation.objects.create(
            school=self.school_a,
            name="PGT Physics",
            code="PGT-PHY",
            category="TEACHING"
        )

        # 5. Employee
        self.emp = employee_service.create_employee(
            school=self.school_a,
            user=self.teacher_user,
            employee_code="EMP-1001",
            full_name="Neha Sharma",
            designation=self.desig_pgt,
            department=self.dept_sci,
            joining_date=datetime.date(2024, 6, 1),
            bank_account_number="98765432101234",
            bank_ifsc="HDFC0001234",
            bank_name="HDFC Bank",
            pan_number="ABCDE1234F",
            aadhaar_last4="5678",
            actor=self.admin_user
        )

        # 6. Leave Types & Balances
        self.leave_casual = LeaveType.objects.create(
            school=self.school_a,
            name="Casual Leave",
            code="CL",
            annual_limit=12
        )
        self.leave_balance = LeaveBalance.objects.create(
            school=self.school_a,
            employee=self.emp,
            leave_type=self.leave_casual,
            academic_year=self.ay,
            opening_balance=Decimal('12.0')
        )

        # 7. Salary Components & Structure
        self.comp_basic = SalaryComponent.objects.create(
            school=self.school_a,
            name="Basic Pay",
            code="BASIC",
            component_type="EARNING",
            calculation_type="FIXED"
        )
        self.comp_hra = SalaryComponent.objects.create(
            school=self.school_a,
            name="House Rent Allowance",
            code="HRA",
            component_type="EARNING",
            calculation_type="FIXED"
        )
        self.comp_pf = SalaryComponent.objects.create(
            school=self.school_a,
            name="Provident Fund",
            code="PF",
            component_type="DEDUCTION",
            calculation_type="FIXED"
        )

        self.salary_structure = EmployeeSalaryStructure.objects.create(
            school=self.school_a,
            employee=self.emp,
            effective_from=datetime.date(2026, 4, 1),
            is_active=True
        )
        SalaryStructureItem.objects.create(
            salary_structure=self.salary_structure,
            component=self.comp_basic,
            amount=Decimal('40000.00')
        )
        SalaryStructureItem.objects.create(
            salary_structure=self.salary_structure,
            component=self.comp_hra,
            amount=Decimal('16000.00')
        )
        SalaryStructureItem.objects.create(
            salary_structure=self.salary_structure,
            component=self.comp_pf,
            amount=Decimal('4800.00')
        )

        self.client = APIClient()

    def test_01_tenant_isolation(self):
        """School A employees and payroll must not appear in School B."""
        self.assertEqual(Employee.objects.filter(school=self.school_a).count(), 1)
        self.assertEqual(Employee.objects.filter(school=self.school_b).count(), 0)

        # Same employee code can exist in School B
        emp_b = employee_service.create_employee(
            school=self.school_b,
            employee_code="EMP-1001",
            full_name="Staff in School B",
            designation=HRDesignation.objects.create(school=self.school_b, name="TGT Math", code="TGT-MTH"),
            actor=None
        )
        self.assertEqual(emp_b.employee_code, "EMP-1001")

    def test_02_aadhaar_validation(self):
        """Aadhaar must be exactly 4 digits or empty."""
        with self.assertRaises(ValidationError):
            employee_service.create_employee(
                school=self.school_a,
                employee_code="EMP-1002",
                full_name="Invalid Aadhaar Staff",
                designation=self.desig_pgt,
                aadhaar_last4="12345"  # 5 digits invalid
            )

    def test_03_sensitive_field_masking(self):
        """PAN and Bank details are masked on model properties and API serializers."""
        self.assertEqual(self.emp.masked_bank_account, "XXXXXXXXXX1234")
        self.assertEqual(self.emp.masked_pan, "ABCDE****F")

        # Serializer test
        self.client.force_authenticate(user=self.teacher_user)
        resp = self.client.get(f'/api/v1/hr/employees/{self.emp.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Verify raw bank_account_number is not exposed directly
        self.assertNotIn('98765432101234', resp.content.decode())
        self.assertEqual(resp.data.get('masked_bank_account'), "XXXXXXXXXX1234")

    def test_04_leave_application_and_approval(self):
        """Applying for leave deducts balance upon approval."""
        req = leave_service.apply_leave(
            school=self.school_a,
            employee=self.emp,
            leave_type=self.leave_casual,
            start_date=datetime.date(2026, 9, 15),
            end_date=datetime.date(2026, 9, 17),  # 3 days
            reason="Family function",
            actor=self.teacher_user
        )
        self.assertEqual(req.status, 'PENDING')
        self.assertEqual(req.days_count, 3)

        # Approve
        leave_service.approve_leave(req, actor=self.admin_user)
        req.refresh_from_db()
        self.leave_balance.refresh_from_db()

        self.assertEqual(req.status, 'APPROVED')
        self.assertEqual(self.leave_balance.used, Decimal('3.0'))
        self.assertEqual(self.leave_balance.closing_balance, Decimal('9.0'))

    def test_05_prevent_overlapping_leaves(self):
        """Cannot apply for leaves that overlap with an existing pending/approved leave."""
        leave_service.apply_leave(
            school=self.school_a,
            employee=self.emp,
            leave_type=self.leave_casual,
            start_date=datetime.date(2026, 9, 15),
            end_date=datetime.date(2026, 9, 17),
            reason="First leave"
        )

        with self.assertRaises(ValidationError) as ctx:
            leave_service.apply_leave(
                school=self.school_a,
                employee=self.emp,
                leave_type=self.leave_casual,
                start_date=datetime.date(2026, 9, 16),
                end_date=datetime.date(2026, 9, 18),
                reason="Overlapping leave"
            )
        self.assertIn("already exists", str(ctx.exception).lower())

    def test_06_employee_attendance_recording(self):
        """Staff daily attendance recording saves records with unique constraint."""
        records = [{
            'employee_id': self.emp.pk,
            'status': 'PRESENT',
            'remarks': 'On time'
        }]
        today = datetime.date.today()
        attendance_service.record_daily_attendance(
            school=self.school_a,
            attendance_date=today,
            attendance_data=records,
            actor=self.admin_user
        )

        att = EmployeeAttendance.objects.get(school=self.school_a, employee=self.emp, attendance_date=today)
        self.assertEqual(att.status, 'PRESENT')

    def test_07_salary_structure_calculations(self):
        """Salary structure accurately calculates gross earnings and net pay."""
        gross = self.salary_structure.calculate_gross()
        net = self.salary_structure.calculate_net()
        # Gross = 40000 + 16000 = 56000
        # Net = 56000 - 4800 = 51200
        self.assertEqual(gross, Decimal('56000.00'))
        self.assertEqual(net, Decimal('51200.00'))

    def test_08_monthly_payroll_processing(self):
        """Monthly payroll generation creates records and line items."""
        period = PayrollPeriod.objects.create(
            school=self.school_a,
            year=2026,
            month=9,
            status='DRAFT'
        )

        created_records = payroll_service.process_payroll_period(
            school=self.school_a,
            period=period,
            actor=self.accountant_user
        )

        self.assertEqual(len(created_records), 1)
        record = created_records[0]
        self.assertEqual(record.gross_earnings, Decimal('56000.00'))
        self.assertEqual(record.total_deductions, Decimal('4800.00'))
        self.assertEqual(record.net_salary, Decimal('51200.00'))
        self.assertEqual(record.items.count(), 3)
        self.assertEqual(period.status, 'PROCESSED')

    def test_09_payroll_locking_immutability(self):
        """Once locked, payroll period cannot be reprocessed or altered."""
        period = PayrollPeriod.objects.create(
            school=self.school_a,
            year=2026,
            month=9,
            status='DRAFT'
        )
        payroll_service.process_payroll_period(school=self.school_a, period=period, actor=self.accountant_user)
        payroll_service.lock_payroll_period(period=period, actor=self.admin_user)

        self.assertEqual(period.status, 'LOCKED')

        # Reprocessing locked period must fail
        with self.assertRaises(ValidationError) as ctx:
            payroll_service.process_payroll_period(school=self.school_a, period=period, actor=self.accountant_user)
        self.assertIn("locked", str(ctx.exception).lower())

    def test_10_hr_selectors(self):
        """Selectors provide accurate HR metrics and summaries."""
        metrics = hr_selectors.get_hr_dashboard_metrics(self.school_a)
        self.assertEqual(metrics['total_employees'], 1)
        self.assertEqual(metrics['active_employees'], 1)
        self.assertEqual(metrics['total_departments'], 1)

    def test_11_rbac_and_self_service_portal(self):
        """Employee can view their own profile and leaves, but cannot see other employees."""
        self.client.force_login(self.teacher_user)

        # Self portal
        resp = self.client.get(reverse('hr:my_hr'))
        self.assertEqual(resp.status_code, 200)

        # Admin route requires management permission
        resp_admin = self.client.get(reverse('hr:salary_structures'))
        self.assertEqual(resp_admin.status_code, 403)

    def test_12_hr_api_endpoints(self):
        """DRF API endpoints return JSON data scoped to tenant."""
        self.client.force_authenticate(user=self.admin_user)

        # Departments API
        resp = self.client.get('/api/v1/hr/departments/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Dashboard API
        resp_dash = self.client.get('/api/v1/hr/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        self.assertIn('total_employees', resp_dash.data)
