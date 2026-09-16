from rest_framework import serializers
from django_school_management.attendance.models import AttendanceRecord, AttendanceCorrectionLog
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    roll_number = serializers.CharField(source='student.roll_number', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    class_name = serializers.CharField(source='grade_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    session_name = serializers.CharField(source='academic_year.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'school', 'academic_year', 'session_name', 'attendance_date',
            'student', 'student_name', 'roll_number', 'admission_number',
            'grade_level', 'class_name', 'section', 'section_name',
            'status', 'status_display', 'marked_by', 'marked_by_name',
            'marked_at', 'updated_by', 'updated_by_name', 'updated_at', 'remarks'
        ]
        read_only_fields = ['id', 'school', 'marked_by', 'marked_at', 'updated_by', 'updated_at']


class BulkStudentAttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=True)
    status = serializers.ChoiceField(choices=AttendanceRecord.STATUS_CHOICES, default=AttendanceRecord.STATUS_PRESENT)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')
    correction_reason = serializers.CharField(required=False, allow_blank=True, default='')


class BulkMarkAttendanceSerializer(serializers.Serializer):
    academic_year = serializers.IntegerField(required=True)
    grade_level = serializers.IntegerField(required=True)
    section = serializers.IntegerField(required=True)
    attendance_date = serializers.DateField(required=True)
    entries = BulkStudentAttendanceItemSerializer(many=True, required=True)


class AttendanceCorrectionSerializer(serializers.Serializer):
    new_status = serializers.ChoiceField(choices=AttendanceRecord.STATUS_CHOICES, required=True)
    reason = serializers.CharField(required=True, min_length=3, help_text="Mandatory explanation for correcting attendance")


class AttendanceCorrectionLogSerializer(serializers.ModelSerializer):
    corrected_by_name = serializers.CharField(source='corrected_by.get_full_name', read_only=True)
    student_name = serializers.CharField(source='attendance_record.student.name', read_only=True)
    attendance_date = serializers.DateField(source='attendance_record.attendance_date', read_only=True)

    class Meta:
        model = AttendanceCorrectionLog
        fields = [
            'id', 'attendance_record', 'student_name', 'attendance_date',
            'previous_status', 'new_status', 'reason',
            'corrected_by', 'corrected_by_name', 'corrected_at'
        ]
        read_only_fields = ['id', 'corrected_at']
