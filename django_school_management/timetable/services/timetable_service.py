"""
PrimeSoul Timetable - Core Timetable Services
Handles creation, mutation, cloning, clearing, and CSV export of timetable entries with audit logging.
"""
import csv
import io
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.core.exceptions import ValidationError

from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, Subject
)
from django_school_management.teachers.models import Teacher
from django_school_management.core.audit import log_timetable_event
from .conflict_service import validate_timetable_entry_conflicts


def create_timetable_entry(
    school,
    academic_year: AcademicYear,
    working_day: WorkingDay,
    time_slot: TimeSlot,
    section: Section,
    subject: Optional[Subject] = None,
    teacher: Optional[Teacher] = None,
    room: Optional[Classroom] = None,
    entry_type: str = TimetableEntry.TYPE_CLASS,
    notes: str = '',
    actor=None,
    strict_assignment: bool = True
) -> TimetableEntry:
    """
    Validates and creates a new timetable entry.
    """
    is_valid, conflicts = validate_timetable_entry_conflicts(
        school=school,
        academic_year=academic_year,
        working_day=working_day,
        time_slot=time_slot,
        section=section,
        teacher=teacher,
        subject=subject,
        room=room,
        entry_type=entry_type,
        strict_teacher_assignment=strict_assignment
    )
    if not is_valid:
        raise ValidationError("; ".join(conflicts))

    with transaction.atomic():
        entry = TimetableEntry.objects.create(
            school=school,
            academic_year=academic_year,
            working_day=working_day,
            time_slot=time_slot,
            section=section,
            subject=subject,
            teacher=teacher,
            room=room,
            entry_type=entry_type,
            notes=notes,
            created_by=actor
        )

        log_timetable_event(
            actor=actor,
            school=school,
            action='CREATE_TIMETABLE_ENTRY',
            resource_id=str(entry.id),
            details={
                'section': str(section),
                'day': working_day.day_name,
                'slot': time_slot.name,
                'subject': subject.name if subject else None,
                'teacher': teacher.name if teacher else None,
                'room': room.room_number if room else None,
            }
        )

    return entry


def update_timetable_entry(
    entry: TimetableEntry,
    working_day: Optional[WorkingDay] = None,
    time_slot: Optional[TimeSlot] = None,
    section: Optional[Section] = None,
    subject: Optional[Subject] = None,
    teacher: Optional[Teacher] = None,
    room: Optional[Classroom] = None,
    entry_type: Optional[str] = None,
    notes: Optional[str] = None,
    actor=None,
    strict_assignment: bool = True
) -> TimetableEntry:
    """
    Validates and updates an existing timetable entry.
    """
    wd = working_day or entry.working_day
    ts = time_slot or entry.time_slot
    sec = section or entry.section
    sub = subject if subject is not None else entry.subject
    tchr = teacher if teacher is not None else entry.teacher
    rm = room if room is not None else entry.room
    etype = entry_type or entry.entry_type

    is_valid, conflicts = validate_timetable_entry_conflicts(
        school=entry.school,
        academic_year=entry.academic_year,
        working_day=wd,
        time_slot=ts,
        section=sec,
        teacher=tchr,
        subject=sub,
        room=rm,
        entry_type=etype,
        exclude_entry_id=entry.id,
        strict_teacher_assignment=strict_assignment
    )
    if not is_valid:
        raise ValidationError("; ".join(conflicts))

    with transaction.atomic():
        entry.working_day = wd
        entry.time_slot = ts
        entry.section = sec
        entry.subject = sub
        entry.teacher = tchr
        entry.room = rm
        entry.entry_type = etype
        if notes is not None:
            entry.notes = notes
        entry.save()

        log_timetable_event(
            actor=actor,
            school=entry.school,
            action='UPDATE_TIMETABLE_ENTRY',
            resource_id=str(entry.id),
            details={
                'section': str(entry.section),
                'day': entry.working_day.day_name,
                'slot': entry.time_slot.name,
                'subject': entry.subject.name if entry.subject else None,
                'teacher': entry.teacher.name if entry.teacher else None,
            }
        )

    return entry


def delete_timetable_entry(entry: TimetableEntry, actor=None, hard_delete: bool = False) -> None:
    """
    Soft-deactivates or permanently deletes a timetable entry.
    """
    school = entry.school
    entry_id = str(entry.id)
    sec_str = str(entry.section)
    slot_str = f"{entry.working_day.day_name} {entry.time_slot.name}"

    with transaction.atomic():
        if hard_delete:
            entry.delete()
        else:
            entry.is_active = False
            entry.save(update_fields=['is_active'])

        log_timetable_event(
            actor=actor,
            school=school,
            action='DELETE_TIMETABLE_ENTRY',
            resource_id=entry_id,
            details={'section': sec_str, 'slot': slot_str, 'hard_delete': hard_delete}
        )


def clear_timetable(
    school,
    academic_year: AcademicYear,
    section: Optional[Section] = None,
    actor=None
) -> int:
    """
    Clears all active timetable entries for a school and academic year (optionally scoped to a section).
    Destructive POST action protected by audit logging.
    """
    qs = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        is_active=True
    )
    if section:
        qs = qs.filter(section=section)

    count = qs.count()
    with transaction.atomic():
        qs.delete()
        log_timetable_event(
            actor=actor,
            school=school,
            action='CLEAR_TIMETABLE',
            details={
                'academic_year': academic_year.name,
                'section': str(section) if section else 'ALL',
                'cleared_count': count
            }
        )

    return count


def clone_timetable(
    school,
    source_academic_year: AcademicYear,
    target_academic_year: AcademicYear,
    actor=None,
    clone_working_days: bool = True,
    clone_time_slots: bool = True,
    clone_entries: bool = True
) -> Dict[str, Any]:
    """
    Clones working days, time slots, and timetable entries from source to target academic year.
    Silently skips entries that would cause conflicts in the target year.
    """
    if source_academic_year.id == target_academic_year.id:
        raise ValidationError("Source and target academic sessions cannot be the same.")

    stats = {
        'working_days_created': 0,
        'time_slots_created': 0,
        'entries_created': 0,
        'skipped_entries': 0
    }

    with transaction.atomic():
        day_map = {}
        if clone_working_days:
            src_days = WorkingDay.objects.filter(school=school, academic_year=source_academic_year)
            for d in src_days:
                target_day, created = WorkingDay.objects.get_or_create(
                    school=school,
                    academic_year=target_academic_year,
                    weekday=d.weekday,
                    defaults={
                        'day_name': d.day_name,
                        'is_working': d.is_working,
                        'display_order': d.display_order
                    }
                )
                day_map[d.id] = target_day
                if created:
                    stats['working_days_created'] += 1
        else:
            # map by weekday
            target_days = {td.weekday: td for td in WorkingDay.objects.filter(school=school, academic_year=target_academic_year)}
            for sd in WorkingDay.objects.filter(school=school, academic_year=source_academic_year):
                if sd.weekday in target_days:
                    day_map[sd.id] = target_days[sd.weekday]

        slot_map = {}
        if clone_time_slots:
            src_slots = TimeSlot.objects.filter(school=school, academic_year=source_academic_year)
            for s in src_slots:
                target_slot, created = TimeSlot.objects.get_or_create(
                    school=school,
                    academic_year=target_academic_year,
                    name=s.name,
                    defaults={
                        'period_number': s.period_number,
                        'start_time': s.start_time,
                        'end_time': s.end_time,
                        'is_break': s.is_break,
                        'display_order': s.display_order,
                        'is_active': s.is_active
                    }
                )
                slot_map[s.id] = target_slot
                if created:
                    stats['time_slots_created'] += 1
        else:
            target_slots = {ts.name: ts for ts in TimeSlot.objects.filter(school=school, academic_year=target_academic_year)}
            for ss in TimeSlot.objects.filter(school=school, academic_year=source_academic_year):
                if ss.name in target_slots:
                    slot_map[ss.id] = target_slots[ss.name]

        if clone_entries:
            src_entries = TimetableEntry.objects.filter(
                school=school,
                academic_year=source_academic_year,
                is_active=True
            ).select_related('working_day', 'time_slot', 'section', 'subject', 'teacher', 'room')

            for entry in src_entries:
                target_wd = day_map.get(entry.working_day_id)
                target_ts = slot_map.get(entry.time_slot_id)

                if not target_wd or not target_ts:
                    stats['skipped_entries'] += 1
                    continue

                is_valid, _ = validate_timetable_entry_conflicts(
                    school=school,
                    academic_year=target_academic_year,
                    working_day=target_wd,
                    time_slot=target_ts,
                    section=entry.section,
                    teacher=entry.teacher,
                    subject=entry.subject,
                    room=entry.room,
                    entry_type=entry.entry_type,
                    strict_teacher_assignment=False
                )
                if is_valid:
                    TimetableEntry.objects.create(
                        school=school,
                        academic_year=target_academic_year,
                        working_day=target_wd,
                        time_slot=target_ts,
                        section=entry.section,
                        subject=entry.subject,
                        teacher=entry.teacher,
                        room=entry.room,
                        entry_type=entry.entry_type,
                        notes=entry.notes,
                        created_by=actor
                    )
                    stats['entries_created'] += 1
                else:
                    stats['skipped_entries'] += 1

        log_timetable_event(
            actor=actor,
            school=school,
            action='CLONE_TIMETABLE',
            details={
                'source': source_academic_year.name,
                'target': target_academic_year.name,
                'stats': stats
            }
        )

    return stats


def export_timetable_csv(school, academic_year: AcademicYear, section=None, teacher=None) -> str:
    """
    Generates a CSV string representation of the timetable.
    """
    qs = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        is_active=True
    ).select_related('working_day', 'time_slot', 'section', 'subject', 'teacher', 'room')

    if section:
        qs = qs.filter(section=section)
    if teacher:
        qs = qs.filter(teacher=teacher)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "School", "Academic Year", "Class / Section", "Day", "Period / Slot",
        "Start Time", "End Time", "Type", "Subject", "Teacher", "Room", "Notes"
    ])

    for e in qs:
        writer.writerow([
            school.name,
            academic_year.name,
            str(e.section),
            e.working_day.day_name,
            e.time_slot.name,
            e.time_slot.start_time.strftime('%H:%M'),
            e.time_slot.end_time.strftime('%H:%M'),
            e.get_entry_type_display(),
            e.subject.name if e.subject else "",
            e.teacher.name if e.teacher else "",
            e.room.room_number if e.room else "",
            e.notes or ""
        ])

    return output.getvalue()
