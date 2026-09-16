import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from django_school_management.utils.india_localization import (
    is_valid_indian_mobile, clean_indian_mobile, format_inr,
    COUNTRY_CODE, CURRENCY_CODE, CURRENCY_SYMBOL
)
from django_school_management.accounts.models import User
from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel
from django_school_management.institute.models import EducationBoard
from django_school_management.institute.education_boards import COUNTRY_IN
from django_school_management.students.models import Student
from django_school_management.students.forms import StudentForm
from django_school_management.fees.models import (
    FeeInvoice, PaymentTransaction, FeeReceipt,
    PaymentGateway, PaymentStatus, ChequeClearanceStatus, InvoiceStatus
)
from django_school_management.fees.services.payment_service import (
    record_offline_payment, process_cheque_clearance, process_cheque_bounce
)
from django_school_management.fees.services.receipt_service import render_receipt_pdf_bytes


class IndiaLocalizationUnitTests(TestCase):
    """Tests the centralized India localization layer."""

    def test_constants(self):
        self.assertEqual(COUNTRY_CODE, "IN")
        self.assertEqual(CURRENCY_CODE, "INR")
        self.assertEqual(CURRENCY_SYMBOL, "₹")

    def test_is_valid_indian_mobile(self):
        # Valid Indian mobiles (10 digits starting with 6, 7, 8, 9)
        valid_numbers = [
            "9876543210",
            "+91 9876543210",
            "+91-9876543210",
            "09876543210",
            "919876543210",
            "8123456789",
            "7012345678",
            "6212345678",
        ]
        for num in valid_numbers:
            self.assertTrue(is_valid_indian_mobile(num), f"Failed for valid number: {num}")

        # Invalid numbers
        invalid_numbers = [
            "1234567890",  # Starts with 1
            "5555555555",  # Starts with 5
            "987654321",   # 9 digits
            "98765432100", # 11 digits without 0/+91
            "abcdefghij",
            "",
            None,
        ]
        for num in invalid_numbers:
            self.assertFalse(is_valid_indian_mobile(num), f"Should fail for invalid number: {num}")

    def test_clean_indian_mobile(self):
        self.assertEqual(clean_indian_mobile("+91 9876543210"), "9876543210")
        self.assertEqual(clean_indian_mobile("09876543210"), "9876543210")
        self.assertEqual(clean_indian_mobile("919876543210"), "9876543210")
        self.assertEqual(clean_indian_mobile("9876543210"), "9876543210")

    def test_format_inr(self):
        self.assertEqual(format_inr(100), "₹100.00")
        self.assertEqual(format_inr(1000), "₹1,000.00")
        self.assertEqual(format_inr(10000), "₹10,000.00")
        self.assertEqual(format_inr(150000), "₹1,50,000.00")
        self.assertEqual(format_inr(10000000), "₹1,00,00,000.00")

    def test_indian_education_boards_populated(self):
        boards = EducationBoard.get_boards_for_country('IN')
        self.assertTrue(boards.exists())
        board_names = [b.name for b in boards]
        self.assertTrue(any("CBSE" in name for name in board_names))
        self.assertTrue(any("ICSE" in name for name in board_names))


class StudentFormIndiaTests(TestCase):
    """Tests student admission form behavior with Indian mobile validation & Class 1-12 choices."""

    def test_student_form_indian_phone_validation(self):
        # Valid Indian phone
        form = StudentForm(data={
            'name': 'Rohan Verma',
            'gender': 'M',
            'mobile_number': '+91 9876543210',
            'guardian_mobile_number': '9876543211',
            'applying_for_class': '10',
        })
        form.is_valid()
        self.assertNotIn('mobile_number', form.errors)
        self.assertNotIn('guardian_mobile_number', form.errors)

    def test_student_form_rejects_invalid_phone(self):
        form = StudentForm(data={
            'name': 'Rohan Verma',
            'gender': 'M',
            'mobile_number': '12345',  # Invalid phone
        })
        form.is_valid()
        self.assertIn('mobile_number', form.errors)


class FeesWorkflowAndPDFTests(TestCase):
    """Tests receipt PDF download, overpayment prevention, and cheque clearance workflows."""

    def setUp(self):
        self.client = Client()
        self.school = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            subdomain="dpsdelhi-test",
            board="CBSE",
            country="India"
        )
        self.admin_user = User.objects.create_user(
            username="admin_test_qa",
            email="admin_qa@primesoul.com",
            password="demo@password123",
            requested_role="SCHOOL_ADMIN",
            school=self.school
        )
        self.acad_year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.grade = GradeLevel.objects.create(
            school=self.school,
            name="Class 10"
        )
        self.student = Student.objects.create(
            school=self.school,
            first_name="Aarav",
            last_name="Sharma",
            admission_number="ADM-TEST-001",
            roll_number="101",
            grade_level=self.grade,
            academic_year=self.acad_year,
            nationality="Indian"
        )
        self.client.force_login(self.admin_user)

    def test_receipt_pdf_download_endpoint(self):
        # Create payment & receipt
        payment = PaymentTransaction.objects.create(
            school=self.school,
            student=self.student,
            amount=Decimal("5000.00"),
            gateway=PaymentGateway.UPI,
            status=PaymentStatus.SUCCESS,
            transaction_id="TXN-TEST-PDF-1",
            paid_at=timezone.now()
        )
        receipt = FeeReceipt.objects.create(
            school=self.school,
            payment=payment,
            student=self.student,
            amount=payment.amount,
            payment_method="UPI",
            receipt_date=timezone.now().date(),
            receipt_number="REC-TEST-PDF-1",
            qr_verification_code="QR-TEST-CODE-1"
        )

        resp = self.client.get(f"/fees/receipts/{receipt.id}/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_overpayment_prevention_on_invoice(self):
        # Create ₹10,000 invoice
        invoice = FeeInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.acad_year,
            invoice_number="INV-OVERPAY-01",
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=30),
            subtotal=Decimal("10000.00"),
            total=Decimal("10000.00"),
            balance_amount=Decimal("10000.00"),
            status=InvoiceStatus.PENDING
        )

        # Attempt to pay ₹12,000 on ₹10,000 invoice via payments_view
        resp = self.client.post("/fees/payments/", {
            'action': 'collect_offline',
            'student_id': self.student.id,
            'invoice_id': invoice.id,
            'amount': '12000.00',  # Overpayment!
            'gateway': 'CASH'
        }, follow=True)

        # Must redirect back with error message
        self.assertEqual(resp.status_code, 200)
        messages_list = list(resp.context['messages'])
        self.assertTrue(any("cannot exceed" in m.message.lower() for m in messages_list))
        # Invoice balance should remain unchanged
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_amount, Decimal("10000.00"))

    def test_zero_or_negative_payment_prevention(self):
        resp = self.client.post("/fees/payments/", {
            'action': 'collect_offline',
            'student_id': self.student.id,
            'amount': '0.00',
            'gateway': 'CASH'
        }, follow=True)
        messages_list = list(resp.context['messages'])
        self.assertTrue(any("greater than" in m.message.lower() for m in messages_list))

    def test_cheque_clearance_and_bounce_lifecycle(self):
        # 1. Record cheque payment
        payment = record_offline_payment(
            school=self.school,
            student=self.student,
            amount=Decimal("4500.00"),
            gateway=PaymentGateway.CHEQUE,
            cheque_number="CHQ-00129",
            bank_name="HDFC Bank",
            clearance_status=ChequeClearanceStatus.PENDING
        )
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.clearance_status, ChequeClearanceStatus.PENDING)

        # 2. Clear cheque
        cleared = process_cheque_clearance(payment, actor=self.admin_user)
        self.assertEqual(cleared.status, PaymentStatus.SUCCESS)
        self.assertEqual(cleared.clearance_status, ChequeClearanceStatus.CLEARED)

        # 3. Test bounce handling on another cheque
        pay2 = record_offline_payment(
            school=self.school,
            student=self.student,
            amount=Decimal("3000.00"),
            gateway=PaymentGateway.CHEQUE,
            cheque_number="CHQ-00130",
            bank_name="State Bank of India",
            clearance_status=ChequeClearanceStatus.PENDING
        )
        bounced = process_cheque_bounce(pay2, reason="Insufficient Balance", actor=self.admin_user)
        self.assertEqual(bounced.status, PaymentStatus.FAILED)
        self.assertEqual(bounced.clearance_status, ChequeClearanceStatus.BOUNCED)
