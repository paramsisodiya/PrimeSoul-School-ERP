import hmac
import hashlib
import uuid
import datetime
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_school_management.fees.models import (
    PaymentTransaction, PaymentGateway, PaymentStatus,
    ChequeClearanceStatus, FeeInvoice, FeeInstallment
)
from .audit_service import log_fee_event
from .allocation_service import (
    auto_waterfall_allocation,
    rollback_payment_allocations,
    allocate_payment_to_installment,
    allocate_payment_to_invoice
)


def get_razorpay_credentials():
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
    return key_id, key_secret, webhook_secret


@transaction.atomic
def record_offline_payment(
    school,
    student,
    amount: Decimal,
    gateway: str, # CASH, CHEQUE, UPI, CARD, NET_BANKING, OTHER
    payment_method: str = "",
    transaction_id: str = None,
    invoice: FeeInvoice = None,
    installment: FeeInstallment = None,
    collected_by=None,
    notes: str = "",
    # Cheque fields
    cheque_number: str = "",
    bank_name: str = "",
    cheque_date=None,
    clearance_status: str = ChequeClearanceStatus.CLEARED,
    ip_address: str = None
) -> PaymentTransaction:
    """
    Records an offline cash/cheque/UPI/POS payment.
    If Cheque is PENDING, allocations and revenue recognition are deferred until cleared.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValueError("Payment amount must be greater than zero.")

    now = timezone.now()
    if not transaction_id:
        prefix = gateway[:3].upper()
        transaction_id = f"{prefix}-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    # Determine status based on gateway & cheque clearance
    if gateway == PaymentGateway.CHEQUE:
        if clearance_status == ChequeClearanceStatus.CLEARED:
            status = PaymentStatus.SUCCESS
            paid_at = now
            cleared_at = now
        elif clearance_status == ChequeClearanceStatus.BOUNCED:
            status = PaymentStatus.FAILED
            paid_at = None
            cleared_at = None
        else:
            status = PaymentStatus.PENDING
            paid_at = None
            cleared_at = None
    else:
        status = PaymentStatus.SUCCESS
        paid_at = now
        cleared_at = now
        clearance_status = ChequeClearanceStatus.CLEARED

    payment = PaymentTransaction.objects.create(
        school=school,
        student=student,
        invoice=invoice,
        transaction_id=transaction_id,
        gateway=gateway,
        payment_method=payment_method or gateway,
        amount=amount,
        currency="INR",
        status=status,
        paid_at=paid_at,
        notes=notes,
        collected_by=collected_by,
        cheque_number=cheque_number,
        bank_name=bank_name,
        cheque_date=cheque_date,
        clearance_status=clearance_status,
        cleared_at=cleared_at
    )

    # If successfully paid, perform allocation
    if status == PaymentStatus.SUCCESS:
        if installment:
            allocate_payment_to_installment(payment, installment, min(amount, installment.balance_amount), actor=collected_by, ip_address=ip_address)
        elif invoice:
            allocate_payment_to_invoice(payment, invoice, min(amount, invoice.balance_amount), actor=collected_by, ip_address=ip_address)
        else:
            auto_waterfall_allocation(payment, student, actor=collected_by, ip_address=ip_address)

    log_fee_event(
        school=school,
        action="OFFLINE_PAYMENT_RECORDED",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=collected_by,
        after_state={
            "transaction_id": payment.transaction_id,
            "amount": str(payment.amount),
            "gateway": payment.gateway,
            "status": payment.status,
            "clearance_status": payment.clearance_status
        },
        ip_address=ip_address
    )

    return payment


@transaction.atomic
def process_cheque_clearance(payment: PaymentTransaction, actor=None, ip_address=None) -> PaymentTransaction:
    """
    Clears a pending cheque payment, transitioning status to SUCCESS and allocating dues.
    """
    if payment.gateway != PaymentGateway.CHEQUE:
        raise ValueError("Cannot clear non-cheque payment via cheque clearance workflow.")

    if payment.clearance_status == ChequeClearanceStatus.CLEARED:
        return payment

    now = timezone.now()
    before_state = {
        "status": payment.status,
        "clearance_status": payment.clearance_status
    }

    payment.clearance_status = ChequeClearanceStatus.CLEARED
    payment.status = PaymentStatus.SUCCESS
    payment.cleared_at = now
    payment.paid_at = now
    payment.save(update_fields=['clearance_status', 'status', 'cleared_at', 'paid_at', 'updated_at'])

    # Allocate cleared funds
    if payment.invoice:
        allocate_payment_to_invoice(payment, payment.invoice, min(payment.amount, payment.invoice.balance_amount), actor=actor, ip_address=ip_address)
    else:
        auto_waterfall_allocation(payment, payment.student, actor=actor, ip_address=ip_address)

    log_fee_event(
        school=payment.school,
        action="CHEQUE_CLEARED",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=actor,
        before_state=before_state,
        after_state={"status": payment.status, "clearance_status": payment.clearance_status},
        ip_address=ip_address
    )

    return payment


@transaction.atomic
def process_cheque_bounce(payment: PaymentTransaction, reason: str = "Insufficient Funds", actor=None, ip_address=None) -> PaymentTransaction:
    """
    Marks a cheque as BOUNCED, transitions status to FAILED, and rolls back all allocations.
    """
    if payment.gateway != PaymentGateway.CHEQUE:
        raise ValueError("Cannot bounce non-cheque payment.")

    before_state = {
        "status": payment.status,
        "clearance_status": payment.clearance_status
    }

    payment.clearance_status = ChequeClearanceStatus.BOUNCED
    payment.status = PaymentStatus.FAILED
    payment.notes = f"{payment.notes} | Cheque Bounced: {reason}".strip(" |")
    payment.save(update_fields=['clearance_status', 'status', 'notes', 'updated_at'])

    # Roll back any previously allocated funds
    rollback_payment_allocations(payment, actor=actor, reason=f"Cheque Bounced: {reason}", ip_address=ip_address)

    log_fee_event(
        school=payment.school,
        action="CHEQUE_BOUNCED",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=actor,
        before_state=before_state,
        after_state={"status": payment.status, "clearance_status": payment.clearance_status, "reason": reason},
        ip_address=ip_address
    )

    return payment


# ==============================================================================
# RAZORPAY ONLINE PAYMENT INTEGRATION
# ==============================================================================

def create_razorpay_order_record(
    school,
    student,
    amount: Decimal,
    invoice: FeeInvoice = None,
    actor=None,
    ip_address=None
) -> PaymentTransaction:
    """
    Creates a server-side initiated PaymentTransaction and Razorpay Order ID.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValueError("Order amount must be greater than zero.")

    key_id, key_secret, _ = get_razorpay_credentials()
    order_id = f"order_{uuid.uuid4().hex[:14]}"

    # In production with razorpay installed and configured, create order via client:
    # client = razorpay.Client(auth=(key_id, key_secret))
    # rz_order = client.order.create({"amount": int(amount * 100), "currency": "INR", "receipt": ...})
    # order_id = rz_order['id']

    transaction_id = f"RZP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    payment = PaymentTransaction.objects.create(
        school=school,
        student=student,
        invoice=invoice,
        transaction_id=transaction_id,
        gateway=PaymentGateway.RAZORPAY,
        payment_method="ONLINE_RAZORPAY",
        amount=amount,
        currency="INR",
        status=PaymentStatus.INITIATED,
        razorpay_order_id=order_id,
        notes=f"Razorpay order initiated for {student.name}"
    )

    log_fee_event(
        school=school,
        action="RAZORPAY_ORDER_CREATED",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=actor,
        after_state={"order_id": order_id, "amount": str(amount), "transaction_id": transaction_id},
        ip_address=ip_address
    )

    return payment


def verify_razorpay_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, key_secret: str = None) -> bool:
    """
    Cryptographically verifies Razorpay payment signature using HMAC SHA256.
    """
    if not key_secret:
        _, key_secret, _ = get_razorpay_credentials()

    if not key_secret or not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return False

    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    expected_signature = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_signature, razorpay_signature)


@transaction.atomic
def complete_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    gateway_response: dict = None,
    actor=None,
    ip_address=None
) -> PaymentTransaction:
    """
    Server-side validation and completion of Razorpay payment.
    Idempotent: If payment is already SUCCESS, returns existing record.
    """
    payment = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).first()
    if not payment:
        raise ValueError(f"No payment transaction found matching Razorpay order {razorpay_order_id}")

    # Idempotency check: Already processed?
    if payment.status == PaymentStatus.SUCCESS:
        return payment

    # Cryptographic verification
    is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    if not is_valid:
        payment.status = PaymentStatus.FAILED
        payment.gateway_response = gateway_response or {"error": "Invalid signature"}
        payment.save(update_fields=['status', 'gateway_response', 'updated_at'])
        log_fee_event(
            school=payment.school,
            action="RAZORPAY_SIGNATURE_FAILED",
            model_name="PaymentTransaction",
            object_id=payment.pk,
            actor=actor,
            after_state={"order_id": razorpay_order_id, "payment_id": razorpay_payment_id},
            ip_address=ip_address
        )
        raise ValueError("Invalid Razorpay payment signature.")

    now = timezone.now()
    payment.status = PaymentStatus.SUCCESS
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.paid_at = now
    payment.gateway_response = gateway_response or {}
    payment.save(update_fields=['status', 'razorpay_payment_id', 'razorpay_signature', 'paid_at', 'gateway_response', 'updated_at'])

    # Automatic dues allocation
    if payment.invoice:
        allocate_payment_to_invoice(payment, payment.invoice, min(payment.amount, payment.invoice.balance_amount), actor=actor, ip_address=ip_address)
    else:
        auto_waterfall_allocation(payment, payment.student, actor=actor, ip_address=ip_address)

    log_fee_event(
        school=payment.school,
        action="RAZORPAY_PAYMENT_SUCCESS",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=actor,
        after_state={"order_id": razorpay_order_id, "payment_id": razorpay_payment_id, "amount": str(payment.amount)},
        ip_address=ip_address
    )

    return payment


def verify_razorpay_webhook_signature(payload_bytes: bytes, signature_header: str, webhook_secret: str = None) -> bool:
    """
    Validates HMAC SHA256 webhook signature from Razorpay.
    """
    if not webhook_secret:
        _, _, webhook_secret = get_razorpay_credentials()

    if not webhook_secret or not signature_header or not payload_bytes:
        return False

    expected_signature = hmac.new(webhook_secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)
