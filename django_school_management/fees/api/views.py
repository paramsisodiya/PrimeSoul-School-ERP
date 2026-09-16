import json
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions, views
from rest_framework.decorators import action
from rest_framework.response import Response

from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeConcession, StudentFeeAssignment,
    FeeInstallment, FeeInvoice, PaymentTransaction, FeeReceipt,
    PaymentGateway, PaymentStatus, ChequeClearanceStatus
)
from django_school_management.students.models import Student
from django_school_management.academics.models import AcademicYear
from .serializers import (
    FeeHeadSerializer, FeeStructureSerializer, FeeConcessionSerializer,
    StudentFeeAssignmentSerializer, FeeInstallmentSerializer,
    FeeInvoiceSerializer, PaymentTransactionSerializer, FeeReceiptSerializer,
    OfflinePaymentCreateSerializer, RazorpayOrderCreateSerializer,
    RazorpayPaymentVerifySerializer, BulkInstallmentGenerateSerializer
)
from .permissions import (
    IsSchoolAdminOrAccountant, CanManageFeeStructures,
    CanCollectPayments, CanApproveConcessions, StudentOrParentFeeAccess,
    check_roles
)
from django_school_management.fees.services.installment_service import generate_student_installments
from django_school_management.fees.services.invoice_service import create_fee_invoice, cancel_fee_invoice
from django_school_management.fees.services.payment_service import (
    record_offline_payment, process_cheque_clearance, process_cheque_bounce,
    create_razorpay_order_record, complete_razorpay_payment,
    verify_razorpay_webhook_signature
)
from django_school_management.fees.services.receipt_service import generate_fee_receipt, render_receipt_pdf_bytes
from django_school_management.fees.selectors.dashboard_selectors import get_fee_dashboard_summary


class TenantFilteredMixin:
    """Ensures querysets are strictly scoped to the requesting user's school tenant."""
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        if user.is_superuser:
            return self.queryset.all()
        if not user.school:
            return self.queryset.none()
        return self.queryset.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)


class FeeHeadViewSet(TenantFilteredMixin, viewsets.ModelViewSet):
    queryset = FeeHead.objects.all()
    serializer_class = FeeHeadSerializer
    permission_classes = [CanManageFeeStructures]


class FeeStructureViewSet(TenantFilteredMixin, viewsets.ModelViewSet):
    queryset = FeeStructure.objects.prefetch_related('items__fee_head').select_related('grade_level', 'academic_year')
    serializer_class = FeeStructureSerializer
    permission_classes = [CanManageFeeStructures]


class FeeConcessionViewSet(TenantFilteredMixin, viewsets.ModelViewSet):
    queryset = FeeConcession.objects.prefetch_related('applicable_fee_heads')
    serializer_class = FeeConcessionSerializer
    permission_classes = [CanManageFeeStructures]

    @action(detail=True, methods=['post'], permission_classes=[CanApproveConcessions])
    def approve(self, request, pk=None):
        concession = self.get_object()
        concession.is_approved = True
        concession.approved_by = request.user
        concession.save(update_fields=['is_approved', 'approved_by', 'updated_at'])
        return Response({"detail": f"Concession '{concession.name}' approved successfully."})


class StudentFeeAssignmentViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeAssignment.objects.select_related('student', 'fee_structure', 'academic_year', 'concession')
    serializer_class = StudentFeeAssignmentSerializer
    permission_classes = [IsSchoolAdminOrAccountant]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        if user.is_superuser:
            return self.queryset.all()
        return self.queryset.filter(student__school=user.school)

    @action(detail=False, methods=['post'])
    def generate_installments(self, request):
        serializer = BulkInstallmentGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(Student, pk=data['student_id'], school=request.user.school if not request.user.is_superuser else None)
        fee_structure = get_object_or_404(FeeStructure, pk=data['fee_structure_id'], school=request.user.school if not request.user.is_superuser else None)
        academic_year = get_object_or_404(AcademicYear, pk=data['academic_year_id'])
        concession = FeeConcession.objects.filter(pk=data.get('concession_id')).first() if data.get('concession_id') else None

        installments = generate_student_installments(
            student=student,
            fee_structure=fee_structure,
            academic_year=academic_year,
            concession=concession,
            custom_concession=data.get('custom_concession', Decimal('0.00')),
            actor=request.user
        )

        return Response({
            "detail": f"Successfully generated {len(installments)} installments.",
            "installments": FeeInstallmentSerializer(installments, many=True).data
        }, status=status.HTTP_201_CREATED)


class FeeInstallmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeeInstallment.objects.select_related('student', 'academic_year', 'fee_structure')
    serializer_class = FeeInstallmentSerializer
    permission_classes = [permissions.IsAuthenticated, StudentOrParentFeeAccess]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        if user.is_superuser:
            qs = self.queryset.all()
        elif check_roles(user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACCOUNTANT', 'RECEPTIONIST']):
            qs = self.queryset.filter(student__school=user.school)
        elif check_roles(user, ['PARENT']):
            qs = self.queryset.filter(student__guardian_relationships__guardian__user=user)
        elif check_roles(user, ['STUDENT']):
            qs = self.queryset.filter(student__user=user)
        else:
            return self.queryset.none()

        student_id = self.request.query_params.get('student_id')
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs


class FeeInvoiceViewSet(TenantFilteredMixin, viewsets.ModelViewSet):
    queryset = FeeInvoice.objects.select_related('student', 'academic_year')
    serializer_class = FeeInvoiceSerializer
    permission_classes = [IsSchoolAdminOrAccountant]

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        reason = request.data.get('reason', 'Cancelled by accountant')
        try:
            cancelled = cancel_fee_invoice(invoice, actor=request.user, reason=reason)
            return Response({"detail": f"Invoice {cancelled.invoice_number} cancelled successfully."})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentTransactionViewSet(TenantFilteredMixin, viewsets.ModelViewSet):
    queryset = PaymentTransaction.objects.select_related('student', 'invoice').prefetch_related('allocations')
    serializer_class = PaymentTransactionSerializer
    permission_classes = [CanCollectPayments]

    @action(detail=False, methods=['post'], permission_classes=[CanCollectPayments])
    def collect_offline(self, request):
        serializer = OfflinePaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        student = get_object_or_404(Student, pk=d['student_id'], school=request.user.school if not request.user.is_superuser else None)
        invoice = FeeInvoice.objects.filter(pk=d.get('invoice_id')).first() if d.get('invoice_id') else None
        installment = FeeInstallment.objects.filter(pk=d.get('installment_id')).first() if d.get('installment_id') else None

        payment = record_offline_payment(
            school=request.user.school or student.school,
            student=student,
            amount=d['amount'],
            gateway=d['gateway'],
            payment_method=d.get('payment_method', ''),
            transaction_id=d.get('transaction_id'),
            invoice=invoice,
            installment=installment,
            collected_by=request.user,
            notes=d.get('notes', ''),
            cheque_number=d.get('cheque_number', ''),
            bank_name=d.get('bank_name', ''),
            cheque_date=d.get('cheque_date'),
            clearance_status=d.get('clearance_status', ChequeClearanceStatus.CLEARED),
            ip_address=request.META.get('REMOTE_ADDR')
        )

        receipt = None
        if payment.status == PaymentStatus.SUCCESS:
            receipt = generate_fee_receipt(payment, issued_by=request.user, ip_address=request.META.get('REMOTE_ADDR'))

        return Response({
            "detail": "Offline payment recorded successfully.",
            "payment": PaymentTransactionSerializer(payment).data,
            "receipt_number": receipt.receipt_number if receipt else None
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsSchoolAdminOrAccountant])
    def clear_cheque(self, request, pk=None):
        payment = self.get_object()
        try:
            cleared = process_cheque_clearance(payment, actor=request.user, ip_address=request.META.get('REMOTE_ADDR'))
            receipt = generate_fee_receipt(cleared, issued_by=request.user, ip_address=request.META.get('REMOTE_ADDR'))
            return Response({
                "detail": f"Cheque {cleared.cheque_number} cleared successfully.",
                "receipt_number": receipt.receipt_number
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsSchoolAdminOrAccountant])
    def bounce_cheque(self, request, pk=None):
        payment = self.get_object()
        reason = request.data.get('reason', 'Insufficient Funds')
        try:
            bounced = process_cheque_bounce(payment, reason=reason, actor=request.user, ip_address=request.META.get('REMOTE_ADDR'))
            return Response({"detail": f"Cheque {bounced.cheque_number} marked as BOUNCED. Allocations rolled back."})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def initiate_razorpay_order(self, request):
        serializer = RazorpayOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        student = get_object_or_404(Student, pk=d['student_id'], school=request.user.school if not request.user.is_superuser else None)
        invoice = FeeInvoice.objects.filter(pk=d.get('invoice_id')).first() if d.get('invoice_id') else None

        payment = create_razorpay_order_record(
            school=request.user.school or student.school,
            student=student,
            amount=d['amount'],
            invoice=invoice,
            actor=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            "order_id": payment.razorpay_order_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "transaction_id": payment.transaction_id
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def verify_razorpay_payment(self, request):
        serializer = RazorpayPaymentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        try:
            payment = complete_razorpay_payment(
                razorpay_order_id=d['razorpay_order_id'],
                razorpay_payment_id=d['razorpay_payment_id'],
                razorpay_signature=d['razorpay_signature'],
                gateway_response=d.get('gateway_response'),
                actor=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            receipt = generate_fee_receipt(payment, issued_by=request.user, ip_address=request.META.get('REMOTE_ADDR'))
            return Response({
                "detail": "Payment verified and recorded successfully.",
                "receipt_number": receipt.receipt_number,
                "amount": payment.amount
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FeeReceiptViewSet(TenantFilteredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = FeeReceipt.objects.select_related('student', 'payment', 'issued_by')
    serializer_class = FeeReceiptSerializer
    permission_classes = [permissions.IsAuthenticated, StudentOrParentFeeAccess]

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        receipt = self.get_object()
        pdf_bytes = render_receipt_pdf_bytes(receipt)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'
        return response


class FeeDashboardAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdminOrAccountant]

    def get(self, request):
        school = request.user.school
        if not school and not request.user.is_superuser:
            return Response({"error": "No tenant associated with user"}, status=status.HTTP_400_BAD_REQUEST)

        ay_id = request.query_params.get('academic_year_id')
        academic_year = AcademicYear.objects.filter(pk=ay_id).first() if ay_id else None

        summary = get_fee_dashboard_summary(school=school, academic_year=academic_year)
        return Response(summary)


class RazorpayWebhookAPIView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature', '')
        payload_bytes = request.body

        if not verify_razorpay_webhook_signature(payload_bytes, signature):
            return Response({"error": "Invalid webhook signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            event_data = json.loads(payload_bytes.decode('utf-8'))
        except Exception:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event_data.get('event')
        if event_type in ['payment.captured', 'order.paid']:
            payload = event_data.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payload.get('order_id')
            payment_id = payload.get('id')

            if order_id and payment_id:
                payment = PaymentTransaction.objects.filter(razorpay_order_id=order_id).first()
                if payment and payment.status != PaymentStatus.SUCCESS:
                    payment.status = PaymentStatus.SUCCESS
                    payment.razorpay_payment_id = payment_id
                    payment.paid_at = timezone.now()
                    payment.gateway_response = event_data
                    payment.save(update_fields=['status', 'razorpay_payment_id', 'paid_at', 'gateway_response', 'updated_at'])
                    # Generate receipt
                    generate_fee_receipt(payment)

        return Response({"status": "received"})
