"""
PrimeSoul Timetable - Data Selectors & Matrix Construction
Provides read models, 2D matrix grids, and KPI aggregations for timetable views.
"""
from typing import Dict, Any, List, Optional
from django.db.models import Count, Q

from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, GradeLevel
)
from django_school_management.teachers.models import Teacher


def get_active_academic_year(school, requested_year_id: Optional[int] = None) -> Optional[AcademicYear]:
    """Resolves target academic year for timetable operations."""
    if requested_year_id:
        ay = AcademicYear.objects.filter(school=school, pk=requested_year_id).first()
        if ay:
            return ay
    return AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).first()


def get_timetable_dashboard_metrics(school, academic_year: Optional[AcademicYear] = None) -> Dict[str, Any]:
    """
    Computes real KPIs and configuration status for the Timetable dashboard.
    """
    ay = academic_year or get_active_academic_year(school)
    if not ay:
        return {
            'academic_year': None,
            'working_days_count': 0,
            'time_slots_count': 0,
            'classrooms_count': 0,
            'scheduled_entries_count': 0,
            'scheduled_sections_count': 0,
            'active_faculty_count': 0,
            'is_configured': False
        }

    working_days_count = WorkingDay.objects.filter(school=school, academic_year=ay, is_working=True).count()
    time_slots_count = TimeSlot.objects.filter(school=school, academic_year=ay, is_active=True).count()
    classrooms_count = Classroom.objects.filter(school=school, is_active=True).count()
    
    entries_qs = TimetableEntry.objects.filter(school=school, academic_year=ay, is_active=True)
    scheduled_entries_count = entries_qs.count()
    scheduled_sections_count = entries_qs.values('section').distinct().count()
    active_faculty_count = entries_qs.filter(teacher__isnull=False).values('teacher').distinct().count()

    total_sections_count = Section.objects.filter(school=school, is_active=True).count()

    return {
        'academic_year': ay,
        'working_days_count': working_days_count,
        'time_slots_count': time_slots_count,
        'classrooms_count': classrooms_count,
        'scheduled_entries_count': scheduled_entries_count,
        'scheduled_sections_count': scheduled_sections_count,
        'total_sections_count': total_sections_count,
        'active_faculty_count': active_faculty_count,
        'is_configured': (working_days_count > 0 and time_slots_count > 0)
    }


def get_class_timetable_matrix(school, section: Section, academic_year: Optional[AcademicYear] = None) -> Dict[str, Any]:
    """
    Constructs a 2D matrix [TimeSlots x WorkingDays] for a specific section.
    """
    ay = academic_year or get_active_academic_year(school)
    working_days = list(WorkingDay.objects.filter(
        school=school, academic_year=ay, is_working=True
    ).order_by('display_order', 'weekday'))

    time_slots = list(TimeSlot.objects.filter(
        school=school, academic_year=ay, is_active=True
    ).order_by('display_order', 'start_time'))

    entries = TimetableEntry.objects.filter(
        school=school,
        academic_year=ay,
        section=section,
        is_active=True
    ).select_related('working_day', 'time_slot', 'subject', 'teacher', 'room')

    entry_map = {(e.working_day_id, e.time_slot_id): e for e in entries}

    # Build rows: each row is a time slot, columns are working days
    grid_rows = []
    for slot in time_slots:
        row_cells = []
        for day in working_days:
            cell_entry = entry_map.get((day.id, slot.id))
            row_cells.append({
                'day': day,
                'slot': slot,
                'entry': cell_entry
            })
        grid_rows.append({
            'slot': slot,
            'cells': row_cells
        })

    return {
        'academic_year': ay,
        'section': section,
        'working_days': working_days,
        'time_slots': time_slots,
        'grid_rows': grid_rows,
        'total_entries': len(entries)
    }


def get_teacher_timetable_matrix(school, teacher: Teacher, academic_year: Optional[AcademicYear] = None) -> Dict[str, Any]:
    """
    Constructs a 2D matrix [TimeSlots x WorkingDays] for a specific faculty member.
    """
    ay = academic_year or get_active_academic_year(school)
    working_days = list(WorkingDay.objects.filter(
        school=school, academic_year=ay, is_working=True
    ).order_by('display_order', 'weekday'))

    time_slots = list(TimeSlot.objects.filter(
        school=school, academic_year=ay, is_active=True
    ).order_by('display_order', 'start_time'))

    entries = TimetableEntry.objects.filter(
        school=school,
        academic_year=ay,
        teacher=teacher,
        is_active=True
    ).select_related('working_day', 'time_slot', 'section', 'subject', 'room')

    entry_map = {(e.working_day_id, e.time_slot_id): e for e in entries}

    grid_rows = []
    for slot in time_slots:
        row_cells = []
        for day in working_days:
            cell_entry = entry_map.get((day.id, slot.id))
            row_cells.append({
                'day': day,
                'slot': slot,
                'entry': cell_entry
            })
        grid_rows.append({
            'slot': slot,
            'cells': row_cells
        })

    return {
        'academic_year': ay,
        'teacher': teacher,
        'working_days': working_days,
        'time_slots': time_slots,
        'grid_rows': grid_rows,
        'total_entries': len(entries)
    }


def get_room_timetable_matrix(school, room: Classroom, academic_year: Optional[AcademicYear] = None) -> Dict[str, Any]:
    """
    Constructs a 2D matrix [TimeSlots x WorkingDays] for a physical classroom / laboratory.
    """
    ay = academic_year or get_active_academic_year(school)
    working_days = list(WorkingDay.objects.filter(
        school=school, academic_year=ay, is_working=True
    ).order_by('display_order', 'weekday'))

    time_slots = list(TimeSlot.objects.filter(
        school=school, academic_year=ay, is_active=True
    ).order_by('display_order', 'start_time'))

    entries = TimetableEntry.objects.filter(
        school=school,
        academic_year=ay,
        room=room,
        is_active=True
    ).select_related('working_day', 'time_slot', 'section', 'subject', 'teacher')

    entry_map = {(e.working_day_id, e.time_slot_id): e for e in entries}

    grid_rows = []
    for slot in time_slots:
        row_cells = []
        for day in working_days:
            cell_entry = entry_map.get((day.id, slot.id))
            row_cells.append({
                'day': day,
                'slot': slot,
                'entry': cell_entry
            })
        grid_rows.append({
            'slot': slot,
            'cells': row_cells
        })

    return {
        'academic_year': ay,
        'room': room,
        'working_days': working_days,
        'time_slots': time_slots,
        'grid_rows': grid_rows,
        'total_entries': len(entries)
    }


def get_weekly_timetable_grid(
    school,
    section: Optional[Section] = None,
    teacher: Optional[Teacher] = None,
    academic_year: Optional[AcademicYear] = None
) -> Dict[str, Any]:
    """
    Constructs a weekly timetable grid filtered by section or teacher.
    """
    if section:
        return get_class_timetable_matrix(school, section, academic_year)
    elif teacher:
        return get_teacher_timetable_matrix(school, teacher, academic_year)
    else:
        first_sec = Section.objects.filter(school=school, is_active=True).first()
        if first_sec:
            return get_class_timetable_matrix(school, first_sec, academic_year)
        ay = academic_year or get_active_academic_year(school)
        working_days = list(WorkingDay.objects.filter(school=school, academic_year=ay, is_working=True).order_by('display_order', 'weekday'))
        time_slots = list(TimeSlot.objects.filter(school=school, academic_year=ay, is_active=True).order_by('display_order', 'start_time'))
        return {
            'academic_year': ay,
            'working_days': working_days,
            'time_slots': time_slots,
            'grid_rows': [],
            'total_entries': 0
        }

