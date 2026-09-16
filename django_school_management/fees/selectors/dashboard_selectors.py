import datetime
from decimal import Decimal
from django.db.models import Sum, Count, Case, When, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_school_management.fees.models import (
    FeeInstallment, FeeInvoice, PaymentTransaction, PaymentAllocation,
    FeeHead, InstallmentStatus, PaymentStatus, PaymentGateway
)


def get_fee_dashboard_summary(school, academic_year=None) -> dict:
    """
    Returns aggregated financial analytics for a school tenant.
    Zero N+1 queries via database-level aggregate functions.
    """
    today = timezone.now().date()
    current_month_start = today.replace(day=1)

    # 1. Installment Aggregations (Dues, Expected, Outstanding, Overdue)
    inst_qs = FeeInstallment.objects.filter(student__school=school)
    if academic_year:
        inst_qs = inst_qs.filter(academic_year=academic_year)

    installments_agg = inst_qs.aggregate(
        total_expected=Coalesce(Sum('payable_amount'), Value(Decimal('0.00')), output_field=DecimalField()),
        total_collected=Coalesce(Sum('paid_amount'), Value(Decimal('0.00')), output_field=DecimalField()),
        total_outstanding=Coalesce(Sum('balance_amount'), Value(Decimal('0.00')), output_field=DecimalField()),
        total_concessions=Coalesce(Sum('concession_amount'), Value(Decimal('0.00')), output_field=DecimalField()),
        total_overdue=Coalesce(
            Sum(
                Case(
                    When(due_date__lt=today, balance_amount__gt=Decimal('0.00'), then='balance_amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField()
                )
            ),
            Value(Decimal('0.00')),
            output_field=DecimalField()
        ),
        total_pending_count=Count(
            Case(When(status__in=[InstallmentStatus.PENDING, InstallmentStatus.PARTIAL, InstallmentStatus.OVERDUE], then=1))
        ),
        total_paid_count=Count(Case(When(status=InstallmentStatus.PAID, then=1)))
    )

    # 2. Payment Transaction Aggregations (Today's, Month's, Total)
    pay_qs = PaymentTransaction.objects.filter(school=school, status=PaymentStatus.SUCCESS)

    today_collection = pay_qs.filter(paid_at__date=today).aggregate(
        amount=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField())
    )['amount']

    month_collection = pay_qs.filter(paid_at__date__gte=current_month_start).aggregate(
        amount=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField())
    )['amount']

    # 3. Collection breakdown by Payment Gateway/Method
    collection_by_gateway = list(
        pay_qs.values('gateway')
        .annotate(
            total_amount=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField()),
            transaction_count=Count('id')
        )
        .order_by('-total_amount')
    )

    # 4. Collection breakdown by Grade Level / Class
    collection_by_grade = list(
        PaymentAllocation.objects.filter(payment__school=school, payment__status=PaymentStatus.SUCCESS)
        .values(
            grade_id=F('installment__fee_structure__grade_level__id'),
            grade_name=F('installment__fee_structure__grade_level__name')
        )
        .annotate(
            total_amount=Coalesce(Sum('allocated_amount'), Value(Decimal('0.00')), output_field=DecimalField()),
            students_count=Count('installment__student', distinct=True)
        )
        .filter(grade_name__isnull=False)
        .order_by('-total_amount')
    )

    # 5. Fee Head distribution
    fee_heads = list(
        FeeHead.objects.filter(school=school, is_active=True).values('id', 'name', 'code', 'category')
    )

    return {
        "total_fee_expected": installments_agg['total_expected'],
        "total_fee_collected": installments_agg['total_collected'],
        "total_fee_outstanding": installments_agg['total_outstanding'],
        "total_concessions_granted": installments_agg['total_concessions'],
        "total_fee_overdue": installments_agg['total_overdue'],
        "today_collection": today_collection,
        "monthly_collection": month_collection,
        "pending_installments_count": installments_agg['total_pending_count'],
        "paid_installments_count": installments_agg['total_paid_count'],
        "collection_by_gateway": collection_by_gateway,
        "collection_by_grade": collection_by_grade,
        "active_fee_heads_count": len(fee_heads),
    }
