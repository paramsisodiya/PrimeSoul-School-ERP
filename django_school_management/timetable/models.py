import datetime
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django_school_management.academics.models import AcademicYear, GradeLevel, Section, Subject
from django_school_management.teachers.models import Teacher


class WorkingDay(ExportModelOperationsMixin('working_day'), TimeStampedModel):
    """
    Configurable school working day per Academic Year (e.g. Monday - Saturday, Sunday Off).
    Avoids hardcoding fixed school operating days.
    """
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

    WEEKDAY_CHOICES = (
        (MONDAY, 'Monday'),
        (TUESDAY, 'Tuesday'),
        (WEDNESDAY, 'Wednesday'),
        (THURSDAY, 'Thursday'),
        (FRIDAY, 'Friday'),
        (SATURDAY, 'Saturday'),
        (SUNDAY, 'Sunday'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='working_days'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='working_days'
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    day_name = models.CharField(max_length=20, blank=True)
    is_working = models.BooleanField(default=True, help_text="Uncheck for weekends or non-working days.")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'weekday']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'weekday'],
                name='unique_school_academic_working_day'
            )
        ]

    def __str__(self):
        day = dict(self.WEEKDAY_CHOICES).get(self.weekday, f"Day {self.weekday}")
        status = "Working" if self.is_working else "Off"
        return f"{day} ({status})"

    def save(self, *args, **kwargs):
        if not self.day_name:
            self.day_name = dict(self.WEEKDAY_CHOICES).get(self.weekday, f"Day {self.weekday}")
        if self.display_order == 0:
            self.display_order = self.weekday
        super().save(*args, **kwargs)


class TimeSlot(ExportModelOperationsMixin('time_slot'), TimeStampedModel):
    """
    Daily school period or time slot configuration per Academic Year.
    Allows variable periods, zero periods, assemblies, breaks, and recesses.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='time_slots'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='time_slots'
    )
    name = models.CharField(max_length=100, help_text="e.g. Period 1, Assembly, Morning Break, Period 6")
    period_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Sequential academic period index (null for breaks, assemblies, etc.)"
    )
    start_time = models.TimeField(help_text="Slot start time (HH:MM)")
    end_time = models.TimeField(help_text="Slot end time (HH:MM)")
    is_break = models.BooleanField(default=False, help_text="Designates non-instructional slots (Recess, Lunch, Break)")
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year', 'name'],
                name='unique_school_academic_time_slot_name'
            )
        ]

    def __str__(self):
        break_tag = " [BREAK]" if self.is_break else ""
        period_tag = f" #{self.period_number}" if self.period_number else ""
        time_range = f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
        return f"{self.name}{period_tag} ({time_range}){break_tag}"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': "End time must be strictly after start time."})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Classroom(ExportModelOperationsMixin('classroom'), TimeStampedModel):
    """
    Physical rooms, labs, and facilities for tracking room occupancy and avoiding conflicts.
    """
    ROOM_TYPE_CHOICES = (
        ('CLASSROOM', 'General Classroom'),
        ('LAB', 'Science / Computer Lab'),
        ('LIBRARY', 'Library Room'),
        ('AUDITORIUM', 'Auditorium / Multipurpose Hall'),
        ('ACTIVITY', 'Sports / Music / Activity Hall'),
        ('OTHER', 'Other Special Facility'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='classrooms'
    )
    name = models.CharField(max_length=100, help_text="e.g. Room 101, Physics Lab, Senior Computer Lab")
    room_number = models.CharField(max_length=30, help_text="e.g. 101, LAB-02, AUD")
    room_type = models.CharField(max_length=30, choices=ROOM_TYPE_CHOICES, default='CLASSROOM')
    capacity = models.PositiveIntegerField(default=40, help_text="Seating capacity")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['room_number', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'room_number'],
                name='unique_school_room_number'
            )
        ]

    def __str__(self):
        return f"{self.room_number} - {self.name} ({self.get_room_type_display()})"


class TimetableEntry(ExportModelOperationsMixin('timetable_entry'), TimeStampedModel):
    """
    Core schedule entry mapping a section, day, period, subject, teacher, and optional room.
    Multi-tenant scoped and conflict-checked.
    """
    TYPE_CLASS = 'CLASS'
    TYPE_LAB = 'LAB'
    TYPE_ACTIVITY = 'ACTIVITY'
    TYPE_BREAK = 'BREAK'
    TYPE_FREE = 'FREE'

    ENTRY_TYPE_CHOICES = (
        (TYPE_CLASS, 'Regular Class'),
        (TYPE_LAB, 'Practical / Lab'),
        (TYPE_ACTIVITY, 'Co-Curricular / Activity'),
        (TYPE_BREAK, 'Scheduled Break'),
        (TYPE_FREE, 'Self Study / Free Period'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='timetable_entries'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='timetable_entries'
    )
    working_day = models.ForeignKey(
        WorkingDay,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='timetable_entries'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='timetable_entries'
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timetable_entries'
    )
    room = models.ForeignKey(
        Classroom,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timetable_entries'
    )
    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPE_CHOICES,
        default=TYPE_CLASS
    )
    notes = models.CharField(max_length=255, blank=True, help_text="Optional remarks or lesson topic")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = [
            'working_day__display_order',
            'time_slot__display_order',
            'time_slot__start_time'
        ]
        indexes = [
            models.Index(fields=['school', 'academic_year', 'working_day', 'time_slot']),
            models.Index(fields=['teacher', 'working_day', 'time_slot']),
            models.Index(fields=['section', 'working_day', 'time_slot']),
            models.Index(fields=['room', 'working_day', 'time_slot']),
        ]

    def __str__(self):
        subj_name = self.subject.name if self.subject else self.get_entry_type_display()
        teacher_name = self.teacher.name if self.teacher else 'Unassigned'
        return f"{self.section} | {self.working_day.day_name} {self.time_slot.name}: {subj_name} ({teacher_name})"
