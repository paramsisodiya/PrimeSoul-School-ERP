import datetime
from typing import Dict, Any, List, Optional
from django.db import models
from django.db.models import Count, Q, Case, When, IntegerField, F
from django.utils import timezone

from django_school_management.attendance.models import AttendanceRecord
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, StudentEnrollment,
    SubjectAssignment, ClassTeacherAssignment
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher


def get_attendance_dashboard_metrics(school, target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Computes real-time attendance KPIs for a school tenant on a given date (defaults to today).
    """
    if not school:
        return {}

    date = target_date or timezone.localdate()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    records_today = AttendanceRecord.objects.filter(school=school, attendance_date=date)
    agg = records_today.aggregate(
        total_today=Count('id'),
        present_today=Count(Case(When(status=AttendanceRecord.STATUS_PRESENT, then=1), output_field=IntegerField())),
        absent_today=Count(Case(When(status=AttendanceRecord.STATUS_ABSENT, then=1), output_field=IntegerField())),
        late_today=Count(Case(When(status=AttendanceRecord.STATUS_LATE, then=1), output_field=IntegerField())),
        half_day_today=Count(Case(When(status=AttendanceRecord.STATUS_HALF_DAY, then=1), output_field=IntegerField())),
        excused_today=Count(Case(When(status=AttendanceRecord.STATUS_EXCUSED, then=1), output_field=IntegerField())),
    )

    total_today = agg['total_today'] or 0
    present_today = agg['present_today'] or 0
    absent_today = agg['absent_today'] or 0
    late_today = agg['late_today'] or 0
    half_day_today = agg['half_day_today'] or 0
    excused_today = agg['excused_today'] or 0

    effective_present = present_today + late_today + (0.5 * half_day_today)
    today_percentage = round((effective_present / total_today * 100.0), 1) if total_today > 0 else 0.0

    # Total active sections in current academic year
    sections_qs = Section.objects.filter(school=school, is_active=True)
    if current_year:
        sections_qs = sections_qs.filter(Q(academic_year=current_year) | Q(academic_year__isnull=True))

    total_sections_count = sections_qs.count()
    marked_sections_count = records_today.values('section').distinct().count()
    pending_sections_count = max(0, total_sections_count - marked_sections_count)

    # Low attendance count in current year
    low_attendance_students = get_low_attendance_students(school, current_year, threshold=75.0)
    low_attendance_count = len(low_attendance_students)

    return {
        'target_date': date,
        'current_year': current_year,
        'total_today': total_today,
        'present_today': present_today,
        'absent_today': absent_today,
        'late_today': late_today,
        'half_day_today': half_day_today,
        'excused_today': excused_today,
        'today_percentage': today_percentage,
        'total_sections_count': total_sections_count,
        'marked_sections_count': marked_sections_count,
        'pending_sections_count': pending_sections_count,
        'low_attendance_count': low_attendance_count,
    }


def get_daily_attendance_sheet(
    school,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    section: Section,
    target_date: datetime.date
) -> List[Dict[str, Any]]:
    """
    Fetches all enrolled students in a class-section and joins any existing attendance records for the date.
    """
    # 1. Fetch enrolled students
    enrollments = StudentEnrollment.objects.filter(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        status__in=['ACTIVE', 'ENROLLED']
    ).select_related('student').order_by('roll_number', 'student__first_name')

    students = []
    if enrollments.exists():
        for e in enrollments:
            students.append({
                'student': e.student,
                'roll_number': e.roll_number or e.student.roll_number or e.student.roll or "-",
            })
    else:
        # Fallback to direct student placement
        st_qs = Student.objects.filter(
            school=school,
            grade_level=grade_level,
            section=section,
            is_active=True
        ).order_by('roll_number', 'first_name')
        for s in st_qs:
            students.append({
                'student': s,
                'roll_number': s.roll_number or s.roll or "-",
            })

    # 2. Fetch existing attendance records
    existing_records = AttendanceRecord.objects.filter(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        attendance_date=target_date
    ).select_related('marked_by', 'updated_by')

    record_map = {r.student_id: r for r in existing_records}

    sheet = []
    for item in students:
        st = item['student']
        rec = record_map.get(st.id)
        sheet.append({
            'student_id': st.id,
            'student_name': st.name,
            'admission_number': getattr(st, 'admission_number', '') or getattr(st, 'admission_student_id', ''),
            'roll_number': item['roll_number'],
            'gender': getattr(st, 'gender', ''),
            'status': rec.status if rec else AttendanceRecord.STATUS_PRESENT,
            'remarks': rec.remarks if rec else '',
            'is_existing': rec is not None,
            'record_id': rec.id if rec else None,
            'marked_by': rec.marked_by.get_full_name() if rec and rec.marked_by else None,
            'updated_by': rec.updated_by.get_full_name() if rec and rec.updated_by else None,
        })

    return sheet


def get_attendance_history_queryset(school, filters: Optional[Dict[str, Any]] = None):
    """
    Returns an optimized queryset for attendance history with dynamic filters.
    """
    qs = AttendanceRecord.objects.filter(school=school).select_related(
        'student', 'grade_level', 'section', 'academic_year', 'marked_by', 'updated_by'
    )

    if not filters:
        return qs

    if filters.get('academic_year_id'):
        qs = qs.filter(academic_year_id=filters['academic_year_id'])
    if filters.get('grade_level_id'):
        qs = qs.filter(grade_level_id=filters['grade_level_id'])
    if filters.get('section_id'):
        qs = qs.filter(section_id=filters['section_id'])
    if filters.get('student_id'):
        qs = qs.filter(student_id=filters['student_id'])
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    if filters.get('start_date'):
        qs = qs.filter(attendance_date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(attendance_date__lte=filters['end_date'])
    if filters.get('search'):
        term = filters['search'].strip()
        qs = qs.filter(
            Q(student__first_name__icontains=term) |
            Q(student__last_name__icontains=term) |
            Q(student__admission_number__icontains=term) |
            Q(student__roll_number__icontains=term) |
            Q(remarks__icontains=term)
        )

    return qs


def get_student_attendance_summary(
    school,
    student: Student,
    academic_year: Optional[AcademicYear] = None
) -> Dict[str, Any]:
    """
    Aggregates attendance metrics for an individual student.
    """
    qs = AttendanceRecord.objects.filter(school=school, student=student)
    if academic_year:
        qs = qs.filter(academic_year=academic_year)

    agg = qs.aggregate(
        total_records=Count('id'),
        present_count=Count(Case(When(status=AttendanceRecord.STATUS_PRESENT, then=1), output_field=IntegerField())),
        absent_count=Count(Case(When(status=AttendanceRecord.STATUS_ABSENT, then=1), output_field=IntegerField())),
        late_count=Count(Case(When(status=AttendanceRecord.STATUS_LATE, then=1), output_field=IntegerField())),
        half_day_count=Count(Case(When(status=AttendanceRecord.STATUS_HALF_DAY, then=1), output_field=IntegerField())),
        excused_count=Count(Case(When(status=AttendanceRecord.STATUS_EXCUSED, then=1), output_field=IntegerField())),
    )

    total_records = agg['total_records'] or 0
    present_count = agg['present_count'] or 0
    absent_count = agg['absent_count'] or 0
    late_count = agg['late_count'] or 0
    half_day_count = agg['half_day_count'] or 0
    excused_count = agg['excused_count'] or 0

    effective_present = present_count + late_count + (0.5 * half_day_count)
    percentage = round((effective_present / total_records * 100.0), 2) if total_records > 0 else 0.0

    recent_records = qs.select_related('grade_level', 'section', 'academic_year').order_by('-attendance_date')[:30]

    return {
        'student': student,
        'academic_year': academic_year,
        'total_records': total_records,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'half_day_count': half_day_count,
        'excused_count': excused_count,
        'effective_present': effective_present,
        'percentage': percentage,
        'recent_records': recent_records,
    }


def get_monthly_attendance_summary(
    school,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    section: Section,
    year: int,
    month: int
) -> List[Dict[str, Any]]:
    """
    Aggregates monthly attendance by student for a given class, section, year, and month.
    """
    records = AttendanceRecord.objects.filter(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        attendance_date__year=year,
        attendance_date__month=month
    ).values('student').annotate(
        total_days=Count('id'),
        present_days=Count(Case(When(status=AttendanceRecord.STATUS_PRESENT, then=1), output_field=IntegerField())),
        absent_days=Count(Case(When(status=AttendanceRecord.STATUS_ABSENT, then=1), output_field=IntegerField())),
        late_days=Count(Case(When(status=AttendanceRecord.STATUS_LATE, then=1), output_field=IntegerField())),
        half_days=Count(Case(When(status=AttendanceRecord.STATUS_HALF_DAY, then=1), output_field=IntegerField())),
        excused_days=Count(Case(When(status=AttendanceRecord.STATUS_EXCUSED, then=1), output_field=IntegerField())),
    )

    rec_by_student = {r['student']: r for r in records}

    # Fetch all students in that class and section
    sheet = get_daily_attendance_sheet(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        target_date=datetime.date(year, month, 1)
    )

    summary_rows = []
    for item in sheet:
        st_id = item['student_id']
        r = rec_by_student.get(st_id, {})
        tot = r.get('total_days', 0)
        p = r.get('present_days', 0)
        a = r.get('absent_days', 0)
        l = r.get('late_days', 0)
        hd = r.get('half_days', 0)
        ex = r.get('excused_days', 0)
        eff = p + l + (0.5 * hd)
        pct = round((eff / tot * 100.0), 1) if tot > 0 else 0.0

        summary_rows.append({
            'student_id': st_id,
            'student_name': item['student_name'],
            'roll_number': item['roll_number'],
            'total_days': tot,
            'present_days': p,
            'absent_days': a,
            'late_days': l,
            'half_days': hd,
            'excused_days': ex,
            'percentage': pct,
        })

    return summary_rows


def get_low_attendance_students(
    school,
    academic_year: Optional[AcademicYear] = None,
    threshold: float = 75.0
) -> List[Dict[str, Any]]:
    """
    Identifies students whose attendance percentage in the academic year falls below the specified threshold.
    """
    qs = AttendanceRecord.objects.filter(school=school)
    if academic_year:
        qs = qs.filter(academic_year=academic_year)

    student_stats = qs.values('student').annotate(
        total_days=Count('id'),
        present_days=Count(Case(When(status=AttendanceRecord.STATUS_PRESENT, then=1), output_field=IntegerField())),
        late_days=Count(Case(When(status=AttendanceRecord.STATUS_LATE, then=1), output_field=IntegerField())),
        half_days=Count(Case(When(status=AttendanceRecord.STATUS_HALF_DAY, then=1), output_field=IntegerField())),
        absent_days=Count(Case(When(status=AttendanceRecord.STATUS_ABSENT, then=1), output_field=IntegerField())),
    ).filter(total_days__gt=0)

    low_list = []
    # Pre-fetch students to avoid N+1
    student_ids = [s['student'] for s in student_stats]
    students_map = {s.id: s for s in Student.objects.filter(id__in=student_ids).select_related('grade_level', 'section')}

    for stat in student_stats:
        tot = stat['total_days']
        eff = stat['present_days'] + stat['late_days'] + (0.5 * stat['half_days'])
        pct = round((eff / tot * 100.0), 2)
        if pct < threshold:
            st = students_map.get(stat['student'])
            if st:
                low_list.append({
                    'student': st,
                    'total_days': tot,
                    'present_days': stat['present_days'],
                    'absent_days': stat['absent_days'],
                    'percentage': pct,
                    'grade_level': st.grade_level.name if st.grade_level else '-',
                    'section': st.section.name if st.section else '-',
                })

    low_list.sort(key=lambda x: x['percentage'])
    return low_list


def get_pending_attendance_sections(
    school,
    academic_year: Optional[AcademicYear],
    target_date: datetime.date,
    teacher_user=None
) -> List[Dict[str, Any]]:
    """
    Returns the list of sections and indicates whether attendance has been marked for target_date.
    Optionally scoped to a teacher's assigned sections.
    """
    sections_qs = Section.objects.filter(school=school, is_active=True).select_related('grade_level', 'class_teacher')
    if academic_year:
        sections_qs = sections_qs.filter(Q(academic_year=academic_year) | Q(academic_year__isnull=True))

    # If teacher_user is provided and is a teacher, scope to assigned sections
    if teacher_user and not teacher_user.is_superuser:
        from django_school_management.attendance.services.attendance_service import can_user_mark_section
        scoped = []
        for sec in sections_qs:
            if can_user_mark_section(teacher_user, school, sec):
                scoped.append(sec)
        sections_qs = scoped

    # Get distinct sections that have at least 1 attendance record on target_date
    marked_records = AttendanceRecord.objects.filter(
        school=school,
        attendance_date=target_date
    ).values('section').annotate(
        marked_count=Count('id')
    )
    marked_map = {r['section']: r['marked_count'] for r in marked_records}

    result = []
    for sec in sections_qs:
        count = marked_map.get(sec.id, 0)
        result.append({
            'section': sec,
            'grade_level': sec.grade_level,
            'is_marked': count > 0,
            'records_count': count,
            'class_teacher': sec.class_teacher.name if sec.class_teacher else 'Unassigned'
        })

    # Sort pending first, then by class order
    result.sort(key=lambda x: (x['is_marked'], x['grade_level'].display_order, x['section'].name))
    return result
