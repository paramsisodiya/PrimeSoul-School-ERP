"""
PrimeSoul Timetable - REST API Serializers
"""
from rest_framework import serializers
from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, Subject
)
from django_school_management.teachers.models import Teacher


class WorkingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingDay
        fields = ['id', 'school', 'academic_year', 'weekday', 'day_name', 'is_working', 'display_order']
        read_only_fields = ['id', 'school']


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ['id', 'school', 'academic_year', 'name', 'period_number', 'start_time', 'end_time', 'is_break', 'display_order', 'is_active']
        read_only_fields = ['id', 'school']


class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ['id', 'school', 'name', 'room_number', 'room_type', 'capacity', 'is_active']
        read_only_fields = ['id', 'school']


class TimetableEntrySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='working_day.day_name', read_only=True)
    slot_name = serializers.CharField(source='time_slot.name', read_only=True)
    section_name = serializers.CharField(source='section.__str__', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    teacher_name = serializers.CharField(source='teacher.name', read_only=True, default='')
    room_name = serializers.CharField(source='room.name', read_only=True, default='')

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'school', 'academic_year', 'working_day', 'day_name',
            'time_slot', 'slot_name', 'section', 'section_name',
            'subject', 'subject_name', 'teacher', 'teacher_name',
            'room', 'room_name', 'entry_type', 'notes', 'is_active'
        ]
        read_only_fields = ['id', 'school']


class TimetableConflictValidationSerializer(serializers.Serializer):
    academic_year_id = serializers.IntegerField()
    working_day_id = serializers.IntegerField()
    time_slot_id = serializers.IntegerField()
    section_id = serializers.IntegerField()
    teacher_id = serializers.IntegerField(required=False, allow_null=True)
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    room_id = serializers.IntegerField(required=False, allow_null=True)
    entry_type = serializers.CharField(default='CLASS')
    exclude_entry_id = serializers.IntegerField(required=False, allow_null=True)


class TimetableGenerateRequestSerializer(serializers.Serializer):
    academic_year_id = serializers.IntegerField()
    section_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=[]
    )


class TimetableCloneRequestSerializer(serializers.Serializer):
    source_academic_year_id = serializers.IntegerField()
    target_academic_year_id = serializers.IntegerField()
    clone_working_days = serializers.BooleanField(default=True)
    clone_time_slots = serializers.BooleanField(default=True)
    clone_entries = serializers.BooleanField(default=True)
