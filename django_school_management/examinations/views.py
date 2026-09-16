import csv
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.students.models import Student
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, Subject, StudentEnrollment
from django_school_management.examinations.models import (
    ExaminationSession, Exam, ExamSubject, GradeScale, GradeScaleBand,
    StudentMark, StudentExamResult, MarksCorrectionLog, AssessmentType
)
from django_school_management.examinations.forms import (
    ExaminationSessionForm, ExamForm, ExamSubjectForm, GradeScaleForm,
    GradeScaleBandForm, MarksCorrectionForm
)
from django_school_management.examinations.services import (
    exam_service, marks_service, result_calculation_service, report_card_service
)
from django_school_management.examinations.selectors import exam_selectors


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
    from django_school_management.tenants.models import School
    return School.objects.first()


# =============================================================================
# 1. DASHBOARD
# =============================================================================

@login_required
def dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "School context required.")
        return redirect('index_view')

    metrics = exam_selectors.get_exam_dashboard_metrics(school)
    context = {
        'school': school,
        'metrics': metrics,
    }
    return render(request, 'examinations/dashboard.html', context)


# =============================================================================
# 2. SESSIONS MANAGEMENT
# =============================================================================

@login_required
def session_list(request):
    school = _resolve_school(request)
    sessions = ExaminationSession.objects.filter(school=school).select_related('academic_year')
    context = {'school': school, 'sessions': sessions}
    return render(request, 'examinations/sessions.html', context)


@login_required
def session_create(request):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Only Administrators and Principals can create examination sessions.")

    if request.method == 'POST':
        form = ExaminationSessionForm(request.POST, school=school)
        if form.is_valid():
            session = form.save(commit=False)
            session.school = school
            session.created_by = request.user
            session.save()
            messages.success(request, f"Examination Session '{session.name}' created successfully.")
            return redirect('examinations:session_list')
    else:
        form = ExaminationSessionForm(school=school)

    return render(request, 'examinations/session_form.html', {'form': form, 'school': school, 'action': 'Create'})


@login_required
def session_edit(request, pk):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Unauthorized to edit examination sessions.")

    session = get_object_or_404(ExaminationSession, pk=pk, school=school)
    if request.method == 'POST':
        form = ExaminationSessionForm(request.POST, instance=session, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Session '{session.name}' updated successfully.")
            return redirect('examinations:session_list')
    else:
        form = ExaminationSessionForm(instance=session, school=school)

    return render(request, 'examinations/session_form.html', {'form': form, 'school': school, 'action': 'Edit', 'session': session})


# =============================================================================
# 3. EXAMS MANAGEMENT
# =============================================================================

@login_required
def exam_list(request):
    school = _resolve_school(request)
    exams = Exam.objects.filter(school=school).select_related(
        'session', 'academic_year', 'grade_level', 'section', 'assessment_type', 'grade_scale'
    )
    context = {'school': school, 'exams': exams}
    return render(request, 'examinations/exams.html', context)


@login_required
def exam_create(request):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Unauthorized to create examinations.")

    if request.method == 'POST':
        form = ExamForm(request.POST, school=school)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.school = school
            exam.created_by = request.user
            exam.updated_by = request.user
            exam.save()
            messages.success(request, f"Examination '{exam.name}' created. Configure subjects below.")
            return redirect('examinations:exam_subjects', exam_id=exam.id)
    else:
        form = ExamForm(school=school)

    return render(request, 'examinations/exam_form.html', {'form': form, 'school': school, 'action': 'Create'})


@login_required
def exam_edit(request, pk):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Unauthorized to edit examinations.")

    exam = get_object_or_404(Exam, pk=pk, school=school)
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam, school=school)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.updated_by = request.user
            exam.save()
            messages.success(request, f"Examination '{exam.name}' updated successfully.")
            return redirect('examinations:exam_list')
    else:
        form = ExamForm(instance=exam, school=school)

    return render(request, 'examinations/exam_form.html', {'form': form, 'school': school, 'action': 'Edit', 'exam': exam})


# =============================================================================
# 4. EXAM SUBJECTS CONFIGURATION
# =============================================================================

@login_required
def exam_subjects_config(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)

    if request.method == 'POST':
        if not exam_service.can_user_manage_exam(request.user, school):
            raise PermissionDenied("Unauthorized to configure exam subjects.")
        form = ExamSubjectForm(request.POST, school=school)
        if form.is_valid():
            es = form.save(commit=False)
            es.school = school
            es.exam = exam
            es.save()
            messages.success(request, f"Subject '{es.subject.name}' added to {exam.name}.")
            return redirect('examinations:exam_subjects', exam_id=exam.id)
    else:
        form = ExamSubjectForm(school=school)

    configured_subjects = exam.subjects.select_related('subject').order_by('sequence_order', 'subject__name')
    context = {
        'school': school,
        'exam': exam,
        'form': form,
        'configured_subjects': configured_subjects,
    }
    return render(request, 'examinations/subjects.html', context)


@login_required
@require_POST
def exam_subject_delete(request, exam_id, subject_id):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Unauthorized.")
    es = get_object_or_404(ExamSubject, id=subject_id, exam_id=exam_id, school=school)
    subj_name = es.subject.name
    es.delete()
    messages.info(request, f"Subject '{subj_name}' removed from exam.")
    return redirect('examinations:exam_subjects', exam_id=exam_id)


# =============================================================================
# 5. GRADE SCALES & BANDS
# =============================================================================

@login_required
def grade_scale_list(request):
    school = _resolve_school(request)
    scales = GradeScale.objects.filter(school=school).prefetch_related('bands')
    context = {'school': school, 'scales': scales}
    return render(request, 'examinations/grades.html', context)


@login_required
def grade_scale_create(request):
    school = _resolve_school(request)
    if not exam_service.can_user_manage_exam(request.user, school):
        raise PermissionDenied("Unauthorized to configure grading scales.")

    if request.method == 'POST':
        form = GradeScaleForm(request.POST)
        if form.is_valid():
            scale = form.save(commit=False)
            scale.school = school
            scale.created_by = request.user
            scale.save()
            messages.success(request, f"Grade Scale '{scale.name}' created. Add grade bands below.")
            return redirect('examinations:grade_scale_detail', pk=scale.id)
    else:
        form = GradeScaleForm()

    return render(request, 'examinations/grade_scale_form.html', {'form': form, 'school': school})


@login_required
def grade_scale_detail(request, pk):
    school = _resolve_school(request)
    scale = get_object_or_404(GradeScale, pk=pk, school=school)

    if request.method == 'POST':
        if not exam_service.can_user_manage_exam(request.user, school):
            raise PermissionDenied("Unauthorized.")
        form = GradeScaleBandForm(request.POST)
        if form.is_valid():
            band = form.save(commit=False)
            band.scale = scale
            band.save()
            messages.success(request, f"Grade Band '{band.name}' ({band.min_percentage}% - {band.max_percentage}%) added.")
            return redirect('examinations:grade_scale_detail', pk=scale.id)
    else:
        form = GradeScaleBandForm()

    bands = scale.bands.all().order_by('-min_percentage')
    return render(request, 'examinations/grade_scale_detail.html', {'scale': scale, 'bands': bands, 'form': form, 'school': school})


# =============================================================================
# 6. MARKS ENTRY (HIGH FREQUENCY WORKFLOW)
# =============================================================================

@login_required
def marks_entry_view(request):
    school = _resolve_school(request)
    exam_id = request.GET.get('exam') or request.POST.get('exam_id')
    subject_id = request.GET.get('subject') or request.POST.get('subject_id')
    section_id = request.GET.get('section') or request.POST.get('section_id')

    # Accessible exams
    exams_qs = Exam.objects.filter(school=school).select_related('grade_level', 'section', 'session')
    
    selected_exam = exams_qs.filter(id=exam_id).first() if exam_id else exams_qs.first()
    selected_es = None
    selected_section = None
    sheet_data = []

    if selected_exam:
        subjects_qs = selected_exam.subjects.filter(is_active=True).select_related('subject')
        selected_es = subjects_qs.filter(id=subject_id).first() if subject_id else subjects_qs.first()
        
        sections_qs = Section.objects.filter(grade_level=selected_exam.grade_level, school=school, is_active=True)
        if selected_exam.section:
            selected_section = selected_exam.section
        elif section_id:
            selected_section = sections_qs.filter(id=section_id).first()
        else:
            selected_section = sections_qs.first()

    # Process Form POST (Bulk Save)
    if request.method == 'POST' and selected_exam and selected_es:
        correction_reason = request.POST.get('correction_reason', '').strip()
        marks_payload = []

        # Parse student row inputs
        student_ids = request.POST.getlist('student_id')
        for sid in student_ids:
            st_status = request.POST.get(f'status_{sid}', StudentMark.STATUS_NOT_ENTERED)
            raw_val = request.POST.get(f'marks_{sid}', '').strip()
            rem = request.POST.get(f'remarks_{sid}', '').strip()
            marks_payload.append({
                'student_id': int(sid),
                'status': st_status,
                'marks_obtained': raw_val if raw_val else None,
                'remarks': rem,
            })

        try:
            saved = marks_service.save_bulk_marks(
                school=school,
                exam=selected_exam,
                exam_subject=selected_es,
                section=selected_section,
                marks_data=marks_payload,
                actor=request.user,
                correction_reason=correction_reason or None
            )
            messages.success(request, f"Saved marks for {len(saved)} students in {selected_es.subject.name} successfully.")
            return redirect(f"{reverse('examinations:marks_entry')}?exam={selected_exam.id}&subject={selected_es.id}&section={selected_section.id if selected_section else ''}")
        except (ValidationError, PermissionDenied) as e:
            messages.error(request, f"Error saving marks: {e}")

    if selected_exam and selected_es:
        sheet_data = exam_selectors.get_marks_entry_sheet(
            school=school,
            exam=selected_exam,
            exam_subject=selected_es,
            section=selected_section
        )

    context = {
        'school': school,
        'exams': exams_qs,
        'selected_exam': selected_exam,
        'selected_es': selected_es,
        'selected_section': selected_section,
        'sheet_data': sheet_data,
        'sections': Section.objects.filter(grade_level=selected_exam.grade_level, school=school, is_active=True) if selected_exam else [],
    }
    return render(request, 'examinations/marks_entry.html', context)


# =============================================================================
# 7. RESULTS MANAGEMENT & ACTIONS
# =============================================================================

@login_required
def results_list_view(request):
    school = _resolve_school(request)
    exam_id = request.GET.get('exam')
    section_id = request.GET.get('section')
    status_filter = request.GET.get('status')
    result_filter = request.GET.get('result_status')
    search = request.GET.get('search', '').strip()

    exams_qs = Exam.objects.filter(school=school).select_related('grade_level', 'section')
    selected_exam = exams_qs.filter(id=exam_id).first() if exam_id else exams_qs.first()

    results_qs = StudentExamResult.objects.filter(school=school)
    if selected_exam:
        results_qs = results_qs.filter(exam=selected_exam)

    # Scoping for students and parents
    if user_has_role(request.user, Role.STUDENT):
        results_qs = results_qs.filter(student__user=request.user, status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED])
    elif user_has_role(request.user, Role.PARENT):
        results_qs = results_qs.filter(
            student__guardian_relationships__guardian__user=request.user,
            status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]
        )
    elif user_has_role(request.user, Role.TEACHER) and not (request.user.is_superuser or user_has_role(request.user, Role.SCHOOL_ADMIN) or user_has_role(request.user, Role.PRINCIPAL)):
        # Teacher view
        teacher = exam_service.get_teacher_for_user(request.user, school)
        if teacher:
            assigned_sections = Section.objects.filter(class_teacher=teacher, school=school)
            results_qs = results_qs.filter(enrollment__section__in=assigned_sections)

    if section_id:
        results_qs = results_qs.filter(enrollment__section_id=section_id)
    if status_filter:
        results_qs = results_qs.filter(status=status_filter)
    if result_filter:
        results_qs = results_qs.filter(result_status=result_filter)
    if search:
        results_qs = results_qs.filter(
            student__first_name__icontains=search
        ) | results_qs.filter(student__admission_number__icontains=search)

    results_qs = results_qs.select_related('student', 'enrollment__section').order_by('class_rank', '-percentage')

    paginator = Paginator(results_qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    sections = Section.objects.filter(grade_level=selected_exam.grade_level, school=school) if selected_exam else []

    context = {
        'school': school,
        'exams': exams_qs,
        'selected_exam': selected_exam,
        'page_obj': page_obj,
        'total_count': paginator.count,
        'sections': sections,
        'selected_section_id': int(section_id) if section_id else None,
    }
    return render(request, 'examinations/results.html', context)


@login_required
@require_POST
def calculate_results_action(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)
    try:
        calculated = result_calculation_service.calculate_exam_results(
            school=school, exam=exam, actor=request.user
        )
        messages.success(request, f"Results calculated successfully for {len(calculated)} students in {exam.name}.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, f"Could not calculate results: {e}")
    return redirect(f"{reverse('examinations:results_list')}?exam={exam.id}")


@login_required
@require_POST
def finalize_results_action(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)
    try:
        count = result_calculation_service.finalize_exam_results(school=school, exam=exam, actor=request.user)
        messages.success(request, f"Finalized {count} student results for {exam.name}.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, f"Could not finalize results: {e}")
    return redirect(f"{reverse('examinations:results_list')}?exam={exam.id}")


@login_required
@require_POST
def publish_results_action(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)
    try:
        count = result_calculation_service.publish_exam_results(school=school, exam=exam, actor=request.user)
        messages.success(request, f"Published {count} results for {exam.name}. Results are now viewable by students & parents.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, f"Could not publish results: {e}")
    return redirect(f"{reverse('examinations:results_list')}?exam={exam.id}")


@login_required
@require_POST
def lock_results_action(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)
    try:
        count = result_calculation_service.lock_exam_results(school=school, exam=exam, actor=request.user)
        messages.warning(request, f"Locked {count} results for {exam.name}. Further changes require audit corrections.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, f"Could not lock results: {e}")
    return redirect(f"{reverse('examinations:results_list')}?exam={exam.id}")


# =============================================================================
# 8. CLASS SUMMARY & STUDENT PROFILE
# =============================================================================

@login_required
def class_result_summary_view(request, exam_id=None):
    school = _resolve_school(request)
    exams_qs = Exam.objects.filter(school=school).select_related('grade_level', 'section')
    selected_exam = exams_qs.filter(id=exam_id).first() if exam_id else exams_qs.first()

    if not selected_exam:
        messages.warning(request, "No examination records found.")
        return redirect('examinations:dashboard')

    section_id = request.GET.get('section')
    selected_section = Section.objects.filter(id=section_id, school=school).first() if section_id else None

    summary = exam_selectors.get_class_result_summary(school, selected_exam, selected_section)
    sections = Section.objects.filter(grade_level=selected_exam.grade_level, school=school)

    context = {
        'school': school,
        'exams': exams_qs,
        'selected_exam': selected_exam,
        'selected_section': selected_section,
        'sections': sections,
        'summary': summary,
    }
    return render(request, 'examinations/class_summary.html', context)


@login_required
def student_result_profile_view(request, student_id=None):
    school = _resolve_school(request)
    student = None

    if student_id:
        student = get_object_or_404(Student, id=student_id, school=school)
    else:
        if user_has_role(request.user, Role.STUDENT):
            student = Student.objects.filter(school=school, user=request.user).first()
        elif user_has_role(request.user, Role.PARENT):
            student = Student.objects.filter(school=school, guardian_relationships__guardian__user=request.user).first()
        else:
            first_st = Student.objects.filter(school=school, is_active=True).first()
            if first_st:
                return redirect('examinations:student_results', student_id=first_st.id)

    if not student:
        messages.warning(request, "Student profile not found.")
        return redirect('examinations:dashboard')

    # Security scoping
    if user_has_role(request.user, Role.STUDENT) and student.user != request.user:
        raise PermissionDenied("You can only access your own academic result profile.")
    if user_has_role(request.user, Role.PARENT):
        is_child = Student.objects.filter(
            id=student.id, school=school, guardian_relationships__guardian__user=request.user
        ).exists()
        if not is_child:
            raise PermissionDenied("You can only access your registered child's result profile.")

    results_qs = StudentExamResult.objects.filter(school=school, student=student)
    if user_has_role(request.user, Role.STUDENT) or user_has_role(request.user, Role.PARENT):
        results_qs = results_qs.filter(status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED])

    results = list(results_qs.select_related('exam', 'academic_year').order_by('-exam__start_date'))

    context = {
        'school': school,
        'student': student,
        'results': results,
    }
    return render(request, 'examinations/student_results.html', context)


# =============================================================================
# 9. REPORT CARD (HTML & REPORTLAB PDF)
# =============================================================================

@login_required
def report_card_view(request, pk):
    school = _resolve_school(request)
    result = get_object_or_404(
        StudentExamResult.objects.select_related('exam', 'student', 'enrollment__section', 'school'),
        pk=pk, school=school
    )

    # Scoping
    if user_has_role(request.user, Role.STUDENT):
        if result.student.user != request.user or result.status not in [StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]:
            raise PermissionDenied("Unauthorized to view this report card.")
    elif user_has_role(request.user, Role.PARENT):
        is_child = Student.objects.filter(
            id=result.student.id, school=school, guardian_relationships__guardian__user=request.user
        ).exists()
        if not is_child or result.status not in [StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]:
            raise PermissionDenied("Unauthorized to view this report card.")

    exam = result.exam
    exam_subjects = exam.subjects.filter(is_active=True).select_related('subject').order_by('sequence_order')
    marks_map = {m.exam_subject_id: m for m in StudentMark.objects.filter(exam=exam, student=result.student)}

    subject_rows = []
    for es in exam_subjects:
        m = marks_map.get(es.id)
        subject_rows.append({'subject': es.subject, 'exam_subject': es, 'mark': m})

    context = {
        'school': school,
        'result': result,
        'subject_rows': subject_rows,
        'verification_url': request.build_absolute_uri(reverse('examinations:public_verify_result', args=[result.verification_code])),
    }
    return render(request, 'examinations/report_card.html', context)


@login_required
def report_card_pdf_view(request, pk):
    school = _resolve_school(request)
    result = get_object_or_404(StudentExamResult, pk=pk, school=school)

    # Scoping
    if user_has_role(request.user, Role.STUDENT):
        if result.student.user != request.user or result.status not in [StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]:
            raise PermissionDenied("Unauthorized.")
    elif user_has_role(request.user, Role.PARENT):
        is_child = Student.objects.filter(
            id=result.student.id, school=school, guardian_relationships__guardian__user=request.user
        ).exists()
        if not is_child or result.status not in [StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]:
            raise PermissionDenied("Unauthorized.")

    base_url = request.build_absolute_uri('/')
    pdf_bytes = report_card_service.render_report_card_pdf_bytes(result, verification_base_url=base_url)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"ReportCard_{result.student.admission_number or result.student.id}_{result.exam.name.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# =============================================================================
# 10. PUBLIC TAMPER-EVIDENT VERIFICATION
# =============================================================================

def public_result_verification_view(request, verification_code):
    """
    Public, unauthenticated verification endpoint.
    Safely verifies official credential authenticity without exposing confidential student info (phone, address, fees, etc.).
    """
    result = StudentExamResult.objects.filter(
        verification_code=verification_code,
        status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]
    ).select_related('school', 'exam', 'student', 'enrollment__section').first()

    context = {
        'is_verified': bool(result is not None),
        'result': result,
        'verification_code': verification_code,
    }
    return render(request, 'examinations/verify.html', context)


# =============================================================================
# 11. MARKS CORRECTION VIEW
# =============================================================================

@login_required
def correct_student_mark_view(request, pk):
    school = _resolve_school(request)
    mark_record = get_object_or_404(StudentMark, pk=pk, school=school)

    if not exam_service.can_user_enter_marks(request.user, school, mark_record.exam, mark_record.exam_subject):
        raise PermissionDenied("Unauthorized to correct marks.")

    if request.method == 'POST':
        form = MarksCorrectionForm(request.POST)
        if form.is_valid():
            try:
                marks_service.correct_single_student_mark(
                    school=school,
                    mark_record=mark_record,
                    new_status=form.cleaned_data['new_status'],
                    new_marks=form.cleaned_data['new_marks'],
                    reason=form.cleaned_data['reason'],
                    actor=request.user
                )
                messages.success(request, f"Mark corrected with audit trail for {mark_record.student.name}.")
                return redirect('examinations:marks_entry')
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, str(e))
    else:
        form = MarksCorrectionForm(initial={
            'new_status': mark_record.status,
            'new_marks': mark_record.marks_obtained,
        })

    corrections = mark_record.corrections.select_related('corrected_by').order_by('-corrected_at')
    context = {
        'school': school,
        'mark_record': mark_record,
        'form': form,
        'corrections': corrections,
    }
    return render(request, 'examinations/mark_correct.html', context)


# =============================================================================
# 12. CSV EXPORTS
# =============================================================================

@login_required
def export_marks_csv(request, exam_id, subject_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)
    es = get_object_or_404(ExamSubject, id=subject_id, exam=exam)

    marks = StudentMark.objects.filter(exam=exam, exam_subject=es).select_related('student', 'enrollment__section')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Marks_{exam.name}_{es.subject.name}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Admission Number', 'Student Name', 'Section', 'Status', 'Marks Obtained', 'Max Marks', 'Grade', 'Passed', 'Remarks'])

    for m in marks:
        writer.writerow([
            getattr(m.student, 'roll_number', ''),
            getattr(m.student, 'admission_number', ''),
            m.student.name,
            m.enrollment.section.name if (m.enrollment and m.enrollment.section) else '',
            m.status,
            m.marks_obtained if m.marks_obtained is not None else '',
            es.max_marks,
            m.grade,
            'Yes' if m.is_passed else 'No',
            m.remarks
        ])

    return response


@login_required
def export_results_csv(request, exam_id):
    school = _resolve_school(request)
    exam = get_object_or_404(Exam, id=exam_id, school=school)

    results = StudentExamResult.objects.filter(exam=exam, school=school).select_related('student', 'enrollment__section')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Results_{exam.name}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Class Rank', 'Section Rank', 'Roll Number', 'Admission No', 'Student Name', 'Section', 'Total Marks', 'Max Marks', 'Percentage', 'Grade', 'Result Status', 'Attendance %', 'Verification Code'])

    for r in results:
        writer.writerow([
            r.class_rank or '',
            r.section_rank or '',
            getattr(r.student, 'roll_number', ''),
            getattr(r.student, 'admission_number', ''),
            r.student.name,
            r.enrollment.section.name if (r.enrollment and r.enrollment.section) else '',
            r.total_marks_obtained,
            r.total_max_marks,
            f"{r.percentage:.2f}%",
            r.overall_grade,
            r.get_result_status_display(),
            f"{r.attendance_percentage}%" if r.attendance_percentage is not None else '',
            r.verification_code
        ])

    return response
