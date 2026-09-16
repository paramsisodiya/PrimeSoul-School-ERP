"""
PrimeSoul Library - Selectors (Read-Only Queries)
Dashboard metrics, search, member info, overdue tracking, and fine summaries.
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
from django.db.models import Count, Sum, Q, F
from django.utils import timezone

from django_school_management.library.models import (
    Library, Book, BookCopy, LibraryMember, LibraryIssue, LibraryFine,
    BookCategory, Author, Publisher, LibraryShelf
)


def get_dashboard_metrics(school, library: Optional[Library] = None) -> Dict[str, Any]:
    """Returns real database metrics for the library dashboard."""
    base_q = Q(school=school)
    if library:
        base_q &= Q(library=library) if hasattr(LibraryIssue, 'library') else Q()

    today = timezone.localdate()

    total_books = Book.objects.filter(school=school, is_active=True).count()
    total_copies = BookCopy.objects.filter(school=school).count()
    available_copies = BookCopy.objects.filter(school=school, status=BookCopy.STATUS_AVAILABLE).count()
    issued_copies = BookCopy.objects.filter(school=school, status=BookCopy.STATUS_ISSUED).count()
    lost_books = BookCopy.objects.filter(school=school, status=BookCopy.STATUS_LOST).count()
    damaged_books = BookCopy.objects.filter(school=school, status=BookCopy.STATUS_DAMAGED).count()

    overdue_issues = LibraryIssue.objects.filter(
        school=school, status=LibraryIssue.STATUS_ISSUED, due_date__lt=today
    ).count()

    active_members = LibraryMember.objects.filter(school=school, is_active=True).count()

    today_issues = LibraryIssue.objects.filter(school=school, issue_date=today).count()
    today_returns = LibraryIssue.objects.filter(
        school=school, returned_date=today, status=LibraryIssue.STATUS_RETURNED
    ).count()

    outstanding_fines = LibraryFine.objects.filter(
        school=school, paid=False
    ).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')

    return {
        'total_books': total_books,
        'total_titles': total_books,
        'total_copies': total_copies,
        'available_copies': available_copies,
        'issued_copies': issued_copies,
        'overdue_books': overdue_issues,
        'lost_books': lost_books,
        'damaged_books': damaged_books,
        'active_members': active_members,
        'today_issues': today_issues,
        'today_returns': today_returns,
        'outstanding_fines': outstanding_fines,
    }


get_library_dashboard_metrics = get_dashboard_metrics


def search_catalog(school, query: str = '', **filters):
    """Searches book catalog and returns queryset."""
    qs = Book.objects.filter(school=school, is_active=True)
    if query:
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(isbn__icontains=query) |
            Q(book_authors__author__name__icontains=query)
        ).distinct()
    if filters.get('category_id'):
        qs = qs.filter(category_id=filters['category_id'])
    if filters.get('publisher_id'):
        qs = qs.filter(publisher_id=filters['publisher_id'])
    return qs


def get_overdue_books(school) -> list:
    """Returns list of currently overdue issues."""
    today = timezone.localdate()
    return list(
        LibraryIssue.objects.filter(
            school=school,
            status=LibraryIssue.STATUS_ISSUED,
            due_date__lt=today
        ).select_related('member', 'book_copy', 'book_copy__book', 'library')
        .order_by('due_date')
    )


get_overdue_issues = get_overdue_books


def get_member_issues(school, member: LibraryMember, active_only: bool = False) -> list:
    """Returns issues for a specific member."""
    qs = LibraryIssue.objects.filter(school=school, member=member)
    if active_only:
        qs = qs.filter(status=LibraryIssue.STATUS_ISSUED)
    return list(qs.select_related('book_copy', 'book_copy__book', 'library').order_by('-issue_date'))


def get_student_library_info(student) -> Optional[Dict[str, Any]]:
    """Returns library info for a student (parent/student portal safe)."""
    member = LibraryMember.objects.filter(
        student=student, is_active=True
    ).first()
    if not member:
        return None

    active_issues = LibraryIssue.objects.filter(
        member=member, status=LibraryIssue.STATUS_ISSUED
    ).select_related('book_copy', 'book_copy__book').order_by('-issue_date')

    fines = LibraryFine.objects.filter(
        issue__member=member, paid=False
    ).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')

    history = LibraryIssue.objects.filter(
        member=member
    ).select_related('book_copy', 'book_copy__book').order_by('-issue_date')[:20]

    return {
        'member': member,
        'active_issues': list(active_issues),
        'outstanding_fines': fines,
        'history': list(history),
    }


def get_fine_summary(school) -> Dict[str, Any]:
    """Returns fine summary for the school."""
    fines = LibraryFine.objects.filter(school=school)
    total_fines = fines.aggregate(total=Sum('calculated_fine'))['total'] or Decimal('0.00')
    total_waived = fines.aggregate(total=Sum('waived_fine'))['total'] or Decimal('0.00')
    total_collected = fines.filter(paid=True).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')
    total_outstanding = fines.filter(paid=False).aggregate(total=Sum('final_fine'))['total'] or Decimal('0.00')

    return {
        'total_fines': total_fines,
        'total_waived': total_waived,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
    }


def get_inventory_summary(school) -> Dict[str, Any]:
    """Returns inventory summary grouped by status."""
    status_counts = BookCopy.objects.filter(school=school).values('status').annotate(
        count=Count('id')
    ).order_by('status')

    category_counts = Book.objects.filter(school=school, is_active=True).values(
        'category__name'
    ).annotate(count=Count('id')).order_by('-count')

    return {
        'status_breakdown': {item['status']: item['count'] for item in status_counts},
        'category_breakdown': list(category_counts),
    }
