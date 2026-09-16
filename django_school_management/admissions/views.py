from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.academics.models import GradeLevel, Section
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from django_school_management.admissions.forms import (
    AdmissionSessionForm, AdmissionClassConfigForm, AdmissionEnquiryForm,
    AdmissionApplicationForm, PublicAdmissionApplicationForm,
    AdmissionDocumentForm, AdmissionInterviewForm, AdmissionAssessmentForm,
    AdmissionReviewForm, AdmissionConvertForm
)
from django_school_management.admissions.selectors.admissions_selectors import (
    get_admissions_dashboard_metrics,
    get_class_seat_availability,
    get_applications_list,
    get_application_detail,
    get_active_admission_session
)
from django_school_management.admissions.services.admission_service import (
    create_admission_enquiry,
    create_admission_application,
    transition_application_status,
    verify_admission_document,
    schedule_admission_interview,
    record_assessment,
    approve_and_admit_student
)


def resolve_school(request) -> School:
    """Helper to resolve current tenant school."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    return School.objects.first()


# ---------------------------------------------------------------------------
# Admissions Staff Views
# ---------------------------------------------------------------------------

@login_required
def admissions_dashboard(request):
    """
    Admissions overview showing pipeline metrics, conversion rates, and seat occupancy.
    """
    school = resolve_school(request)
    session_id = request.GET.get('session')
    metrics = get_admissions_dashboard_metrics(school, int(session_id) if session_id else None)
    seat_breakdown = get_class_seat_availability(school, int(session_id) if session_id else None)
    recent_applications = get_applications_list(school, int(session_id) if session_id else None)[:6]
    sessions = AdmissionSession.objects.filter(school=school, active=True)

    context = {
        'school': school,
        'metrics': metrics,
        'seat_breakdown': seat_breakdown,
        'recent_applications': recent_applications,
        'sessions': sessions,
        'selected_session_id': session_id,
    }
    return render(request, 'admissions/dashboard.html', context)


@login_required
def session_list(request):
    """
    Manage admission intake sessions.
    """
    school = resolve_school(request)
    sessions = AdmissionSession.objects.filter(school=school).select_related('academic_year')

    if request.method == 'POST':
        form = AdmissionSessionForm(request.POST, school=school)
        if form.is_valid():
            sess = form.save(commit=False)
            sess.school = school
            sess.save()
            messages.success(request, f"Admission Session '{sess.name}' created.")
            return redirect('admissions:session_list')
    else:
        form = AdmissionSessionForm(school=school)

    context = {
        'school': school,
        'sessions': sessions,
        'form': form,
    }
    return render(request, 'admissions/sessions.html', context)


@login_required
def class_config_list(request):
    """
    Manage seat quotas and application fees per class.
    """
    school = resolve_school(request)
    configs = AdmissionClassConfig.objects.filter(school=school).select_related('admission_session', 'grade_level')

    if request.method == 'POST':
        form = AdmissionClassConfigForm(request.POST, school=school)
        if form.is_valid():
            cfg = form.save(commit=False)
            cfg.school = school
            cfg.save()
            messages.success(request, f"Seat capacity for {cfg.grade_level.name} configured.")
            return redirect('admissions:class_config_list')
    else:
        form = AdmissionClassConfigForm(school=school)

    context = {
        'school': school,
        'configs': configs,
        'form': form,
    }
    return render(request, 'admissions/classes.html', context)


@login_required
def enquiry_list(request):
    """
    Enquiry / leads management list with status filters.
    """
    school = resolve_school(request)
    qs = AdmissionEnquiry.objects.filter(school=school).select_related('admission_session', 'interested_grade', 'assigned_to')

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.method == 'POST':
        form = AdmissionEnquiryForm(request.POST, school=school)
        if form.is_valid():
            enq = form.save(commit=False)
            enq.school = school
            enq.save()
            messages.success(request, f"Enquiry #{enq.enquiry_number} for {enq.student_name} registered.")
            return redirect('admissions:enquiry_list')
    else:
        form = AdmissionEnquiryForm(school=school)

    context = {
        'school': school,
        'enquiries': qs,
        'form': form,
        'status_filter': status_filter,
    }
    return render(request, 'admissions/enquiries.html', context)


@login_required
def enquiry_detail(request, pk):
    """
    View and update single enquiry lead.
    """
    school = resolve_school(request)
    enquiry = get_object_or_404(AdmissionEnquiry, pk=pk, school=school)

    if request.method == 'POST':
        form = AdmissionEnquiryForm(request.POST, instance=enquiry, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Enquiry #{enquiry.enquiry_number} updated.")
            return redirect('admissions:enquiry_list')
    else:
        form = AdmissionEnquiryForm(instance=enquiry, school=school)

    context = {
        'school': school,
        'enquiry': enquiry,
        'form': form,
    }
    return render(request, 'admissions/enquiry_detail.html', context)


@login_required
def application_list(request):
    """
    Searchable & filterable applications list.
    """
    school = resolve_school(request)
    session_id = request.GET.get('session')
    status_filter = request.GET.get('status')
    grade_id = request.GET.get('grade')
    search_q = request.GET.get('q')

    applications = get_applications_list(
        school=school,
        session_id=int(session_id) if session_id else None,
        status=status_filter,
        grade_id=int(grade_id) if grade_id else None,
        search_query=search_q
    )

    sessions = AdmissionSession.objects.filter(school=school, active=True)
    grades = GradeLevel.objects.filter(school=school, is_active=True)

    context = {
        'school': school,
        'applications': applications,
        'sessions': sessions,
        'grades': grades,
        'selected_session': session_id,
        'selected_status': status_filter,
        'selected_grade': grade_id,
        'search_q': search_q,
    }
    return render(request, 'admissions/applications.html', context)


@login_required
def application_create(request):
    """
    Staff manual entry of a formal student admission application.
    """
    school = resolve_school(request)

    if request.method == 'POST':
        form = AdmissionApplicationForm(request.POST, school=school)
        if form.is_valid():
            app = form.save(commit=False)
            app.school = school
            app.save()
            messages.success(request, f"Application #{app.application_number} for {app.get_full_name()} submitted.")
            return redirect('admissions:application_detail', pk=app.pk)
    else:
        form = AdmissionApplicationForm(school=school)

    context = {
        'school': school,
        'form': form,
    }
    return render(request, 'admissions/application_form.html', context)


@login_required
def application_detail(request, pk):
    """
    Complete application view with document verification, interview history, assessment scores, and review actions.
    """
    school = resolve_school(request)
    application = get_application_detail(pk, school)
    if not application:
        messages.error(request, "Application not found.")
        return redirect('admissions:application_list')

    review_form = AdmissionReviewForm(initial={
        'status': application.status,
        'remarks': application.remarks,
        'rejection_reason': application.rejection_reason
    })
    doc_form = AdmissionDocumentForm()
    interview_form = AdmissionInterviewForm()
    assessment_form = AdmissionAssessmentForm()
    convert_form = AdmissionConvertForm(school=school, grade_level=application.requested_grade)

    context = {
        'school': school,
        'application': application,
        'review_form': review_form,
        'doc_form': doc_form,
        'interview_form': interview_form,
        'assessment_form': assessment_form,
        'convert_form': convert_form,
    }
    return render(request, 'admissions/application_detail.html', context)


@login_required
@require_POST
def application_review(request, pk):
    """
    Performs application status transition with validation and remarks audit.
    """
    school = resolve_school(request)
    application = get_object_or_404(AdmissionApplication, pk=pk, school=school)
    form = AdmissionReviewForm(request.POST)

    if form.is_valid():
        new_status = form.cleaned_data.get('status')
        remarks = form.cleaned_data.get('remarks')
        rejection_reason = form.cleaned_data.get('rejection_reason')

        try:
            transition_application_status(
                application=application,
                new_status=new_status,
                user=request.user,
                remarks=remarks,
                rejection_reason=rejection_reason
            )
            messages.success(request, f"Application #{application.application_number} updated to {application.get_status_display()}.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('admissions:application_detail', pk=application.pk)


@login_required
@require_POST
def application_convert(request, pk):
    """
    Approves and admits the applicant, transactionally creating the enrolled Student entity.
    """
    school = resolve_school(request)
    application = get_object_or_404(AdmissionApplication, pk=pk, school=school)
    form = AdmissionConvertForm(request.POST, school=school, grade_level=application.requested_grade)

    if form.is_valid():
        section = form.cleaned_data.get('section')
        roll_number = form.cleaned_data.get('roll_number')

        try:
            student = approve_and_admit_student(
                application=application,
                section=section,
                roll_number=roll_number,
                user=request.user
            )
            messages.success(
                request,
                f"Student '{student.get_full_name()}' successfully admitted! "
                f"Admission Number: {student.admission_number}."
            )
        except ValidationError as e:
            messages.error(request, f"Admission conversion failed: {e}")
    else:
        messages.error(request, "Invalid section or roll number provided.")

    return redirect('admissions:application_detail', pk=application.pk)


@login_required
@require_POST
def document_upload(request, application_id):
    """
    Uploads a supporting document to an application.
    """
    school = resolve_school(request)
    application = get_object_or_404(AdmissionApplication, pk=application_id, school=school)
    form = AdmissionDocumentForm(request.POST, request.FILES)

    if form.is_valid():
        doc = form.save(commit=False)
        doc.school = school
        doc.application = application
        doc.save()
        messages.success(request, f"Document '{doc.get_document_type_display()}' uploaded successfully.")
    else:
        messages.error(request, "Failed to upload document. Please check file format.")

    return redirect('admissions:application_detail', pk=application.pk)


@login_required
@require_POST
def document_verify(request, pk):
    """
    Verifies or rejects an uploaded admission document.
    """
    school = resolve_school(request)
    doc = get_object_or_404(AdmissionDocument, pk=pk, school=school)
    action_type = request.POST.get('action')  # 'verify' or 'reject'
    reason = request.POST.get('rejection_reason', '')

    is_verified = (action_type == 'verify')
    verify_admission_document(doc, is_verified=is_verified, user=request.user, rejection_reason=reason)

    messages.info(request, f"Document marked as {doc.get_status_display()}.")
    return redirect('admissions:application_detail', pk=doc.application.pk)


@login_required
@require_POST
def interview_schedule(request, application_id):
    """
    Schedules an interview for the application.
    """
    school = resolve_school(request)
    application = get_object_or_404(AdmissionApplication, pk=application_id, school=school)
    form = AdmissionInterviewForm(request.POST)

    if form.is_valid():
        interview = form.save(commit=False)
        interview.school = school
        interview.application = application
        interview.save()

        transition_application_status(
            application=application,
            new_status=AdmissionApplication.STATUS_INTERVIEW,
            user=request.user,
            remarks=f"Interview scheduled for {interview.scheduled_at}."
        )
        messages.success(request, f"Interview scheduled for {interview.scheduled_at}.")
    else:
        messages.error(request, "Failed to schedule interview.")

    return redirect('admissions:application_detail', pk=application.pk)


@login_required
@require_POST
def assessment_record_view(request, application_id):
    """
    Records an assessment score.
    """
    school = resolve_school(request)
    application = get_object_or_404(AdmissionApplication, pk=application_id, school=school)
    form = AdmissionAssessmentForm(request.POST)

    if form.is_valid():
        assessment = form.save(commit=False)
        assessment.school = school
        assessment.application = application
        assessment.assessed_by = request.user
        assessment.save()
        messages.success(request, f"Assessment for '{assessment.subject}' recorded ({assessment.score}/{assessment.max_score}).")
    else:
        messages.error(request, "Failed to record assessment score.")

    return redirect('admissions:application_detail', pk=application.pk)


@login_required
def reports_view(request):
    """
    Conversion reports, lead analytics, and class seat utilization.
    """
    school = resolve_school(request)
    session_id = request.GET.get('session')
    metrics = get_admissions_dashboard_metrics(school, int(session_id) if session_id else None)
    seat_breakdown = get_class_seat_availability(school, int(session_id) if session_id else None)
    sessions = AdmissionSession.objects.filter(school=school, active=True)

    context = {
        'school': school,
        'metrics': metrics,
        'seat_breakdown': seat_breakdown,
        'sessions': sessions,
        'selected_session_id': session_id,
    }
    return render(request, 'admissions/reports.html', context)


# ---------------------------------------------------------------------------
# Public-Safe Application Workflows
# ---------------------------------------------------------------------------

def public_apply(request):
    """
    Safe public-facing application form for parents.
    Does NOT leak internal staff IDs or database IDs.
    """
    school = resolve_school(request)
    active_session = get_active_admission_session(school)

    if not active_session or not active_session.is_open:
        return render(request, 'admissions/public/closed.html', {'school': school})

    if request.method == 'POST':
        form = PublicAdmissionApplicationForm(request.POST, school=school)
        if form.is_valid():
            app = form.save(commit=False)
            app.school = school
            app.admission_session = active_session
            app.status = AdmissionApplication.STATUS_SUBMITTED
            app.submitted_at = timezone.now()
            app.save()

            return render(request, 'admissions/public/success.html', {
                'school': school,
                'application': app,
            })
    else:
        form = PublicAdmissionApplicationForm(school=school)

    context = {
        'school': school,
        'session': active_session,
        'form': form,
    }
    return render(request, 'admissions/public/apply.html', context)


def public_status(request):
    """
    Public lookup of application status by application number and applicant Date of Birth.
    """
    school = resolve_school(request)
    app_record = None
    searched = False

    app_num = request.GET.get('app_num', '').strip()
    dob_str = request.GET.get('dob', '').strip()

    if app_num and dob_str:
        searched = True
        app_record = AdmissionApplication.objects.filter(
            school=school,
            application_number__iexact=app_num,
            date_of_birth=dob_str
        ).select_related('requested_grade', 'admission_session').first()

    context = {
        'school': school,
        'application': app_record,
        'searched': searched,
        'app_num': app_num,
        'dob_str': dob_str,
    }
    return render(request, 'admissions/public/status.html', context)
