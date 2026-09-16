from decimal import Decimal
from django.db import transaction
from django_school_management.fees.models import (
    PaymentTransaction, PaymentAllocation, FeeInvoice, FeeInstallment,
    InstallmentStatus, InvoiceStatus, PaymentStatus
)
from .audit_service import log_fee_event


@transaction.atomic
def allocate_payment_to_installment(
    payment: PaymentTransaction,
    installment: FeeInstallment,
    amount: Decimal,
    actor=None,
    ip_address=None
) -> PaymentAllocation:
    """
    Allocates a portion of a PaymentTransaction to a single FeeInstallment atomically.
    Updates the installment's paid_amount and balance_amount.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValueError("Allocation amount must be strictly greater than zero.")

    # Check total allocations on this payment so far
    existing_allocated = sum([a.allocated_amount for a in payment.allocations.all()]) or Decimal('0.00')
    available_payment_funds = payment.amount - existing_allocated

    if amount > available_payment_funds:
        raise ValueError(
            f"Allocation ₹{amount} exceeds remaining unallocated payment funds ₹{available_payment_funds} (Total: ₹{payment.amount})"
        )

    if amount > installment.balance_amount:
        raise ValueError(
            f"Allocation ₹{amount} exceeds outstanding installment balance ₹{installment.balance_amount}"
        )

    # Create allocation record
    allocation = PaymentAllocation.objects.create(
        payment=payment,
        installment=installment,
        allocated_amount=amount
    )

    # Update installment state
    installment.paid_amount += amount
    installment.update_balance_and_status()

    log_fee_event(
        school=payment.school,
        action="PAYMENT_ALLOCATED_INSTALLMENT",
        model_name="PaymentAllocation",
        object_id=allocation.pk,
        actor=actor,
        after_state={
            "payment_id": payment.pk,
            "installment_id": installment.pk,
            "allocated_amount": str(amount),
            "new_installment_balance": str(installment.balance_amount),
            "new_installment_status": installment.status
        },
        ip_address=ip_address
    )

    return allocation


@transaction.atomic
def allocate_payment_to_invoice(
    payment: PaymentTransaction,
    invoice: FeeInvoice,
    amount: Decimal,
    actor=None,
    ip_address=None
) -> PaymentAllocation:
    """
    Allocates a portion of a PaymentTransaction to a FeeInvoice atomically.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValueError("Allocation amount must be strictly greater than zero.")

    existing_allocated = sum([a.allocated_amount for a in payment.allocations.all()]) or Decimal('0.00')
    available_payment_funds = payment.amount - existing_allocated

    if amount > available_payment_funds:
        raise ValueError(
            f"Allocation ₹{amount} exceeds remaining unallocated payment funds ₹{available_payment_funds}"
        )

    if amount > invoice.balance_amount:
        raise ValueError(
            f"Allocation ₹{amount} exceeds outstanding invoice balance ₹{invoice.balance_amount}"
        )

    allocation = PaymentAllocation.objects.create(
        payment=payment,
        invoice=invoice,
        allocated_amount=amount
    )

    invoice.paid_amount += amount
    invoice.update_balance_and_status()

    log_fee_event(
        school=payment.school,
        action="PAYMENT_ALLOCATED_INVOICE",
        model_name="PaymentAllocation",
        object_id=allocation.pk,
        actor=actor,
        after_state={
            "payment_id": payment.pk,
            "invoice_id": invoice.pk,
            "allocated_amount": str(amount),
            "new_invoice_balance": str(invoice.balance_amount),
            "new_invoice_status": invoice.status
        },
        ip_address=ip_address
    )

    return allocation


@transaction.atomic
def auto_waterfall_allocation(payment: PaymentTransaction, student, actor=None, ip_address=None):
    """
    Automatically allocates an unallocated payment amount against a student's pending/partial installments
    in chronological order (oldest due_date first).
    """
    existing_allocated = sum([a.allocated_amount for a in payment.allocations.all()]) or Decimal('0.00')
    remaining_payment = payment.amount - existing_allocated

    if remaining_payment <= Decimal('0.00'):
        return []

    # Get all outstanding installments for this student ordered by due date
    outstanding_installments = FeeInstallment.objects.filter(
        student=student,
        status__in=[InstallmentStatus.PENDING, InstallmentStatus.PARTIAL, InstallmentStatus.OVERDUE]
    ).order_by('due_date')

    allocations = []
    for inst in outstanding_installments:
        if remaining_payment <= Decimal('0.00'):
            break

        to_allocate = min(remaining_payment, inst.balance_amount)
        if to_allocate > Decimal('0.00'):
            alloc = allocate_payment_to_installment(
                payment=payment,
                installment=inst,
                amount=to_allocate,
                actor=actor,
                ip_address=ip_address
            )
            allocations.append(alloc)
            remaining_payment -= to_allocate

    return allocations


@transaction.atomic
def rollback_payment_allocations(payment: PaymentTransaction, actor=None, reason: str = "", ip_address=None):
    """
    Rolls back all allocations for a payment (e.g. when a cheque bounces or transaction is reversed/cancelled).
    Re-establishes previous balances on installments and invoices.
    """
    allocations = list(payment.allocations.select_related('installment', 'invoice').all())

    for alloc in allocations:
        if alloc.installment:
            inst = alloc.installment
            inst.paid_amount = max(Decimal('0.00'), inst.paid_amount - alloc.allocated_amount)
            inst.update_balance_and_status()

        if alloc.invoice:
            inv = alloc.invoice
            inv.paid_amount = max(Decimal('0.00'), inv.paid_amount - alloc.allocated_amount)
            inv.update_balance_and_status()

        alloc.delete()

    log_fee_event(
        school=payment.school,
        action="PAYMENT_ALLOCATIONS_ROLLEDBACK",
        model_name="PaymentTransaction",
        object_id=payment.pk,
        actor=actor,
        after_state={"reason": reason, "rolled_back_count": len(allocations)},
        ip_address=ip_address
    )
