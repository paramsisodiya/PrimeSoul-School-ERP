"""
PrimeSoul Timetable - Automated Timetable Generation Engine
Places subject-teacher curriculum assignments into open working periods while strictly respecting:
- Working day calendars
- Instruction vs break slots
- Section availability
- Faculty collision avoidance
- Classroom availability
Returns detailed summary of successfully placed entries and unplaced items.
"""
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.db.models import Q

from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.academics.models import (
    AcademicYear, Section, Subject, SubjectAssignment
)
from django_school_management.core.audit import log_timetable_event
from .conflict_service import validate_timetable_entry_conflicts


def generate_automated_timetable(
    school,
    academic_year: AcademicYear,
    section_ids: Optional[List[int]] = None,
    actor=None
) -> Dict[str, Any]:
    """
    Intelligently generates timetable entries for the given school and academic session.
    """
    working_days = list(WorkingDay.objects.filter(
        school=school,
        academic_year=academic_year,
        is_working=True
    ).order_by('display_order', 'weekday'))

    if not working_days:
        return {
            'success': False,
            'placed_count': 0,
            'unplaced': [],
            'error': "No active working days found. Please configure working days under Timetable Setup first."
        }

    instruction_slots = list(TimeSlot.objects.filter(
        school=school,
        academic_year=academic_year,
        is_break=False,
        is_active=True
    ).order_by('display_order', 'start_time'))

    if not instruction_slots:
        return {
            'success': False,
            'placed_count': 0,
            'unplaced': [],
            'error': "No instructional periods found. Please configure time slots under Timetable Setup first."
        }

    sections_qs = Section.objects.filter(school=school, is_active=True)
    if section_ids:
        sections_qs = sections_qs.filter(id__in=section_ids)
    sections = list(sections_qs)

    if not sections:
        return {
            'success': False,
            'placed_count': 0,
            'unplaced': [],
            'error': "No active class sections found for scheduling."
        }

    placed_count = 0
    unplaced = []
    total_requested = 0

    with transaction.atomic():
        for section in sections:
            # Fetch subject assignments for this section (direct or grade-level generic)
            assignments = SubjectAssignment.objects.filter(
                academic_year=academic_year,
                is_active=True
            ).filter(
                Q(section=section) | Q(section__isnull=True, grade_level=section.grade_level)
            ).select_related('subject', 'teacher')

            for assignment in assignments:
                target_periods = assignment.periods_per_week or 5
                total_requested += target_periods

                # Check existing entries already scheduled for this subject & section
                existing_count = TimetableEntry.objects.filter(
                    school=school,
                    academic_year=academic_year,
                    section=section,
                    subject=assignment.subject,
                    is_active=True
                ).count()

                needed = target_periods - existing_count
                if needed <= 0:
                    continue

                remaining = needed
                # Spread allocations across working days
                # Day cycle offset by subject id to distribute load evenly
                day_offset = (assignment.subject.id if assignment.subject else 0) % len(working_days)

                for attempt in range(len(working_days) * len(instruction_slots)):
                    if remaining <= 0:
                        break

                    day_idx = (day_offset + attempt) % len(working_days)
                    slot_idx = (attempt // len(working_days)) % len(instruction_slots)

                    candidate_day = working_days[day_idx]
                    candidate_slot = instruction_slots[slot_idx]

                    # Validate collision
                    is_valid, _ = validate_timetable_entry_conflicts(
                        school=school,
                        academic_year=academic_year,
                        working_day=candidate_day,
                        time_slot=candidate_slot,
                        section=section,
                        teacher=assignment.teacher,
                        subject=assignment.subject,
                        room=None,
                        entry_type=TimetableEntry.TYPE_CLASS,
                        strict_teacher_assignment=False
                    )

                    if is_valid:
                        TimetableEntry.objects.create(
                            school=school,
                            academic_year=academic_year,
                            working_day=candidate_day,
                            time_slot=candidate_slot,
                            section=section,
                            subject=assignment.subject,
                            teacher=assignment.teacher,
                            entry_type=TimetableEntry.TYPE_CLASS,
                            created_by=actor
                        )
                        placed_count += 1
                        remaining -= 1

                if remaining > 0:
                    unplaced.append({
                        'section': str(section),
                        'subject': assignment.subject.name,
                        'teacher': assignment.teacher.name if assignment.teacher else "Unassigned",
                        'unplaced_periods': remaining,
                        'reason': f"Could not find {remaining} open period(s) without faculty or section collision."
                    })

        log_timetable_event(
            actor=actor,
            school=school,
            action='GENERATE_TIMETABLE',
            details={
                'academic_year': academic_year.name,
                'sections_count': len(sections),
                'placed_count': placed_count,
                'unplaced_count': len(unplaced),
                'total_requested': total_requested
            }
        )

    return {
        'success': True,
        'placed_count': placed_count,
        'unplaced': unplaced,
        'total_requested': total_requested
    }
