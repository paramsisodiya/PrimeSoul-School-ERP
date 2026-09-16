from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FeeHeadViewSet, FeeStructureViewSet, FeeConcessionViewSet,
    StudentFeeAssignmentViewSet, FeeInstallmentViewSet,
    FeeInvoiceViewSet, PaymentTransactionViewSet, FeeReceiptViewSet,
    FeeDashboardAPIView, RazorpayWebhookAPIView
)

router = DefaultRouter()
router.register(r'fee-heads', FeeHeadViewSet, basename='fee-head')
router.register(r'fee-structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'concessions', FeeConcessionViewSet, basename='fee-concession')
router.register(r'student-fees', StudentFeeAssignmentViewSet, basename='student-fee-assignment')
router.register(r'installments', FeeInstallmentViewSet, basename='fee-installment')
router.register(r'invoices', FeeInvoiceViewSet, basename='fee-invoice')
router.register(r'payments', PaymentTransactionViewSet, basename='fee-payment')
router.register(r'receipts', FeeReceiptViewSet, basename='fee-receipt')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', FeeDashboardAPIView.as_view(), name='fee-dashboard'),
    path('webhooks/razorpay/', RazorpayWebhookAPIView.as_view(), name='razorpay-webhook'),
]
