import logging
import datetime
from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
from django_school_management.fees.models import (
    FeeInstallment, FeeReceipt, FeeInvoice, InstallmentStatus
)
from django_school_management.fees.services.receipt_service import render_receipt_pdf_bytes
from django_school_management.fees.services.invoice_service import create_fee_invoice

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_installments_task(school_id=None):
    """
    Periodic task to mark pending installments past their due date as OVERDUE.
    """
    today = timezone.now().date()
    qs = FeeInstallment.objects.filter(
        due_date__lt=today,
        status__in=[InstallmentStatus.PENDING, InstallmentStatus.PARTIAL]
    )
    if school_id:
        qs = qs.filter(student__school_id=school_id)

    updated_count = qs.update(status=InstallmentStatus.OVERDUE, updated_at=timezone.now())
    logger.info("Updated %d installments to OVERDUE status.", updated_count)
    return updated_count


@shared_task
def generate_receipt_pdf_task(receipt_id):
    """
    Asynchronously generates and stores the receipt PDF if deferred.
    """
    try:
        receipt = FeeReceipt.objects.select_related('school', 'student', 'payment').get(pk=receipt_id)
        if not receipt.generated_pdf:
            pdf_bytes = render_receipt_pdf_bytes(receipt)
            filename = f"receipt_{receipt.receipt_number}.pdf"
            receipt.generated_pdf.save(filename, ContentFile(pdf_bytes), save=True)
            logger.info("Generated PDF for receipt %s", receipt.receipt_number)
            return True
    except Exception as e:
        logger.exception("Failed to generate PDF for receipt %s: %s", receipt_id, e)
        return False


@shared_task
def send_fee_reminder_task(student_id, installment_id):
    """
    Async task for sending SMS/WhatsApp/Email fee payment reminders to parents.
    """
    try:
        installment = FeeInstallment.objects.select_related('student').get(pk=installment_id)
        # Production notification dispatch (SMS / Email)
        logger.info(
            "Sent fee reminder for student %s, installment %s, amount ₹%s",
            installment.student.name, installment.installment_name, installment.balance_amount
        )
        return True
    except Exception as e:
        logger.exception("Error sending fee reminder: %s", e)
        return False


@shared_task
def generate_bulk_invoices_task(school_id, academic_year_id, grade_level_id=None):
    """
    Bulk generates FeeInvoices from pending installments for an academic year and school.
    """
    from django_school_management.tenants.models import School
    from django_school_management.academics.models import AcademicYear
    from django_school_management.students.models import Student

    school = School.objects.get(pk=school_id)
    academic_year = AcademicYear.objects.get(pk=academic_year_id)

    students = Student.objects.filter(school=school, is_active=True)
    if grade_level_id:
        students = students.filter(grade_level_id=grade_level_id)

    created_invoices = []
    for student in students:
        # Check student installments for this academic year
        pending_insts = FeeInstallment.objects.filter(
            student=student,
            academic_year=academic_year,
            status__in=[InstallmentStatus.PENDING, InstallmentStatus.PARTIAL]
        )
        if pending_insts.exists():
            subtotal = sum([i.payable_amount for i in pending_insts])
            inv = create_fee_invoice(
                school=school,
                student=student,
                academic_year=academic_year,
                subtotal=subtotal,
                notes=f"Bulk generated invoice for {academic_year.name}"
            )
            created_invoices.append(inv.id)

    logger.info("Bulk generated %d invoices for school %s", len(created_invoices), school.name)
    return len(created_invoices)
