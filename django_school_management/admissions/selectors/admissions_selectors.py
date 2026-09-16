from typing import Optional, Dict, Any, List
from django.db.models import Count, Q, Sum
from django_school_management.tenants.models import School
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)


def get_active_admission_session(school: School) -> Optional[AdmissionSession]:
    """
    Finds the active open or most recent admission session for the school.
    """
    session = AdmissionSession.objects.filter(
        school=school,
        status=AdmissionSession.STATUS_OPEN,
        active=True
    ).first()
    if not session:
        session = AdmissionSession.objects.filter(school=school, active=True).order_by('-created').first()
    return session


def get_admissions_dashboard_metrics(school: School, session_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes comprehensive admission pipeline metrics using database aggregations.
    """
    if session_id:
        session = AdmissionSession.objects.filter(school=school, pk=session_id).first()
    else:
        session = get_active_admission_session(school)

    session_qs = AdmissionSession.objects.filter(school=school, active=True)
    enquiries_qs = AdmissionEnquiry.objects.filter(school=school)
    apps_qs = AdmissionApplication.objects.filter(school=school)
    configs_qs = AdmissionClassConfig.objects.filter(school=school, active=True)

    if session:
        enquiries_qs = enquiries_qs.filter(admission_session=session)
        apps_qs = apps_qs.filter(admission_session=session)
        configs_qs = configs_qs.filter(admission_session=session)

    # 1. Enquiry Aggregation
    enquiry_stats = enquiries_qs.aggregate(
        total=Count('id'),
        new=Count('id', filter=Q(status=AdmissionEnquiry.STATUS_NEW)),
        contacted=Count('id', filter=Q(status=AdmissionEnquiry.STATUS_CONTACTED)),
        converted=Count('id', filter=Q(status=AdmissionEnquiry.STATUS_CONVERTED)),
        lost=Count('id', filter=Q(status=AdmissionEnquiry.STATUS_LOST)),
    )

    # 2. Application Pipeline Aggregation
    app_stats = apps_qs.aggregate(
        total_apps=Count('id'),
        draft=Count('id', filter=Q(status=AdmissionApplication.STATUS_DRAFT)),
        submitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_SUBMITTED)),
        under_review=Count('id', filter=Q(status=AdmissionApplication.STATUS_UNDER_REVIEW)),
        shortlisted=Count('id', filter=Q(status=AdmissionApplication.STATUS_SHORTLISTED)),
        interview=Count('id', filter=Q(status=AdmissionApplication.STATUS_INTERVIEW)),
        approved=Count('id', filter=Q(status=AdmissionApplication.STATUS_APPROVED)),
        rejected=Count('id', filter=Q(status=AdmissionApplication.STATUS_REJECTED)),
        waitlisted=Count('id', filter=Q(status=AdmissionApplication.STATUS_WAITLISTED)),
        admitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_ADMITTED)),
    )

    # 3. Seat Quota Aggregation
    total_configured_seats = configs_qs.aggregate(seats=Sum('total_seats'))['seats'] or 0
    total_admitted = app_stats['admitted'] or 0
    seats_remaining = max(0, total_configured_seats - total_admitted)

    # 4. Conversion Rates
    total_enquiries = enquiry_stats['total'] or 0
    enquiry_conv_rate = (enquiry_stats['converted'] / total_enquiries * 100) if total_enquiries > 0 else 0.0

    total_applications = app_stats['total_apps'] or 0
    app_admit_rate = (total_admitted / total_applications * 100) if total_applications > 0 else 0.0

    return {
        "session": session,
        "total_sessions": session_qs.count(),
        # Enquiry Metrics
        "total_enquiries": total_enquiries,
        "new_enquiries": enquiry_stats['new'] or 0,
        "converted_enquiries": enquiry_stats['converted'] or 0,
        "enquiry_conversion_rate": round(enquiry_conv_rate, 1),
        # Application Metrics
        "total_applications": total_applications,
        "submitted_applications": app_stats['submitted'] or 0,
        "under_review_applications": app_stats['under_review'] or 0,
        "shortlisted_applications": app_stats['shortlisted'] or 0,
        "interview_applications": app_stats['interview'] or 0,
        "approved_applications": app_stats['approved'] or 0,
        "admitted_applications": total_admitted,
        "rejected_applications": app_stats['rejected'] or 0,
        "waitlisted_applications": app_stats['waitlisted'] or 0,
        "application_admission_rate": round(app_admit_rate, 1),
        # Capacity Metrics
        "total_configured_seats": total_configured_seats,
        "seats_remaining": seats_remaining,
        "seat_occupancy_rate": round((total_admitted / total_configured_seats * 100), 1) if total_configured_seats > 0 else 0.0,
    }


def get_class_seat_availability(
    school: School,
    session_id: Optional[int] = None,
    grade_level_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Returns seat availability, filled counts, and vacancy breakdown per class.
    """
    if session_id:
        session = AdmissionSession.objects.filter(school=school, pk=session_id).first()
    else:
        session = get_active_admission_session(school)

    if not session:
        return []

    configs = AdmissionClassConfig.objects.filter(
        school=school,
        admission_session=session,
        active=True
    ).select_related('grade_level')

    if grade_level_id:
        configs = configs.filter(grade_level_id=grade_level_id)

    results = []
    for cfg in configs:
        grade = cfg.grade_level
        apps_in_grade = AdmissionApplication.objects.filter(
            school=school,
            admission_session=session,
            requested_grade=grade
        )

        app_counts = apps_in_grade.aggregate(
            total_apps=Count('id'),
            approved=Count('id', filter=Q(status=AdmissionApplication.STATUS_APPROVED)),
            admitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_ADMITTED)),
            pending=Count('id', filter=Q(status__in=[
                AdmissionApplication.STATUS_SUBMITTED,
                AdmissionApplication.STATUS_UNDER_REVIEW,
                AdmissionApplication.STATUS_SHORTLISTED,
                AdmissionApplication.STATUS_INTERVIEW
            ]))
        )

        admitted_num = app_counts['admitted'] or 0
        total_seats = cfg.total_seats
        remaining = max(0, total_seats - admitted_num)
        occ_pct = round((admitted_num / total_seats * 100), 1) if total_seats > 0 else 0.0

        results.append({
            "config_id": cfg.id,
            "grade_level": grade,
            "grade_name": grade.name,
            "total_seats": total_seats,
            "reserved_seats": cfg.reserved_seats,
            "admitted_count": admitted_num,
            "approved_count": app_counts['approved'] or 0,
            "pending_count": app_counts['pending'] or 0,
            "total_applications": app_counts['total_apps'] or 0,
            "remaining_seats": remaining,
            "occupancy_percentage": occ_pct,
            "application_fee": cfg.application_fee,
        })

    return results


def get_applications_list(
    school: School,
    session_id: Optional[int] = None,
    status: Optional[str] = None,
    grade_id: Optional[int] = None,
    search_query: Optional[str] = None
):
    """
    Returns filtered and searched admission applications queryset.
    """
    qs = AdmissionApplication.objects.filter(school=school).select_related(
        'admission_session', 'requested_grade', 'requested_stream',
        'reviewed_by', 'admitted_student', 'enquiry'
    ).prefetch_related('documents', 'interviews', 'assessments')

    if session_id:
        qs = qs.filter(admission_session_id=session_id)
    if status:
        qs = qs.filter(status=status)
    if grade_id:
        qs = qs.filter(requested_grade_id=grade_id)
    if search_query:
        qs = qs.filter(
            Q(application_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(father_name__icontains=search_query) |
            Q(father_mobile__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(mother_mobile__icontains=search_query)
        )

    return qs.order_by('-created')


def get_application_detail(application_id: int, school: School) -> Optional[AdmissionApplication]:
    """
    Fetches full application details including all related sub-objects with tenant scoping.
    """
    return AdmissionApplication.objects.filter(
        pk=application_id,
        school=school
    ).select_related(
        'admission_session', 'requested_grade', 'requested_stream',
        'reviewed_by', 'admitted_student', 'enquiry'
    ).prefetch_related(
        'documents', 'interviews', 'assessments'
    ).first()
