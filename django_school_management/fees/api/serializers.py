from decimal import Decimal
from rest_framework import serializers
from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeStructureItem, FeeConcession,
    StudentFeeAssignment, FeeInstallment, FeeInvoice,
    PaymentTransaction, PaymentAllocation, FeeReceipt
)
from django_school_management.students.models import Student
from django_school_management.academics.models import AcademicYear, GradeLevel


class FeeHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeHead
        fields = [
            'id', 'school', 'name', 'code', 'description',
            'category', 'is_recurring', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def validate_code(self, value):
        return value.strip().upper()


class FeeStructureItemSerializer(serializers.ModelSerializer):
    fee_head_name = serializers.ReadOnlyField(source='fee_head.name')
    fee_head_code = serializers.ReadOnlyField(source='fee_head.code')

    class Meta:
        model = FeeStructureItem
        fields = [
            'id', 'fee_head', 'fee_head_name', 'fee_head_code',
            'amount', 'mandatory', 'due_day'
        ]


class FeeStructureSerializer(serializers.ModelSerializer):
    items = FeeStructureItemSerializer(many=True, required=False)
    grade_level_name = serializers.ReadOnlyField(source='grade_level.name')
    academic_year_name = serializers.ReadOnlyField(source='academic_year.name')
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='total_structure_amount')

    class Meta:
        model = FeeStructure
        fields = [
            'id', 'school', 'academic_year', 'academic_year_name',
            'grade_level', 'grade_level_name', 'name',
            'effective_from', 'effective_to', 'frequency',
            'is_active', 'items', 'total_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        structure = FeeStructure.objects.create(**validated_data)
        for item_data in items_data:
            FeeStructureItem.objects.create(fee_structure=structure, **item_data)
        return structure


class FeeConcessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeConcession
        fields = [
            'id', 'school', 'name', 'concession_type', 'value',
            'maximum_amount', 'applicable_fee_heads', 'valid_from', 'valid_to',
            'approval_required', 'is_approved', 'approved_by', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'is_approved', 'approved_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        concession_type = attrs.get('concession_type')
        value = attrs.get('value')
        if concession_type == 'PERCENTAGE' and value:
            if value < Decimal('0.00') or value > Decimal('100.00'):
                raise serializers.ValidationError({"value": "Percentage concession must be between 0 and 100."})
        elif concession_type == 'FIXED_AMOUNT' and value:
            if value < Decimal('0.00'):
                raise serializers.ValidationError({"value": "Fixed concession cannot be negative."})
        return attrs


class StudentFeeAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    fee_structure_name = serializers.ReadOnlyField(source='fee_structure.name')
    concession_name = serializers.ReadOnlyField(source='concession.name')

    class Meta:
        model = StudentFeeAssignment
        fields = [
            'id', 'student', 'student_name', 'fee_structure', 'fee_structure_name',
            'academic_year', 'concession', 'concession_name',
            'custom_concession_amount', 'start_date', 'end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FeeInstallmentSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    admission_number = serializers.ReadOnlyField(source='student.admission_number')

    class Meta:
        model = FeeInstallment
        fields = [
            'id', 'student', 'student_name', 'admission_number',
            'academic_year', 'fee_structure', 'installment_name',
            'due_date', 'base_amount', 'concession_amount', 'late_fee',
            'payable_amount', 'paid_amount', 'balance_amount', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FeeInvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')

    class Meta:
        model = FeeInvoice
        fields = [
            'id', 'school', 'student', 'student_name', 'academic_year',
            'invoice_number', 'invoice_date', 'due_date',
            'subtotal', 'concession', 'late_fee', 'total',
            'paid_amount', 'balance_amount', 'status', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'invoice_number', 'total', 'paid_amount', 'balance_amount', 'created_at', 'updated_at']

    def create(self, validated_data):
        from django_school_management.fees.services.invoice_service import create_fee_invoice
        request = self.context.get('request')
        school = validated_data.pop('school', None) or (request.user.school if request and request.user.is_authenticated else None)
        student = validated_data.pop('student')
        if not school:
            school = student.school

        academic_year = validated_data.pop('academic_year', None)
        subtotal = validated_data.pop('subtotal', Decimal('0.00'))
        concession = validated_data.pop('concession', Decimal('0.00'))
        late_fee = validated_data.pop('late_fee', Decimal('0.00'))
        due_date = validated_data.pop('due_date', None)
        invoice_date = validated_data.pop('invoice_date', None)
        notes = validated_data.pop('notes', '')
        actor = request.user if request and request.user.is_authenticated else None

        return create_fee_invoice(
            school=school,
            student=student,
            academic_year=academic_year,
            subtotal=subtotal,
            concession=concession,
            late_fee=late_fee,
            due_date=due_date,
            invoice_date=invoice_date,
            notes=notes,
            actor=actor
        )


class PaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ['id', 'payment', 'invoice', 'installment', 'allocated_amount', 'created_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'school', 'student', 'student_name', 'invoice',
            'transaction_id', 'gateway', 'payment_method',
            'amount', 'currency', 'status', 'paid_at', 'notes',
            'collected_by', 'cheque_number', 'bank_name', 'cheque_date',
            'clearance_status', 'cleared_at', 'razorpay_order_id',
            'razorpay_payment_id', 'allocations', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'school', 'transaction_id', 'status', 'paid_at',
            'cleared_at', 'razorpay_order_id', 'razorpay_payment_id', 'created_at', 'updated_at'
        ]


class FeeReceiptSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    transaction_id = serializers.ReadOnlyField(source='payment.transaction_id')

    class Meta:
        model = FeeReceipt
        fields = [
            'id', 'school', 'receipt_number', 'payment', 'transaction_id',
            'student', 'student_name', 'amount', 'payment_method',
            'receipt_date', 'generated_pdf', 'qr_verification_code',
            'issued_by', 'created_at'
        ]
        read_only_fields = ['id', 'school', 'receipt_number', 'qr_verification_code', 'created_at']


# Action & Request Serializers
class OfflinePaymentCreateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    gateway = serializers.ChoiceField(choices=['CASH', 'CHEQUE', 'UPI', 'CARD', 'NET_BANKING', 'OTHER'])
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True)
    transaction_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    installment_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Cheque fields
    cheque_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    clearance_status = serializers.ChoiceField(choices=['PENDING', 'CLEARED'], default='CLEARED')


class RazorpayOrderCreateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))
    invoice_id = serializers.IntegerField(required=False, allow_null=True)


class RazorpayPaymentVerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=100, required=True)
    razorpay_payment_id = serializers.CharField(max_length=100, required=True)
    razorpay_signature = serializers.CharField(max_length=255, required=True)
    gateway_response = serializers.JSONField(required=False, default=dict)


class BulkInstallmentGenerateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=True)
    fee_structure_id = serializers.IntegerField(required=True)
    academic_year_id = serializers.IntegerField(required=True)
    concession_id = serializers.IntegerField(required=False, allow_null=True)
    custom_concession = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
