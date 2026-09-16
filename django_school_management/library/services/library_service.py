"""
PrimeSoul Library - Business Services Layer
Handles book issue/return, fine calculation, renewals, lost/damaged processing.
All operations are atomic and audited.
"""
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.library.models import (
    Library, BookCopy, LibraryMember, LibraryIssue, LibraryFine, Book
)
from django_school_management.core.audit import log_library_event


def calculate_fine(library_or_issue, due_date: Optional[date] = None, return_date: Optional[date] = None) -> Decimal:
    """
    Centralized fine calculation. Uses library-configured rates.
    Accepts either (library, due_date, return_date) or (issue, return_date).
    Returns the calculated fine amount (before any waivers).
    """
    if hasattr(library_or_issue, 'due_date'):
        issue = library_or_issue
        library = issue.library
        eff_due_date = issue.due_date
        effective_return_date = due_date or return_date or timezone.localdate()
    else:
        library = library_or_issue
        eff_due_date = due_date
        effective_return_date = return_date or timezone.localdate()

    if not eff_due_date or effective_return_date <= eff_due_date:
        return Decimal('0.00')

    overdue_days = (effective_return_date - eff_due_date).days
    grace = library.grace_period_days or 0
    billable_days = max(0, overdue_days - grace)

    if billable_days == 0:
        return Decimal('0.00')

    raw_fine = library.fine_per_day * billable_days
    return min(raw_fine, library.max_fine)


@transaction.atomic
def issue_book(
    school=None,
    library: Optional[Library] = None,
    member: Optional[LibraryMember] = None,
    book_copy: Optional[BookCopy] = None,
    issue_date: Optional[date] = None,
    due_date: Optional[date] = None,
    loan_days: Optional[int] = None,
    issued_by=None,
    actor=None,
    remarks: str = ''
) -> LibraryIssue:
    """
    Issues a book copy to a member. Validates availability, limits, and tenant.
    """
    if school is None:
        school = getattr(library, 'school', None) or getattr(book_copy, 'school', None) or getattr(member, 'school', None)

    eff_actor = actor or issued_by

    # Tenant validation
    if book_copy.school_id != school.id:
        raise ValidationError("Book copy does not belong to this school.")
    if member.school_id != school.id:
        raise ValidationError("Member does not belong to this school.")
    if not member.is_active:
        raise ValidationError("Member account is not active.")

    # Availability check
    if book_copy.status != BookCopy.STATUS_AVAILABLE:
        raise ValidationError(f"Book copy '{book_copy.accession_number}' is not available (status: {book_copy.status}).")

    # Duplicate issue check
    active_issue = LibraryIssue.objects.filter(
        book_copy=book_copy,
        status=LibraryIssue.STATUS_ISSUED
    ).exists()
    if active_issue:
        raise ValidationError("This book copy is already issued to someone.")

    # Issue limit check
    current_issued = LibraryIssue.objects.filter(
        school=school,
        member=member,
        status=LibraryIssue.STATUS_ISSUED
    ).count()
    limit = member.get_issue_limit(library)
    if current_issued >= limit:
        raise ValidationError(f"Member has reached the issue limit ({limit} books).")

    # Create issue
    eff_issue_date = issue_date or timezone.localdate()
    days = loan_days if loan_days is not None else (library.default_loan_days if library else 14)
    eff_due_date = due_date or (eff_issue_date + timedelta(days=days))

    if eff_due_date <= eff_issue_date:
        raise ValidationError("Due date must be after issue date.")

    issue = LibraryIssue.objects.create(
        school=school,
        library=library,
        member=member,
        book_copy=book_copy,
        issue_date=eff_issue_date,
        due_date=eff_due_date,
        status=LibraryIssue.STATUS_ISSUED,
        issued_by=eff_actor,
        remarks=remarks
    )

    # Update copy status
    book_copy.status = BookCopy.STATUS_ISSUED
    book_copy.save(update_fields=['status'])

    log_library_event(
        actor=eff_actor, school=school, action='ISSUE_BOOK',
        resource='LibraryIssue', resource_id=str(issue.pk),
        details={'accession': book_copy.accession_number, 'member': member.member_code}
    )

    return issue


@transaction.atomic
def return_book(
    issue: LibraryIssue,
    school=None,
    return_date: Optional[date] = None,
    returned_by=None,
    actor=None,
    waive_fine: bool = False,
    waiver_reason: str = '',
    waived_by=None,
    remarks: str = ''
) -> LibraryIssue:
    """
    Processes a book return. Calculates and records applicable fine.
    """
    eff_school = school or issue.school
    eff_actor = actor or returned_by

    if issue.school_id != eff_school.id:
        raise ValidationError("Issue does not belong to this school.")
    if issue.status != LibraryIssue.STATUS_ISSUED:
        raise ValidationError(f"Cannot return: issue status is '{issue.status}'.")

    eff_return_date = return_date or timezone.localdate()
    issue.returned_date = eff_return_date
    issue.status = LibraryIssue.STATUS_RETURNED
    issue.returned_by = eff_actor
    if remarks:
        issue.remarks = remarks
    issue.save(update_fields=['returned_date', 'status', 'returned_by', 'remarks'])

    # Update copy status back to available
    copy = issue.book_copy
    copy.status = BookCopy.STATUS_AVAILABLE
    copy.save(update_fields=['status'])

    # Calculate and record fine
    fine_amount = calculate_fine(issue.library, issue.due_date, eff_return_date)
    if fine_amount > Decimal('0.00'):
        if waive_fine:
            LibraryFine.objects.create(
                school=eff_school,
                issue=issue,
                calculated_fine=fine_amount,
                waived_fine=fine_amount,
                final_fine=Decimal('0.00'),
                waiver_reason=waiver_reason,
                waived_by=waived_by,
                paid=False
            )
        else:
            LibraryFine.objects.create(
                school=eff_school,
                issue=issue,
                calculated_fine=fine_amount,
                waived_fine=Decimal('0.00'),
                final_fine=fine_amount,
                paid=False
            )

    log_library_event(
        actor=eff_actor, school=eff_school, action='RETURN_BOOK',
        resource='LibraryIssue', resource_id=str(issue.pk),
        details={'accession': copy.accession_number, 'fine': str(fine_amount)}
    )

    return issue


@transaction.atomic
def renew_book(
    issue: LibraryIssue,
    school=None,
    new_due_date: Optional[date] = None,
    actor=None
) -> LibraryIssue:
    """Extends the due date of an existing issue."""
    eff_school = school or issue.school
    if issue.school_id != eff_school.id:
        raise ValidationError("Issue does not belong to this school.")
    if issue.status != LibraryIssue.STATUS_ISSUED:
        raise ValidationError("Can only renew currently issued books.")

    if new_due_date is None:
        new_due_date = issue.due_date + timedelta(days=issue.library.default_loan_days)

    if new_due_date <= issue.due_date:
        raise ValidationError("New due date must be after current due date.")

    old_due = issue.due_date
    issue.due_date = new_due_date
    issue.save(update_fields=['due_date'])

    log_library_event(
        actor=actor, school=eff_school, action='RENEW_BOOK',
        resource='LibraryIssue', resource_id=str(issue.pk),
        details={'old_due': str(old_due), 'new_due': str(new_due_date)}
    )

    return issue


@transaction.atomic
def mark_book_lost(issue: LibraryIssue, school=None, actor=None, remarks: str = '') -> LibraryIssue:
    """Marks a book as lost. Updates copy status and records fine."""
    eff_school = school or issue.school
    if issue.school_id != eff_school.id:
        raise ValidationError("Issue does not belong to this school.")
    if issue.status not in (LibraryIssue.STATUS_ISSUED, LibraryIssue.STATUS_OVERDUE):
        raise ValidationError("Can only mark issued/overdue books as lost.")

    issue.status = LibraryIssue.STATUS_LOST
    issue.returned_date = timezone.localdate()
    if remarks:
        issue.remarks = remarks
    issue.save(update_fields=['status', 'returned_date', 'remarks'])

    copy = issue.book_copy
    copy.status = BookCopy.STATUS_LOST
    copy.save(update_fields=['status'])

    # Calculate fine
    fine_amount = calculate_fine(issue.library, issue.due_date)
    if not hasattr(issue, 'fine') or issue.fine is None:
        LibraryFine.objects.create(
            school=eff_school, issue=issue,
            calculated_fine=fine_amount, waived_fine=Decimal('0.00'),
            final_fine=fine_amount, paid=False
        )

    log_library_event(
        actor=actor, school=eff_school, action='MARK_LOST',
        resource='BookCopy', resource_id=str(copy.pk),
        details={'accession': copy.accession_number, 'remarks': remarks}
    )

    return issue


mark_lost = mark_book_lost


@transaction.atomic
def mark_book_damaged(issue: LibraryIssue, school=None, actor=None, remarks: str = '') -> LibraryIssue:
    """Marks a book as damaged during return."""
    eff_school = school or issue.school
    if issue.school_id != eff_school.id:
        raise ValidationError("Issue does not belong to this school.")

    issue.status = LibraryIssue.STATUS_DAMAGED
    issue.returned_date = timezone.localdate()
    if remarks:
        issue.remarks = remarks
    issue.save(update_fields=['status', 'returned_date', 'remarks'])

    copy = issue.book_copy
    copy.status = BookCopy.STATUS_DAMAGED
    copy.condition = BookCopy.CONDITION_DAMAGED
    copy.save(update_fields=['status', 'condition'])

    log_library_event(
        actor=actor, school=eff_school, action='MARK_DAMAGED',
        resource='BookCopy', resource_id=str(copy.pk),
        details={'accession': copy.accession_number, 'remarks': remarks}
    )

    return issue


mark_damaged = mark_book_damaged


def create_book_copy(
    school,
    book: Book,
    accession_number: str,
    barcode: str = '',
    shelf=None,
    purchase_date=None,
    purchase_price=None,
    condition: str = BookCopy.CONDITION_NEW,
    notes: str = '',
    actor=None
) -> BookCopy:
    """Creates a new book copy with unique accession number validation."""
    if book.school_id != school.id:
        raise ValidationError("Book does not belong to this school.")

    if BookCopy.objects.filter(school=school, accession_number=accession_number).exists():
        raise ValidationError(f"Accession number '{accession_number}' already exists in this school.")

    copy = BookCopy.objects.create(
        school=school,
        book=book,
        accession_number=accession_number,
        barcode=barcode,
        shelf=shelf,
        purchase_date=purchase_date,
        purchase_price=purchase_price,
        condition=condition,
        status=BookCopy.STATUS_AVAILABLE,
        notes=notes
    )

    log_library_event(
        actor=actor, school=school, action='CREATE_COPY',
        resource='BookCopy', resource_id=str(copy.pk),
        details={'accession': accession_number, 'book': book.title}
    )

    return copy


def search_catalog(school, query: str = '', **filters) -> Dict[str, Any]:
    """
    Searches the library catalog with multiple filter options.
    Returns dict with books queryset and filter metadata.
    """
    qs = Book.objects.filter(school=school, is_active=True)

    if query:
        from django.db.models import Q
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(subtitle__icontains=query) |
            Q(isbn__icontains=query) |
            Q(book_authors__author__name__icontains=query)
        ).distinct()

    if filters.get('category_id'):
        qs = qs.filter(category_id=filters['category_id'])
    if filters.get('publisher_id'):
        qs = qs.filter(publisher_id=filters['publisher_id'])
    if filters.get('language'):
        qs = qs.filter(language=filters['language'])
    if filters.get('available_only'):
        qs = qs.filter(copies__status=BookCopy.STATUS_AVAILABLE).distinct()

    return {
        'books': qs,
        'total': qs.count()
    }
