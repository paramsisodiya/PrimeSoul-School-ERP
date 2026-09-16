import uuid
from typing import Optional, Dict, Any
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from django_school_management.utils.india_localization import (
    is_valid_indian_mobile, clean_indian_mobile
)

User = get_user_model()


def generate_application_number(school: School, session: AdmissionSession) -> str:
    """
    Generates a concurrency-safe unique application number for an admission session.
    Format: {prefix}-{count + 1:05d} e.g. APP-2026-00001
    """
    prefix = session.application_number_prefix or "APP-2026"
    count = AdmissionApplication.objects.filter(
        school=school,
        admission_session=session
    ).count()

    seq = count + 1
    candidate = f"{prefix}-{seq:05d}"
    while AdmissionApplication.objects.filter(school=school, admission_session=session, application_number=candidate).exists():
        seq += 1
        candidate = f"{prefix}-{seq:05d}"

    return candidate


def generate_admission_number(school: School, session: Optional[AdmissionSession] = None) -> str:
    """
    Generates a unique school admission number.
    Format: {prefix}-{seq:05d} e.g. ADM-2026-00001
    """
    prefix = session.admission_number_prefix if session and session.admission_number_prefix else "ADM-2026"
    count = Student.objects.filter(school=school).count()
    seq = count + 1
    candidate = f"{prefix}-{seq:05d}"
    while Student.objects.filter(school=school, admission_number=candidate).exists():
        seq += 1
        candidate = f"{prefix}-{seq:05d}"

    return candidate


def create_admission_enquiry(
    school: School,
    admission_session: AdmissionSession,
    student_name: str,
    parent_name: str,
    mobile: str,
    interested_grade: Optional[GradeLevel] = None,
    email: str = "",
    source: str = AdmissionEnquiry.SOURCE_WALK_IN,
    notes: str = "",
    assigned_to=None
) -> AdmissionEnquiry:
    """
    Creates and records a prospective student enquiry lead.
    Validates Indian mobile format.
    """
    if not is_valid_indian_mobile(mobile):
        raise ValidationError({"mobile": "Please provide a valid 10-digit Indian mobile number."})

    cleaned_mobile = clean_indian_mobile(mobile)

    # Generate unique enquiry number
    year_str = str(timezone.now().year)
    count = AdmissionEnquiry.objects.filter(school=school).count()
    enquiry_number = f"ENQ-{year_str}-{count + 1:05d}"

    enquiry = AdmissionEnquiry.objects.create(
        school=school,
        admission_session=admission_session,
        enquiry_number=enquiry_number,
        student_name=student_name.strip(),
        parent_name=parent_name.strip(),
        mobile=cleaned_mobile,
        email=email.strip().lower(),
        interested_grade=interested_grade,
        source=source,
        notes=notes,
        status=AdmissionEnquiry.STATUS_NEW,
        assigned_to=assigned_to
    )
    return enquiry


@transaction.atomic
def create_admission_application(
    school: School,
    admission_session: AdmissionSession,
    first_name: str,
    date_of_birth,
    gender: str,
    requested_grade: GradeLevel,
    middle_name: str = "",
    last_name: str = "",
    blood_group: str = "",
    nationality: str = "Indian",
    category: str = "General",
    aadhaar_number: str = "",
    requested_stream=None,
    previous_school: str = "",
    previous_school_tc_number: str = "",
    previous_grade: str = "",
    previous_percentage=None,
    father_name: str = "",
    father_mobile: str = "",
    father_email: str = "",
    father_occupation: str = "",
    father_aadhaar: str = "",
    mother_name: str = "",
    mother_mobile: str = "",
    mother_email: str = "",
    mother_occupation: str = "",
    mother_aadhaar: str = "",
    guardian_name: str = "",
    guardian_mobile: str = "",
    guardian_relation: str = "",
    current_address: str = "",
    permanent_address: str = "",
    emergency_contact_name: str = "",
    emergency_contact_number: str = "",
    enquiry: Optional[AdmissionEnquiry] = None,
    application_fee_status: str = AdmissionApplication.FEE_NOT_REQUIRED,
    status: str = AdmissionApplication.STATUS_SUBMITTED
) -> AdmissionApplication:
    """
    Submits a new admission application for evaluation.
    """
    # Validate primary contact mobile
    primary_mobile = father_mobile or mother_mobile or guardian_mobile
    if primary_mobile and not is_valid_indian_mobile(primary_mobile):
        raise ValidationError("Please provide a valid 10-digit Indian mobile number for primary guardian.")

    app_num = generate_application_number(school, admission_session)

    application = AdmissionApplication.objects.create(
        school=school,
        admission_session=admission_session,
        enquiry=enquiry,
        application_number=app_num,
        first_name=first_name.strip(),
        middle_name=middle_name.strip(),
        last_name=last_name.strip(),
        date_of_birth=date_of_birth,
        gender=gender,
        blood_group=blood_group,
        nationality=nationality,
        category=category,
        aadhaar_number=aadhaar_number.strip(),
        requested_grade=requested_grade,
        requested_stream=requested_stream,
        previous_school=previous_school.strip(),
        previous_school_tc_number=previous_school_tc_number.strip(),
        previous_grade=previous_grade.strip(),
        previous_percentage=previous_percentage,
        father_name=father_name.strip(),
        father_mobile=clean_indian_mobile(father_mobile) if father_mobile else "",
        father_email=father_email.strip().lower(),
        father_occupation=father_occupation.strip(),
        father_aadhaar=father_aadhaar.strip(),
        mother_name=mother_name.strip(),
        mother_mobile=clean_indian_mobile(mother_mobile) if mother_mobile else "",
        mother_email=mother_email.strip().lower(),
        mother_occupation=mother_occupation.strip(),
        mother_aadhaar=mother_aadhaar.strip(),
        guardian_name=guardian_name.strip(),
        guardian_mobile=clean_indian_mobile(guardian_mobile) if guardian_mobile else "",
        guardian_relation=guardian_relation.strip(),
        current_address=current_address.strip(),
        permanent_address=permanent_address.strip(),
        emergency_contact_name=emergency_contact_name.strip(),
        emergency_contact_number=clean_indian_mobile(emergency_contact_number) if emergency_contact_number else "",
        application_fee_status=application_fee_status,
        status=status,
        submitted_at=timezone.now() if status != AdmissionApplication.STATUS_DRAFT else None
    )

    if enquiry and enquiry.status != AdmissionEnquiry.STATUS_CONVERTED:
        enquiry.status = AdmissionEnquiry.STATUS_CONVERTED
        enquiry.save(update_fields=['status'])

    return application


VALID_TRANSITIONS = {
    AdmissionApplication.STATUS_DRAFT: [
        AdmissionApplication.STATUS_SUBMITTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_SUBMITTED: [
        AdmissionApplication.STATUS_UNDER_REVIEW,
        AdmissionApplication.STATUS_SHORTLISTED,
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_APPROVED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_UNDER_REVIEW: [
        AdmissionApplication.STATUS_SHORTLISTED,
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_APPROVED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_SHORTLISTED: [
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_APPROVED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_INTERVIEW: [
        AdmissionApplication.STATUS_APPROVED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_APPROVED: [
        AdmissionApplication.STATUS_ADMITTED,
        AdmissionApplication.STATUS_WITHDRAWN,
        AdmissionApplication.STATUS_REJECTED,
    ],
    AdmissionApplication.STATUS_WAITLISTED: [
        AdmissionApplication.STATUS_SHORTLISTED,
        AdmissionApplication.STATUS_APPROVED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    ],
    AdmissionApplication.STATUS_REJECTED: [
        AdmissionApplication.STATUS_UNDER_REVIEW,  # Allow reconsideration upon appeal
    ],
    AdmissionApplication.STATUS_ADMITTED: [],  # Final terminal state
    AdmissionApplication.STATUS_WITHDRAWN: [],
}


def transition_application_status(
    application: AdmissionApplication,
    new_status: str,
    user=None,
    remarks: str = "",
    rejection_reason: str = ""
) -> AdmissionApplication:
    """
    Transitions the application state with validation preventing invalid workflows.
    """
    if application.status == new_status:
        return application

    allowed = VALID_TRANSITIONS.get(application.status, [])
    if new_status not in allowed and not (user and user.is_superuser):
        raise ValidationError(
            f"Invalid transition from {application.get_status_display()} to {new_status}."
        )

    application.status = new_status
    application.reviewed_by = user
    application.reviewed_at = timezone.now()

    if remarks:
        application.remarks = f"{application.remarks}\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {remarks}".strip()
    if rejection_reason:
        application.rejection_reason = rejection_reason

    application.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'remarks', 'rejection_reason'])
    return application


def verify_admission_document(
    document: AdmissionDocument,
    is_verified: bool,
    user=None,
    rejection_reason: str = ""
) -> AdmissionDocument:
    """
    Marks an uploaded admission document as VERIFIED or REJECTED.
    """
    document.status = AdmissionDocument.STATUS_VERIFIED if is_verified else AdmissionDocument.STATUS_REJECTED
    document.verified_at = timezone.now()
    document.verified_by = user
    if not is_verified and rejection_reason:
        document.rejection_reason = rejection_reason

    document.save(update_fields=['status', 'verified_at', 'verified_by', 'rejection_reason'])
    return document


def schedule_admission_interview(
    application: AdmissionApplication,
    scheduled_at,
    location: str = "Campus Admissions Office",
    interviewer=None,
    user=None
) -> AdmissionInterview:
    """
    Schedules an in-person or online interaction / interview for the applicant.
    """
    interview = AdmissionInterview.objects.create(
        school=application.school,
        application=application,
        scheduled_at=scheduled_at,
        location=location,
        interviewer=interviewer,
        status=AdmissionInterview.STATUS_SCHEDULED
    )
    if application.status in (AdmissionApplication.STATUS_SUBMITTED, AdmissionApplication.STATUS_UNDER_REVIEW, AdmissionApplication.STATUS_SHORTLISTED):
        transition_application_status(
            application=application,
            new_status=AdmissionApplication.STATUS_INTERVIEW,
            user=user,
            remarks=f"Interview scheduled for {scheduled_at} at {location}."
        )
    return interview


def record_assessment(
    application: AdmissionApplication,
    subject: str,
    score,
    max_score=100.00,
    user=None,
    remarks: str = ""
) -> AdmissionAssessment:
    """
    Records written test or aptitude scores for an applicant.
    """
    assessment = AdmissionAssessment.objects.create(
        school=application.school,
        application=application,
        subject=subject.strip(),
        max_score=max_score,
        score=score,
        remarks=remarks,
        assessed_by=user
    )
    return assessment


@transaction.atomic
def approve_and_admit_student(
    application: AdmissionApplication,
    section: Optional[Section] = None,
    roll_number: Optional[str] = None,
    user=None
) -> Student:
    """
    Converts an approved admission application into an active enrolled Student record.
    Transactionally creates/links ParentProfile, StudentGuardianRelationship, and StudentEnrollment.
    Enforces seat quota capacity.
    """
    if application.status == AdmissionApplication.STATUS_ADMITTED or application.admitted_student:
        raise ValidationError("This applicant is already admitted.")

    school = application.school
    session = application.admission_session
    grade_level = application.requested_grade

    # 1. Capacity & Seat Availability Verification
    class_config = AdmissionClassConfig.objects.filter(
        school=school,
        admission_session=session,
        grade_level=grade_level,
        active=True
    ).first()

    if class_config:
        already_admitted = AdmissionApplication.objects.filter(
            school=school,
            admission_session=session,
            requested_grade=grade_level,
            status=AdmissionApplication.STATUS_ADMITTED
        ).count()

        if already_admitted >= class_config.total_seats:
            raise ValidationError(
                f"Cannot admit student: Seat quota for {grade_level.name} is full "
                f"({already_admitted}/{class_config.total_seats} seats filled)."
            )

    # 2. Concurrency-Safe Unique Admission Number Generation
    admission_number = generate_admission_number(school, session)

    # 3. Create Student Entity
    primary_guardian_phone = (
        application.father_mobile or
        application.mother_mobile or
        application.guardian_mobile or
        application.emergency_contact_number
    )

    assigned_roll_number = roll_number
    if section and not assigned_roll_number:
        existing_count = Student.objects.filter(
            school=school,
            academic_year=session.academic_year,
            grade_level=grade_level,
            section=section
        ).count()
        assigned_roll_number = str(existing_count + 1).zfill(2)
    elif not section:
        assigned_roll_number = assigned_roll_number or None

    student = Student.objects.create(
        school=school,
        first_name=application.first_name,
        middle_name=application.middle_name,
        last_name=application.last_name,
        date_of_birth=application.date_of_birth,
        gender=application.gender,
        blood_group=application.blood_group,
        nationality=application.nationality,
        category=application.category,
        aadhaar_number=application.aadhaar_number,
        admission_number=admission_number,
        roll_number=assigned_roll_number,
        admission_date=timezone.now().date(),
        academic_year=session.academic_year,
        grade_level=grade_level,
        section=section,
        stream=application.requested_stream,
        current_address=application.current_address,
        permanent_address=application.permanent_address,
        emergency_contact_number=application.emergency_contact_number,
        previous_school=application.previous_school,
        previous_school_tc_number=application.previous_school_tc_number,
        guardian_mobile=primary_guardian_phone,
        admitted_by=user,
        is_active=True
    )

    # 4. Create / Link Parent Profile & Guardian Relationships
    # A. Father
    if application.father_name:
        father_mobile = application.father_mobile or primary_guardian_phone
        father_profile = None
        if father_mobile:
            father_profile = ParentProfile.objects.filter(
                school=school,
                mobile_number=father_mobile
            ).first()

        if not father_profile:
            father_profile = ParentProfile.objects.create(
                school=school,
                first_name=application.father_name,
                mobile_number=father_mobile or "0000000000",
                email=application.father_email,
                occupation=application.father_occupation,
                aadhaar_number=application.father_aadhaar,
                relationship_type='Father',
                address=application.current_address
            )

        StudentGuardianRelationship.objects.get_or_create(
            student=student,
            guardian=father_profile,
            defaults={
                'relationship_type': 'Father',
                'is_primary_contact': True,
                'can_pickup': True
            }
        )

    # B. Mother
    if application.mother_name:
        mother_mobile = application.mother_mobile
        mother_profile = None
        if mother_mobile:
            mother_profile = ParentProfile.objects.filter(
                school=school,
                mobile_number=mother_mobile
            ).first()

        if not mother_profile:
            mother_profile = ParentProfile.objects.create(
                school=school,
                first_name=application.mother_name,
                mobile_number=mother_mobile or "0000000000",
                email=application.mother_email,
                occupation=application.mother_occupation,
                aadhaar_number=application.mother_aadhaar,
                relationship_type='Mother',
                address=application.current_address
            )

        StudentGuardianRelationship.objects.get_or_create(
            student=student,
            guardian=mother_profile,
            defaults={
                'relationship_type': 'Mother',
                'is_primary_contact': not bool(application.father_name),
                'can_pickup': True
            }
        )

    # C. Other Guardian
    if application.guardian_name and not application.father_name and not application.mother_name:
        guard_mobile = application.guardian_mobile or primary_guardian_phone
        guard_profile = None
        if guard_mobile:
            guard_profile = ParentProfile.objects.filter(
                school=school,
                mobile_number=guard_mobile
            ).first()

        if not guard_profile:
            guard_profile = ParentProfile.objects.create(
                school=school,
                first_name=application.guardian_name,
                mobile_number=guard_mobile or "0000000000",
                relationship_type='Guardian',
                address=application.current_address
            )

        StudentGuardianRelationship.objects.get_or_create(
            student=student,
            guardian=guard_profile,
            defaults={
                'relationship_type': application.guardian_relation or 'Guardian',
                'is_primary_contact': True,
                'can_pickup': True
            }
        )

    # 5. Create StudentEnrollment
    StudentEnrollment.objects.create(
        school=school,
        student=student,
        academic_year=session.academic_year,
        grade_level=grade_level,
        section=section,
        roll_number=roll_number or "",
        status=StudentEnrollment.STATUS_ACTIVE,
        enrollment_date=timezone.now().date(),
        created_by=user
    )

    # 6. Update Application Status to ADMITTED
    application.status = AdmissionApplication.STATUS_ADMITTED
    application.admitted_student = student
    application.admitted_at = timezone.now()
    application.save(update_fields=['status', 'admitted_student', 'admitted_at'])

    return student
