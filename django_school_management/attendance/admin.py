from django.contrib import admin
from .models import AttendanceRecord, AttendanceCorrectionLog


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('attendance_date', 'student', 'grade_level', 'section', 'status', 'marked_by', 'school')
    list_filter = ('school', 'academic_year', 'grade_level', 'status', 'attendance_date')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'remarks')
    date_hierarchy = 'attendance_date'


@admin.register(AttendanceCorrectionLog)
class AttendanceCorrectionLogAdmin(admin.ModelAdmin):
    list_display = ('attendance_record', 'previous_status', 'new_status', 'corrected_by', 'corrected_at', 'school')
    list_filter = ('school', 'previous_status', 'new_status', 'corrected_at')
    search_fields = ('reason', 'attendance_record__student__first_name', 'attendance_record__student__last_name')
    readonly_fields = ('attendance_record', 'previous_status', 'new_status', 'reason', 'corrected_by', 'corrected_at', 'school')
