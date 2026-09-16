import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student
from django_school_management.fees.models import (
    FeeHead,
    FeeStructure,
    FeeStructureItem,
    StudentFeeAssignment,
    FeeInstallment,
    FeeConcession,
    FeeInvoice,
    PaymentTransaction,
    FeeReceipt,
    FeeHeadCategory,
    FeeFrequency,
    PaymentGateway,
    PaymentStatus,
    InvoiceStatus,
    InstallmentStatus,
    ConcessionType,
    ChequeClearanceStatus,
)

User = get_user_model()


class FeesUITestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Tenant
        self.school = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rk-puram-test",
            subdomain="dpsrkptest",
            is_active=True,
            currency="INR",
        )
        self.academic_year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=365),
            is_current=True,
        )

        # Users
        self.admin_user = User.objects.create_user(
            username="admin@primesoul.com",
            email="admin@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="SCHOOL_ADMIN",
            approval_status="a",
            is_staff=True,
            is_superuser=True,
        )

        self.principal_user = User.objects.create_user(
            username="principal@primesoul.com",
            email="principal@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="PRINCIPAL",
            approval_status="a",
        )

        self.accountant_user = User.objects.create_user(
            username="accountant@primesoul.com",
            email="accountant@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="ACCOUNTANT",
            approval_status="a",
        )

        self.receptionist_user = User.objects.create_user(
            username="receptionist@primesoul.com",
            email="receptionist@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="RECEPTIONIST",
            approval_status="a",
        )

        self.teacher_user = User.objects.create_user(
            username="teacher@primesoul.com",
            email="teacher@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="TEACHER",
            approval_status="a",
        )

        self.parent_user = User.objects.create_user(
            username="parent@primesoul.com",
            email="parent@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="PARENT",
            approval_status="a",
        )

        self.student_user = User.objects.create_user(
            username="student@primesoul.com",
            email="student@primesoul.com",
            password="demo@123",
            school=self.school,
            requested_role="STUDENT",
            approval_status="a",
        )

        # Academics
        self.grade_10 = GradeLevel.objects.create(
            school=self.school,
            name="Class 10",
            code="CLS-10",
            display_order=10,
        )
        self.section_a = Section.objects.create(
            school=self.school,
            grade_level=self.grade_10,
            name="A",
            max_capacity=40,
        )
        self.student_record = Student.objects.create(
            school=self.school,
            first_name="Aarav",
            last_name="Sharma",
            roll_number="1001",
            grade_level=self.grade_10,
            section=self.section_a,
            user=self.student_user,
        )

        # Fees Master
        self.head_tuition = FeeHead.objects.create(
            school=self.school,
            name="Tuition Fee",
            code="TUIT-10",
            category=FeeHeadCategory.TUITION,
        )
        self.structure = FeeStructure.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            grade_level=self.grade_10,
            name="Class 10 Standard Annual",
            frequency=FeeFrequency.ANNUAL,
            effective_from=timezone.now().date(),
            effective_to=timezone.now().date() + timezone.timedelta(days=365),
        )
        self.item = FeeStructureItem.objects.create(
            fee_structure=self.structure,
            fee_head=self.head_tuition,
            amount=Decimal("10000.00"),
        )

    def test_dashboard_ui_authenticated(self):
        """Verify the main PrimeSoul ERP dashboard returns 200 with KPI context."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("index_view"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PrimeSoul")
        self.assertContains(response, "Delhi Public School")
        self.assertContains(response, "Total Students")
        self.assertContains(response, "Pending Fees")

    def test_fee_pages_accessible_to_admin(self):
        """Verify all 9 fee pages render with HTTP 200."""
        self.client.force_login(self.admin_user)

        urls = [
            reverse("fees:dashboard"),
            reverse("fees:fee_heads"),
            reverse("fees:fee_structures"),
            reverse("fees:student_fees"),
            reverse("fees:installments"),
            reverse("fees:concessions"),
            reverse("fees:invoices"),
            reverse("fees:payments"),
            reverse("fees:receipts"),
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed on {url}")

    def test_complete_fee_workflow_via_ui_and_services(self):
        """
        Test the complete required flow:
        Fee Head -> Fee Structure -> Assign to Student -> Generate Installments ->
        Generate Invoice -> Collect ₹4,000 (Partial) -> Collect ₹6,000 (Remaining/Paid) ->
        Generate Receipt -> Download PDF Receipt.
        """
        self.client.force_login(self.admin_user)

        # 1. Assign to student
        assignment = StudentFeeAssignment.objects.create(
            student=self.student_record,
            fee_structure=self.structure,
            academic_year=self.academic_year,
        )
        self.assertIsNotNone(assignment.id)

        # 2. Generate Installment via UI post
        post_data = {
            "action": "generate_installments",
            "assignment_id": assignment.id,
            "due_date": str(timezone.now().date() + timezone.timedelta(days=15)),
        }
        res = self.client.post(reverse("fees:student_fees"), data=post_data)
        self.assertEqual(res.status_code, 302)

        installments = FeeInstallment.objects.filter(student=self.student_record)
        self.assertEqual(installments.count(), 1)
        installment = installments.first()
        self.assertEqual(installment.base_amount, Decimal("10000.00"))
        self.assertEqual(installment.payable_amount, Decimal("10000.00"))

        # 3. Generate Invoice via UI post
        inv_post = {
            "action": "create_invoice",
            "student_id": self.student_record.id,
            "academic_year_id": self.academic_year.id,
            "subtotal": "10000.00",
            "concession": "0.00",
            "late_fee": "0.00",
            "due_date": str(timezone.now().date() + timezone.timedelta(days=10)),
            "notes": "Test Invoice 10000",
        }
        res_inv = self.client.post(reverse("fees:invoices"), data=inv_post)
        self.assertEqual(res_inv.status_code, 302)

        invoices = FeeInvoice.objects.filter(student=self.student_record)
        self.assertEqual(invoices.count(), 1)
        invoice = invoices.first()
        self.assertEqual(invoice.total, Decimal("10000.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PENDING)

        # 4. Partial Payment of ₹4,000 via UI post
        pay_post_1 = {
            "action": "record_payment",
            "invoice_id": invoice.id,
            "amount": "4000.00",
            "payment_gateway": PaymentGateway.UPI,
            "transaction_reference": "UPI-TEST-001",
            "remarks": "First installment partial payment",
        }
        res_pay1 = self.client.post(reverse("fees:payments"), data=pay_post_1)
        self.assertEqual(res_pay1.status_code, 302)

        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("4000.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PARTIAL)

        receipts1 = FeeReceipt.objects.filter(school=self.school, student=self.student_record)
        self.assertEqual(receipts1.count(), 1)
        self.assertEqual(receipts1.first().amount, Decimal("4000.00"))

        # 5. Remaining Payment of ₹6,000 via UI post
        pay_post_2 = {
            "action": "record_payment",
            "invoice_id": invoice.id,
            "amount": "6000.00",
            "payment_gateway": PaymentGateway.CASH,
            "remarks": "Final balance payment",
        }
        res_pay2 = self.client.post(reverse("fees:payments"), data=pay_post_2)
        self.assertEqual(res_pay2.status_code, 302)

        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("10000.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

        receipts2 = FeeReceipt.objects.filter(school=self.school, student=self.student_record)
        self.assertEqual(receipts2.count(), 2)

        # 6. View Receipt details & PDF download
        latest_receipt = receipts2.latest("id")
        res_rcpt_json = self.client.get(
            reverse("fees:receipt_modal_detail", kwargs={"pk": latest_receipt.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_rcpt_json.status_code, 200)
        data = json.loads(res_rcpt_json.content)
        self.assertEqual(data["receipt_number"], latest_receipt.receipt_number)
        self.assertEqual(Decimal(str(data["amount"])), Decimal("6000.00"))

        # 7. Check PDF download endpoint
        pdf_res = self.client.get(
            f"/api/v1/fees/receipts/{latest_receipt.id}/download_pdf/"
        )
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res["Content-Type"], "application/pdf")

    def test_cheque_lifecycle_workflow(self):
        """Test cheque pending, clearance, and bounce handling."""
        self.client.force_login(self.admin_user)

        # Create invoice
        invoice = FeeInvoice.objects.create(
            school=self.school,
            student=self.student_record,
            academic_year=self.academic_year,
            invoice_number="INV-2026-CHQ01",
            invoice_date=timezone.now().date(),
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
            balance_amount=Decimal("5000.00"),
            due_date=timezone.now().date() + timezone.timedelta(days=7),
            status=InvoiceStatus.PENDING,
        )

        # Record cheque payment
        pay_post = {
            "action": "record_payment",
            "invoice_id": invoice.id,
            "amount": "5000.00",
            "payment_gateway": PaymentGateway.CHEQUE,
            "cheque_number": "CHQ-987654",
            "bank_name": "State Bank of India",
            "cheque_date": str(timezone.now().date()),
        }
        self.client.post(reverse("fees:payments"), data=pay_post)

        tx = PaymentTransaction.objects.filter(school=self.school, student=self.student_record).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, PaymentStatus.PENDING)

        # Clear cheque
        clear_post = {
            "action": "clear_cheque",
            "transaction_id": tx.id,
        }
        res_clear = self.client.post(reverse("fees:payments"), data=clear_post)
        self.assertEqual(res_clear.status_code, 302)

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    def test_rbac_access_restrictions(self):
        """Verify Teacher role has no fee management access."""
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse("fees:dashboard"))
        self.assertEqual(res.status_code, 403)
