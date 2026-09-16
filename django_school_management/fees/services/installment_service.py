import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django_school_management.fees.models import (
    FeeStructure, FeeInstallment, StudentFeeAssignment,
    FeeConcession, ConcessionType, FeeFrequency, InstallmentStatus
)
from .audit_service import log_fee_event


def calculate_concession_discount(base_amount: Decimal, concession: FeeConcession, structure_items=None) -> Decimal:
    """
    Deterministically computes the concession discount in INR.
    Guarantees that discount is >= 0 and discount <= base_amount.
    """
    if not concession or not concession.is_active or not concession.is_approved:
        return Decimal('0.00')

    base_amount = Decimal(str(base_amount))
    discount = Decimal('0.00')

    # If concession has specific applicable fee heads and structure items are provided, calculate on those heads
    eligible_base = base_amount
    if structure_items and concession.applicable_fee_heads.exists():
        applicable_head_ids = set(concession.applicable_fee_heads.values_list('id', flat=True))
        matching_amount = sum(
            [Decimal(str(item.amount)) for item in structure_items if item.fee_head_id in applicable_head_ids]
        )
        if matching_amount > 0:
            eligible_base = matching_amount

    if concession.concession_type == ConcessionType.FULL_WAIVER:
        discount = eligible_base
    elif concession.concession_type == ConcessionType.PERCENTAGE:
        pct = Decimal(str(concession.value))
        calculated = (eligible_base * pct) / Decimal('100.00')
        if concession.maximum_amount:
            max_cap = Decimal(str(concession.maximum_amount))
            calculated = min(calculated, max_cap)
        discount = calculated
    elif concession.concession_type == ConcessionType.FIXED_AMOUNT:
        fixed_val = Decimal(str(concession.value))
        discount = min(eligible_base, fixed_val)

    # Quantize to 2 decimal places (paise)
    discount = discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    # Ensure bounds: 0 <= discount <= base_amount
    discount = max(Decimal('0.00'), min(discount, base_amount))
    return discount


@transaction.atomic
def generate_student_installments(student, fee_structure: FeeStructure, academic_year, concession: FeeConcession = None, custom_concession: Decimal = Decimal('0.00'), actor=None):
    """
    Generates installment schedule for an enrolled student based on FeeStructure frequency for an April–March session.
    """
    # Sum base line items
    items = list(fee_structure.items.select_related('fee_head').all())
    total_structure_base = sum([Decimal(str(item.amount)) for item in items]) or Decimal('0.00')

    start_year = academic_year.start_date.year if academic_year and academic_year.start_date else datetime.date.today().year
    end_year = start_year + 1

    # Define installment periods based on frequency
    installment_defs = []
    
    if fee_structure.frequency == FeeFrequency.QUARTERLY:
        # Standard 4 Quarters for Indian Schools (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar)
        q_base = (total_structure_base / Decimal('4.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        installment_defs = [
            ("Q1 (Apr - Jun)", datetime.date(start_year, 4, 10), q_base),
            ("Q2 (Jul - Sep)", datetime.date(start_year, 7, 10), q_base),
            ("Q3 (Oct - Dec)", datetime.date(start_year, 10, 10), q_base),
            ("Q4 (Jan - Mar)", datetime.date(end_year, 1, 10), q_base),
        ]
    elif fee_structure.frequency == FeeFrequency.MONTHLY:
        # 12 Monthly installments
        m_base = (total_structure_base / Decimal('12.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        months = [
            ("April", start_year, 4), ("May", start_year, 5), ("June", start_year, 6),
            ("July", start_year, 7), ("August", start_year, 8), ("September", start_year, 9),
            ("October", start_year, 10), ("November", start_year, 11), ("December", start_year, 12),
            ("January", end_year, 1), ("February", end_year, 2), ("March", end_year, 3)
        ]
        for name, yr, m in months:
            installment_defs.append((f"{name} Fee", datetime.date(yr, m, 10), m_base))
    elif fee_structure.frequency == FeeFrequency.HALF_YEARLY:
        h_base = (total_structure_base / Decimal('2.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        installment_defs = [
            ("Term 1 (Apr - Sep)", datetime.date(start_year, 4, 10), h_base),
            ("Term 2 (Oct - Mar)", datetime.date(start_year, 10, 10), h_base),
        ]
    elif fee_structure.frequency == FeeFrequency.ANNUAL:
        installment_defs = [
            ("Annual Session Fee", datetime.date(start_year, 4, 10), total_structure_base)
        ]
    else:
        # Default single custom installment
        installment_defs = [
            (fee_structure.name, fee_structure.effective_from or datetime.date.today(), total_structure_base)
        ]

    created_installments = []
    num_installments = len(installment_defs)
    custom_concession_per_inst = (Decimal(str(custom_concession)) / Decimal(str(num_installments))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if custom_concession > 0 else Decimal('0.00')

    for name, due_date, base_amt in installment_defs:
        rule_discount = calculate_concession_discount(base_amt, concession, items)
        total_discount = min(base_amt, rule_discount + custom_concession_per_inst)
        payable_amt = max(Decimal('0.00'), base_amt - total_discount)

        installment = FeeInstallment.objects.create(
            student=student,
            academic_year=academic_year,
            fee_structure=fee_structure,
            installment_name=name,
            due_date=due_date,
            base_amount=base_amt,
            concession_amount=total_discount,
            late_fee=Decimal('0.00'),
            payable_amount=payable_amt,
            paid_amount=Decimal('0.00'),
            balance_amount=payable_amt,
            status=InstallmentStatus.PAID if payable_amt == Decimal('0.00') else InstallmentStatus.PENDING
        )
        created_installments.append(installment)

    # Log audit event
    log_fee_event(
        school=fee_structure.school,
        action="INSTALLMENTS_GENERATED",
        model_name="FeeInstallment",
        object_id=student.pk,
        actor=actor,
        after_state={
            "student_id": student.pk,
            "fee_structure_id": fee_structure.pk,
            "count": len(created_installments),
            "total_payable": str(sum([i.payable_amount for i in created_installments]))
        }
    )

    return created_installments
