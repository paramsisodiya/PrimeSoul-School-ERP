"""
PrimeSoul ERP Academic Management - REST API Serializers
"""
from rest_framework import serializers
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject,
    SubjectAssignment, StudentEnrollment
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'status', 'is_current', 'created', 'modified']
        read_only_fields = ['id', 'created', 'modified']


class GradeLevelSerializer(serializers.ModelSerializer):
    section_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = GradeLevel
        fields = ['id', 'name', 'code', 'board', 'stream_applicable', 'display_order', 'is_active', 'section_count', 'created', 'modified']
        read_only_fields = ['id', 'created', 'modified']


class SectionSerializer(serializers.ModelSerializer):
    grade_name = serializers.CharField(source='grade_level.name', read_only=True)
    teacher_name = serializers.CharField(source='class_teacher.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)

    class Meta:
        model = Section
        fields = [
            'id', 'name', 'grade_level', 'grade_name', 'academic_year', 'academic_year_name',
            'class_teacher', 'teacher_name', 'room_number', 'max_capacity', 'is_active', 'created', 'modified'
        ]
        read_only_fields = ['id', 'created', 'modified']


class SubjectSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.name', read_only=True)

    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'subject_code', 'subject_type', 'max_marks', 'passing_marks',
            'instructor', 'instructor_name', 'theory_marks', 'practical_marks', 'is_active', 'created', 'modified'
        ]
        read_only_fields = ['id', 'created', 'modified']


class SubjectAssignmentSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    grade_name = serializers.CharField(source='grade_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = SubjectAssignment
        fields = [
            'id', 'academic_year', 'academic_year_name', 'grade_level', 'grade_name',
            'section', 'section_name', 'subject', 'subject_name', 'teacher', 'teacher_name',
            'periods_per_week', 'is_active', 'created', 'modified'
        ]
        read_only_fields = ['id', 'created', 'modified']


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    grade_name = serializers.CharField(source='grade_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = [
            'id', 'student', 'student_name', 'admission_number', 'academic_year', 'academic_year_name',
            'grade_level', 'grade_name', 'section', 'section_name', 'roll_number', 'status',
            'enrollment_date', 'notes', 'created', 'modified'
        ]
        read_only_fields = ['id', 'created', 'modified']


class PromotionExecuteSerializer(serializers.Serializer):
    source_year = serializers.IntegerField(required=True)
    target_year = serializers.IntegerField(required=True)
    source_grade = serializers.IntegerField(required=True)
    target_grade = serializers.IntegerField(required=True)
    source_section = serializers.IntegerField(required=False, allow_null=True)
    target_section = serializers.IntegerField(required=False, allow_null=True)
    student_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
