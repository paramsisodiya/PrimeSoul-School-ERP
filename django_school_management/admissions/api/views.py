from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from .serializers import (
    AdmissionSessionSerializer, AdmissionClassConfigSerializer,
    AdmissionEnquirySerializer, AdmissionApplicationSerializer,
    AdmissionDocumentSerializer, AdmissionInterviewSerializer,
    AdmissionAssessmentSerializer, PublicAdmissionApplySerializer,
    PublicAdmissionStatusSerializer, AdmissionConvertSerializer
)
from django_school_management.admissions.services.admission_service import (
    create_admission_enquiry, create_admission_application,
    transition_application_status, verify_admission_document,
    approve_and_admit_student
)
from django_school_management.admissions.selectors.admissions_selectors import (
    get_admissions_dashboard_metrics, get_active_admission_session
)
from django_school_management.academics.models import Section


def get_request_school(request):
    """Safely resolves school tenant from request."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    from django_school_management.tenants.models import School
    return School.objects.first()


class AdmissionSessionViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionSession.objects.filter(school=school).order_by('-created')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school)


class AdmissionClassConfigViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionClassConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionClassConfig.objects.filter(school=school).select_related('grade_level', 'admission_session')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school)


class AdmissionEnquiryViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionEnquirySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionEnquiry.objects.filter(school=school).select_related('interested_grade', 'admission_session')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        enquiry = create_admission_enquiry(
            school=school,
            admission_session=serializer.validated_data['admission_session'],
            student_name=serializer.validated_data['student_name'],
            parent_name=serializer.validated_data['parent_name'],
            mobile=serializer.validated_data['mobile'],
            interested_grade=serializer.validated_data.get('interested_grade'),
            email=serializer.validated_data.get('email', ''),
            source=serializer.validated_data.get('source', AdmissionEnquiry.SOURCE_WALK_IN),
            notes=serializer.validated_data.get('notes', ''),
            assigned_to=self.request.user
        )
        serializer.instance = enquiry


class AdmissionApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionApplication.objects.filter(school=school).select_related(
            'admission_session', 'requested_grade', 'requested_stream',
            'reviewed_by', 'admitted_student'
        ).prefetch_related('documents', 'interviews', 'assessments').order_by('-created')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        data = serializer.validated_data
        app = create_admission_application(
            school=school,
            admission_session=data['admission_session'],
            first_name=data['first_name'],
            date_of_birth=data['date_of_birth'],
            gender=data['gender'],
            requested_grade=data['requested_grade'],
            middle_name=data.get('middle_name', ''),
            last_name=data.get('last_name', ''),
            blood_group=data.get('blood_group', ''),
            nationality=data.get('nationality', 'Indian'),
            category=data.get('category', 'General'),
            aadhaar_number=data.get('aadhaar_number', ''),
            requested_stream=data.get('requested_stream'),
            previous_school=data.get('previous_school', ''),
            previous_school_tc_number=data.get('previous_school_tc_number', ''),
            previous_grade=data.get('previous_grade', ''),
            previous_percentage=data.get('previous_percentage'),
            father_name=data.get('father_name', ''),
            father_mobile=data.get('father_mobile', ''),
            father_email=data.get('father_email', ''),
            father_occupation=data.get('father_occupation', ''),
            father_aadhaar=data.get('father_aadhaar', ''),
            mother_name=data.get('mother_name', ''),
            mother_mobile=data.get('mother_mobile', ''),
            mother_email=data.get('mother_email', ''),
            mother_occupation=data.get('mother_occupation', ''),
            mother_aadhaar=data.get('mother_aadhaar', ''),
            guardian_name=data.get('guardian_name', ''),
            guardian_mobile=data.get('guardian_mobile', ''),
            guardian_relation=data.get('guardian_relation', ''),
            current_address=data.get('current_address', ''),
            permanent_address=data.get('permanent_address', ''),
            emergency_contact_name=data.get('emergency_contact_name', ''),
            emergency_contact_number=data.get('emergency_contact_number', ''),
            enquiry=data.get('enquiry'),
            application_fee_status=data.get('application_fee_status', AdmissionApplication.FEE_NOT_REQUIRED),
            status=data.get('status', AdmissionApplication.STATUS_SUBMITTED)
        )
        serializer.instance = app

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        app = self.get_object()
        new_status = request.data.get('status')
        remarks = request.data.get('remarks', '')
        rejection_reason = request.data.get('rejection_reason', '')

        try:
            transition_application_status(
                application=app,
                new_status=new_status,
                user=request.user,
                remarks=remarks,
                rejection_reason=rejection_reason
            )
            return Response(AdmissionApplicationSerializer(app).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        app = self.get_object()
        serializer = AdmissionConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section = None
        sec_id = serializer.validated_data.get('section_id')
        if sec_id:
            section = Section.objects.filter(school=app.school, pk=sec_id).first()

        roll_number = serializer.validated_data.get('roll_number')

        try:
            student = approve_and_admit_student(
                application=app,
                section=section,
                roll_number=roll_number,
                user=request.user
            )
            return Response({
                'status': 'admitted',
                'student_id': student.id,
                'admission_number': student.admission_number,
                'student_name': student.get_full_name()
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AdmissionDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionDocument.objects.filter(school=school)

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        doc = self.get_object()
        is_verified = request.data.get('verified', True)
        rejection_reason = request.data.get('rejection_reason', '')
        verify_admission_document(doc, is_verified=bool(is_verified), user=request.user, rejection_reason=rejection_reason)
        return Response(AdmissionDocumentSerializer(doc).data)


class AdmissionInterviewViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionInterviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionInterview.objects.filter(school=school).select_related('interviewer')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school)


class AdmissionAssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AdmissionAssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AdmissionAssessment.objects.filter(school=school)

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school, assessed_by=self.request.user)


class AdmissionDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = get_request_school(request)
        session_id = request.GET.get('session')
        metrics = get_admissions_dashboard_metrics(school, int(session_id) if session_id else None)
        # Remove non-serializable session model object from response dict
        metrics_data = dict(metrics)
        metrics_data['session_id'] = metrics['session'].id if metrics['session'] else None
        metrics_data['session_name'] = metrics['session'].name if metrics['session'] else None
        del metrics_data['session']
        return Response(metrics_data)


class PublicAdmissionApplyAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        school = get_request_school(request)
        active_session = get_active_admission_session(school)
        if not active_session or not active_session.is_open:
            return Response(
                {'error': 'Admissions are currently closed for this institution.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PublicAdmissionApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        app = create_admission_application(
            school=school,
            admission_session=active_session,
            first_name=data['first_name'],
            date_of_birth=data['date_of_birth'],
            gender=data['gender'],
            requested_grade=data['requested_grade'],
            middle_name=data.get('middle_name', ''),
            last_name=data.get('last_name', ''),
            blood_group=data.get('blood_group', ''),
            category=data.get('category', 'General'),
            aadhaar_number=data.get('aadhaar_number', ''),
            previous_school=data.get('previous_school', ''),
            previous_grade=data.get('previous_grade', ''),
            previous_percentage=data.get('previous_percentage'),
            father_name=data.get('father_name', ''),
            father_mobile=data.get('father_mobile', ''),
            father_email=data.get('father_email', ''),
            father_occupation=data.get('father_occupation', ''),
            mother_name=data.get('mother_name', ''),
            mother_mobile=data.get('mother_mobile', ''),
            mother_email=data.get('mother_email', ''),
            current_address=data.get('current_address', ''),
            emergency_contact_number=data.get('emergency_contact_number', ''),
            status=AdmissionApplication.STATUS_SUBMITTED
        )

        return Response({
            'status': 'submitted',
            'application_number': app.application_number,
            'student_name': app.get_full_name(),
            'message': 'Application successfully submitted.'
        }, status=status.HTTP_201_CREATED)


class PublicAdmissionStatusAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        school = get_request_school(request)
        app_num = request.GET.get('app_num', '').strip()
        dob = request.GET.get('dob', '').strip()

        if not app_num or not dob:
            return Response(
                {'error': 'Please provide both application_number and date_of_birth.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        app = AdmissionApplication.objects.filter(
            school=school,
            application_number__iexact=app_num,
            date_of_birth=dob
        ).select_related('requested_grade', 'admission_session').first()

        if not app:
            return Response({'error': 'Application not found with provided credentials.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicAdmissionStatusSerializer(app)
        return Response(serializer.data)
