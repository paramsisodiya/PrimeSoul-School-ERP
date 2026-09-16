from django.contrib import admin
from .models import (
    FeeHead, FeeStructure, FeeStructureItem, FeeConcession,
    StudentFeeAssignment, FeeInstallment, FeeInvoice,
    PaymentTransaction, PaymentAllocation, FeeReceipt, FeeAuditLog
)


class FeeStructureItemInline(admin.TabularInline):
    model = FeeStructureItem
    extra = 1


@admin.register(FeeHead)
class FeeHeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'school', 'is_recurring', 'is_active')
    list_filter = ('category', 'is_recurring', 'is_active', 'school')
    search_fields = ('name', 'code', 'school__name')


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'grade_level', 'frequency', 'school', 'is_active')
    list_filter = ('frequency', 'academic_year', 'grade_level', 'school')
    search_fields = ('name', 'school__name')
    inlines = [FeeStructureItemInline]


@admin.register(FeeConcession)
class FeeConcessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'concession_type', 'value', 'school', 'is_approved', 'is_active')
    list_filter = ('concession_type', 'is_approved', 'is_active', 'school')
    search_fields = ('name', 'school__name')


@admin.register(StudentFeeAssignment)
class StudentFeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'academic_year', 'concession', 'status')
    list_filter = ('status', 'academic_year', 'fee_structure')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')


@admin.register(FeeInstallment)
class FeeInstallmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'installment_name', 'due_date', 'payable_amount', 'paid_amount', 'balance_amount', 'status')
    list_filter = ('status', 'academic_year')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'installment_name')


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'student', 'invoice_date', 'due_date', 'total', 'paid_amount', 'balance_amount', 'status', 'school')
    list_filter = ('status', 'school', 'academic_year')
    search_fields = ('invoice_number', 'student__first_name', 'student__last_name', 'student__admission_number')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'student', 'gateway', 'amount', 'currency', 'status', 'clearance_status', 'paid_at', 'school')
    list_filter = ('gateway', 'status', 'clearance_status', 'school')
    search_fields = ('transaction_id', 'student__first_name', 'student__last_name', 'cheque_number', 'razorpay_payment_id')


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ('payment', 'invoice', 'installment', 'allocated_amount', 'created_at')


@admin.register(FeeReceipt)
class FeeReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'amount', 'payment_method', 'receipt_date', 'school')
    list_filter = ('payment_method', 'school')
    search_fields = ('receipt_number', 'student__first_name', 'student__last_name')


@admin.register(FeeAuditLog)
class FeeAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'object_id', 'actor', 'school', 'timestamp')
    list_filter = ('action', 'model_name', 'school')
    search_fields = ('action', 'model_name', 'object_id', 'actor__username')
    readonly_fields = [f.name for f in FeeAuditLog._meta.fields]
