from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.students.models import Student
from django_school_management.academics.models import Section
from django_school_management.examinations.models import (
    AssessmentType, GradeScale, ExaminationSession,
    Exam, ExamSubject, StudentMark, StudentExamResult
)
from django_school_management.examinations.services import (
    exam_service, marks_service, result_calculation_service
)
from django_school_management.examinations.selectors import exam_selectors
from .serializers import (
    AssessmentTypeSerializer, GradeScaleSerializer, ExaminationSessionSerializer,
    ExamSerializer, ExamSubjectSerializer, StudentMarkSerializer,
    BulkMarksEntrySerializer, StudentExamResultSerializer, MarksCorrectionSerializer
)


class TenantScopedMixin:
    """Ensures queryset is strictly filtered by the authenticated user's school tenant."""
    def get_school(self):
        if hasattr(self.request, 'tenant') and self.request.tenant:
            return self.request.tenant
        if hasattr(self.request, 'school') and self.request.school:
            return self.request.school
        user = self.request.user
        if user.is_authenticated:
            return getattr(user, 'school', None)
        return None

    def perform_create(self, serializer):
        school = self.get_school()
        serializer.save(school=school, created_by=self.request.user)


class ExaminationSessionViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = ExaminationSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return ExaminationSession.objects.none()
        return ExaminationSession.objects.filter(school=school)


class ExamViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return Exam.objects.none()
        return Exam.objects.filter(school=school)


class ExamSubjectViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = ExamSubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return ExamSubject.objects.none()
        return ExamSubject.objects.filter(school=school)


class GradeScaleViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = GradeScaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return GradeScale.objects.none()
        return GradeScale.objects.filter(school=school)


class StudentMarkViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentMarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return StudentMark.objects.none()
        qs = StudentMark.objects.filter(school=school)
        user = self.request.user

        if user_has_role(user, Role.STUDENT):
            return qs.filter(student__user=user)
        if user_has_role(user, Role.PARENT):
            return qs.filter(student__guardian_relationships__guardian__user=user)
        return qs


class StudentExamResultViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentExamResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.get_school()
        if not school:
            return StudentExamResult.objects.none()

        qs = StudentExamResult.objects.filter(school=school)
        user = self.request.user

        if user_has_role(user, Role.STUDENT):
            return qs.filter(student__user=user, status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED])
        if user_has_role(user, Role.PARENT):
            return qs.filter(
                student__guardian_relationships__guardian__user=user,
                status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED]
            )
        return qs


class BulkMarksAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        school = self.get_school()
        serializer = BulkMarksEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        exam = get_object_or_404(Exam, id=data['exam_id'], school=school)
        exam_subject = get_object_or_404(ExamSubject, id=data['exam_subject_id'], exam=exam)
        section = Section.objects.filter(id=data['section_id'], school=school).first() if data.get('section_id') else None

        try:
            saved = marks_service.save_bulk_marks(
                school=school,
                exam=exam,
                exam_subject=exam_subject,
                section=section,
                marks_data=data['marks'],
                actor=request.user,
                correction_reason=data.get('correction_reason')
            )
            return Response({
                'success': True,
                'message': f"Saved marks for {len(saved)} students.",
                'records_count': len(saved),
            }, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CalculateResultsAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        school = self.get_school()
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        try:
            calculated = result_calculation_service.calculate_exam_results(
                school=school, exam=exam, actor=request.user
            )
            return Response({
                'success': True,
                'message': f"Results calculated for {len(calculated)} students.",
                'evaluated_count': len(calculated)
            }, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FinalizeResultsAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        school = self.get_school()
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        try:
            count = result_calculation_service.finalize_exam_results(school=school, exam=exam, actor=request.user)
            return Response({'success': True, 'finalized_count': count}, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PublishResultsAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        school = self.get_school()
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        try:
            count = result_calculation_service.publish_exam_results(school=school, exam=exam, actor=request.user)
            return Response({'success': True, 'published_count': count}, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LockResultsAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        school = self.get_school()
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        try:
            count = result_calculation_service.lock_exam_results(school=school, exam=exam, actor=request.user)
            return Response({'success': True, 'locked_count': count}, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MarksCorrectionAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        school = self.get_school()
        serializer = MarksCorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        mark_record = get_object_or_404(StudentMark, id=data['mark_id'], school=school)

        try:
            updated = marks_service.correct_single_student_mark(
                school=school,
                mark_record=mark_record,
                new_status=data['new_status'],
                new_marks=data['new_marks'],
                reason=data['reason'],
                actor=request.user
            )
            return Response({
                'success': True,
                'message': f"Mark corrected for {updated.student.name}.",
                'marks_obtained': str(updated.marks_obtained),
                'grade': updated.grade,
            }, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StudentResultHistoryAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        school = self.get_school()
        student = get_object_or_404(Student, id=student_id, school=school)

        if user_has_role(request.user, Role.STUDENT) and student.user != request.user:
            raise PermissionDenied("You can only access your own academic results.")
        if user_has_role(request.user, Role.PARENT):
            is_child = Student.objects.filter(
                id=student.id, school=school, guardian_relationships__guardian__user=request.user
            ).exists()
            if not is_child:
                raise PermissionDenied("You can only access your registered child's results.")

        results_qs = StudentExamResult.objects.filter(school=school, student=student)
        if user_has_role(request.user, Role.STUDENT) or user_has_role(request.user, Role.PARENT):
            results_qs = results_qs.filter(status__in=[StudentExamResult.STATUS_PUBLISHED, StudentExamResult.STATUS_LOCKED])

        serializer = StudentExamResultSerializer(results_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClassResultSummaryAPIView(TenantScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        school = self.get_school()
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        section_id = request.GET.get('section_id')
        section = Section.objects.filter(id=section_id, school=school).first() if section_id else None

        summary = exam_selectors.get_class_result_summary(school, exam, section)
        return Response({
            'exam_id': exam.id,
            'exam_name': exam.name,
            'total_students': summary['total_students'],
            'appeared_count': summary['appeared_count'],
            'absent_count': summary['absent_count'],
            'passed_count': summary['passed_count'],
            'failed_count': summary['failed_count'],
            'compartment_count': summary['compartment_count'],
            'pass_percentage': summary['pass_percentage'],
            'average_percentage': summary['average_percentage'],
            'highest_percentage': summary['highest_percentage'],
            'lowest_percentage': summary['lowest_percentage'],
            'grade_distribution': summary['grade_distribution'],
            'subject_stats': summary['subject_stats'],
        }, status=status.HTTP_200_OK)
