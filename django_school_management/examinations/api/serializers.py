from rest_framework import serializers
from decimal import Decimal

from django_school_management.examinations.models import (
    AssessmentType, GradeScale, GradeScaleBand, ExaminationSession,
    Exam, ExamSubject, StudentMark, StudentExamResult, MarksCorrectionLog
)


class AssessmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentType
        fields = ['id', 'name', 'code', 'description', 'is_active']
        read_only_fields = ['id']


class GradeScaleBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeScaleBand
        fields = ['id', 'name', 'min_percentage', 'max_percentage', 'grade_point', 'is_passing', 'remarks']
        read_only_fields = ['id']


class GradeScaleSerializer(serializers.ModelSerializer):
    bands = GradeScaleBandSerializer(many=True, read_only=True)

    class Meta:
        model = GradeScale
        fields = ['id', 'name', 'code', 'description', 'is_default', 'bands']
        read_only_fields = ['id']


class ExaminationSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ExaminationSession
        fields = ['id', 'name', 'code', 'academic_year', 'start_date', 'end_date', 'status', 'status_display', 'description']
        read_only_fields = ['id', 'status_display']


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = ExamSubject
        fields = ['id', 'exam', 'subject', 'subject_name', 'max_marks', 'passing_marks', 'weightage', 'sequence_order', 'is_optional', 'is_active']
        read_only_fields = ['id', 'subject_name']


class ExamSerializer(serializers.ModelSerializer):
    grade_level_name = serializers.CharField(source='grade_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    subjects = ExamSubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'session', 'session_name', 'academic_year', 'grade_level', 'grade_level_name',
            'section', 'section_name', 'assessment_type', 'grade_scale', 'name',
            'start_date', 'end_date', 'weightage', 'ranking_enabled', 'status', 'status_display', 'subjects'
        ]
        read_only_fields = ['id', 'session_name', 'grade_level_name', 'section_name', 'status_display', 'subjects']


class StudentMarkSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    subject_name = serializers.CharField(source='exam_subject.subject.name', read_only=True)

    class Meta:
        model = StudentMark
        fields = [
            'id', 'exam', 'exam_subject', 'subject_name', 'student', 'student_name',
            'status', 'marks_obtained', 'grade', 'grade_point', 'is_passed', 'remarks'
        ]
        read_only_fields = ['id', 'student_name', 'subject_name', 'grade', 'grade_point', 'is_passed']


class BulkMarkItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=StudentMark.STATUS_CHOICES, default=StudentMark.STATUS_NOT_ENTERED)
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


class BulkMarksEntrySerializer(serializers.Serializer):
    exam_id = serializers.IntegerField()
    exam_subject_id = serializers.IntegerField()
    section_id = serializers.IntegerField(required=False, allow_null=True)
    marks = BulkMarkItemSerializer(many=True)
    correction_reason = serializers.CharField(required=False, allow_blank=True, default='')


class StudentExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    result_status_display = serializers.CharField(source='get_result_status_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = StudentExamResult
        fields = [
            'id', 'exam', 'exam_name', 'student', 'student_name',
            'total_marks_obtained', 'total_max_marks', 'percentage',
            'overall_grade', 'overall_grade_point', 'result_status', 'result_status_display',
            'status', 'status_display', 'subjects_passed', 'subjects_failed',
            'class_rank', 'section_rank', 'attendance_working_days', 'attendance_present_days',
            'attendance_percentage', 'verification_code'
        ]
        read_only_fields = [
            'id', 'exam', 'exam_name', 'student', 'student_name',
            'total_marks_obtained', 'total_max_marks', 'percentage',
            'overall_grade', 'overall_grade_point', 'result_status', 'result_status_display',
            'status', 'status_display', 'subjects_passed', 'subjects_failed',
            'class_rank', 'section_rank', 'attendance_working_days', 'attendance_present_days',
            'attendance_percentage', 'verification_code'
        ]


class MarksCorrectionSerializer(serializers.Serializer):
    mark_id = serializers.IntegerField()
    new_status = serializers.ChoiceField(choices=StudentMark.STATUS_CHOICES)
    new_marks = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(required=True)
