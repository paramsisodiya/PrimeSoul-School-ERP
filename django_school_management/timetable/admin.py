from django.contrib import admin
from .models import WorkingDay, TimeSlot, Classroom, TimetableEntry


@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'day_name', 'weekday', 'is_working', 'display_order')
    list_filter = ('school', 'academic_year', 'is_working')
    ordering = ('school', 'academic_year', 'display_order', 'weekday')


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'name', 'period_number', 'start_time', 'end_time', 'is_break', 'display_order', 'is_active')
    list_filter = ('school', 'academic_year', 'is_break', 'is_active')
    ordering = ('school', 'academic_year', 'display_order', 'start_time')


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('school', 'room_number', 'name', 'room_type', 'capacity', 'is_active')
    list_filter = ('school', 'room_type', 'is_active')
    search_fields = ('name', 'room_number')


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('school', 'academic_year', 'section', 'working_day', 'time_slot', 'subject', 'teacher', 'room', 'entry_type', 'is_active')
    list_filter = ('school', 'academic_year', 'entry_type', 'is_active')
    search_fields = ('section__name', 'subject__name', 'teacher__name', 'room__name')
