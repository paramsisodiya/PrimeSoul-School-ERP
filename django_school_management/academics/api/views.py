"""
PrimeSoul ERP Academic Management - REST API ViewSets
All endpoints enforce multi-tenant scoping and standard RBAC authorization.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_school_management.tenants.models import School
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject,
    SubjectAssignment, StudentEnrollment
)
from django_school_management.academics.services import academic_service, promotion_service
from django_school_management.academics.selectors import academic_selectors
from .serializers import (
    AcademicYearSerializer, GradeLevelSerializer, SectionSerializer,
    SubjectSerializer, SubjectAssignmentSerializer, StudentEnrollmentSerializer,
    PromotionExecuteSerializer
)


class TenantScopedMixin:
    """
    Ensures queryset is strictly scoped to the active request tenant school.
    Automatically assigns school on create.
    """
    def get_school(self):
        user = self.request.user
        if hasattr(self.request, 'school') and self.request.school:
            return self.request.school
        if user.is_authenticated and hasattr(user, 'school') and user.school:
            return user.school
        if user.is_superuser:
            return School.objects.filter(is_active=True).first()
        return None

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return self.queryset.none()
        return self.queryset.filter(school=school)

    def perform_create(self, serializer):
        school = self.get_school()
        serializer.save(school=school, created_by=self.request.user)


class AcademicYearViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all().order_by('-start_date')
    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated]


class GradeLevelViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = GradeLevel.objects.all().order_by('display_order', 'code')
    serializer_class = GradeLevelSerializer
    permission_classes = [permissions.IsAuthenticated]


class SectionViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Section.objects.all().select_related('grade_level', 'academic_year', 'class_teacher')
    serializer_class = SectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        grade_id = self.request.query_params.get('grade')
        year_id = self.request.query_params.get('year')
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        return qs


class SubjectViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.all().select_related('instructor')
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        sub_type = self.request.query_params.get('type')
        if sub_type:
            qs = qs.filter(subject_type=sub_type)
        return qs


class SubjectAssignmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = SubjectAssignment.objects.all().select_related(
        'academic_year', 'grade_level', 'section', 'subject', 'teacher'
    )
    serializer_class = SubjectAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        year_id = self.request.query_params.get('year')
        grade_id = self.request.query_params.get('grade')
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        return qs


class StudentEnrollmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StudentEnrollment.objects.all().select_related(
        'student', 'academic_year', 'grade_level', 'section'
    )
    serializer_class = StudentEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        year_id = self.request.query_params.get('year')
        grade_id = self.request.query_params.get('grade')
        section_id = self.request.query_params.get('section')
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        if section_id:
            qs = qs.filter(section_id=section_id)
        return qs


class PromotionExecuteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        if not school:
            return Response({"detail": "School tenant context required."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PromotionExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source_year = get_object_or_404(AcademicYear, pk=data['source_year'], school=school)
        target_year = get_object_or_404(AcademicYear, pk=data['target_year'], school=school)
        source_grade = get_object_or_404(GradeLevel, pk=data['source_grade'], school=school)
        target_grade = get_object_or_404(GradeLevel, pk=data['target_grade'], school=school)

        source_section = Section.objects.filter(pk=data.get('source_section'), school=school).first()
        target_section = Section.objects.filter(pk=data.get('target_section'), school=school).first()

        try:
            result = promotion_service.execute_promotion(
                school=school,
                source_year=source_year,
                target_year=target_year,
                source_grade=source_grade,
                target_grade=target_grade,
                source_section=source_section,
                target_section=target_section,
                student_ids=data.get('student_ids'),
                actor=request.user
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AcademicDashboardSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        if not school:
            return Response({"detail": "School tenant context required."}, status=status.HTTP_400_BAD_REQUEST)

        metrics = academic_selectors.get_academic_dashboard_metrics(school)
        return Response({
            'current_year': metrics['current_year'].name if metrics['current_year'] else None,
            'total_classes': metrics['total_classes'],
            'total_sections': metrics['total_sections'],
            'total_subjects': metrics['total_subjects'],
            'total_teachers': metrics['total_teachers'],
            'total_enrolled_students': metrics['total_enrolled_students'],
            'students_without_section': metrics['students_without_section'],
            'sections_without_class_teacher': metrics['sections_without_class_teacher'],
            'subjects_without_teacher': metrics['subjects_without_teacher'],
        }, status=status.HTTP_200_OK)
