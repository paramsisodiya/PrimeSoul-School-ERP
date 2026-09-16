import json
import datetime
from decimal import Decimal
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.tenants.context import set_current_school, clear_current_school
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import AcademicYear, GradeLevel
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeStructureItem, FeeConcession, StudentFeeAssignment,
    FeeInstallment, FeeInvoice, PaymentTransaction, PaymentAllocation,
    FeeReceipt, FeeAuditLog, FeeHeadCategory, FeeFrequency, ConcessionType,
    InstallmentStatus, InvoiceStatus, PaymentGateway, PaymentStatus, ChequeClearanceStatus
)
from django_school_management.fees.services.installment_service import (
    generate_student_installments, calculate_concession_discount
)
from django_school_management.fees.services.invoice_service import (
    create_fee_invoice, cancel_fee_invoice, generate_next_invoice_number
)
from django_school_management.fees.services.payment_service import (
    record_offline_payment, process_cheque_clearance, process_cheque_bounce,
    create_razorpay_order_record, complete_razorpay_payment,
    verify_razorpay_signature, verify_razorpay_webhook_signature
)
from django_school_management.fees.services.allocation_service import (
    allocate_payment_to_installment, allocate_payment_to_invoice,
    auto_waterfall_allocation, rollback_payment_allocations
)
from django_school_management.fees.services.receipt_service import (
    generate_fee_receipt, generate_next_receipt_number
)
from django_school_management.fees.selectors.dashboard_selectors import get_fee_dashboard_summary

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['*'],
    RAZORPAY_KEY_ID='rzp_test_key123',
    RAZORPAY_KEY_SECRET='rzp_test_secret456',
    RAZORPAY_WEBHOOK_SECRET='rzp_webhook_secret789'
)
class PrimeSoulFeeManagementTests(TestCase):
    def setUp(self):
        clear_current_school()
        ensure_system_roles_exist()
        self.client = APIClient()

        # 1. School Tenants
        self.school_a = School.objects.create(
            name="Delhi Public School R.K. Puram",
            slug="dps-rkp",
            subdomain="dpsrkp",
            school_code="DEL102",
            is_active=True
        )
        self.school_b = School.objects.create(
            name="National Public School Bangalore",
            slug="nps-blr",
            subdomain="npsblr",
            school_code="BLR201",
            is_active=True
        )

        # 2. Academic Years & Grade Levels
        self.ay_a = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.grade_10_a = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="CLS-10",
            display_order=10
        )

        self.ay_b = AcademicYear.objects.create(
            school=self.school_b,
            name="2026-2027",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
            is_current=True
        )
        self.grade_10_b = GradeLevel.objects.create(
            school=self.school_b,
            name="Class 10",
            code="CLS-10",
            display_order=10
        )

        # 3. Users with RBAC Roles
        self.admin_user_a = User.objects.create_user(
            username="admin_dps",
            email="admin@dps.edu",
            password="pass",
            school=self.school_a,
            requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user_a, Role.SCHOOL_ADMIN)

        self.accountant_user_a = User.objects.create_user(
            username="accountant_dps",
            email="accounts@dps.edu",
            password="pass",
            school=self.school_a,
            requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user_a, Role.ACCOUNTANT)

        self.teacher_user_a = User.objects.create_user(
            username="teacher_dps",
            email="teacher@dps.edu",
            password="pass",
            school=self.school_a,
            requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user_a, Role.TEACHER)

        self.parent_user_a = User.objects.create_user(
            username="parent_arav",
            email="parent@example.com",
            password="pass",
            school=self.school_a,
            requested_role=Role.PARENT
        )
        assign_role_to_user(self.parent_user_a, Role.PARENT)

        self.student_user_a = User.objects.create_user(
            username="student_arav",
            email="arav@example.com",
            password="pass",
            school=self.school_a,
            requested_role=Role.STUDENT
        )
        assign_role_to_user(self.student_user_a, Role.STUDENT)

        # 4. Students
        self.parent_profile_a = ParentProfile.objects.create(
            school=self.school_a,
            user=self.parent_user_a,
            first_name="Sunil",
            last_name="Sharma",
            mobile_number="+919876543210"
        )
        self.student_a1 = Student.objects.create(
            school=self.school_a,
            user=self.student_user_a,
            first_name="Arav",
            last_name="Sharma",
            admission_number="ADM-2026-001",
            grade_level=self.grade_10_a,
            academic_year=self.ay_a,
            is_active=True
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_a1,
            guardian=self.parent_profile_a,
            is_primary_contact=True
        )

        self.student_b1 = Student.objects.create(
            school=self.school_b,
            first_name="Rohan",
            last_name="Nair",
            admission_number="ADM-BLR-001",
            grade_level=self.grade_10_b,
            academic_year=self.ay_b,
            is_active=True
        )

        # 5. Fee Heads
        self.tuition_head_a = FeeHead.objects.create(
            school=self.school_a,
            name="Tuition Fee",
            code="TUITION",
            category=FeeHeadCategory.TUITION
        )
        self.computer_head_a = FeeHead.objects.create(
            school=self.school_a,
            name="Computer Lab Fee",
            code="COMPUTER",
            category=FeeHeadCategory.COMPUTER
        )

    # --------------------------------------------------------------------------
    # 1. Fee Head Tenant Isolation
    # --------------------------------------------------------------------------
    def test_01_fee_head_tenant_isolation(self):
        head_b = FeeHead.objects.create(
            school=self.school_b,
            name="Tuition Fee",
            code="TUITION",
            category=FeeHeadCategory.TUITION
        )
        self.assertEqual(FeeHead.objects.filter(school=self.school_a, code="TUITION").count(), 1)
        self.assertEqual(FeeHead.objects.filter(school=self.school_b, code="TUITION").count(), 1)
        self.assertNotEqual(self.tuition_head_a.id, head_b.id)

    # --------------------------------------------------------------------------
    # 2. Fee Structure Creation
    # --------------------------------------------------------------------------
    def test_02_fee_structure_creation(self):
        structure = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade_10_a,
            name="Class 10 General Structure 2026-27",
            frequency=FeeFrequency.QUARTERLY,
            effective_from=datetime.date(2026, 4, 1),
            effective_to=datetime.date(2027, 3, 31)
        )
        FeeStructureItem.objects.create(
            fee_structure=structure,
            fee_head=self.tuition_head_a,
            amount=Decimal('20000.00'),
            due_day=10
        )
        FeeStructureItem.objects.create(
            fee_structure=structure,
            fee_head=self.computer_head_a,
            amount=Decimal('4000.00'),
            due_day=10
        )
        self.assertEqual(structure.total_structure_amount, Decimal('24000.00'))
        self.assertEqual(structure.items.count(), 2)

    # --------------------------------------------------------------------------
    # 3. Duplicate Fee Head Prevention
    # --------------------------------------------------------------------------
    def test_03_duplicate_fee_head_prevention(self):
        structure = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade_10_a,
            name="Structure Test",
            frequency=FeeFrequency.ANNUAL,
            effective_from=datetime.date(2026, 4, 1),
            effective_to=datetime.date(2027, 3, 31)
        )
        FeeStructureItem.objects.create(fee_structure=structure, fee_head=self.tuition_head_a, amount=Decimal('5000.00'))
        with self.assertRaises(IntegrityError):
            FeeStructureItem.objects.create(fee_structure=structure, fee_head=self.tuition_head_a, amount=Decimal('5000.00'))

    # --------------------------------------------------------------------------
    # 4. Student Fee Assignment
    # --------------------------------------------------------------------------
    def test_04_student_fee_assignment(self):
        structure = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade_10_a,
            name="Class 10 Regular",
            frequency=FeeFrequency.QUARTERLY,
            effective_from=datetime.date(2026, 4, 1),
            effective_to=datetime.date(2027, 3, 31)
        )
        assignment = StudentFeeAssignment.objects.create(
            student=self.student_a1,
            fee_structure=structure,
            academic_year=self.ay_a,
            status='ACTIVE'
        )
        self.assertEqual(assignment.student, self.student_a1)
        self.assertEqual(assignment.fee_structure, structure)
        # Check unique constraint on re-assignment
        with self.assertRaises(IntegrityError):
            StudentFeeAssignment.objects.create(
                student=self.student_a1,
                fee_structure=structure,
                academic_year=self.ay_a
            )

    # --------------------------------------------------------------------------
    # 5. Percentage Concession
    # --------------------------------------------------------------------------
    def test_05_percentage_concession(self):
        concession = FeeConcession.objects.create(
            school=self.school_a,
            name="Sibling Concession 25%",
            concession_type=ConcessionType.PERCENTAGE,
            value=Decimal('25.00'),
            maximum_amount=Decimal('10000.00')
        )
        discount = calculate_concession_discount(base_amount=Decimal('20000.00'), concession=concession)
        self.assertEqual(discount, Decimal('5000.00'))

    # --------------------------------------------------------------------------
    # 6. Fixed Concession
    # --------------------------------------------------------------------------
    def test_06_fixed_concession(self):
        concession = FeeConcession.objects.create(
            school=self.school_a,
            name="Staff Ward Flat ₹3000",
            concession_type=ConcessionType.FIXED_AMOUNT,
            value=Decimal('3000.00')
        )
        discount = calculate_concession_discount(base_amount=Decimal('10000.00'), concession=concession)
        self.assertEqual(discount, Decimal('3000.00'))

    # --------------------------------------------------------------------------
    # 7. Full Waiver
    # --------------------------------------------------------------------------
    def test_07_full_waiver(self):
        concession = FeeConcession.objects.create(
            school=self.school_a,
            name="RTE / EWS 100% Waiver",
            concession_type=ConcessionType.FULL_WAIVER,
            value=Decimal('100.00')
        )
        discount = calculate_concession_discount(base_amount=Decimal('15000.00'), concession=concession)
        self.assertEqual(discount, Decimal('15000.00'))

    # --------------------------------------------------------------------------
    # 8. Negative Payable Prevention
    # --------------------------------------------------------------------------
    def test_08_negative_payable_prevention(self):
        concession = FeeConcession.objects.create(
            school=self.school_a,
            name="Excessive Concession",
            concession_type=ConcessionType.FIXED_AMOUNT,
            value=Decimal('50000.00')
        )
        discount = calculate_concession_discount(base_amount=Decimal('10000.00'), concession=concession)
        # Discount cannot exceed base amount
        self.assertEqual(discount, Decimal('10000.00'))
        payable = max(Decimal('0.00'), Decimal('10000.00') - discount)
        self.assertEqual(payable, Decimal('0.00'))

    # --------------------------------------------------------------------------
    # 9. Monthly Installment Generation (12 months)
    # --------------------------------------------------------------------------
    def test_09_monthly_installment_generation(self):
        structure = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade_10_a,
            name="Monthly Structure",
            frequency=FeeFrequency.MONTHLY,
            effective_from=datetime.date(2026, 4, 1),
            effective_to=datetime.date(2027, 3, 31)
        )
        FeeStructureItem.objects.create(
            fee_structure=structure,
            fee_head=self.tuition_head_a,
            amount=Decimal('120000.00')
        )
        installments = generate_student_installments(
            student=self.student_a1,
            fee_structure=structure,
            academic_year=self.ay_a
        )
        self.assertEqual(len(installments), 12)
        total_payable = sum([i.payable_amount for i in installments])
        self.assertEqual(total_payable, Decimal('120000.00'))
        self.assertEqual(installments[0].installment_name, "April Fee")
        self.assertEqual(installments[11].installment_name, "March Fee")

    # --------------------------------------------------------------------------
    # 10. Quarterly Installment Generation (Q1 - Q4)
    # --------------------------------------------------------------------------
    def test_10_quarterly_installment_generation(self):
        structure = FeeStructure.objects.create(
            school=self.school_a,
            academic_year=self.ay_a,
            grade_level=self.grade_10_a,
            name="Quarterly Structure",
            frequency=FeeFrequency.QUARTERLY,
            effective_from=datetime.date(2026, 4, 1),
            effective_to=datetime.date(2027, 3, 31)
        )
        FeeStructureItem.objects.create(
            fee_structure=structure,
            fee_head=self.tuition_head_a,
            amount=Decimal('40000.00')
        )
        installments = generate_student_installments(
            student=self.student_a1,
            fee_structure=structure,
            academic_year=self.ay_a
        )
        self.assertEqual(len(installments), 4)
        self.assertEqual(installments[0].installment_name, "Q1 (Apr - Jun)")
        self.assertEqual(installments[1].installment_name, "Q2 (Jul - Sep)")
        self.assertEqual(installments[2].installment_name, "Q3 (Oct - Dec)")
        self.assertEqual(installments[3].installment_name, "Q4 (Jan - Mar)")
        self.assertEqual(installments[0].payable_amount, Decimal('10000.00'))

    # --------------------------------------------------------------------------
    # 11. Invoice Numbering Sequential Per School
    # --------------------------------------------------------------------------
    def test_11_invoice_numbering(self):
        inv1 = create_fee_invoice(self.school_a, self.student_a1, self.ay_a, subtotal=Decimal('5000.00'))
        inv2 = create_fee_invoice(self.school_a, self.student_a1, self.ay_a, subtotal=Decimal('6000.00'))
        year = datetime.date.today().year
        self.assertEqual(inv1.invoice_number, f"INV-{year}-00001")
        self.assertEqual(inv2.invoice_number, f"INV-{year}-00002")

    # --------------------------------------------------------------------------
    # 12. Concurrent Invoice Safety & Unique Constraints
    # --------------------------------------------------------------------------
    def test_12_concurrent_invoice_safety(self):
        inv_a = create_fee_invoice(self.school_a, self.student_a1, self.ay_a, subtotal=Decimal('1000.00'))
        # School B gets its own sequential numbering
        inv_b = create_fee_invoice(self.school_b, self.student_b1, self.ay_b, subtotal=Decimal('1000.00'))
        self.assertEqual(inv_a.invoice_number, inv_b.invoice_number) # Both have INV-YYYY-00001 in their respective schools
        self.assertNotEqual(inv_a.school_id, inv_b.school_id)

    # --------------------------------------------------------------------------
    # 13. Partial Payment
    # --------------------------------------------------------------------------
    def test_13_partial_payment(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1 Fee",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('10000.00'),
            payable_amount=Decimal('10000.00'),
            balance_amount=Decimal('10000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('4000.00'),
            gateway=PaymentGateway.CASH,
            installment=inst
        )
        inst.refresh_from_db()
        self.assertEqual(inst.paid_amount, Decimal('4000.00'))
        self.assertEqual(inst.balance_amount, Decimal('6000.00'))
        self.assertEqual(inst.status, InstallmentStatus.PARTIAL)

    # --------------------------------------------------------------------------
    # 14. Full Payment
    # --------------------------------------------------------------------------
    def test_14_full_payment(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1 Fee",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('10000.00'),
            payable_amount=Decimal('10000.00'),
            balance_amount=Decimal('10000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('10000.00'),
            gateway=PaymentGateway.CASH,
            installment=inst
        )
        inst.refresh_from_db()
        self.assertEqual(inst.paid_amount, Decimal('10000.00'))
        self.assertEqual(inst.balance_amount, Decimal('0.00'))
        self.assertEqual(inst.status, InstallmentStatus.PAID)

    # --------------------------------------------------------------------------
    # 15. Payment Allocation
    # --------------------------------------------------------------------------
    def test_15_payment_allocation(self):
        inst1 = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('5000.00'),
            payable_amount=Decimal('5000.00'),
            balance_amount=Decimal('5000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('5000.00'),
            gateway=PaymentGateway.UPI
        )
        allocations = list(payment.allocations.all())
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].allocated_amount, Decimal('5000.00'))
        self.assertEqual(allocations[0].installment, inst1)

    # --------------------------------------------------------------------------
    # 16. Over-Allocation Rejection
    # --------------------------------------------------------------------------
    def test_16_over_allocation_rejection(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('5000.00'),
            payable_amount=Decimal('5000.00'),
            balance_amount=Decimal('5000.00')
        )
        payment = PaymentTransaction.objects.create(
            school=self.school_a,
            student=self.student_a1,
            transaction_id="TEST-TXN-01",
            gateway=PaymentGateway.CASH,
            amount=Decimal('2000.00'),
            status=PaymentStatus.SUCCESS
        )
        with self.assertRaises(ValueError):
            # Attempt to allocate ₹3000 from a ₹2000 payment
            allocate_payment_to_installment(payment, inst, Decimal('3000.00'))

    # --------------------------------------------------------------------------
    # 17. Offline Cash Payment
    # --------------------------------------------------------------------------
    def test_17_offline_cash_payment(self):
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('7500.00'),
            gateway=PaymentGateway.CASH,
            collected_by=self.accountant_user_a
        )
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(payment.currency, "INR")
        self.assertIsNotNone(payment.paid_at)

    # --------------------------------------------------------------------------
    # 18. Cheque Pending
    # --------------------------------------------------------------------------
    def test_18_cheque_pending(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('8000.00'),
            payable_amount=Decimal('8000.00'),
            balance_amount=Decimal('8000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('8000.00'),
            gateway=PaymentGateway.CHEQUE,
            cheque_number="CHQ-987654",
            bank_name="State Bank of India",
            clearance_status=ChequeClearanceStatus.PENDING,
            collected_by=self.accountant_user_a
        )
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.clearance_status, ChequeClearanceStatus.PENDING)
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('8000.00')) # Dues not yet credited

    # --------------------------------------------------------------------------
    # 19. Cheque Cleared
    # --------------------------------------------------------------------------
    def test_19_cheque_cleared(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('8000.00'),
            payable_amount=Decimal('8000.00'),
            balance_amount=Decimal('8000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('8000.00'),
            gateway=PaymentGateway.CHEQUE,
            cheque_number="CHQ-987654",
            bank_name="HDFC Bank",
            clearance_status=ChequeClearanceStatus.PENDING
        )
        cleared = process_cheque_clearance(payment, actor=self.accountant_user_a)
        self.assertEqual(cleared.status, PaymentStatus.SUCCESS)
        self.assertEqual(cleared.clearance_status, ChequeClearanceStatus.CLEARED)
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('0.00'))
        self.assertEqual(inst.status, InstallmentStatus.PAID)

    # --------------------------------------------------------------------------
    # 20. Cheque Bounced
    # --------------------------------------------------------------------------
    def test_20_cheque_bounced(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('10000.00'),
            payable_amount=Decimal('10000.00'),
            balance_amount=Decimal('10000.00')
        )
        payment = record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('10000.00'),
            gateway=PaymentGateway.CHEQUE,
            cheque_number="CHQ-BOUNCE-1",
            clearance_status=ChequeClearanceStatus.CLEARED # temporarily cleared
        )
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('0.00'))

        # Now bounce it
        bounced = process_cheque_bounce(payment, reason="Insufficient Funds", actor=self.accountant_user_a)
        self.assertEqual(bounced.status, PaymentStatus.FAILED)
        self.assertEqual(bounced.clearance_status, ChequeClearanceStatus.BOUNCED)
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('10000.00')) # Dues reinstated!
        self.assertEqual(inst.status, InstallmentStatus.PENDING)

    # --------------------------------------------------------------------------
    # 21. Razorpay Signature Verification
    # --------------------------------------------------------------------------
    def test_21_razorpay_signature_verification(self):
        import hmac, hashlib
        order_id = "order_987654"
        payment_id = "pay_123456"
        secret = "rzp_test_secret456"
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        self.assertTrue(verify_razorpay_signature(order_id, payment_id, valid_sig, secret))
        self.assertFalse(verify_razorpay_signature(order_id, payment_id, "invalid_sig_abc", secret))

    # --------------------------------------------------------------------------
    # 22. Invalid Webhook Rejection
    # --------------------------------------------------------------------------
    def test_22_invalid_webhook_rejection(self):
        payload = b'{"event": "payment.captured"}'
        self.assertFalse(verify_razorpay_webhook_signature(payload, "forged_signature_123"))

    # --------------------------------------------------------------------------
    # 23. Duplicate Webhook Idempotency
    # --------------------------------------------------------------------------
    def test_23_duplicate_webhook_idempotency(self):
        inst = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('5000.00'),
            payable_amount=Decimal('5000.00'),
            balance_amount=Decimal('5000.00')
        )
        payment = create_razorpay_order_record(self.school_a, self.student_a1, Decimal('5000.00'))
        import hmac, hashlib
        secret = "rzp_test_secret456"
        msg = f"{payment.razorpay_order_id}|pay_test_999".encode('utf-8')
        sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        # First completion
        completed1 = complete_razorpay_payment(payment.razorpay_order_id, "pay_test_999", sig)
        self.assertEqual(completed1.status, PaymentStatus.SUCCESS)
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('0.00'))

        # Duplicate delivery
        completed2 = complete_razorpay_payment(payment.razorpay_order_id, "pay_test_999", sig)
        self.assertEqual(completed2.id, completed1.id)
        inst.refresh_from_db()
        self.assertEqual(inst.balance_amount, Decimal('0.00')) # No double crediting!

    # --------------------------------------------------------------------------
    # 24. Receipt Numbering Sequential Per School
    # --------------------------------------------------------------------------
    def test_24_receipt_numbering(self):
        p1 = record_offline_payment(self.school_a, self.student_a1, Decimal('1000.00'), gateway=PaymentGateway.CASH)
        p2 = record_offline_payment(self.school_a, self.student_a1, Decimal('2000.00'), gateway=PaymentGateway.CASH)
        r1 = generate_fee_receipt(p1)
        r2 = generate_fee_receipt(p2)
        year = datetime.date.today().year
        self.assertEqual(r1.receipt_number, f"RCP-{year}-00001")
        self.assertEqual(r2.receipt_number, f"RCP-{year}-00002")

    # --------------------------------------------------------------------------
    # 25. Accountant Permissions
    # --------------------------------------------------------------------------
    def test_25_accountant_permissions(self):
        self.client.force_authenticate(user=self.accountant_user_a)
        response = self.client.get('/api/v1/fees/fee-heads/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create invoice as accountant
        response = self.client.post('/api/v1/fees/invoices/', {
            'student': self.student_a1.id,
            'academic_year': self.ay_a.id,
            'invoice_date': '2026-04-10',
            'due_date': '2026-04-25',
            'subtotal': '15000.00',
            'total': '15000.00'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --------------------------------------------------------------------------
    # 26. Teacher Financial Access Rejection
    # --------------------------------------------------------------------------
    def test_26_teacher_financial_access_rejection(self):
        self.client.force_authenticate(user=self.teacher_user_a)
        # Teacher trying to collect payments
        response = self.client.post('/api/v1/fees/payments/collect_offline/', {
            'student_id': self.student_a1.id,
            'amount': '5000.00',
            'gateway': 'CASH'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Teacher trying to view installments
        response = self.client.get('/api/v1/fees/installments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --------------------------------------------------------------------------
    # 27. Parent Can Only See Own Child's Fees
    # --------------------------------------------------------------------------
    def test_27_parent_can_only_see_own_child_fees(self):
        inst_a = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1 Arav",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('5000.00'),
            payable_amount=Decimal('5000.00'),
            balance_amount=Decimal('5000.00')
        )
        # Student A2 in same school but different parent
        student_a2 = Student.objects.create(
            school=self.school_a,
            first_name="Other",
            last_name="Child",
            admission_number="ADM-002",
            grade_level=self.grade_10_a,
            academic_year=self.ay_a
        )
        inst_a2 = FeeInstallment.objects.create(
            student=student_a2,
            academic_year=self.ay_a,
            installment_name="Q1 Other",
            due_date=datetime.date(2026, 4, 10),
            base_amount=Decimal('5000.00'),
            payable_amount=Decimal('5000.00'),
            balance_amount=Decimal('5000.00')
        )

        self.client.force_authenticate(user=self.parent_user_a)
        response = self.client.get('/api/v1/fees/installments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        installment_ids = [item['id'] for item in results]
        self.assertIn(inst_a.id, installment_ids)
        self.assertNotIn(inst_a2.id, installment_ids)

    # --------------------------------------------------------------------------
    # 28. Cross-School Financial Access Rejection
    # --------------------------------------------------------------------------
    def test_28_cross_school_financial_access_rejection(self):
        # Admin of School A attempting to access School B's fee head
        head_b = FeeHead.objects.create(
            school=self.school_b,
            name="Hostel Fee",
            code="HOSTEL_B",
            category=FeeHeadCategory.HOSTEL
        )
        self.client.force_authenticate(user=self.admin_user_a)
        response = self.client.get(f'/api/v1/fees/fee-heads/{head_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --------------------------------------------------------------------------
    # 29. Dashboard Aggregation Correctness
    # --------------------------------------------------------------------------
    def test_29_dashboard_aggregation_correctness(self):
        inst1 = FeeInstallment.objects.create(
            student=self.student_a1,
            academic_year=self.ay_a,
            installment_name="Q1",
            due_date=datetime.date.today(),
            base_amount=Decimal('10000.00'),
            payable_amount=Decimal('10000.00'),
            balance_amount=Decimal('10000.00')
        )
        record_offline_payment(
            school=self.school_a,
            student=self.student_a1,
            amount=Decimal('6000.00'),
            gateway=PaymentGateway.CASH,
            installment=inst1
        )
        summary = get_fee_dashboard_summary(self.school_a)
        self.assertEqual(summary['total_fee_expected'], Decimal('10000.00'))
        self.assertEqual(summary['total_fee_collected'], Decimal('6000.00'))
        self.assertEqual(summary['total_fee_outstanding'], Decimal('4000.00'))
        self.assertEqual(summary['today_collection'], Decimal('6000.00'))

    # --------------------------------------------------------------------------
    # 30. Audit Log Creation
    # --------------------------------------------------------------------------
    def test_30_audit_log_creation(self):
        initial_log_count = FeeAuditLog.objects.filter(school=self.school_a).count()
        inv = create_fee_invoice(
            school=self.school_a,
            student=self.student_a1,
            academic_year=self.ay_a,
            subtotal=Decimal('8000.00'),
            actor=self.accountant_user_a
        )
        new_log_count = FeeAuditLog.objects.filter(school=self.school_a).count()
        self.assertEqual(new_log_count, initial_log_count + 1)
        latest_log = FeeAuditLog.objects.filter(school=self.school_a).first()
        self.assertEqual(latest_log.action, "INVOICE_CREATED")
        self.assertEqual(latest_log.actor, self.accountant_user_a)
