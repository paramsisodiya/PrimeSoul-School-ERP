import datetime
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.attendance.models import AttendanceRecord, AttendanceCorrectionLog
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student
from django_school_management.attendance.services import attendance_service
from django_school_management.attendance.selectors import attendance_selectors
from .serializers import (
    AttendanceRecordSerializer, BulkMarkAttendanceSerializer,
    AttendanceCorrectionSerializer, AttendanceCorrectionLogSerializer
)


class TenantScopedMixin:
    """
    Ensures queryset is strictly scoped to the active request tenant school.
    Enforces role-based visibility restrictions for students, parents, and teachers.
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

        qs = self.queryset.filter(school=school)
        user = self.request.user

        # Student scoping
        if user_has_role(user, Role.STUDENT):
            return qs.filter(student__user=user)

        # Parent scoping
        if user_has_role(user, Role.PARENT):
            return qs.filter(student__guardian_relationships__guardian__user=user)

        # Teacher scoping
        if user_has_role(user, Role.TEACHER) and not (user.is_superuser or user_has_role(user, Role.SCHOOL_ADMIN)):
            # Scope to assigned sections
            assigned_sections = Section.objects.filter(school=school)
            allowed_section_ids = [
                s.id for s in assigned_sections
                if attendance_service.can_user_mark_section(user, school, s)
            ]
            return qs.filter(section_id__in=allowed_section_ids)

        return qs


class AttendanceRecordViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.all().select_related(
        'student', 'grade_level', 'section', 'academic_year', 'marked_by', 'updated_by'
    )
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        school = self.get_school()
        serializer.save(school=school, marked_by=self.request.user)


class BulkMarkAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkMarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.cleaned_data if hasattr(serializer, 'cleaned_data') else serializer.validated_data
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        if not school:
            return Response({"detail": "School tenant required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            academic_year = AcademicYear.objects.get(id=data['academic_year'], school=school)
            grade_level = GradeLevel.objects.get(id=data['grade_level'], school=school)
            section = Section.objects.get(id=data['section'], school=school, grade_level=grade_level)
        except Exception as e:
            return Response({"detail": f"Invalid reference IDs: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            res = attendance_service.save_daily_attendance(
                school=school,
                academic_year=academic_year,
                grade_level=grade_level,
                section=section,
                attendance_date=data['attendance_date'],
                attendance_entries=data['entries'],
                actor=request.user
            )
            return Response(res, status=status.HTTP_200_OK)
        except PermissionDenied as pe:
            return Response({"detail": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"An unexpected error occurred: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AttendanceCorrectionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        record = get_object_or_404(AttendanceRecord, id=pk, school=school)
        serializer = AttendanceCorrectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['new_status']
        reason = serializer.validated_data['reason']

        try:
            updated_record = attendance_service.correct_attendance_record(
                record=record,
                new_status=new_status,
                reason=reason,
                actor=request.user
            )
            return Response(AttendanceRecordSerializer(updated_record).data, status=status.HTTP_200_OK)
        except PermissionDenied as pe:
            return Response({"detail": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)


class TodayAttendanceSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        date_str = request.query_params.get('date')
        if date_str:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                target_date = timezone.localdate()
        else:
            target_date = timezone.localdate()

        metrics = attendance_selectors.get_attendance_dashboard_metrics(school, target_date)
        # Format for JSON serialization
        if metrics.get('current_year'):
            metrics['current_year_id'] = metrics['current_year'].id
            metrics['current_year_name'] = metrics['current_year'].name
            del metrics['current_year']
        metrics['target_date'] = str(metrics.get('target_date'))

        return Response(metrics, status=status.HTTP_200_OK)


class StudentAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        student = get_object_or_404(Student, id=pk, school=school)

        # RBAC Check: Student can only view own record
        if user_has_role(request.user, Role.STUDENT) and student.user != request.user:
            raise PermissionDenied("You can only access your own attendance record.")

        # RBAC Check: Parent can only view child record
        if user_has_role(request.user, Role.PARENT):
            is_child = Student.objects.filter(
                id=student.id, school=school,
                guardian_relationships__guardian__user=request.user
            ).exists()
            if not is_child:
                raise PermissionDenied("You can only access your registered child's attendance.")

        current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
        summary = attendance_selectors.get_student_attendance_summary(school, student, current_year)

        data = {
            'student_id': student.id,
            'student_name': student.name,
            'admission_number': getattr(student, 'admission_number', ''),
            'academic_year': current_year.name if current_year else None,
            'total_records': summary['total_records'],
            'present_count': summary['present_count'],
            'absent_count': summary['absent_count'],
            'late_count': summary['late_count'],
            'half_day_count': summary['half_day_count'],
            'excused_count': summary['excused_count'],
            'percentage': summary['percentage'],
        }
        return Response(data, status=status.HTTP_200_OK)


class PendingAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None)
        if not school and request.user.is_superuser:
            school = School.objects.filter(is_active=True).first()

        dt_str = request.query_params.get('date')
        target_date = datetime.date.fromisoformat(dt_str) if dt_str else timezone.localdate()
        current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

        is_teacher = user_has_role(request.user, Role.TEACHER) and not (request.user.is_superuser or user_has_role(request.user, Role.SCHOOL_ADMIN))
        sections = attendance_selectors.get_pending_attendance_sections(
            school=school,
            academic_year=current_year,
            target_date=target_date,
            teacher_user=request.user if is_teacher else None
        )

        data = [{
            'section_id': item['section'].id,
            'section_name': item['section'].name,
            'class_id': item['grade_level'].id,
            'class_name': item['grade_level'].name,
            'is_marked': item['is_marked'],
            'records_count': item['records_count'],
            'class_teacher': item['class_teacher'],
        } for item in sections]

        return Response({
            'target_date': str(target_date),
            'sections': data
        }, status=status.HTTP_200_OK)
