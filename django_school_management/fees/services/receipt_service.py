import io
import hashlib
import datetime
from decimal import Decimal
from django.db import transaction
from django.core.files.base import ContentFile
from django_school_management.fees.models import FeeReceipt, PaymentTransaction, PaymentStatus
from .audit_service import log_fee_event

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_next_receipt_number(school, year: int = None) -> str:
    """
    Safely generates the next sequential receipt number for a school tenant.
    Pattern: RCP-{YEAR}-{SEQUENCE:05d} (e.g. RCP-2026-00001)
    """
    if not year:
        year = datetime.date.today().year

    prefix = f"RCP-{year}-"
    latest_rcp = (
        FeeReceipt.objects.filter(school=school, receipt_number__startswith=prefix)
        .order_by('-receipt_number')
        .values_list('receipt_number', flat=True)
        .first()
    )

    if latest_rcp:
        try:
            seq_part = latest_rcp.replace(prefix, "")
            next_seq = int(seq_part) + 1
        except (ValueError, TypeError):
            next_seq = FeeReceipt.objects.filter(school=school, receipt_number__startswith=prefix).count() + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


def generate_receipt_qr_code_payload(school, receipt_number: str, student_name: str, amount: Decimal) -> str:
    """
    Generates a tamper-evident verification string for QR verification on printed fee receipts.
    """
    secret = getattr(school, 'code', 'PRIMESOUL')
    raw = f"{school.id}:{receipt_number}:{student_name}:{amount}:{secret}"
    signature = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"VERIFY:PS-ERP|SCH:{school.id}|RCP:{receipt_number}|AMT:{amount}|SIG:{signature}"


def render_receipt_pdf_bytes(receipt: FeeReceipt) -> bytes:
    """
    Renders a clean, professional school fee receipt in PDF format.
    """
    if not REPORTLAB_AVAILABLE:
        return b"%PDF-1.4 Mock Receipt File"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'SchoolTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        alignment=1, # Center
        textColor=colors.HexColor('#1E293B')
    )
    subtitle_style = ParagraphStyle(
        'SchoolSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#64748B')
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )

    elements = []

    # School Header
    school = receipt.school
    elements.append(Paragraph(f"<b>{school.name.upper()}</b>", title_style))
    elements.append(Paragraph(f"{school.address or 'Indian CBSE / ICSE / State Affiliated School'}", subtitle_style))
    school_phone = getattr(school, 'phone', '')
    school_email = getattr(school, 'email', '')
    contact_parts = []
    if school_phone:
        contact_parts.append(f"Contact: {school_phone}")
    if school_email:
        contact_parts.append(f"Email: {school_email}")
    if contact_parts:
        elements.append(Paragraph(" | ".join(contact_parts), subtitle_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=10))

    # Receipt Metadata Header
    elements.append(Paragraph("<b>OFFICIAL FEE PAYMENT RECEIPT</b>", ParagraphStyle('Sub', parent=title_style, fontSize=12, leading=14, textColor=colors.HexColor('#2563EB'))))
    elements.append(Spacer(1, 10))

    # Student & Receipt Details Table
    student = receipt.student
    student_class = getattr(student, 'grade_level', None)
    class_name = student_class.name if student_class else "N/A"
    admission_no = getattr(student, 'admission_number', '') or getattr(student, 'roll_number', str(student.pk))
    student_full_name = f"{student.first_name} {student.last_name}".strip() if (hasattr(student, 'first_name') and student.first_name) else getattr(student, 'name', 'Student')

    info_data = [
        [
            Paragraph(f"<b>Receipt No:</b> {receipt.receipt_number}", styles['Normal']),
            Paragraph(f"<b>Date:</b> {receipt.receipt_date.strftime('%d-%b-%Y')}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Student Name:</b> {student_full_name}", styles['Normal']),
            Paragraph(f"<b>Roll / Adm No:</b> {admission_no}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Class / Grade:</b> {class_name}", styles['Normal']),
            Paragraph(f"<b>Payment Mode:</b> {receipt.payment_method}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Transaction Ref:</b> {receipt.payment.transaction_id if receipt.payment else 'N/A'}", styles['Normal']),
            Paragraph(f"<b>Status:</b> {receipt.payment.get_status_display() if (receipt.payment and hasattr(receipt.payment, 'get_status_display')) else 'SUCCESS'}", styles['Normal'])
        ]
    ]

    info_table = Table(info_data, colWidths=[260, 260])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # Allocations / Fee Breakup Table
    allocations = list(receipt.payment.allocations.select_related('installment', 'invoice').all()) if receipt.payment else []
    table_rows = [
        [
            Paragraph("<b>S.No.</b>", styles['Normal']),
            Paragraph("<b>Fee Particulars / Installment</b>", styles['Normal']),
            Paragraph("<b>Paid Amount (INR)</b>", styles['Normal'])
        ]
    ]

    if allocations:
        for idx, alloc in enumerate(allocations, 1):
            desc = (alloc.installment.title if hasattr(alloc.installment, 'title') else getattr(alloc.installment, 'installment_name', 'Installment')) if alloc.installment else (f"Invoice #{alloc.invoice.invoice_number}" if alloc.invoice else "Fee Payment")
            table_rows.append([
                str(idx),
                desc,
                f"INR {alloc.allocated_amount:,.2f}"
            ])
    else:
        table_rows.append(["1", "Direct Student Fee Payment", f"INR {receipt.amount:,.2f}"])

    table_rows.append(["", "<b>TOTAL RECEIVED</b>", f"<b>INR {receipt.amount:,.2f}</b>"])

    items_table = Table(table_rows, colWidths=[40, 360, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 20))

    # Verification and Signature
    sig_data = [
        [
            Paragraph(f"<b>Verification QR Payload:</b><br/><font size='7'>{receipt.qr_verification_code}</font>", subtitle_style),
            Paragraph("<b>Authorised Signatory / Accounts Office</b><br/><br/>___________________________", ParagraphStyle('Sig', parent=styles['Normal'], alignment=2))
        ]
    ]
    sig_table = Table(sig_data, colWidths=[300, 220])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


@transaction.atomic
def generate_fee_receipt(payment: PaymentTransaction, issued_by=None, ip_address=None) -> FeeReceipt:
    """
    Generates a FeeReceipt for a successful PaymentTransaction.
    """
    if payment.status != PaymentStatus.SUCCESS:
        raise ValueError("Cannot issue receipt for non-successful payment.")

    # Idempotent receipt creation
    if hasattr(payment, 'receipt') and payment.receipt:
        return payment.receipt

    school = payment.school
    student = payment.student
    student_full_name = f"{student.first_name} {student.last_name}".strip() if (hasattr(student, 'first_name') and student.first_name) else getattr(student, 'name', 'Student')
    receipt_number = generate_next_receipt_number(school)
    qr_code = generate_receipt_qr_code_payload(school, receipt_number, student_full_name, payment.amount)

    receipt = FeeReceipt.objects.create(
        school=school,
        receipt_number=receipt_number,
        payment=payment,
        student=student,
        amount=payment.amount,
        payment_method=payment.get_gateway_display(),
        receipt_date=datetime.date.today(),
        qr_verification_code=qr_code,
        issued_by=issued_by
    )

    # Render PDF and attach
    try:
        pdf_bytes = render_receipt_pdf_bytes(receipt)
        filename = f"receipt_{receipt.receipt_number}.pdf"
        receipt.generated_pdf.save(filename, ContentFile(pdf_bytes), save=True)
    except Exception as e:
        # Do not fail financial transaction if PDF generation hits an edge case
        pass

    log_fee_event(
        school=school,
        action="RECEIPT_ISSUED",
        model_name="FeeReceipt",
        object_id=receipt.pk,
        actor=issued_by,
        after_state={
            "receipt_number": receipt.receipt_number,
            "payment_id": payment.pk,
            "amount": str(receipt.amount),
            "student_id": student.pk
        },
        ip_address=ip_address
    )

    return receipt
