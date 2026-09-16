"""
PrimeSoul Timetable - REST API ViewSets & Actions
Provides tenant-scoped endpoints with full RBAC authorization.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.academics.models import AcademicYear, Section, Subject
from django_school_management.teachers.models import Teacher
from django_school_management.students.models import Student

from django_school_management.timetable.models import (
    WorkingDay, TimeSlot, Classroom, TimetableEntry
)
from django_school_management.timetable.services import (
    timetable_service, conflict_service, generator_service
)
from django_school_management.timetable.selectors import timetable_selectors
from .serializers import (
    WorkingDaySerializer, TimeSlotSerializer, ClassroomSerializer,
    TimetableEntrySerializer, TimetableConflictValidationSerializer,
    TimetableGenerateRequestSerializer, TimetableCloneRequestSerializer
)


class TenantScopedMixin:
    """Ensures querysets are strictly scoped to the active request school tenant."""
    def get_school(self):
        user = self.request.user
        if hasattr(self.request, 'tenant') and self.request.tenant:
            return self.request.tenant
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

        # Student scoping: only their own section entries
        if user_has_role(user, Role.STUDENT):
            student = Student.objects.filter(school=school, user=user).first()
            if student and student.section_id:
                return qs.filter(section_id=student.section_id)
            return qs.none()

        # Parent scoping: child's section entries
        if user_has_role(user, Role.PARENT):
            parent = getattr(user, 'parent_profile', None)
            rel = parent.student_relationships.first() if parent else None
            student = rel.student if rel else None
            if student and student.section_id:
                return qs.filter(section_id=student.section_id)
            return qs.none()

        # Teacher scoping: assigned entries if read-only
        if user_has_role(user, Role.TEACHER) and not (user.is_superuser or user_has_role(user, Role.SCHOOL_ADMIN)):
            teacher = Teacher.objects.filter(school=school, email=user.email).first()
            if teacher:
                return qs.filter(teacher=teacher)
            return qs.none()

        return qs


class WorkingDayViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = WorkingDay.objects.all()
    serializer_class = WorkingDaySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class TimeSlotViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class ClassroomViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class TimetableEntryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.filter(is_active=True)
    serializer_class = TimetableEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        school = self.get_school()
        if not user_has_role(request.user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL, Role.ACADEMIC_COORDINATOR):
            return Response({'detail': "Write permission denied for timetable creation."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        ay = get_object_or_404(AcademicYear, pk=data.get('academic_year'), school=school)
        wd = get_object_or_404(WorkingDay, pk=data.get('working_day'), school=school)
        ts = get_object_or_404(TimeSlot, pk=data.get('time_slot'), school=school)
        sec = get_object_or_404(Section, pk=data.get('section'), school=school)

        sub = Subject.objects.filter(pk=data.get('subject'), school=school).first() if data.get('subject') else None
        tchr = Teacher.objects.filter(pk=data.get('teacher'), school=school).first() if data.get('teacher') else None
        rm = Classroom.objects.filter(pk=data.get('room'), school=school).first() if data.get('room') else None

        try:
            entry = timetable_service.create_timetable_entry(
                school=school,
                academic_year=ay,
                working_day=wd,
                time_slot=ts,
                section=sec,
                subject=sub,
                teacher=tchr,
                room=rm,
                entry_type=data.get('entry_type', TimetableEntry.TYPE_CLASS),
                notes=data.get('notes', ''),
                actor=request.user
            )
            serializer = self.get_serializer(entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        if not user_has_role(request.user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL, Role.ACADEMIC_COORDINATOR):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        timetable_service.delete_timetable_entry(instance, actor=request.user, hard_delete=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimetableConflictValidationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TimetableConflictValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()

        ay = get_object_or_404(AcademicYear, pk=data['academic_year_id'], school=school)
        wd = get_object_or_404(WorkingDay, pk=data['working_day_id'], school=school)
        ts = get_object_or_404(TimeSlot, pk=data['time_slot_id'], school=school)
        sec = get_object_or_404(Section, pk=data['section_id'], school=school)

        tchr = Teacher.objects.filter(pk=data.get('teacher_id'), school=school).first() if data.get('teacher_id') else None
        sub = Subject.objects.filter(pk=data.get('subject_id'), school=school).first() if data.get('subject_id') else None
        rm = Classroom.objects.filter(pk=data.get('room_id'), school=school).first() if data.get('room_id') else None

        is_valid, conflicts = conflict_service.validate_timetable_entry_conflicts(
            school=school,
            academic_year=ay,
            working_day=wd,
            time_slot=ts,
            section=sec,
            teacher=tchr,
            subject=sub,
            room=rm,
            entry_type=data.get('entry_type', 'CLASS'),
            exclude_entry_id=data.get('exclude_entry_id')
        )
        return Response({
            'is_valid': is_valid,
            'conflicts': conflicts
        })


class TimetableGenerateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL, Role.ACADEMIC_COORDINATOR):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TimetableGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        ay = get_object_or_404(AcademicYear, pk=data['academic_year_id'], school=school)

        result = generator_service.generate_automated_timetable(
            school=school,
            academic_year=ay,
            section_ids=data.get('section_ids'),
            actor=user
        )
        return Response(result)


class TimetableCloneAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL, Role.ACADEMIC_COORDINATOR):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TimetableCloneRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        src_ay = get_object_or_404(AcademicYear, pk=data['source_academic_year_id'], school=school)
        tgt_ay = get_object_or_404(AcademicYear, pk=data['target_academic_year_id'], school=school)

        try:
            stats = timetable_service.clone_timetable(
                school=school,
                source_academic_year=src_ay,
                target_academic_year=tgt_ay,
                actor=user,
                clone_working_days=data['clone_working_days'],
                clone_time_slots=data['clone_time_slots'],
                clone_entries=data['clone_entries']
            )
            return Response({'success': True, 'stats': stats})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TimetableClearAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL):
            return Response({'detail': "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        ay_id = request.data.get('academic_year_id')
        sec_id = request.data.get('section_id')

        ay = get_object_or_404(AcademicYear, pk=ay_id, school=school) if ay_id else timetable_selectors.get_active_academic_year(school)
        sec = get_object_or_404(Section, pk=sec_id, school=school) if sec_id else None

        count = timetable_service.clear_timetable(
            school=school,
            academic_year=ay,
            section=sec,
            actor=user
        )
        return Response({'success': True, 'cleared_count': count})
