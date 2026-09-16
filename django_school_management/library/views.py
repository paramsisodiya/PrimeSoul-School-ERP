"""
PrimeSoul Library - UI Views Layer
Tenant-scoped, RBAC-protected views with support for full library operations and student/staff self-portal.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.library.models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)
from django_school_management.library.forms import (
    LibraryForm, BookCategoryForm, AuthorForm, PublisherForm,
    LibraryShelfForm, BookForm, BookCopyForm, LibraryMemberForm,
    IssueBookForm, ReturnBookForm
)
from django_school_management.library.services import library_service
from django_school_management.library.selectors import library_selectors


def _resolve_school(request):
    """Safely extracts tenant School from request context or user attributes."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated:
        user_school = getattr(request.user, 'school', None)
        if user_school:
            return user_school
    return School.objects.filter(is_active=True).first()


def _check_library_management_perm(user):
    """Verifies administrative management privileges for Library."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_has_role(
        user,
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.LIBRARIAN
    )


@login_required
def library_dashboard(request):
    school = _resolve_school(request)
    if not school:
        messages.error(request, "No active school tenant context available.")
        return redirect('dashboard')

    if not _check_library_management_perm(request.user):
        return redirect('library:my_library')

    metrics = library_selectors.get_library_dashboard_metrics(school)
    recent_issues = LibraryIssue.objects.filter(school=school).select_related('member', 'book_copy__book').order_by('-issue_date')[:10]
    overdue_issues = library_selectors.get_overdue_issues(school)[:5]

    context = {
        'metrics': metrics,
        'recent_issues': recent_issues,
        'overdue_issues': overdue_issues,
        'page_title': 'Library Dashboard'
    }
    return render(request, 'library/dashboard.html', context)


@login_required
def book_list(request):
    school = _resolve_school(request)
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')

    books = Book.objects.filter(school=school, is_active=True).select_related('category', 'publisher').prefetch_related('authors')
    if query:
        books = library_selectors.search_catalog(school, query)
    elif category_id:
        books = books.filter(category_id=category_id)

    categories = BookCategory.objects.filter(school=school, is_active=True)
    context = {
        'books': books,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'can_manage': _check_library_management_perm(request.user),
        'page_title': 'Book Catalog'
    }
    return render(request, 'library/books.html', context)


@login_required
def book_detail(request, pk):
    school = _resolve_school(request)
    book = get_object_or_404(Book, school=school, pk=pk)
    copies = BookCopy.objects.filter(school=school, book=book).select_related('shelf')
    copy_form = BookCopyForm(school=school) if _check_library_management_perm(request.user) else None

    context = {
        'book': book,
        'copies': copies,
        'copy_form': copy_form,
        'can_manage': _check_library_management_perm(request.user),
        'page_title': book.title
    }
    return render(request, 'library/book_detail.html', context)


@login_required
def book_create(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied("You do not have permission to add books.")

    if request.method == 'POST':
        form = BookForm(request.POST, school=school)
        if form.is_valid():
            book = form.save(commit=False)
            book.school = school
            book.save()
            form.save_m2m()
            messages.success(request, f"Book '{book.title}' created successfully.")
            return redirect('library:book_detail', pk=book.pk)
    else:
        form = BookForm(school=school)

    return render(request, 'library/book_form.html', {'form': form, 'page_title': 'Add New Book'})


@login_required
@require_POST
def book_copy_create(request, book_pk):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    book = get_object_or_404(Book, school=school, pk=book_pk)
    form = BookCopyForm(request.POST, school=school)
    if form.is_valid():
        try:
            library_service.create_book_copy(
                school=school,
                book=book,
                accession_number=form.cleaned_data['accession_number'],
                barcode=form.cleaned_data.get('barcode', ''),
                shelf=form.cleaned_data.get('shelf'),
                purchase_date=form.cleaned_data.get('purchase_date'),
                purchase_price=form.cleaned_data.get('purchase_price'),
                condition=form.cleaned_data.get('condition', 'NEW'),
                status=form.cleaned_data.get('status', 'AVAILABLE'),
                notes=form.cleaned_data.get('notes', ''),
                actor=request.user
            )
            messages.success(request, f"Copy '{form.cleaned_data['accession_number']}' added successfully.")
        except Exception as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Invalid copy form data.")
    return redirect('library:book_detail', pk=book.pk)


@login_required
def member_list(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    members = LibraryMember.objects.filter(school=school).select_related('student', 'teacher', 'user')
    form = LibraryMemberForm(school=school)

    if request.method == 'POST':
        form = LibraryMemberForm(request.POST, school=school)
        if form.is_valid():
            member = form.save(commit=False)
            member.school = school
            member.save()
            messages.success(request, f"Member '{member.member_code}' added successfully.")
            return redirect('library:members')

    context = {
        'members': members,
        'form': form,
        'page_title': 'Library Members'
    }
    return render(request, 'library/members.html', context)


@login_required
def issue_list(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    status_filter = request.GET.get('status')
    issues = LibraryIssue.objects.filter(school=school).select_related('member', 'book_copy__book', 'library').order_by('-issue_date')
    if status_filter:
        issues = issues.filter(status=status_filter)

    context = {
        'issues': issues,
        'selected_status': status_filter,
        'page_title': 'Circulation / Book Issues'
    }
    return render(request, 'library/issues.html', context)


@login_required
def issue_book_view(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    if request.method == 'POST':
        form = IssueBookForm(request.POST, school=school)
        if form.is_valid():
            try:
                accession = form.cleaned_data['accession_number'].strip()
                book_copy = BookCopy.objects.filter(school=school, accession_number=accession).first()
                if not book_copy:
                    # check barcode
                    book_copy = BookCopy.objects.filter(school=school, barcode=accession).first()

                if not book_copy:
                    messages.error(request, f"No book copy found with identifier '{accession}'.")
                else:
                    issue = library_service.issue_book(
                        school=school,
                        library=form.cleaned_data['library'],
                        member=form.cleaned_data['member'],
                        book_copy=book_copy,
                        issued_by=request.user,
                        loan_days=form.cleaned_data.get('loan_days'),
                        remarks=form.cleaned_data.get('remarks', '')
                    )
                    messages.success(request, f"Book '{book_copy.book.title}' successfully issued to {issue.member.get_name()}. Due date: {issue.due_date}")
                    return redirect('library:issues')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = IssueBookForm(school=school)

    return render(request, 'library/issue_book.html', {'form': form, 'page_title': 'Issue Book'})


@login_required
def return_book_view(request, issue_pk):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    issue = get_object_or_404(LibraryIssue, school=school, pk=issue_pk)
    fine_preview = library_service.calculate_fine(issue)

    if request.method == 'POST':
        form = ReturnBookForm(request.POST)
        if form.is_valid():
            try:
                library_service.return_book(
                    issue=issue,
                    returned_by=request.user,
                    waive_fine=form.cleaned_data.get('waive_fine', False),
                    waiver_reason=form.cleaned_data.get('waiver_reason', ''),
                    waived_by=request.user if form.cleaned_data.get('waive_fine') else None,
                    remarks=form.cleaned_data.get('remarks', '')
                )
                messages.success(request, f"Book '{issue.book_copy.book.title}' returned successfully.")
                return redirect('library:issues')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = ReturnBookForm()

    context = {
        'issue': issue,
        'form': form,
        'fine_preview': fine_preview,
        'page_title': f"Return: {issue.book_copy.book.title}"
    }
    return render(request, 'library/return_book.html', context)


@login_required
def overdue_list(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    overdue_issues = library_selectors.get_overdue_issues(school)
    context = {
        'overdue_issues': overdue_issues,
        'page_title': 'Overdue Books'
    }
    return render(request, 'library/overdue.html', context)


@login_required
def fines_list(request):
    school = _resolve_school(request)
    if not _check_library_management_perm(request.user):
        raise PermissionDenied()

    fines = LibraryFine.objects.filter(school=school).select_related('issue__member', 'issue__book_copy__book').order_by('-pk')
    fine_summary = library_selectors.get_fine_summary(school)

    context = {
        'fines': fines,
        'summary': fine_summary,
        'page_title': 'Library Fines Register'
    }
    return render(request, 'library/fines.html', context)


@login_required
def my_library(request):
    school = _resolve_school(request)
    student = getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)
    teacher = getattr(request.user, 'teacher_profile', None) or getattr(request.user, 'teacher', None)

    member = None
    if student:
        member = LibraryMember.objects.filter(school=school, student=student).first()
    elif teacher:
        member = LibraryMember.objects.filter(school=school, teacher=teacher).first()
    if not member:
        member = LibraryMember.objects.filter(school=school, user=request.user).first()

    my_issues = LibraryIssue.objects.filter(school=school, member=member).select_related('book_copy__book').order_by('-issue_date') if member else []
    active_issues = [i for i in my_issues if i.status == 'ISSUED']

    context = {
        'member': member,
        'my_issues': my_issues,
        'active_issues': active_issues,
        'page_title': 'My Library Dashboard'
    }
    return render(request, 'library/my_library.html', context)
