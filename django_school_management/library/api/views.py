"""
PrimeSoul Library - REST API ViewSets & Actions
Tenant-scoped endpoints with RBAC authorization.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.students.models import Student

from django_school_management.library.models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)
from django_school_management.library.services import library_service
from django_school_management.library.selectors import library_selectors
from .serializers import (
    LibrarySerializer, BookCategorySerializer, AuthorSerializer,
    PublisherSerializer, LibraryShelfSerializer, BookSerializer,
    BookCopySerializer, LibraryMemberSerializer, LibraryIssueSerializer,
    LibraryFineSerializer, IssueBookRequestSerializer, ReturnBookRequestSerializer
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
        return self.queryset.filter(school=school)


class LibraryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Library.objects.all()
    serializer_class = LibrarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class BookCategoryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = BookCategory.objects.all()
    serializer_class = BookCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class AuthorViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class PublisherViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class LibraryShelfViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LibraryShelf.objects.all()
    serializer_class = LibraryShelfSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class BookViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class BookCopyViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = BookCopy.objects.all()
    serializer_class = BookCopySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class LibraryMemberViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LibraryMember.objects.all()
    serializer_class = LibraryMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())


class LibraryIssueViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LibraryIssue.objects.all()
    serializer_class = LibraryIssueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        school = self.get_school()

        # Students see only their own issues
        if user_has_role(user, Role.STUDENT):
            member = LibraryMember.objects.filter(school=school, student__user=user).first()
            return qs.filter(member=member) if member else qs.none()

        # Parents see only their children's issues
        if user_has_role(user, Role.PARENT):
            parent = getattr(user, 'parent_profile', None)
            if parent:
                rel = parent.student_relationships.first()
                student = rel.student if rel else None
                if student:
                    member = LibraryMember.objects.filter(school=school, student=student).first()
                    return qs.filter(member=member) if member else qs.none()
            return qs.none()

        return qs


class IssueBookAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.LIBRARIAN):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = IssueBookRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        library = get_object_or_404(Library, pk=data['library_id'], school=school)
        member = get_object_or_404(LibraryMember, pk=data['member_id'], school=school)

        if data.get('book_copy_id'):
            book_copy = get_object_or_404(BookCopy, pk=data['book_copy_id'], school=school)
        elif data.get('accession_number'):
            book_copy = get_object_or_404(BookCopy, accession_number=data['accession_number'], school=school)
        else:
            return Response({'error': 'book_copy_id or accession_number required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            issue = library_service.issue_book(
                school=school, library=library, member=member, book_copy=book_copy,
                issue_date=data.get('issue_date'), due_date=data.get('due_date'),
                loan_days=data.get('loan_days'), issued_by=user, remarks=data.get('remarks', '')
            )
            return Response(LibraryIssueSerializer(issue).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReturnBookAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user_has_role(user, Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.LIBRARIAN):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ReturnBookRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()
        issue = get_object_or_404(LibraryIssue, pk=data['issue_id'], school=school)

        try:
            returned = library_service.return_book(
                school=school, issue=issue, return_date=data.get('return_date'),
                returned_by=user, waive_fine=data.get('waive_fine', False),
                waiver_reason=data.get('waiver_reason', ''), waived_by=user if data.get('waive_fine') else None,
                remarks=data.get('remarks', '')
            )
            return Response(LibraryIssueSerializer(returned).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LibraryDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'school', None) or getattr(request.user, 'school', None) or School.objects.first()
        metrics = library_selectors.get_dashboard_metrics(school)
        return Response(metrics)


class MyLibraryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        school = getattr(request, 'school', None) or getattr(user, 'school', None) or School.objects.first()

        student = None
        if user_has_role(user, Role.STUDENT):
            student = Student.objects.filter(school=school, user=user).first()
        elif user_has_role(user, Role.PARENT):
            parent = getattr(user, 'parent_profile', None)
            rel = parent.student_relationships.first() if parent else None
            student = rel.student if rel else None

        if not student:
            return Response({'detail': 'No student record linked.'}, status=status.HTTP_404_NOT_FOUND)

        info = library_selectors.get_student_library_info(student)
        if not info:
            return Response({'detail': 'No library membership found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'member_code': info['member'].member_code,
            'active_books': len(info['active_issues']),
            'outstanding_fines': str(info['outstanding_fines']),
        })
