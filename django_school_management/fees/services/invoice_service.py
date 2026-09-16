import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Max
from django_school_management.fees.models import FeeInvoice, InvoiceStatus, FeeInstallment
from .audit_service import log_fee_event


def generate_next_invoice_number(school, year: int = None) -> str:
    """
    Safely generates the next sequential invoice number for a school tenant.
    Pattern: INV-{YEAR}-{SEQUENCE:05d} (e.g. INV-2026-00001)
    """
    if not year:
        year = datetime.date.today().year

    prefix = f"INV-{year}-"
    # Find the maximum existing invoice number with this prefix for this school
    latest_inv = (
        FeeInvoice.objects.filter(school=school, invoice_number__startswith=prefix)
        .order_by('-invoice_number')
        .values_list('invoice_number', flat=True)
        .first()
    )

    if latest_inv:
        try:
            seq_part = latest_inv.replace(prefix, "")
            next_seq = int(seq_part) + 1
        except (ValueError, TypeError):
            next_seq = FeeInvoice.objects.filter(school=school, invoice_number__startswith=prefix).count() + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


@transaction.atomic
def create_fee_invoice(
    school,
    student,
    academic_year,
    subtotal: Decimal,
    concession: Decimal = Decimal('0.00'),
    late_fee: Decimal = Decimal('0.00'),
    due_date=None,
    invoice_date=None,
    notes: str = "",
    installments=None,
    actor=None,
    ip_address=None
) -> FeeInvoice:
    """
    Creates a new FeeInvoice with atomic sequential numbering.
    """
    if not invoice_date:
        invoice_date = datetime.date.today()
    if not due_date:
        due_date = invoice_date + datetime.timedelta(days=15)

    subtotal = Decimal(str(subtotal))
    concession = Decimal(str(concession))
    late_fee = Decimal(str(late_fee))
    
    total = max(Decimal('0.00'), (subtotal - concession) + late_fee)
    invoice_number = generate_next_invoice_number(school, year=invoice_date.year)

    invoice = FeeInvoice.objects.create(
        school=school,
        student=student,
        academic_year=academic_year,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=subtotal,
        concession=concession,
        late_fee=late_fee,
        total=total,
        paid_amount=Decimal('0.00'),
        balance_amount=total,
        status=InvoiceStatus.PAID if total == Decimal('0.00') else InvoiceStatus.PENDING,
        notes=notes
    )

    log_fee_event(
        school=school,
        action="INVOICE_CREATED",
        model_name="FeeInvoice",
        object_id=invoice.pk,
        actor=actor,
        after_state={
            "invoice_number": invoice.invoice_number,
            "student_id": student.pk,
            "total": str(invoice.total),
            "due_date": str(invoice.due_date)
        },
        ip_address=ip_address
    )

    return invoice


@transaction.atomic
def cancel_fee_invoice(invoice: FeeInvoice, actor=None, reason: str = "", ip_address=None) -> FeeInvoice:
    """
    Cancels an unpaid or partially paid invoice.
    """
    if invoice.paid_amount > Decimal('0.00'):
        raise ValueError("Cannot cancel an invoice that has payments allocated. Refund or reallocate payments first.")

    before_state = {"status": invoice.status, "balance": str(invoice.balance_amount)}
    invoice.status = InvoiceStatus.CANCELLED
    invoice.notes = f"{invoice.notes} | Cancelled: {reason}".strip(" |")
    invoice.save(update_fields=['status', 'notes', 'updated_at'])

    log_fee_event(
        school=invoice.school,
        action="INVOICE_CANCELLED",
        model_name="FeeInvoice",
        object_id=invoice.pk,
        actor=actor,
        before_state=before_state,
        after_state={"status": invoice.status, "reason": reason},
        ip_address=ip_address
    )

    return invoice
