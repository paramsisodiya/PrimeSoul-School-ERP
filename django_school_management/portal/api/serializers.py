"""
PrimeSoul Unified Portal - REST API Serializers
Clean, tenant-safe serialization for Parent, Student, and Teacher portals.
Sensitive fields (bank accounts, PAN, unmasked Aadhaar) are omitted.
"""
from rest_framework import serializers
from django_school_management.notices.models import Notice
from django_school_management.students.models import Student, ParentProfile
from django_school_management.teachers.models import Teacher
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.fees.models import FeeInstallment, FeeInvoice, PaymentTransaction, FeeReceipt
from django_school_management.examinations.models import StudentExamResult, StudentMark
from django_school_management.timetable.models import TimetableEntry
from django_school_management.hr.models import Employee, LeaveBalance, LeaveRequest, PayrollRecord


class PortalNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ['id', 'title', 'notice_type', 'content', 'file', 'expires_at', 'created']


class PortalStudentSummarySerializer(serializers.ModelSerializer):
    grade_name = serializers.CharField(source='grade_level.name', read_only=True, default='')
    section_name = serializers.CharField(source='section.name', read_only=True, default='')
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True, default='')
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'roll_number', 'first_name', 'last_name',
            'full_name', 'grade_name', 'section_name', 'academic_year_name',
            'gender', 'blood_group', 'date_of_birth'
        ]


class PortalAttendanceRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'attendance_date', 'status', 'status_display', 'remarks']


class PortalFeeInstallmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    structure_name = serializers.CharField(source='fee_structure.name', read_only=True, default='')

    class Meta:
        model = FeeInstallment
        fields = [
            'id', 'installment_name', 'due_date', 'base_amount', 'concession_amount',
            'payable_amount', 'paid_amount', 'balance_amount', 'status', 'status_display',
            'structure_name'
        ]


class PortalFeeInvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FeeInvoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date',
            'subtotal', 'concession', 'late_fee', 'total', 'paid_amount', 'balance_amount',
            'status', 'status_display'
        ]


class PortalFeeReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeReceipt
        fields = ['id', 'receipt_number', 'amount', 'payment_method', 'receipt_date', 'generated_pdf']


class PortalStudentMarkSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='exam_subject.subject.name', read_only=True)
    max_marks = serializers.DecimalField(source='exam_subject.max_marks', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = StudentMark
        fields = ['id', 'subject_name', 'marks_obtained', 'max_marks', 'grade', 'is_passed', 'remarks']


class PortalExamResultSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    exam_type = serializers.CharField(source='exam.assessment_type.name', read_only=True, default='')
    status_display = serializers.CharField(source='get_result_status_display', read_only=True)

    class Meta:
        model = StudentExamResult
        fields = [
            'id', 'exam_name', 'exam_type', 'total_marks_obtained', 'total_max_marks',
            'percentage', 'overall_grade', 'result_status', 'status_display',
            'class_rank', 'section_rank', 'verification_code'
        ]


class PortalTimetableEntrySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    teacher_name = serializers.CharField(source='teacher.name', read_only=True, default='')
    room_name = serializers.CharField(source='room.name', read_only=True, default='')
    slot_name = serializers.CharField(source='time_slot.name', read_only=True, default='')
    start_time = serializers.TimeField(source='time_slot.start_time', read_only=True)
    end_time = serializers.TimeField(source='time_slot.end_time', read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'subject_name', 'teacher_name', 'room_name', 'slot_name',
            'start_time', 'end_time'
        ]


class PortalLeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    allocated_days = serializers.DecimalField(source='opening_balance', max_digits=5, decimal_places=1, read_only=True)
    used_days = serializers.DecimalField(source='used', max_digits=5, decimal_places=1, read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'leave_type_name', 'opening_balance', 'accrued', 'used', 'closing_balance', 'allocated_days', 'used_days']


class PortalPayrollRecordSerializer(serializers.ModelSerializer):
    period_label = serializers.CharField(source='payroll_period.__str__', read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            'id', 'period_label', 'gross_earnings', 'total_deductions',
            'net_salary', 'status', 'working_days', 'payable_days'
        ]
