"""
PrimeSoul Timetable - Conflict Detection & Integrity Service
Enforces strict multi-dimensional collision prevention:
- Teacher double-booking
- Section double-booking
- Room double-booking
- Invalid subject-teacher allocation
- Multi-tenant boundary isolation
"""
from typing import List, Tuple, Optional
from django.core.exceptions import ValidationError

from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, Subject, SubjectAssignment
)
from django_school_management.teachers.models import Teacher


def validate_timetable_entry_conflicts(
    school,
    academic_year: AcademicYear,
    working_day: WorkingDay,
    time_slot: TimeSlot,
    section: Section,
    teacher: Optional[Teacher] = None,
    subject: Optional[Subject] = None,
    room: Optional[Classroom] = None,
    entry_type: str = TimetableEntry.TYPE_CLASS,
    exclude_entry_id: Optional[int] = None,
    strict_teacher_assignment: bool = True
) -> Tuple[bool, List[str]]:
    """
    Validates a proposed timetable entry against all active bookings and business invariants.
    Returns (is_valid, list_of_conflict_reasons).
    """
    conflicts = []

    # 1. Multi-Tenant Integrity Checks
    if working_day.school_id != school.id:
        conflicts.append("Working day does not belong to the active school tenant.")
    if time_slot.school_id != school.id:
        conflicts.append("Time slot does not belong to the active school tenant.")
    if section.school_id != school.id:
        conflicts.append("Section does not belong to the active school tenant.")
    if subject and subject.school_id != school.id:
        conflicts.append("Subject does not belong to the active school tenant.")
    if teacher and getattr(teacher, 'school_id', None) and teacher.school_id != school.id:
        conflicts.append("Teacher does not belong to the active school tenant.")
    if room and room.school_id != school.id:
        conflicts.append("Room does not belong to the active school tenant.")

    # 2. Academic Year Alignment
    if working_day.academic_year_id != academic_year.id:
        conflicts.append("Working day belongs to a different academic session.")
    if time_slot.academic_year_id != academic_year.id:
        conflicts.append("Time slot belongs to a different academic session.")
    if section.academic_year_id and section.academic_year_id != academic_year.id:
        conflicts.append("Section is enrolled under a different academic session.")

    # 3. Non-Working Day Restriction
    if not working_day.is_working and entry_type not in (TimetableEntry.TYPE_ACTIVITY,):
        conflicts.append(f"Cannot schedule classes on '{working_day.day_name}' because it is marked as a non-working day.")

    # 4. Break Period Handling
    if time_slot.is_break and entry_type not in (TimetableEntry.TYPE_BREAK,):
        conflicts.append(f"Cannot schedule instruction during '{time_slot.name}' because it is configured as a break / recess.")

    # Base query for active entries during the same slot and day
    base_qs = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        working_day=working_day,
        time_slot=time_slot,
        is_active=True
    )
    if exclude_entry_id:
        base_qs = base_qs.exclude(pk=exclude_entry_id)

    # 5. Section Double Booking
    # Same section cannot have two entries in the same period
    sec_collision = base_qs.filter(section=section).first()
    if sec_collision:
        conflicts.append(
            f"Section Double Booking: Section '{section}' already has an active entry "
            f"({sec_collision.subject.name if sec_collision.subject else sec_collision.get_entry_type_display()}) "
            f"on {working_day.day_name} at {time_slot.name}."
        )

    # 6. Teacher Double Booking
    # Same teacher cannot be booked in multiple classes at the same time
    if teacher:
        teacher_collision = base_qs.filter(teacher=teacher).first()
        if teacher_collision:
            conflicts.append(
                f"Teacher Double Booking: Faculty '{teacher.name}' is already booked teaching "
                f"Section '{teacher_collision.section}' on {working_day.day_name} at {time_slot.name}."
            )

    # 7. Room Double Booking
    # Same room cannot host multiple classes simultaneously
    if room:
        room_collision = base_qs.filter(room=room).first()
        if room_collision:
            conflicts.append(
                f"Room Double Booking: Room '{room.name}' ({room.room_number}) is already allocated to "
                f"Section '{room_collision.section}' on {working_day.day_name} at {time_slot.name}."
            )

    # 8. Teacher-Subject Assignment Validity
    # Checks whether this teacher is formally allocated to teach this subject in this section/class
    if strict_teacher_assignment and teacher and subject and entry_type == TimetableEntry.TYPE_CLASS:
        has_assignment = SubjectAssignment.objects.filter(
            academic_year=academic_year,
            subject=subject,
            teacher=teacher,
            is_active=True
        ).filter(
            models.Q(section=section) | models.Q(section__isnull=True, grade_level=section.grade_level)
        ).exists()

        if not has_assignment:
            conflicts.append(
                f"Invalid Teacher Assignment: Faculty '{teacher.name}' is not formally assigned to teach "
                f"'{subject.name}' for {section} in the {academic_year.name} academic session."
            )

    is_valid = len(conflicts) == 0
    return is_valid, conflicts


from django.db import models
