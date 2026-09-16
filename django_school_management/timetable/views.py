"""
PrimeSoul Timetable - Modern UI Views
Handles dashboard, setup, weekly grid, class schedule, teacher schedule, rooms, generation, clone, and export.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, Subject
from django_school_management.teachers.models import Teacher
from django_school_management.students.models import Student

from .models import WorkingDay, TimeSlot, Classroom, TimetableEntry
from .forms import (
    WorkingDayForm, TimeSlotForm, ClassroomForm,
    TimetableEntryForm, TimetableCloneForm, TimetableGenerateForm
)
from .services import timetable_service, generator_service
from .selectors import timetable_selectors


def _resolve_school(request):
    """Safely extracts tenant School from request context or user attributes."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated:
        user_school = getattr(request.user, 'school', None)
        if user_school:
            return user_school
    return School.objects.filter(is_active=True).first()


def _check_timetable_management_perm(user):
    """Verifies administrative write privileges for Timetable."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_has_role(
        user,
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.VICE_PRINCIPAL,
        Role.ACADEMIC_COORDINATOR
    )


# =============================================================================
# 1. DASHBOARD & ENTRY POINT
# =============================================================================

@login_required
def dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "School context required.")
        return redirect('index_view')

    user = request.user
    # Accountants have no timetable access
    if user_has_role(user, Role.ACCOUNTANT) and not user.is_superuser:
        raise PermissionDenied("Accountants do not have access to academic scheduling.")

    # Redirect Students/Parents to their direct view
    if user_has_role(user, Role.STUDENT, Role.PARENT) and not user.is_superuser:
        return redirect('timetable:my_timetable')

    academic_year = timetable_selectors.get_active_academic_year(school)
    metrics = timetable_selectors.get_timetable_dashboard_metrics(school, academic_year)
    sections = Section.objects.filter(school=school, is_active=True).select_related('grade_level')
    can_manage = _check_timetable_management_perm(user)

    context = {
        'school': school,
        'academic_year': academic_year,
        'metrics': metrics,
        'sections': sections,
        'can_manage': can_manage,
    }
    return render(request, 'timetable/dashboard.html', context)


# =============================================================================
# 2. SETUP (WORKING DAYS, PERIODS, ROOMS)
# =============================================================================

@login_required
def setup_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied("You do not have permission to configure timetable settings.")

    academic_year = timetable_selectors.get_active_academic_year(school)
    if not academic_year:
        messages.warning(request, "Please create an active Academic Year before configuring timetable settings.")
        return redirect('timetable:dashboard')

    # Ensure 7 standard weekday records exist for this academic year if none created yet
    existing_days = WorkingDay.objects.filter(school=school, academic_year=academic_year).count()
    if existing_days == 0:
        weekdays = [
            (0, 'Monday', True, 0),
            (1, 'Tuesday', True, 1),
            (2, 'Wednesday', True, 2),
            (3, 'Thursday', True, 3),
            (4, 'Friday', True, 4),
            (5, 'Saturday', True, 5),
            (6, 'Sunday', False, 6),
        ]
        for w, name, is_work, order in weekdays:
            WorkingDay.objects.create(
                school=school,
                academic_year=academic_year,
                weekday=w,
                day_name=name,
                is_working=is_work,
                display_order=order
            )

    working_days = WorkingDay.objects.filter(school=school, academic_year=academic_year).order_by('display_order', 'weekday')
    time_slots = TimeSlot.objects.filter(school=school, academic_year=academic_year).order_by('display_order', 'start_time')
    classrooms = Classroom.objects.filter(school=school).order_by('room_number')

    slot_form = TimeSlotForm()
    room_form = ClassroomForm()
    clone_form = TimetableCloneForm(school=school)

    context = {
        'school': school,
        'academic_year': academic_year,
        'working_days': working_days,
        'time_slots': time_slots,
        'classrooms': classrooms,
        'slot_form': slot_form,
        'room_form': room_form,
        'clone_form': clone_form,
    }
    return render(request, 'timetable/setup.html', context)


@login_required
@require_POST
def working_day_toggle_view(request, pk):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    day = get_object_or_404(WorkingDay, pk=pk, school=school)
    day.is_working = not day.is_working
    day.save(update_fields=['is_working'])
    status_str = "Working" if day.is_working else "Off / Non-Working"
    messages.success(request, f"{day.day_name} is now set as {status_str}.")
    return redirect('timetable:setup')


@login_required
@require_POST
def time_slot_create_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    academic_year = timetable_selectors.get_active_academic_year(school)
    form = TimeSlotForm(request.POST)
    if form.is_valid():
        slot = form.save(commit=False)
        slot.school = school
        slot.academic_year = academic_year
        slot.save()
        messages.success(request, f"Period / Time slot '{slot.name}' added successfully.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving time slot: {err_msg}")
    return redirect('timetable:setup')


@login_required
@require_POST
def time_slot_delete_view(request, pk):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    slot = get_object_or_404(TimeSlot, pk=pk, school=school)
    name = slot.name
    slot.delete()
    messages.success(request, f"Time slot '{name}' removed.")
    return redirect('timetable:setup')


@login_required
@require_POST
def classroom_create_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    form = ClassroomForm(request.POST)
    if form.is_valid():
        room = form.save(commit=False)
        room.school = school
        room.save()
        messages.success(request, f"Classroom / Lab '{room.name}' added successfully.")
    else:
        err_msg = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Error saving room: {err_msg}")
    return redirect('timetable:setup')


@login_required
@require_POST
def classroom_delete_view(request, pk):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    room = get_object_or_404(Classroom, pk=pk, school=school)
    name = room.name
    room.delete()
    messages.success(request, f"Room '{name}' deleted.")
    return redirect('timetable:setup')


# =============================================================================
# 3. WEEKLY GRID & SECTION / TEACHER TIMETABLES
# =============================================================================

@login_required
def weekly_view(request):
    school = _resolve_school(request)
    user = request.user
    if user_has_role(user, Role.ACCOUNTANT) and not user.is_superuser:
        raise PermissionDenied()

    academic_year = timetable_selectors.get_active_academic_year(school)
    sections = Section.objects.filter(school=school, is_active=True).select_related('grade_level')
    teachers = Teacher.objects.filter(school=school)

    selected_section_id = request.GET.get('section')
    selected_teacher_id = request.GET.get('teacher')

    section = None
    teacher = None
    matrix = None

    if selected_section_id:
        section = get_object_or_404(Section, pk=selected_section_id, school=school)
        matrix = timetable_selectors.get_class_timetable_matrix(school, section, academic_year)
    elif selected_teacher_id:
        teacher = get_object_or_404(Teacher, pk=selected_teacher_id, school=school)
        matrix = timetable_selectors.get_teacher_timetable_matrix(school, teacher, academic_year)
    elif sections.exists():
        section = sections.first()
        matrix = timetable_selectors.get_class_timetable_matrix(school, section, academic_year)

    can_manage = _check_timetable_management_perm(user)
    entry_form = TimetableEntryForm(school=school, academic_year=academic_year) if can_manage else None

    context = {
        'school': school,
        'academic_year': academic_year,
        'sections': sections,
        'teachers': teachers,
        'selected_section': section,
        'selected_teacher': teacher,
        'matrix': matrix,
        'can_manage': can_manage,
        'entry_form': entry_form,
    }
    return render(request, 'timetable/weekly.html', context)


@login_required
def class_timetable_view(request, section_id=None):
    school = _resolve_school(request)
    user = request.user
    if user_has_role(user, Role.ACCOUNTANT) and not user.is_superuser:
        raise PermissionDenied()

    academic_year = timetable_selectors.get_active_academic_year(school)
    sections = Section.objects.filter(school=school, is_active=True).select_related('grade_level')

    if section_id:
        section = get_object_or_404(Section, pk=section_id, school=school)
    else:
        section = sections.first()
        if not section:
            messages.warning(request, "No class sections available.")
            return redirect('timetable:dashboard')

    matrix = timetable_selectors.get_class_timetable_matrix(school, section, academic_year)
    can_manage = _check_timetable_management_perm(user)
    entry_form = TimetableEntryForm(school=school, academic_year=academic_year, initial={'section': section}) if can_manage else None

    context = {
        'school': school,
        'academic_year': academic_year,
        'section': section,
        'sections': sections,
        'matrix': matrix,
        'can_manage': can_manage,
        'entry_form': entry_form,
    }
    return render(request, 'timetable/class_timetable.html', context)


@login_required
def teacher_timetable_view(request, teacher_id=None):
    school = _resolve_school(request)
    user = request.user
    if user_has_role(user, Role.ACCOUNTANT) and not user.is_superuser:
        raise PermissionDenied()

    academic_year = timetable_selectors.get_active_academic_year(school)
    teachers = Teacher.objects.filter(school=school)

    teacher = None
    if teacher_id:
        teacher = get_object_or_404(Teacher, pk=teacher_id, school=school)
    elif user_has_role(user, Role.TEACHER):
        teacher = Teacher.objects.filter(school=school, email=user.email).first()

    if not teacher and teachers.exists():
        teacher = teachers.first()

    if not teacher:
        messages.warning(request, "No faculty members found.")
        return redirect('timetable:dashboard')

    matrix = timetable_selectors.get_teacher_timetable_matrix(school, teacher, academic_year)
    can_manage = _check_timetable_management_perm(user)

    context = {
        'school': school,
        'academic_year': academic_year,
        'teacher': teacher,
        'teachers': teachers,
        'matrix': matrix,
        'can_manage': can_manage,
    }
    return render(request, 'timetable/teacher_timetable.html', context)


@login_required
def rooms_view(request, room_id=None):
    school = _resolve_school(request)
    academic_year = timetable_selectors.get_active_academic_year(school)
    classrooms = Classroom.objects.filter(school=school, is_active=True).order_by('room_number')

    room = None
    if room_id:
        room = get_object_or_404(Classroom, pk=room_id, school=school)
    elif classrooms.exists():
        room = classrooms.first()

    matrix = timetable_selectors.get_room_timetable_matrix(school, room, academic_year) if room else None
    can_manage = _check_timetable_management_perm(request.user)

    context = {
        'school': school,
        'academic_year': academic_year,
        'classrooms': classrooms,
        'room': room,
        'matrix': matrix,
        'can_manage': can_manage,
    }
    return render(request, 'timetable/rooms.html', context)


# =============================================================================
# 4. ENTRY CREATION, MUTATION & DELETION (POST-ONLY)
# =============================================================================

@login_required
@require_POST
def entry_create_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied("You do not have permission to modify timetables.")

    academic_year = timetable_selectors.get_active_academic_year(school)
    section_id = request.POST.get('section')
    working_day_id = request.POST.get('working_day')
    time_slot_id = request.POST.get('time_slot')
    subject_id = request.POST.get('subject')
    teacher_id = request.POST.get('teacher')
    room_id = request.POST.get('room')
    entry_type = request.POST.get('entry_type', TimetableEntry.TYPE_CLASS)
    notes = request.POST.get('notes', '')

    section = get_object_or_404(Section, pk=section_id, school=school)
    working_day = get_object_or_404(WorkingDay, pk=working_day_id, school=school)
    time_slot = get_object_or_404(TimeSlot, pk=time_slot_id, school=school)
    subject = get_object_or_404(Subject, pk=subject_id, school=school) if subject_id else None
    teacher = get_object_or_404(Teacher, pk=teacher_id, school=school) if teacher_id else None
    room = get_object_or_404(Classroom, pk=room_id, school=school) if room_id else None

    try:
        timetable_service.create_timetable_entry(
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
            actor=request.user,
            strict_assignment=True
        )
        messages.success(request, f"Scheduled {subject.name if subject else entry_type} for {section} on {working_day.day_name} ({time_slot.name}).")
    except ValidationError as e:
        messages.error(request, f"Schedule Collision: {e.message if hasattr(e, 'message') else str(e)}")

    redirect_url = request.POST.get('next') or reverse('timetable:class_timetable', kwargs={'section_id': section.id})
    return redirect(redirect_url)


@login_required
@require_POST
def entry_delete_view(request, pk):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    entry = get_object_or_404(TimetableEntry, pk=pk, school=school)
    section_id = entry.section_id
    timetable_service.delete_timetable_entry(entry, actor=request.user, hard_delete=True)
    messages.success(request, "Timetable period entry removed.")

    redirect_url = request.POST.get('next') or reverse('timetable:class_timetable', kwargs={'section_id': section_id})
    return redirect(redirect_url)


# =============================================================================
# 5. GENERATION, CLONING & CLEARING
# =============================================================================

@login_required
def generate_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied("You do not have permission to access automated timetable generation.")

    academic_year = timetable_selectors.get_active_academic_year(school)
    sections = Section.objects.filter(school=school, is_active=True).select_related('grade_level')

    if request.method == 'POST':
        form = TimetableGenerateForm(request.POST, school=school)
        if form.is_valid():
            target_ay = form.cleaned_data['academic_year']
            target_sections = form.cleaned_data['sections']
            sec_ids = [s.id for s in target_sections] if target_sections else None

            result = generator_service.generate_automated_timetable(
                school=school,
                academic_year=target_ay,
                section_ids=sec_ids,
                actor=request.user
            )

            if result['success']:
                messages.success(
                    request,
                    f"Automated Schedule Generation Complete! Successfully placed {result['placed_count']} period entries."
                )
                return render(request, 'timetable/generate.html', {
                    'school': school,
                    'academic_year': target_ay,
                    'form': form,
                    'result': result,
                    'generation_completed': True
                })
            else:
                messages.error(request, result.get('error', "Generation failed."))
    else:
        form = TimetableGenerateForm(school=school, initial={'academic_year': academic_year})

    context = {
        'school': school,
        'academic_year': academic_year,
        'sections': sections,
        'form': form,
        'generation_completed': False
    }
    return render(request, 'timetable/generate.html', context)


@login_required
@require_POST
def clone_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    form = TimetableCloneForm(request.POST, school=school)
    if form.is_valid():
        try:
            stats = timetable_service.clone_timetable(
                school=school,
                source_academic_year=form.cleaned_data['source_academic_year'],
                target_academic_year=form.cleaned_data['target_academic_year'],
                actor=request.user,
                clone_working_days=form.cleaned_data['clone_working_days'],
                clone_time_slots=form.cleaned_data['clone_time_slots'],
                clone_entries=form.cleaned_data['clone_entries']
            )
            messages.success(
                request,
                f"Cloned successfully: {stats['working_days_created']} days, {stats['time_slots_created']} slots, "
                f"{stats['entries_created']} periods copied ({stats['skipped_entries']} skipped due to conflicts)."
            )
        except ValidationError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Invalid form submission for timetable cloning.")
    return redirect('timetable:setup')


@login_required
@require_POST
def clear_view(request):
    school = _resolve_school(request)
    if not _check_timetable_management_perm(request.user):
        raise PermissionDenied()

    academic_year = timetable_selectors.get_active_academic_year(school)
    section_id = request.POST.get('section_id')
    section = get_object_or_404(Section, pk=section_id, school=school) if section_id else None

    count = timetable_service.clear_timetable(
        school=school,
        academic_year=academic_year,
        section=section,
        actor=request.user
    )
    scope = f"for {section}" if section else "for entire school"
    messages.success(request, f"Cleared {count} scheduled periods {scope}.")
    return redirect('timetable:dashboard')


@login_required
def export_csv_view(request):
    school = _resolve_school(request)
    academic_year = timetable_selectors.get_active_academic_year(school)
    sec_id = request.GET.get('section')
    teacher_id = request.GET.get('teacher')

    sec = Section.objects.filter(pk=sec_id, school=school).first() if sec_id else None
    tchr = Teacher.objects.filter(pk=teacher_id, school=school).first() if teacher_id else None

    csv_data = timetable_service.export_timetable_csv(school, academic_year, section=sec, teacher=tchr)
    response = HttpResponse(csv_data, content_type='text/csv')
    filename = f"timetable_{school.school_code or 'school'}_{academic_year.name.replace('/', '-')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# =============================================================================
# 6. MY TIMETABLE (STUDENT / PARENT / TEACHER PERSONAL PORTAL)
# =============================================================================

@login_required
def my_timetable_view(request):
    school = _resolve_school(request)
    user = request.user
    academic_year = timetable_selectors.get_active_academic_year(school)

    # 1. Student Persona
    if user_has_role(user, Role.STUDENT):
        student = Student.objects.filter(school=school, user=user).first()
        if not student or not student.section:
            messages.warning(request, "Student enrollment or class section not assigned.")
            return redirect('index_view')
        matrix = timetable_selectors.get_class_timetable_matrix(school, student.section, academic_year)
        return render(request, 'timetable/class_timetable.html', {
            'school': school,
            'academic_year': academic_year,
            'section': student.section,
            'matrix': matrix,
            'is_portal_view': True,
            'can_manage': False
        })

    # 2. Parent Persona
    if user_has_role(user, Role.PARENT):
        parent_profile = getattr(user, 'parent_profile', None)
        relation = parent_profile.student_relationships.first() if parent_profile else None
        student = relation.student if relation else None
        if not student or not student.section:
            messages.warning(request, "Child profile or section not found.")
            return redirect('index_view')
        matrix = timetable_selectors.get_class_timetable_matrix(school, student.section, academic_year)
        return render(request, 'timetable/class_timetable.html', {
            'school': school,
            'academic_year': academic_year,
            'section': student.section,
            'matrix': matrix,
            'is_portal_view': True,
            'can_manage': False
        })

    # 3. Teacher Persona
    if user_has_role(user, Role.TEACHER):
        teacher = Teacher.objects.filter(school=school, email=user.email).first()
        if not teacher:
            messages.warning(request, "Faculty profile not associated with this user.")
            return redirect('index_view')
        return redirect('timetable:teacher_timetable', teacher_id=teacher.id)

    # Fallback to general weekly
    return redirect('timetable:weekly')
